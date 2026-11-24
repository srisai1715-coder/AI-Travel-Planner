"""
Restaurant Search Tool

Purpose:
    Search nearby restaurants efficiently for an AI Travel Planner.

Approach:
1. Make ONE Overpass request around the destination (with caching + fast timeout).
2. If Overpass fails or returns too few results, automatically fall back to Nominatim.
3. Calculate distances in Python.
4. Match the nearest restaurants to each tourist place.
5. Return 3-5 useful restaurants for every place.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple

import requests


# ============================================================
# CONFIGURATION
# ============================================================

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"

DEFAULT_SEARCH_RADIUS_KM = 5.0
DEFAULT_RESTAURANTS_PER_PLACE = 5

REQUEST_TIMEOUT = 10

SERVER_RETRY_DELAY = 0.5

CACHE_TTL_SECONDS = 900  # 15 minutes

_RESTAURANT_CACHE: Dict[Tuple[float, float, float], Tuple[float, List[Dict[str, Any]]]] = {}


# ============================================================
# DISTANCE CALCULATION
# ============================================================

def calculate_distance_km(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    """
    Calculate straight-line distance between two coordinates in kilometres.
    """

    earth_radius_km = 6371.0

    lat1 = math.radians(latitude_1)
    lat2 = math.radians(latitude_2)

    delta_lat = math.radians(latitude_2 - latitude_1)
    delta_lon = math.radians(longitude_2 - longitude_1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * (math.sin(delta_lon / 2) ** 2)
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return earth_radius_km * c


# ============================================================
# QUALITY SCORE
# ============================================================

def calculate_restaurant_quality_score(
    tags: Dict[str, Any],
) -> float:
    """
    Calculate a simple deterministic quality score based on available OSM data.
    """

    score = 70.0

    if tags.get("name"):
        score += 5
    if tags.get("cuisine"):
        score += 5
    if tags.get("phone"):
        score += 3
    if tags.get("website"):
        score += 3
    if tags.get("opening_hours"):
        score += 4

    address_fields = [
        "addr:housenumber",
        "addr:street",
        "addr:city",
    ]
    address_count = sum(
        1 for field in address_fields if tags.get(field)
    )
    score += min(address_count * 2, 6)

    return round(min(score, 95.0), 1)


# ============================================================
# CATEGORY
# ============================================================

def determine_restaurant_category(
    tags: Dict[str, Any],
) -> str:
    """
    Convert OSM food-related tags into a simple category.
    """

    amenity = str(tags.get("amenity") or "").lower()
    shop = str(tags.get("shop") or "").lower()
    cuisine = str(tags.get("cuisine") or "").lower()

    if amenity == "cafe":
        return "Cafe"
    if amenity == "fast_food":
        return "Fast Food"
    if shop in {"bakery", "confectionery"}:
        return "Bakery"
    if "ice_cream" in cuisine:
        return "Ice Cream"

    return "Restaurant"


# ============================================================
# EXTRACT COORDINATES
# ============================================================

def extract_element_coordinates(
    element: Dict[str, Any],
) -> Optional[tuple]:
    """
    Extract latitude and longitude from an OSM element.
    """

    if element.get("lat") is not None and element.get("lon") is not None:
        return (
            float(element["lat"]),
            float(element["lon"]),
        )

    center = element.get("center")
    if center and center.get("lat") is not None and center.get("lon") is not None:
        return (
            float(center["lat"]),
            float(center["lon"]),
        )

    return None


# ============================================================
# BUILD OVERPASS QUERY
# ============================================================

def build_restaurant_overpass_query(
    latitude: float,
    longitude: float,
    radius_meters: int,
) -> str:
    """
    Build ONE Overpass query for restaurants and food places.
    """

    return f"""
[out:json][timeout:8];

(
    node["amenity"="restaurant"](around:{radius_meters},{latitude},{longitude});
    way["amenity"="restaurant"](around:{radius_meters},{latitude},{longitude});
    node["amenity"="cafe"](around:{radius_meters},{latitude},{longitude});
    way["amenity"="cafe"](around:{radius_meters},{latitude},{longitude});
    node["amenity"="fast_food"](around:{radius_meters},{latitude},{longitude});
    way["amenity"="fast_food"](around:{radius_meters},{latitude},{longitude});
    node["shop"="bakery"](around:{radius_meters},{latitude},{longitude});
    way["shop"="bakery"](around:{radius_meters},{latitude},{longitude});
);

out center tags;
"""


# ============================================================
# NOMINATIM FALLBACK FOR RESTAURANTS
# ============================================================

def _bounding_box(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> str:
    lat_delta = radius_km / 111.0
    cos_lat = max(0.2, math.cos(math.radians(latitude)))
    lon_delta = radius_km / (111.0 * cos_lat)
    return (
        f"{longitude - lon_delta:.5f},"
        f"{latitude + lat_delta:.5f},"
        f"{longitude + lon_delta:.5f},"
        f"{latitude - lat_delta:.5f}"
    )


def _fetch_restaurants_via_nominatim(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> List[Dict[str, Any]]:
    """Fallback food/restaurant search via Nominatim when Overpass fails."""
    print("Falling back to Nominatim for nearby restaurants...")
    headers = {
        "User-Agent": "AI-Travel-Planner/2.0 (contact: srisai1715@gmail.com)",
        "Accept": "application/json",
    }
    viewbox = _bounding_box(latitude, longitude, max(radius_km, 8.0))

    queries = [
        ("restaurant", "restaurant"),
        ("cafe", "cafe"),
        ("biryani", "restaurant"),
        ("bakery", "bakery"),
    ]

    synthetic_elements: List[Dict[str, Any]] = []

    for term, default_amenity in queries:
        try:
            params = {
                "q": term,
                "format": "jsonv2",
                "limit": 15,
                "viewbox": viewbox,
                "bounded": 1,
                "extratags": 1,
                "namedetails": 1,
            }
            response = requests.get(
                NOMINATIM_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            results = response.json()
            if not isinstance(results, list):
                continue

            for item in results:
                if not isinstance(item, dict):
                    continue
                namedetails = item.get("namedetails") or {}
                extratags = item.get("extratags") or {}
                name = (
                    namedetails.get("name:en")
                    or item.get("name")
                    or (str(item.get("display_name") or "").split(",")[0].strip())
                )
                if not name:
                    continue

                try:
                    lat = float(item["lat"])
                    lon = float(item["lon"])
                except (KeyError, TypeError, ValueError):
                    continue

                osm_type = str(item.get("type") or default_amenity).lower()
                tags: Dict[str, Any] = {
                    "name": name,
                    "amenity": "cafe" if osm_type == "cafe" else "restaurant",
                    "cuisine": extratags.get("cuisine", ""),
                    "phone": extratags.get("phone"),
                    "website": extratags.get("website"),
                    "opening_hours": extratags.get("opening_hours"),
                }
                if osm_type == "bakery":
                    tags["shop"] = "bakery"

                synthetic_elements.append({
                    "lat": lat,
                    "lon": lon,
                    "tags": tags,
                })

            time.sleep(0.35)
        except Exception as error:
            print(f"Nominatim restaurant fallback failed for '{term}':", error)

    print(f"Nominatim restaurant fallback found {len(synthetic_elements)} candidate venues.")
    return synthetic_elements


# ============================================================
# FETCH FROM OVERPASS (WITH CACHE & NOMINATIM FALLBACK)
# ============================================================

def fetch_restaurants_from_overpass(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> List[Dict[str, Any]]:
    """
    Perform ONE Overpass request with caching and fast fail-over,
    falling back to Nominatim if Overpass fails or returns too few results.
    """

    cache_key = (
        round(float(latitude), 3),
        round(float(longitude), 3),
        round(float(radius_km), 1),
    )
    now = time.time()
    cached = _RESTAURANT_CACHE.get(cache_key)
    if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
        print("Using cached restaurant elements.")
        return [dict(item) for item in cached[1]]

    radius_meters = int(radius_km * 1000)
    query = build_restaurant_overpass_query(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
    )

    last_error = None
    elements: List[Dict[str, Any]] = []

    for index, server in enumerate(
        OVERPASS_SERVERS,
        start=1,
    ):
        try:
            print(f"Trying restaurant Overpass server: {server}")

            response = requests.post(
                server,
                data={"data": query},
                headers={
                    "User-Agent": "AI-Travel-Planner/2.0 (contact: srisai1715@gmail.com)",
                    "Accept": "application/json",
                },
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()
            data = response.json()
            elements = data.get("elements", [])

            print(f"Restaurant Overpass request successful: {server}")
            break

        except Exception as error:
            last_error = error
            print("Restaurant Overpass request failed:", error)
            if index < len(OVERPASS_SERVERS):
                time.sleep(SERVER_RETRY_DELAY)

    if not elements:
        print("All restaurant Overpass servers failed or returned empty.")
        if last_error:
            print("Last restaurant error:", last_error)
        elements = _fetch_restaurants_via_nominatim(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
        )

    if elements:
        _RESTAURANT_CACHE[cache_key] = (now, [dict(item) for item in elements])

    return elements


# ============================================================
# NORMALIZE RESTAURANT
# ============================================================

def normalize_restaurant(
    element: Dict[str, Any],
    destination_latitude: float,
    destination_longitude: float,
) -> Optional[Dict[str, Any]]:
    """
    Convert an Overpass/Nominatim element into our internal format.
    """

    tags = element.get("tags", {})
    coordinates = extract_element_coordinates(element)
    if not coordinates:
        return None

    latitude, longitude = coordinates
    name = (
        tags.get("name")
        or tags.get("name:en")
        or tags.get("official_name")
    )
    if not name:
        return None

    distance = calculate_distance_km(
        destination_latitude,
        destination_longitude,
        latitude,
        longitude,
    )
    category = determine_restaurant_category(tags)
    quality_score = calculate_restaurant_quality_score(tags)
    cuisines = tags.get("cuisine", "")

    return {
        "name": name,
        "category": category,
        "latitude": latitude,
        "longitude": longitude,
        "distance_km": round(distance, 2),
        "restaurant_quality_score": quality_score,
        "cuisine": cuisines,
        "phone": tags.get("phone"),
        "website": tags.get("website"),
        "opening_hours": tags.get("opening_hours"),
        "address": {
            "house_number": tags.get("addr:housenumber"),
            "street": tags.get("addr:street"),
            "city": tags.get("addr:city"),
        },
    }


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicate_restaurants(
    restaurants: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Remove duplicate restaurants.
    """

    unique: Dict[Tuple[str, float, float], Dict[str, Any]] = {}

    for restaurant in restaurants:
        name = str(restaurant.get("name") or "").strip().lower()
        latitude = round(float(restaurant.get("latitude", 0)), 4)
        longitude = round(float(restaurant.get("longitude", 0)), 4)
        key = (name, latitude, longitude)

        if key not in unique:
            unique[key] = restaurant

    return list(unique.values())


# ============================================================
# SEARCH ALL RESTAURANTS
# ============================================================

def search_nearby_restaurants(
    latitude: float,
    longitude: float,
    radius_km: float = DEFAULT_SEARCH_RADIUS_KM,
    max_results: int = 40,
) -> List[Dict[str, Any]]:
    """
    Search nearby restaurants around the destination.
    """

    elements = fetch_restaurants_from_overpass(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )

    restaurants = []
    for element in elements:
        restaurant = normalize_restaurant(
            element=element,
            destination_latitude=latitude,
            destination_longitude=longitude,
        )
        if restaurant:
            restaurants.append(restaurant)

    restaurants = remove_duplicate_restaurants(restaurants)

    restaurants.sort(
        key=lambda item: (
            -item["restaurant_quality_score"],
            item["distance_km"],
        )
    )

    return restaurants[:max_results]


# ============================================================
# FIND RESTAURANTS FOR EACH TOURIST PLACE
# ============================================================

def search_restaurants_for_places(
    places: List[Dict[str, Any]],
    destination_latitude: float,
    destination_longitude: float,
    radius_km: float = DEFAULT_SEARCH_RADIUS_KM,
    restaurants_per_place: int = DEFAULT_RESTAURANTS_PER_PLACE,
) -> Dict[str, Any]:
    """
    Find nearby restaurants for every tourist place.
    """

    if not places:
        return {
            "count": 0,
            "places_checked": 0,
            "items": [],
        }

    all_restaurants = search_nearby_restaurants(
        latitude=destination_latitude,
        longitude=destination_longitude,
        radius_km=radius_km,
        max_results=1000,
    )

    place_results = []
    total_matched = 0

    for place in places:
        place_name = str(place.get("name") or "Unknown place")
        place_latitude = place.get("latitude", place.get("lat"))
        place_longitude = place.get("longitude", place.get("lon"))

        if place_latitude is None or place_longitude is None:
            place_results.append({
                "place_name": place_name,
                "restaurant_count": 0,
                "restaurants": [],
            })
            continue

        try:
            place_latitude = float(place_latitude)
            place_longitude = float(place_longitude)
        except (TypeError, ValueError):
            place_results.append({
                "place_name": place_name,
                "restaurant_count": 0,
                "restaurants": [],
            })
            continue

        matched = []
        for restaurant in all_restaurants:
            distance = calculate_distance_km(
                place_latitude,
                place_longitude,
                restaurant["latitude"],
                restaurant["longitude"],
            )
            restaurant_copy = restaurant.copy()
            restaurant_copy["distance_from_place_km"] = round(distance, 2)
            matched.append(restaurant_copy)

        matched.sort(
            key=lambda item: (
                item["distance_from_place_km"],
                -item["restaurant_quality_score"],
            )
        )
        matched = matched[:restaurants_per_place]

        final_restaurants = []
        for restaurant in matched:
            restaurant["distance_km"] = restaurant["distance_from_place_km"]
            restaurant.pop("distance_from_place_km", None)
            final_restaurants.append(restaurant)

        total_matched += len(final_restaurants)
        place_results.append({
            "place_name": place_name,
            "restaurant_count": len(final_restaurants),
            "restaurants": final_restaurants,
        })

    return {
        "count": total_matched,
        "places_checked": len(places),
        "restaurants_found": len(all_restaurants),
        "items": place_results,
    }


# ============================================================
# ALIAS
# ============================================================

def find_restaurants_for_places(
    places: List[Dict[str, Any]],
    destination_latitude: float,
    destination_longitude: float,
    radius_km: float = DEFAULT_SEARCH_RADIUS_KM,
    restaurants_per_place: int = DEFAULT_RESTAURANTS_PER_PLACE,
) -> Dict[str, Any]:
    """
    Alias for search_restaurants_for_places().
    """

    return search_restaurants_for_places(
        places=places,
        destination_latitude=destination_latitude,
        destination_longitude=destination_longitude,
        radius_km=radius_km,
        restaurants_per_place=restaurants_per_place,
    )