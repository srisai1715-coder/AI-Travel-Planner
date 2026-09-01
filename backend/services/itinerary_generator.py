"""
Smart Travel Itinerary Generator

Creates a practical day-by-day itinerary from tourist places.

The generator considers:
1. Tourist quality
2. Place category
3. Tourist place type
4. Weather suitability
5. Distance from the selected destination
6. Distance between consecutive places
7. Variety between places
8. Maximum places per day

This version is rule-based.
No LLM is used yet.
"""

from datetime import date, timedelta
from math import radians, sin, cos, sqrt, atan2
from typing import Dict, List


# ============================================================
# CONFIGURATION
# ============================================================

MAX_PLACES_PER_DAY = 4

MAX_DAILY_PLACES = 4


# ============================================================
# CATEGORY PRIORITY
# ============================================================

CATEGORY_PRIORITY = {
    "Historical": 5,
    "Tourist Attraction": 4,
    "Nature / Recreation": 3,
    "Religious": 2,
}


# ============================================================
# PLACE TYPE PRIORITY
# ============================================================

PLACE_TYPE_PRIORITY = {
    "major_historical": 30,
    "historical": 20,
    "nature": 15,
    "park": 8,
    "religious": 5,
    "statue": 2,
}


# ============================================================
# WEATHER SUITABILITY
# ============================================================

def _weather_suitability(weather: Dict) -> str:
    """
    Determine whether the weather is good for outdoor travel.

    Returns:
        good
        moderate
        poor
    """

    rain_probability = weather.get(
        "rain_probability",
        0,
    )

    precipitation = weather.get(
        "precipitation",
        0,
    )

    try:
        rain_probability = float(
            rain_probability or 0
        )
    except (TypeError, ValueError):

        rain_probability = 0


    try:
        precipitation = float(
            precipitation or 0
        )
    except (TypeError, ValueError):

        precipitation = 0


    if (
        rain_probability >= 60
        or precipitation >= 10
    ):

        return "poor"


    if (
        rain_probability >= 35
        or precipitation >= 3
    ):

        return "moderate"


    return "good"


# ============================================================
# SAFE VALUE
# ============================================================

def _safe_float(
    value,
    default: float = 0.0,
) -> float:

    try:

        return float(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def _calculate_distance_km(
    lat1,
    lon1,
    lat2,
    lon2,
) -> float:
    """
    Calculate distance between two coordinates.
    """

    lat1 = _safe_float(lat1)
    lon1 = _safe_float(lon1)
    lat2 = _safe_float(lat2)
    lon2 = _safe_float(lon2)


    earth_radius_km = 6371.0


    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)

    delta_lat = radians(
        lat2 - lat1
    )

    delta_lon = radians(
        lon2 - lon1
    )


    a = (
        sin(delta_lat / 2) ** 2
        +
        cos(lat1_rad)
        *
        cos(lat2_rad)
        *
        sin(delta_lon / 2) ** 2
    )


    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a),
    )


    return round(
        earth_radius_km * c,
        2,
    )


# ============================================================
# DAILY WEATHER
# ============================================================

def _get_daily_weather(
    weather: Dict,
    trip_date: str,
) -> Dict:
    """
    Extract weather information for one date.
    """

    if not isinstance(weather, dict):
        return {}


    daily = weather.get(
        "daily",
        {},
    )


    if not isinstance(daily, dict):
        return {}


    dates = daily.get(
        "time",
        [],
    )


    if not isinstance(dates, list):
        return {}


    if trip_date not in dates:
        return {}


    index = dates.index(
        trip_date
    )


    return {
        "weather_code":
            _get_value(
                daily.get(
                    "weather_code",
                    [],
                ),
                index,
            ),

        "temperature_max":
            _get_value(
                daily.get(
                    "temperature_2m_max",
                    [],
                ),
                index,
            ),

        "temperature_min":
            _get_value(
                daily.get(
                    "temperature_2m_min",
                    [],
                ),
                index,
            ),

        "rain_probability":
            _get_value(
                daily.get(
                    "precipitation_probability_max",
                    [],
                ),
                index,
            ),

        "precipitation":
            _get_value(
                daily.get(
                    "precipitation_sum",
                    [],
                ),
                index,
            ),

        "sunrise":
            _get_value(
                daily.get(
                    "sunrise",
                    [],
                ),
                index,
            ),

        "sunset":
            _get_value(
                daily.get(
                    "sunset",
                    [],
                ),
                index,
            ),
    }


# ============================================================
# SAFE LIST VALUE
# ============================================================

def _get_value(
    values: List,
    index: int,
):
    """
    Safely retrieve an item from a list.
    """

    if not isinstance(
        values,
        list,
    ):

        return None


    if (
        index < 0
        or index >= len(values)
    ):

        return None


    return values[index]


# ============================================================
# DETERMINE PLACE TYPE
# ============================================================

def _get_place_type(
    place: Dict,
) -> str:
    """
    Determine the tourist type of a place.

    Uses the existing tourist_place_type
    when available.
    """

    existing_type = place.get(
        "tourist_place_type"
    )


    if existing_type:

        return str(
            existing_type
        ).strip().lower()


    name = str(
        place.get(
            "name",
            "",
        )
    ).strip().lower()


    category = str(
        place.get(
            "category",
            "",
        )
    ).strip()


    if category == "Historical":

        if any(
            keyword in name
            for keyword in [
                "fort",
                "killa",
                "palace",
                "museum",
                "monument",
                "heritage",
                "darwaza",
                "dharvazaa",
            ]
        ):

            return "major_historical"


        if "statue" in name:

            return "statue"


        return "historical"


    if category == "Nature / Recreation":

        if any(
            keyword in name
            for keyword in [
                "park",
            ]
        ):

            return "park"


        return "nature"


    if category == "Religious":

        return "religious"


    return "other"


# ============================================================
# CHECK OUTDOOR PLACE
# ============================================================

def _is_outdoor_place(
    place: Dict,
) -> bool:
    """
    Determine whether a place is primarily outdoor.
    """

    category = str(
        place.get(
            "category",
            "",
        )
    ).strip()


    place_type = _get_place_type(
        place
    )


    if category in {
        "Nature / Recreation",
        "Tourist Attraction",
    }:

        return True


    if place_type in {
        "nature",
        "park",
    }:

        return True


    return False


# ============================================================
# PLACE SCORE
# ============================================================

def _place_score(
    place: Dict,
) -> float:
    """
    Calculate overall itinerary priority.
    """

    score = 0.0


    # --------------------------------------------------------
    # Category
    # --------------------------------------------------------

    category = place.get(
        "category",
        "",
    )


    score += (
        CATEGORY_PRIORITY.get(
            category,
            1,
        )
        * 10
    )


    # --------------------------------------------------------
    # Tourist quality
    # --------------------------------------------------------

    quality = _safe_float(
        place.get(
            "tourist_quality_score",
            0,
        )
    )


    score += quality


    # --------------------------------------------------------
    # Place type
    # --------------------------------------------------------

    place_type = _get_place_type(
        place
    )


    score += (
        PLACE_TYPE_PRIORITY.get(
            place_type,
            0,
        )
    )


    # --------------------------------------------------------
    # Distance from destination
    # --------------------------------------------------------

    distance = _safe_float(
        place.get(
            "distance_km",
            999,
        ),
        999,
    )


    if distance <= 1:

        score += 8

    elif distance <= 3:

        score += 5

    elif distance <= 5:

        score += 3


    return round(
        score,
        1,
    )


# ============================================================
# SORT PLACES
# ============================================================

def _sort_places(
    places: List[Dict],
) -> List[Dict]:
    """
    Sort places by overall itinerary priority.
    """

    valid_places = [
        place
        for place in places
        if isinstance(
            place,
            dict,
        )
    ]


    return sorted(
        valid_places,
        key=_place_score,
        reverse=True,
    )


# ============================================================
# TRIP DATES
# ============================================================

def _get_trip_dates(
    start_date: str,
    end_date: str,
) -> List[str]:
    """
    Generate all dates in the trip.
    """

    start = date.fromisoformat(
        start_date
    )

    end = date.fromisoformat(
        end_date
    )


    if end < start:

        raise ValueError(
            "End date must be on or after start date."
        )


    dates = []


    current = start


    while current <= end:

        dates.append(
            current.isoformat()
        )

        current += timedelta(
            days=1
        )


    return dates


# ============================================================
# WEATHER-AWARE PLACE SCORE
# ============================================================

def _weather_adjusted_score(
    place: Dict,
    weather_status: str,
) -> float:
    """
    Adjust place priority according to weather.
    """

    score = _place_score(
        place
    )


    outdoor = _is_outdoor_place(
        place
    )


    if weather_status == "good":

        if outdoor:

            score += 12

        else:

            score += 3


    elif weather_status == "moderate":

        if outdoor:

            score -= 5

        else:

            score += 5


    elif weather_status == "poor":

        if outdoor:

            score -= 25

        else:

            score += 10


    return round(
        score,
        1,
    )


# ============================================================
# DISTANCE BONUS
# ============================================================

def _route_distance_bonus(
    previous_place: Dict,
    current_place: Dict,
) -> float:
    """
    Prefer places that are close to the
    previously selected place.
    """

    if not previous_place:

        return 0.0


    distance = _calculate_distance_km(
        previous_place.get(
            "latitude"
        ),
        previous_place.get(
            "longitude"
        ),
        current_place.get(
            "latitude"
        ),
        current_place.get(
            "longitude"
        ),
    )


    if distance <= 0.5:

        return 10.0


    if distance <= 1:

        return 7.0


    if distance <= 2:

        return 4.0


    if distance <= 5:

        return 1.0


    return -3.0


# ============================================================
# VARIETY BONUS
# ============================================================

def _variety_bonus(
    place: Dict,
    selected: List[Dict],
) -> float:
    """
    Encourage variety in the day's itinerary.
    """

    if not selected:

        return 0.0


    current_category = place.get(
        "category",
        "",
    )


    current_type = _get_place_type(
        place
    )


    same_category = 0
    same_type = 0


    for selected_place in selected:

        if (
            selected_place.get(
                "category",
                "",
            )
            == current_category
        ):

            same_category += 1


        if (
            _get_place_type(
                selected_place
            )
            == current_type
        ):

            same_type += 1


    bonus = 0.0


    if same_category == 0:

        bonus += 8


    elif same_category == 1:

        bonus += 4


    elif same_category >= 3:

        bonus -= 8


    if same_type >= 3:

        bonus -= 6


    return bonus


# ============================================================
# SELECT NEXT PLACE
# ============================================================

def _select_next_place(
    remaining_places: List[Dict],
    selected_places: List[Dict],
    weather_status: str,
) -> Dict:
    """
    Select the best next place for the day.
    """

    if not remaining_places:

        return None


    previous_place = (
        selected_places[-1]
        if selected_places
        else None
    )


    best_place = None
    best_score = None


    for place in remaining_places:

        score = _weather_adjusted_score(
            place,
            weather_status,
        )


        score += _route_distance_bonus(
            previous_place,
            place,
        )


        score += _variety_bonus(
            place,
            selected_places,
        )


        if best_score is None:

            best_score = score
            best_place = place

            continue


        if score > best_score:

            best_score = score
            best_place = place


    return best_place


# ============================================================
# BUILD DAILY PLACES
# ============================================================

def _build_day_places(
    remaining_places: List[Dict],
    weather_status: str,
    max_places: int,
) -> List[Dict]:
    """
    Build a logical group of places for one day.
    """

    day_places = []


    while (
        remaining_places
        and len(day_places) < max_places
    ):

        next_place = _select_next_place(
            remaining_places,
            day_places,
            weather_status,
        )


        if next_place is None:

            break


        day_places.append(
            next_place
        )


        remaining_places.remove(
            next_place
        )


    return day_places


# ============================================================
# BUILD ITINERARY PLACE OBJECT
# ============================================================

def _build_itinerary_place(
    place: Dict,
    order: int,
) -> Dict:
    """
    Convert a place into the public itinerary format.
    """

    return {
        "order":
            order,

        "name":
            place.get(
                "name",
                "",
            ),

        "category":
            place.get(
                "category",
                "",
            ),

        "distance_km":
            place.get(
                "distance_km",
            ),

        "latitude":
            place.get(
                "latitude",
            ),

        "longitude":
            place.get(
                "longitude",
            ),

        "why_visit":
            place.get(
                "why_visit",
                "",
            ),

        "tourist_quality_score":
            place.get(
                "tourist_quality_score",
                0,
            ),

        "tourist_place_type":
            place.get(
                "tourist_place_type",
                _get_place_type(
                    place
                ),
            ),

        "outdoor":
            _is_outdoor_place(
                place
            ),
    }


# ============================================================
# WEATHER RECOMMENDATION
# ============================================================

def _weather_recommendation(
    weather_status: str,
) -> str:
    """
    Generate a simple recommendation based on weather.
    """

    if weather_status == "poor":

        return (
            "Weather may be unsuitable for "
            "outdoor activities. Prioritize "
            "shorter visits and sheltered "
            "or indoor attractions where possible."
        )


    if weather_status == "moderate":

        return (
            "There may be some rain. Keep the "
            "itinerary flexible and carry "
            "rain protection."
        )


    return (
        "Weather conditions are generally "
        "suitable for travel and outdoor "
        "activities."
    )


# ============================================================
# BUILD ITINERARY
# ============================================================

def generate_itinerary(
    places: List[Dict],
    weather: Dict,
    start_date: str,
    end_date: str,
) -> Dict:
    """
    Generate a smart day-by-day itinerary.

    The generator:
    - considers weather
    - considers tourist quality
    - considers place type
    - considers route distance
    - encourages variety
    - limits places per day
    """

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    trip_dates = _get_trip_dates(
        start_date,
        end_date,
    )


    # --------------------------------------------------------
    # Validate places
    # --------------------------------------------------------

    valid_places = [
        dict(place)
        for place in places
        if isinstance(
            place,
            dict,
        )
    ]


    if not valid_places:

        return {
            "total_days":
                len(trip_dates),

            "total_places":
                0,

            "days":
                [],
        }


    # --------------------------------------------------------
    # Remove duplicate names
    # --------------------------------------------------------

    unique_places = []

    seen_names = set()
    seen_coordinates = set()


    for place in valid_places:

        name = str(
            place.get(
                "name",
                "",
            )
        ).strip().lower()


        if name in seen_names:

            continue


        coordinate_key = None


        try:

            coordinate_key = (
                round(
                    float(
                        place.get(
                            "latitude"
                        )
                    ),
                    4,
                ),

                round(
                    float(
                        place.get(
                            "longitude"
                        )
                    ),
                    4,
                ),
            )

        except (
            TypeError,
            ValueError,
        ):

            coordinate_key = None


        if (
            coordinate_key is not None
            and coordinate_key in seen_coordinates
        ):

            continue


        unique_places.append(
            place
        )


        seen_names.add(
            name
        )


        if coordinate_key is not None:

            seen_coordinates.add(
                coordinate_key
            )


    # --------------------------------------------------------
    # Places available
    # --------------------------------------------------------

    remaining_places = list(
        _sort_places(
            unique_places
        )
    )


    # --------------------------------------------------------
    # Daily capacity
    # --------------------------------------------------------

    total_capacity = (
        len(trip_dates)
        * MAX_PLACES_PER_DAY
    )


    if len(remaining_places) > total_capacity:

        remaining_places = (
            remaining_places[
                :total_capacity
            ]
        )


    # --------------------------------------------------------
    # Build days
    # --------------------------------------------------------

    itinerary_days = []


    for day_number, trip_date in enumerate(
        trip_dates,
        start=1,
    ):

        daily_weather = _get_daily_weather(
            weather,
            trip_date,
        )


        weather_status = _weather_suitability(
            daily_weather
        )


        # ----------------------------------------------------
        # Build day's places
        # ----------------------------------------------------

        day_places = _build_day_places(
            remaining_places,
            weather_status,
            MAX_PLACES_PER_DAY,
        )


        # ----------------------------------------------------
        # Convert places
        # ----------------------------------------------------

        itinerary_places = []


        for order, place in enumerate(
            day_places,
            start=1,
        ):

            itinerary_places.append(
                _build_itinerary_place(
                    place,
                    order,
                )
            )


        # ----------------------------------------------------
        # Recommendation
        # ----------------------------------------------------

        recommendation = (
            _weather_recommendation(
                weather_status
            )
        )


        # ----------------------------------------------------
        # Add day
        # ----------------------------------------------------

        itinerary_days.append(
            {
                "day":
                    day_number,

                "date":
                    trip_date,

                "weather":
                    daily_weather,

                "weather_suitability":
                    weather_status,

                "recommendation":
                    recommendation,

                "places":
                    itinerary_places,
            }
        )


    # ========================================================
    # RETURN
    # ========================================================

    return {
        "total_days":
            len(trip_dates),

        "total_places":
            sum(
                len(
                    day.get(
                        "places",
                        [],
                    )
                )
                for day in itinerary_days
            ),

        "days":
            itinerary_days,
    }