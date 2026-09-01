"""
Restaurant Search Tool

Purpose:
    Search nearby restaurants efficiently for an AI Travel Planner.

Old approach:
    Search Overpass separately for every tourist place.

New approach:
    1. Make ONE Overpass request around the destination.
    2. Collect nearby restaurants/cafes/food places.
    3. Calculate distances in Python.
    4. Match the nearest restaurants to each tourist place.
    5. Return 3-5 useful restaurants for every place.

This avoids making 10 separate Overpass API requests.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional

import requests


# ============================================================
# CONFIGURATION
# ============================================================

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

DEFAULT_SEARCH_RADIUS_KM = 5.0
DEFAULT_RESTAURANTS_PER_PLACE = 5

REQUEST_TIMEOUT = 25

# Small delay between fallback servers if the first one fails.
SERVER_RETRY_DELAY = 1.0


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
    Calculate straight-line distance between two coordinates.

    Uses the Haversine formula.

    Returns:
        Distance in kilometres.
    """

    earth_radius_km = 6371.0

    lat1 = math.radians(latitude_1)
    lat2 = math.radians(latitude_2)

    delta_lat = math.radians(
        latitude_2 - latitude_1
    )

    delta_lon = math.radians(
        longitude_2 - longitude_1
    )

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
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
    Calculate a simple deterministic quality score.

    This is NOT a review/rating from Google or another
    commercial service.

    It is only a ranking score based on available OSM data.
    """

    score = 70.0

    # --------------------------------------------------------
    # Name
    # --------------------------------------------------------

    if tags.get("name"):
        score += 5

    # --------------------------------------------------------
    # Cuisine
    # --------------------------------------------------------

    if tags.get("cuisine"):
        score += 5

    # --------------------------------------------------------
    # Phone
    # --------------------------------------------------------

    if tags.get("phone"):
        score += 3

    # --------------------------------------------------------
    # Website
    # --------------------------------------------------------

    if tags.get("website"):
        score += 3

    # --------------------------------------------------------
    # Opening hours
    # --------------------------------------------------------

    if tags.get("opening_hours"):
        score += 4

    # --------------------------------------------------------
    # Address information
    # --------------------------------------------------------

    address_fields = [
        "addr:housenumber",
        "addr:street",
        "addr:city",
    ]

    address_count = sum(
        1
        for field in address_fields
        if tags.get(field)
    )

    score += min(
        address_count * 2,
        6,
    )

    return round(
        min(score, 95.0),
        1,
    )


# ============================================================
# CATEGORY
# ============================================================

def determine_restaurant_category(
    tags: Dict[str, Any],
) -> str:
    """
    Convert OSM food-related tags into a simple category.
    """

    amenity = (
        tags.get("amenity")
        or ""
    ).lower()

    shop = (
        tags.get("shop")
        or ""
    ).lower()

    cuisine = (
        tags.get("cuisine")
        or ""
    ).lower()

    if amenity == "cafe":
        return "Cafe"

    if amenity == "fast_food":
        return "Fast Food"

    if shop in {
        "bakery",
        "confectionery",
    }:
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

    Nodes:
        element["lat"]
        element["lon"]

    Ways/relations:
        Overpass query uses center output, so:
        element["center"]["lat"]
        element["center"]["lon"]
    """

    # --------------------------------------------------------
    # Node
    # --------------------------------------------------------

    if (
        element.get("lat") is not None
        and element.get("lon") is not None
    ):

        return (
            float(element["lat"]),
            float(element["lon"]),
        )

    # --------------------------------------------------------
    # Way / Relation center
    # --------------------------------------------------------

    center = element.get(
        "center"
    )

    if center:

        if (
            center.get("lat") is not None
            and center.get("lon") is not None
        ):

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

    We intentionally include several useful food categories
    because the LLM may need:
        - lunch
        - dinner
        - snacks
        - cafes
        - bakeries
        - fast food
    """

    return f"""
[out:json][timeout:20];

(
    node[
        "amenity"="restaurant"
    ](
        around:{radius_meters},{latitude},{longitude}
    );

    way[
        "amenity"="restaurant"
    ](
        around:{radius_meters},{latitude},{longitude}
    );

    node[
        "amenity"="cafe"
    ](
        around:{radius_meters},{latitude},{longitude}
    );

    way[
        "amenity"="cafe"
    ](
        around:{radius_meters},{latitude},{longitude}
    );

    node[
        "amenity"="fast_food"
    ](
        around:{radius_meters},{latitude},{longitude}
    );

    way[
        "amenity"="fast_food"
    ](
        around:{radius_meters},{latitude},{longitude}
    );

    node[
        "shop"="bakery"
    ](
        around:{radius_meters},{latitude},{longitude}
    );

    way[
        "shop"="bakery"
    ](
        around:{radius_meters},{latitude},{longitude}
    );
);

out center tags;
"""


# ============================================================
# FETCH FROM OVERPASS
# ============================================================

def fetch_restaurants_from_overpass(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> List[Dict[str, Any]]:
    """
    Perform ONE Overpass request.

    Returns raw restaurant/food-place records.
    """

    radius_meters = int(
        radius_km * 1000
    )

    query = build_restaurant_overpass_query(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
    )

    last_error = None

    for index, server in enumerate(
        OVERPASS_SERVERS,
        start=1,
    ):

        try:

            print(
                f"Trying restaurant Overpass server: "
                f"{server}"
            )

            response = requests.post(
                server,
                data=query,
                headers={
                    "User-Agent":
                        "AI-Travel-Planner/1.0"
                },
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            data = response.json()

            print(
                f"Restaurant Overpass request "
                f"successful: {server}"
            )

            return data.get(
                "elements",
                [],
            )

        except Exception as error:

            last_error = error

            print(
                "Restaurant Overpass request failed:",
                error,
            )

            if index < len(
                OVERPASS_SERVERS
            ):

                time.sleep(
                    SERVER_RETRY_DELAY
                )

    print(
        "All restaurant Overpass servers failed."
    )

    if last_error:
        print(
            "Last restaurant error:",
            last_error,
        )

    return []


# ============================================================
# NORMALIZE RESTAURANT
# ============================================================

def normalize_restaurant(
    element: Dict[str, Any],
    destination_latitude: float,
    destination_longitude: float,
) -> Optional[Dict[str, Any]]:
    """
    Convert an Overpass element into our internal format.
    """

    tags = element.get(
        "tags",
        {},
    )

    coordinates = extract_element_coordinates(
        element
    )

    if not coordinates:
        return None

    latitude, longitude = coordinates

    name = (
        tags.get("name")
        or tags.get("name:en")
        or tags.get("official_name")
    )

    # --------------------------------------------------------
    # Ignore unnamed food places.
    # --------------------------------------------------------

    if not name:
        return None

    distance = calculate_distance_km(
        destination_latitude,
        destination_longitude,
        latitude,
        longitude,
    )

    category = determine_restaurant_category(
        tags
    )

    quality_score = (
        calculate_restaurant_quality_score(
            tags
        )
    )

    cuisines = tags.get(
        "cuisine",
        "",
    )

    return {
        "name": name,

        "category": category,

        "latitude": latitude,

        "longitude": longitude,

        "distance_km": round(
            distance,
            2,
        ),

        "restaurant_quality_score":
            quality_score,

        "cuisine": cuisines,

        "phone":
            tags.get("phone"),

        "website":
            tags.get("website"),

        "opening_hours":
            tags.get("opening_hours"),

        "address": {
            "house_number":
                tags.get(
                    "addr:housenumber"
                ),

            "street":
                tags.get(
                    "addr:street"
                ),

            "city":
                tags.get(
                    "addr:city"
                ),
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

    OSM can sometimes return the same business through
    multiple mapped elements.
    """

    unique = {}

    for restaurant in restaurants:

        name = (
            restaurant.get("name")
            or ""
        ).strip().lower()

        latitude = round(
            float(
                restaurant.get(
                    "latitude",
                    0,
                )
            ),
            4,
        )

        longitude = round(
            float(
                restaurant.get(
                    "longitude",
                    0,
                )
            ),
            4,
        )

        key = (
            name,
            latitude,
            longitude,
        )

        if key not in unique:
            unique[key] = restaurant

    return list(
        unique.values()
    )


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

    IMPORTANT:
        This function makes ONE Overpass request.

    This function is useful for the old/simple API:

        restaurants = search_nearby_restaurants(
            latitude,
            longitude,
        )
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
            restaurants.append(
                restaurant
            )

    restaurants = (
        remove_duplicate_restaurants(
            restaurants
        )
    )

    # --------------------------------------------------------
    # Sort:
    #   1. quality
    #   2. distance
    # --------------------------------------------------------

    restaurants.sort(
        key=lambda item: (
            -item[
                "restaurant_quality_score"
            ],
            item["distance_km"],
        )
    )

    return restaurants[
        :max_results
    ]


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

    IMPORTANT:
        Only ONE Overpass request is performed for the
        complete destination.

    The restaurants are then matched to tourist places
    locally using the Haversine distance calculation.

    Expected place format:

        {
            "name": "Golconda Fort",
            "latitude": 17.3833,
            "longitude": 78.4011
        }

    Returns:

        {
            "count": ...,
            "places_checked": ...,
            "items": [
                {
                    "place_name": "...",
                    "restaurant_count": ...,
                    "restaurants": [...]
                }
            ]
        }
    """

    if not places:
        return {
            "count": 0,
            "places_checked": 0,
            "items": [],
        }

    # ========================================================
    # 1. ONE API CALL
    # ========================================================

    all_restaurants = (
        search_nearby_restaurants(
            latitude=destination_latitude,
            longitude=destination_longitude,
            radius_km=radius_km,
            max_results=1000,
        )
    )

    # ========================================================
    # 2. MATCH RESTAURANTS TO EACH PLACE
    # ========================================================

    place_results = []

    total_matched = 0

    for place in places:

        place_name = (
            place.get("name")
            or "Unknown place"
        )

        place_latitude = (
            place.get("latitude")
            or place.get("lat")
        )

        place_longitude = (
            place.get("longitude")
            or place.get("lon")
        )

        # ----------------------------------------------------
        # If coordinates are missing, return empty results.
        # ----------------------------------------------------

        if (
            place_latitude is None
            or place_longitude is None
        ):

            place_results.append(
                {
                    "place_name":
                        place_name,

                    "restaurant_count":
                        0,

                    "restaurants": [],
                }
            )

            continue

        try:

            place_latitude = float(
                place_latitude
            )

            place_longitude = float(
                place_longitude
            )

        except (
            TypeError,
            ValueError,
        ):

            place_results.append(
                {
                    "place_name":
                        place_name,

                    "restaurant_count":
                        0,

                    "restaurants": [],
                }
            )

            continue

        # ----------------------------------------------------
        # Calculate distance from this place to every
        # restaurant.
        # ----------------------------------------------------

        matched = []

        for restaurant in all_restaurants:

            distance = (
                calculate_distance_km(
                    place_latitude,
                    place_longitude,
                    restaurant[
                        "latitude"
                    ],
                    restaurant[
                        "longitude"
                    ],
                )
            )

            restaurant_copy = (
                restaurant.copy()
            )

            restaurant_copy[
                "distance_from_place_km"
            ] = round(
                distance,
                2,
            )

            matched.append(
                restaurant_copy
            )

        # ----------------------------------------------------
        # Sort by actual distance from tourist place.
        #
        # Quality is used as a secondary factor.
        # ----------------------------------------------------

        matched.sort(
            key=lambda item: (
                item[
                    "distance_from_place_km"
                ],
                -item[
                    "restaurant_quality_score"
                ],
            )
        )

        matched = matched[
            :restaurants_per_place
        ]

        # ----------------------------------------------------
        # Rename the distance field expected by frontend/LLM.
        # ----------------------------------------------------

        final_restaurants = []

        for restaurant in matched:

            restaurant[
                "distance_km"
            ] = restaurant[
                "distance_from_place_km"
            ]

            restaurant.pop(
                "distance_from_place_km",
                None,
            )

            final_restaurants.append(
                restaurant
            )

        total_matched += len(
            final_restaurants
        )

        place_results.append(
            {
                "place_name":
                    place_name,

                "restaurant_count":
                    len(
                        final_restaurants
                    ),

                "restaurants":
                    final_restaurants,
            }
        )

    # ========================================================
    # 3. RETURN STRUCTURED RESULT
    # ========================================================

    return {
        "count":
            total_matched,

        "places_checked":
            len(places),

        "restaurants_found":
            len(all_restaurants),

        "items":
            place_results,
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

    This gives the project a second intuitive function name
    without duplicating any logic.
    """

    return search_restaurants_for_places(
        places=places,
        destination_latitude=destination_latitude,
        destination_longitude=destination_longitude,
        radius_km=radius_km,
        restaurants_per_place=restaurants_per_place,
    )


# ============================================================
# SIMPLE TEST
# ============================================================

if __name__ == "__main__":

    print(
        "\nTesting restaurant search...\n"
    )

    restaurants = (
        search_nearby_restaurants(
            latitude=17.359520,
            longitude=78.476601,
        )
    )

    print(
        "Restaurants found:",
        len(restaurants),
    )

    for restaurant in restaurants:

        print(
            restaurant["name"],
            "|",
            restaurant["category"],
            "|",
            restaurant["distance_km"],
            "km | score:",
            restaurant[
                "restaurant_quality_score"
            ],
        )