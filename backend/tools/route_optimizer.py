"""
Route Optimizer

Optimizes the visiting order of tourist places for each itinerary day.

The optimizer uses the coordinates of the places and the selected
destination as the starting point.

Main goals:
1. Start from the user's selected location.
2. Visit nearby places efficiently.
3. Avoid unnecessary backtracking.
4. Keep the route geographically sensible.
5. Preserve all existing place information.
6. Calculate route distance for each day.
7. Keep the implementation deterministic and explainable.

This version does NOT require an external routing API.
It uses geographic distance calculations only.

Later, a road-routing API such as OSRM can be added to calculate
actual driving distance and travel time.
"""

from math import radians, sin, cos, sqrt, atan2
from typing import Dict, List, Optional


# ============================================================
# CONSTANTS
# ============================================================

EARTH_RADIUS_KM = 6371.0


# ============================================================
# DISTANCE CALCULATION
# ============================================================

def calculate_distance_km(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    """
    Calculate the approximate geographic distance between
    two coordinates using the Haversine formula.

    Returns:
        Distance in kilometers.
    """

    lat1 = radians(float(latitude1))
    lon1 = radians(float(longitude1))

    lat2 = radians(float(latitude2))
    lon2 = radians(float(longitude2))

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(delta_lon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a),
    )

    return EARTH_RADIUS_KM * c


# ============================================================
# SAFE FLOAT CONVERSION
# ============================================================

def _to_float(
    value,
    default: Optional[float] = None,
) -> Optional[float]:
    """
    Safely convert a value to float.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# VALIDATE PLACE COORDINATES
# ============================================================

def _has_valid_coordinates(
    place: Dict,
) -> bool:
    """
    Check whether a place has usable latitude and longitude.
    """

    latitude = _to_float(
        place.get("latitude")
    )

    longitude = _to_float(
        place.get("longitude")
    )

    if latitude is None or longitude is None:
        return False

    if latitude < -90 or latitude > 90:
        return False

    if longitude < -180 or longitude > 180:
        return False

    return True


# ============================================================
# DISTANCE FROM START LOCATION
# ============================================================

def _distance_from_start(
    place: Dict,
    start_latitude: float,
    start_longitude: float,
) -> float:
    """
    Calculate distance from the user's starting location.
    """

    latitude = _to_float(
        place.get("latitude")
    )

    longitude = _to_float(
        place.get("longitude")
    )

    if latitude is None or longitude is None:
        return 999999.0

    return calculate_distance_km(
        start_latitude,
        start_longitude,
        latitude,
        longitude,
    )


# ============================================================
# DISTANCE BETWEEN TWO PLACES
# ============================================================

def _distance_between_places(
    place1: Dict,
    place2: Dict,
) -> float:
    """
    Calculate distance between two tourist places.
    """

    lat1 = _to_float(
        place1.get("latitude")
    )

    lon1 = _to_float(
        place1.get("longitude")
    )

    lat2 = _to_float(
        place2.get("latitude")
    )

    lon2 = _to_float(
        place2.get("longitude")
    )

    if None in (
        lat1,
        lon1,
        lat2,
        lon2,
    ):
        return 999999.0

    return calculate_distance_km(
        lat1,
        lon1,
        lat2,
        lon2,
    )


# ============================================================
# NEAREST PLACE
# ============================================================

def _find_nearest_place(
    current_location: Dict,
    remaining_places: List[Dict],
) -> Optional[Dict]:
    """
    Find the nearest remaining place from the current location.
    """

    if not remaining_places:
        return None

    nearest_place = None
    nearest_distance = 999999.0

    for place in remaining_places:

        distance = _distance_between_places(
            current_location,
            place,
        )

        if distance < nearest_distance:
            nearest_distance = distance
            nearest_place = place

    return nearest_place


# ============================================================
# GREEDY ROUTE OPTIMIZATION
# ============================================================

def optimize_place_order(
    places: List[Dict],
    start_latitude: float,
    start_longitude: float,
) -> List[Dict]:
    """
    Optimize the order of tourist places.

    The algorithm starts at the user's location and repeatedly
    selects the nearest unvisited place.

    This is a simple greedy nearest-neighbor algorithm.

    It is deterministic, fast and suitable for a first version
    of the travel planner.
    """

    if not places:
        return []

    valid_places = []

    for place in places:

        if not isinstance(place, dict):
            continue

        if not _has_valid_coordinates(place):
            continue

        valid_places.append(
            dict(place)
        )

    if not valid_places:
        return []

    current_location = {
        "latitude": start_latitude,
        "longitude": start_longitude,
    }

    remaining_places = valid_places.copy()

    optimized_route = []

    while remaining_places:

        nearest_place = _find_nearest_place(
            current_location,
            remaining_places,
        )

        if nearest_place is None:
            break

        optimized_route.append(
            nearest_place
        )

        remaining_places.remove(
            nearest_place
        )

        current_location = {
            "latitude": nearest_place["latitude"],
            "longitude": nearest_place["longitude"],
        }

    return optimized_route


# ============================================================
# ADD ROUTE INFORMATION
# ============================================================

def add_route_information(
    places: List[Dict],
    start_latitude: float,
    start_longitude: float,
) -> List[Dict]:
    """
    Add route-specific information to each place.

    Adds:

    route_order
    distance_from_previous_km
    cumulative_route_distance_km
    """

    if not places:
        return []

    enriched_places = []

    previous_location = {
        "latitude": start_latitude,
        "longitude": start_longitude,
    }

    cumulative_distance = 0.0

    for index, place in enumerate(
        places,
        start=1,
    ):

        candidate = dict(place)

        distance_from_previous = (
            _distance_between_places(
                previous_location,
                candidate,
            )
        )

        if distance_from_previous >= 999999:
            distance_from_previous = 0.0

        cumulative_distance += (
            distance_from_previous
        )

        candidate["route_order"] = index

        candidate[
            "distance_from_previous_km"
        ] = round(
            distance_from_previous,
            2,
        )

        candidate[
            "cumulative_route_distance_km"
        ] = round(
            cumulative_distance,
            2,
        )

        enriched_places.append(
            candidate
        )

        previous_location = {
            "latitude": candidate["latitude"],
            "longitude": candidate["longitude"],
        }

    return enriched_places


# ============================================================
# OPTIMIZE ONE DAY
# ============================================================

def optimize_daily_route(
    places: List[Dict],
    start_latitude: float,
    start_longitude: float,
) -> Dict:
    """
    Optimize the route for one itinerary day.

    Returns:

    {
        "places": [...],
        "total_distance_km": ...,
        "place_count": ...
    }
    """

    optimized_places = optimize_place_order(
        places=places,
        start_latitude=start_latitude,
        start_longitude=start_longitude,
    )

    optimized_places = add_route_information(
        places=optimized_places,
        start_latitude=start_latitude,
        start_longitude=start_longitude,
    )

    total_distance = 0.0

    if optimized_places:

        total_distance = optimized_places[-1].get(
            "cumulative_route_distance_km",
            0.0,
        )

    return {
        "places": optimized_places,
        "total_distance_km": round(
            total_distance,
            2,
        ),
        "place_count": len(
            optimized_places
        ),
    }


# ============================================================
# OPTIMIZE COMPLETE ITINERARY
# ============================================================

def optimize_itinerary_routes(
    itinerary: Dict,
    start_latitude: float,
    start_longitude: float,
) -> Dict:
    """
    Optimize routes for every day in an itinerary.

    Each day starts from the user's selected destination.

    The function preserves the existing itinerary structure
    and adds route information.
    """

    if not isinstance(
        itinerary,
        dict,
    ):
        return itinerary

    days = itinerary.get(
        "days",
        [],
    )

    if not isinstance(days, list):
        return itinerary

    optimized_itinerary = dict(
        itinerary
    )

    optimized_days = []

    total_route_distance = 0.0
    total_route_places = 0

    for day in days:

        if not isinstance(day, dict):
            continue

        optimized_day = dict(day)

        day_places = day.get(
            "places",
            [],
        )

        if not isinstance(
            day_places,
            list,
        ):
            day_places = []

        route_result = optimize_daily_route(
            places=day_places,
            start_latitude=start_latitude,
            start_longitude=start_longitude,
        )

        optimized_day["places"] = (
            route_result["places"]
        )

        optimized_day[
            "route_distance_km"
        ] = route_result[
            "total_distance_km"
        ]

        optimized_day[
            "route_place_count"
        ] = route_result[
            "place_count"
        ]

        total_route_distance += (
            route_result[
                "total_distance_km"
            ]
        )

        total_route_places += (
            route_result[
                "place_count"
            ]
        )

        optimized_days.append(
            optimized_day
        )

    optimized_itinerary[
        "days"
    ] = optimized_days

    optimized_itinerary[
        "total_route_distance_km"
    ] = round(
        total_route_distance,
        2,
    )

    optimized_itinerary[
        "total_route_places"
    ] = total_route_places

    return optimized_itinerary


# ============================================================
# PUBLIC HELPER
# ============================================================

def optimize_route(
    places: List[Dict],
    start_latitude: float,
    start_longitude: float,
) -> Dict:
    """
    Simple public interface for optimizing a list of places.

    Useful for testing the route optimizer independently.
    """

    route_places = optimize_place_order(
        places=places,
        start_latitude=start_latitude,
        start_longitude=start_longitude,
    )

    route_places = add_route_information(
        places=route_places,
        start_latitude=start_latitude,
        start_longitude=start_longitude,
    )

    total_distance = 0.0

    if route_places:
        total_distance = route_places[-1].get(
            "cumulative_route_distance_km",
            0.0,
        )

    return {
        "places": route_places,
        "total_distance_km": round(
            total_distance,
            2,
        ),
        "total_places": len(
            route_places
        ),
    }