"""Main Travel Data Pipeline for the AI Travel Planner.

This module is intentionally kept as the orchestration layer. It does not
contain LLM prompting or budget calculations. Those belong to llm_service.py.
"""

from typing import Any, Dict, List, Optional, Tuple

from backend.tools.places import search_nearby_places
from backend.tools.place_filter import filter_and_rank_places
from backend.tools.tourist_selector import select_tourist_places
from backend.tools.place_enrichment import enrich_places
from backend.tools.weather import get_weather
from backend.tools.route_optimizer import optimize_route
from backend.tools.restaurant_search import search_restaurants_for_places
from backend.services.itinerary_generator import generate_itinerary
from backend.services.llm_service import generate_travel_recommendation


DEFAULT_DATASET: Dict[str, Any] = {
    "raw_place_count": 0,
    "filtered_place_count": 0,
    "tourist_selected_count": 0,
    "enriched_place_count": 0,
    "final_place_count": 0,
    "places": [],
    "weather": None,
    "route": {"total_places": 0, "total_distance_km": 0, "places": []},
    "itinerary": None,
    "restaurants": {
        "count": 0,
        "places_checked": 0,
        "restaurants_found": 0,
        "items": [],
    },
    "user_query": "",
    "travelers": None,
    "budget": None,
    "preferences": None,
    "ai_recommendation": None,
}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _get_place_coordinates(place: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Read coordinates from either the canonical or legacy place keys."""
    if not isinstance(place, dict):
        return None

    latitude = place.get("latitude", place.get("lat"))
    longitude = place.get("longitude", place.get("lon"))
    if latitude is None or longitude is None:
        return None

    try:
        return float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None


def _place_for_restaurant_search(place: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert an enriched attraction into the restaurant-search input shape."""
    coordinates = _get_place_coordinates(place)
    if not coordinates:
        return None

    latitude, longitude = coordinates
    return {
        "name": str(place.get("name") or "Unknown place"),
        "latitude": latitude,
        "longitude": longitude,
    }


def _empty_route() -> Dict[str, Any]:
    return {
        "total_places": 0,
        "total_distance_km": 0,
        "places": [],
    }


def _empty_restaurants(places_checked: int = 0) -> Dict[str, Any]:
    return {
        "count": 0,
        "places_checked": places_checked,
        "restaurants_found": 0,
        "items": [],
    }


def _run_place_search(
    latitude: float,
    longitude: float,
) -> List[Dict[str, Any]]:
    """Search nearby places and always return a list."""
    result = search_nearby_places(
        latitude=latitude,
        longitude=longitude,
        radius=10000,
    )
    return [item for item in _safe_list(result) if isinstance(item, dict)]


def _run_filter_and_selection(
    raw_places: List[Dict[str, Any]],
    itinerary_places: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Filter/rank places, then select the attractions used by the itinerary."""
    filtered = filter_and_rank_places(raw_places) or []
    filtered = [item for item in _safe_list(filtered) if isinstance(item, dict)]

    selected = select_tourist_places(
        filtered,
        max_places=max(1, int(itinerary_places)),
    ) or []
    selected = [item for item in _safe_list(selected) if isinstance(item, dict)]
    return filtered, selected


def _run_enrichment(
    places: List[Dict[str, Any]],
    location_name: str,
    max_places: int,
) -> List[Dict[str, Any]]:
    """Add descriptions, Wikipedia/background data and place metadata."""
    enriched = enrich_places(
        places=places,
        location_name=location_name,
        max_places=max(1, int(max_places)),
    ) or []
    return [item for item in _safe_list(enriched) if isinstance(item, dict)]


def _run_weather(
    latitude: float,
    longitude: float,
    start_date: Optional[str],
    end_date: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not start_date or not end_date:
        return None
    try:
        return get_weather(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as error:
        print("Weather lookup failed:", error)
        return None


def _run_route(
    places: List[Dict[str, Any]],
    latitude: float,
    longitude: float,
) -> Dict[str, Any]:
    try:
        route = optimize_route(places, latitude, longitude)
        return route if isinstance(route, dict) else _empty_route()
    except Exception as error:
        print("Route optimization failed:", error)
        route = _empty_route()
        route["error"] = str(error)
        return route


def _run_itinerary(
    places: List[Dict[str, Any]],
    weather: Optional[Dict[str, Any]],
    start_date: Optional[str],
    end_date: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not start_date or not end_date:
        return None
    try:
        itinerary = generate_itinerary(
            places=places,
            weather=weather or {},
            start_date=start_date,
            end_date=end_date,
        )
        return itinerary if isinstance(itinerary, dict) else None
    except Exception as error:
        print("Itinerary generation failed:", error)
        return None


def _run_restaurant_search(
    places: List[Dict[str, Any]],
    destination_latitude: float,
    destination_longitude: float,
) -> Dict[str, Any]:
    """Find restaurants around each selected attraction, not just the city center."""
    restaurant_places = []
    for place in places:
        item = _place_for_restaurant_search(place)
        if item:
            restaurant_places.append(item)

    result = _empty_restaurants(len(restaurant_places))
    if not restaurant_places:
        return result

    try:
        found = search_restaurants_for_places(
            places=restaurant_places,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
            radius_km=10.0,
            restaurants_per_place=5,
        )
        if isinstance(found, dict):
            result.update(found)
            result.setdefault("items", [])
            if not isinstance(result["items"], list):
                result["items"] = []
        return result
    except Exception as error:
        print("Restaurant search failed:", error)
        result["error"] = str(error)
        return result


def _llm_error_response(
    location_name: str,
    start_date: Optional[str],
    end_date: Optional[str],
    travelers: Optional[int],
    budget: Optional[str],
    preferences: Optional[str],
    user_query: str,
    error: Exception,
) -> Dict[str, Any]:
    return {
        "title": "AI Travel Plan",
        "trip_overview": (
            "Travel data was generated successfully, but the AI travel "
            "recommendation could not be generated."
        ),
        "trip_summary": {
            "destination": location_name,
            "start_date": start_date,
            "end_date": end_date,
            "travelers": travelers,
            "budget": budget,
            "preferences": preferences,
            "user_query": user_query,
        },
        "highlights": [],
        "days": [],
        "trip_budget": {},
        "important_places": [],
        "travel_tips": [],
        "error": str(error),
    }


def build_travel_place_dataset(
    latitude: float,
    longitude: float,
    location_name: str,
    max_places: int = 10,
    itinerary_places: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_query: str = "",
    travelers: Optional[int] = None,
    budget: Optional[str] = None,
    preferences: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the complete deterministic travel-data pipeline and LLM planner."""
    data = {**DEFAULT_DATASET}
    data["user_query"] = user_query
    data["travelers"] = travelers
    data["budget"] = budget
    data["preferences"] = preferences

    # 1. Nearby attraction discovery.
    raw_places = _run_place_search(latitude, longitude)
    data["raw_place_count"] = len(raw_places)

    # 2. Ranking and tourist-place selection.
    filtered_places, tourist_places = _run_filter_and_selection(
        raw_places, itinerary_places
    )
    data["filtered_place_count"] = len(filtered_places)
    data["tourist_selected_count"] = len(tourist_places)

    # 3. Enrichment. This is the source of the factual attraction context
    #    sent to the LLM.
    enriched_places = _run_enrichment(
        tourist_places, location_name, max_places
    )
    data["enriched_place_count"] = len(enriched_places)
    data["final_place_count"] = len(enriched_places)
    data["places"] = enriched_places

    # 4. Weather.
    weather_data = _run_weather(
        latitude, longitude, start_date, end_date
    )
    data["weather"] = weather_data

    # 5. Route optimization.
    route_data = _run_route(
        enriched_places, latitude, longitude
    )
    data["route"] = route_data

    # 6. Preliminary itinerary.
    itinerary = _run_itinerary(
        enriched_places, weather_data, start_date, end_date
    )
    data["itinerary"] = itinerary

    # 7. Restaurant search is attraction-specific. The LLM later enforces
    #    that meals use the group belonging to the attraction just completed.
    restaurants_data = _run_restaurant_search(
        enriched_places, latitude, longitude
    )
    data["restaurants"] = restaurants_data

    # 8. Final structured LLM plan.
    if start_date and end_date:
        try:
            data["ai_recommendation"] = generate_travel_recommendation(
                destination=location_name,
                start_date=start_date,
                end_date=end_date,
                places=enriched_places,
                route=route_data,
                weather=weather_data,
                itinerary=itinerary,
                restaurants=restaurants_data,
                user_query=user_query,
                travelers=travelers,
                budget=budget,
                preferences=preferences,
            )
        except Exception as error:
            print("LLM travel recommendation failed:", error)
            data["ai_recommendation"] = _llm_error_response(
                location_name=location_name,
                start_date=start_date,
                end_date=end_date,
                travelers=travelers,
                budget=budget,
                preferences=preferences,
                user_query=user_query,
                error=error,
            )

    return data
