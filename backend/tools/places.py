import math
import time
from typing import Any, Dict, List, Optional, Tuple

import requests


# ============================================================
# OPENSTREETMAP OVERPASS & NOMINATIM APIs
# ============================================================

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"


# ============================================================
# SEARCH SETTINGS
# ============================================================

DEFAULT_RADIUS = 10000

MAX_PLACES = 30

REQUEST_TIMEOUT = 12

MAX_RETRIES_PER_SERVER = 1

CACHE_TTL_SECONDS = 900  # 15 minutes

_PLACES_CACHE: Dict[Tuple[float, float, int], Tuple[float, List[Dict[str, Any]]]] = {}


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def calculate_distance_km(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    """
    Calculate the straight-line distance between
    two latitude/longitude coordinates in kilometres.
    """

    earth_radius_km = 6371.0

    lat1 = math.radians(latitude1)
    lat2 = math.radians(latitude2)

    delta_lat = math.radians(latitude2 - latitude1)
    delta_lon = math.radians(longitude2 - longitude1)

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
# CLASSIFY PLACE
# ============================================================

def classify_place(tags: Dict[str, Any]) -> str:
    """
    Convert OpenStreetMap tags into a travel-friendly category.
    """

    tourism = str(tags.get("tourism") or "").lower()
    historic = str(tags.get("historic") or "").lower()
    leisure = str(tags.get("leisure") or "").lower()
    amenity = str(tags.get("amenity") or "").lower()

    if historic in {
        "castle",
        "fort",
        "ruins",
        "monument",
        "memorial",
        "archaeological_site",
        "heritage",
    }:
        return "Historical"

    if tourism in {
        "museum",
        "gallery",
    }:
        return "Museum / Culture"

    if tourism in {
        "viewpoint",
        "picnic_site",
        "zoo",
        "theme_park",
        "aquarium",
        "nature_reserve",
    }:
        return "Nature / Recreation"

    if leisure in {
        "park",
        "garden",
        "nature_reserve",
    }:
        return "Nature / Recreation"

    if tourism == "place_of_worship" or amenity == "place_of_worship":
        return "Religious"

    if tourism in {
        "attraction",
        "artwork",
    }:
        return "Tourist Attraction"

    return "Other"


# ============================================================
# PLACE RELEVANCE SCORE
# ============================================================

def calculate_relevance_score(
    place: Dict[str, Any],
    distance_km: float,
) -> int:
    """
    Give each place a preprocessing relevance score.
    """

    score = 0

    category_scores = {
        "Historical": 100,
        "Museum / Culture": 90,
        "Nature / Recreation": 85,
        "Tourist Attraction": 80,
        "Religious": 65,
        "Other": 10,
    }

    score += category_scores.get(place["category"], 10)

    if distance_km <= 2:
        score += 30
    elif distance_km <= 5:
        score += 20
    elif distance_km <= 10:
        score += 10

    if place["description"]:
        score += 10
    if place["wikipedia"]:
        score += 15
    if place["website"]:
        score += 5
    if place["opening_hours"]:
        score += 5

    return score


# ============================================================
# BUILD OVERPASS QUERY
# ============================================================

def build_overpass_query(
    latitude: float,
    longitude: float,
    radius: int,
) -> str:
    """
    Build the Overpass query.
    """

    return f"""
    [out:json][timeout:10];

    (
        node["tourism"](around:{radius},{latitude},{longitude});
        way["tourism"](around:{radius},{latitude},{longitude});
        relation["tourism"](around:{radius},{latitude},{longitude});

        node["historic"](around:{radius},{latitude},{longitude});
        way["historic"](around:{radius},{latitude},{longitude});
        relation["historic"](around:{radius},{latitude},{longitude});

        node["leisure"="park"](around:{radius},{latitude},{longitude});
        way["leisure"="park"](around:{radius},{latitude},{longitude});
        relation["leisure"="park"](around:{radius},{latitude},{longitude});

        node["amenity"="place_of_worship"](around:{radius},{latitude},{longitude});
        way["amenity"="place_of_worship"](around:{radius},{latitude},{longitude});
        relation["amenity"="place_of_worship"](around:{radius},{latitude},{longitude});
    );

    out center tags;
    """


# ============================================================
# REQUEST HEADERS
# ============================================================

def get_request_headers() -> Dict[str, str]:
    return {
        "User-Agent": "AI-Travel-Planner/2.0 (contact: srisai1715@gmail.com)",
        "Accept": "application/json",
    }


# ============================================================
# CALL OVERPASS WITH FALLBACK
# ============================================================

def request_overpass(
    query: str,
) -> Dict[str, Any]:
    """
    Call Overpass using multiple servers with fast fail-over.
    """

    headers = get_request_headers()
    errors = []

    for server_url in OVERPASS_URLS:
        for attempt in range(1, MAX_RETRIES_PER_SERVER + 1):
            try:
                print(
                    f"Trying Overpass server: "
                    f"{server_url} "
                    f"(attempt {attempt})"
                )

                response = requests.post(
                    server_url,
                    data={"data": query},
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )

                response.raise_for_status()
                data = response.json()

                print(f"Overpass request successful: {server_url}")
                return data

            except requests.exceptions.RequestException as error:
                error_message = (
                    f"{server_url} "
                    f"attempt {attempt}: "
                    f"{error}"
                )
                print(f"Overpass request failed: {error_message}")
                errors.append(error_message)

    error_summary = "\n".join(errors)
    raise RuntimeError(
        "All Overpass API servers failed.\n" + error_summary
    )


# ============================================================
# NOMINATIM FALLBACK WHEN OVERPASS FAILS
# ============================================================

def _bounding_box(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> str:
    """Return Nominatim viewbox string: left,top,right,bottom."""
    lat_delta = radius_km / 111.0
    cos_lat = max(0.2, math.cos(math.radians(latitude)))
    lon_delta = radius_km / (111.0 * cos_lat)
    left = longitude - lon_delta
    right = longitude + lon_delta
    top = latitude + lat_delta
    bottom = latitude - lat_delta
    return f"{left:.5f},{top:.5f},{right:.5f},{bottom:.5f}"


def _classify_nominatim_place(item: Dict[str, Any]) -> str:
    osm_class = str(item.get("class") or "").lower()
    osm_type = str(item.get("type") or "").lower()

    if osm_class == "historic" or osm_type in {
        "castle",
        "fort",
        "monument",
        "memorial",
        "ruins",
        "palace",
        "heritage",
    }:
        return "Historical"
    if osm_type in {"museum", "gallery"}:
        return "Museum / Culture"
    if osm_class == "leisure" or osm_type in {"park", "garden", "zoo", "viewpoint"}:
        return "Nature / Recreation"
    if osm_type == "place_of_worship":
        return "Religious"
    return "Tourist Attraction"


def _search_places_via_nominatim(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> List[Dict[str, Any]]:
    """Fallback landmark search via Nominatim when Overpass is unavailable."""
    print("Falling back to Nominatim for nearby tourist places...")
    headers = get_request_headers()
    viewbox = _bounding_box(latitude, longitude, max(radius_km, 10.0))

    queries = [
        ("museum", "Museum / Culture"),
        ("fort", "Historical"),
        ("palace", "Historical"),
        ("tourist attraction", "Tourist Attraction"),
        ("park", "Nature / Recreation"),
    ]

    collected: List[Dict[str, Any]] = []

    for term, default_category in queries:
        try:
            params = {
                "q": term,
                "format": "jsonv2",
                "limit": 10,
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
                    place_lat = float(item["lat"])
                    place_lon = float(item["lon"])
                except (KeyError, TypeError, ValueError):
                    continue

                dist_km = calculate_distance_km(
                    latitude,
                    longitude,
                    place_lat,
                    place_lon,
                )
                if dist_km > max(radius_km * 1.5, 15.0):
                    continue

                category = _classify_nominatim_place(item)
                if category == "Tourist Attraction" and default_category != "Tourist Attraction":
                    category = default_category

                place = {
                    "name": name,
                    "category": category,
                    "latitude": place_lat,
                    "longitude": place_lon,
                    "distance_km": round(dist_km, 2),
                    "description": str(
                        extratags.get("description:en")
                        or extratags.get("description")
                        or ""
                    ),
                    "wikipedia": str(extratags.get("wikipedia") or ""),
                    "website": str(extratags.get("website") or ""),
                    "opening_hours": str(extratags.get("opening_hours") or ""),
                }
                place["relevance_score"] = calculate_relevance_score(place, dist_km)
                collected.append(place)

            time.sleep(0.35)
        except Exception as error:
            print(f"Nominatim place fallback failed for '{term}':", error)

    print(f"Nominatim fallback found {len(collected)} candidate places.")
    return collected


# ============================================================
# SEARCH NEARBY PLACES
# ============================================================

def search_nearby_places(
    latitude: float,
    longitude: float,
    radius: int = DEFAULT_RADIUS,
) -> List[Dict[str, Any]]:
    """
    Search for useful tourist attractions around the selected coordinates.
    Uses Overpass first, and automatically falls back to Nominatim on failure.
    """

    cache_key = (
        round(float(latitude), 3),
        round(float(longitude), 3),
        int(radius),
    )
    now = time.time()
    cached = _PLACES_CACHE.get(cache_key)
    if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
        print("Using cached nearby places result.")
        return [dict(item) for item in cached[1]]

    places: List[Dict[str, Any]] = []
    overpass_succeeded = False

    try:
        query = build_overpass_query(latitude, longitude, radius)
        data = request_overpass(query)
        overpass_succeeded = True

        for element in data.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name:en") or tags.get("name")
            if not name:
                continue

            if element.get("type") == "node":
                place_latitude = element.get("lat")
                place_longitude = element.get("lon")
            else:
                center = element.get("center", {})
                place_latitude = center.get("lat")
                place_longitude = center.get("lon")

            if place_latitude is None or place_longitude is None:
                continue

            try:
                place_latitude = float(place_latitude)
                place_longitude = float(place_longitude)
            except (TypeError, ValueError):
                continue

            category = classify_place(tags)
            if category == "Other":
                continue

            distance_km = calculate_distance_km(
                latitude,
                longitude,
                place_latitude,
                place_longitude,
            )

            place = {
                "name": name,
                "category": category,
                "latitude": place_latitude,
                "longitude": place_longitude,
                "distance_km": round(distance_km, 2),
                "description": (
                    tags.get("description:en")
                    or tags.get("description")
                    or ""
                ),
                "wikipedia": tags.get("wikipedia") or "",
                "website": tags.get("website") or tags.get("contact:website") or "",
                "opening_hours": tags.get("opening_hours") or "",
            }
            place["relevance_score"] = calculate_relevance_score(
                place,
                distance_km,
            )
            places.append(place)

    except Exception as error:
        print("Overpass places failed, switching to fallback:", error)

    if not overpass_succeeded or len(places) < 3:
        fallback_places = _search_places_via_nominatim(
            latitude=latitude,
            longitude=longitude,
            radius_km=max(radius / 1000.0, 5.0),
        )
        places.extend(fallback_places)

    unique_places: Dict[Tuple[str, float, float], Dict[str, Any]] = {}

    for place in places:
        key = (
            place["name"].strip().lower(),
            round(place["latitude"], 4),
            round(place["longitude"], 4),
        )

        if key not in unique_places:
            unique_places[key] = place
        else:
            existing = unique_places[key]
            if place["relevance_score"] > existing["relevance_score"]:
                unique_places[key] = place

    places = list(unique_places.values())

    places.sort(
        key=lambda item: (
            item["relevance_score"],
            -item["distance_km"],
        ),
        reverse=True,
    )

    places = places[:MAX_PLACES]

    for place in places:
        place.pop("relevance_score", None)

    if places:
        _PLACES_CACHE[cache_key] = (now, [dict(item) for item in places])

    return places