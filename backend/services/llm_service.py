"""
LLM Service
Uses NVIDIA NIM with an OpenAI-compatible API.

Responsibilities:
1. Load NVIDIA API configuration.
2. Test NVIDIA connection.
3. Send grounded travel data to the LLM.
4. Generate a structured AI travel plan.
5. Include nearby restaurants inside the relevant itinerary day.
6. Include attraction, meal, daily, and complete-trip budget estimates.
"""

import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

NVIDIA_MODEL = os.getenv(
    "NVIDIA_MODEL",
    "openai/gpt-oss-20b",
)

NVIDIA_BASE_URL = os.getenv(
    "NVIDIA_BASE_URL",
    "https://integrate.api.nvidia.com/v1",
)


# ============================================================
# NVIDIA CLIENT
# ============================================================

def get_nvidia_client() -> OpenAI:
    """Create and return the NVIDIA OpenAI-compatible client."""

    if not NVIDIA_API_KEY:
        raise RuntimeError(
            "NVIDIA_API_KEY is not configured. "
            "Check your .env file."
        )

    return OpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=NVIDIA_API_KEY,
        timeout=120.0,
        max_retries=1,
    )


# ============================================================
# CONNECTION TEST
# ============================================================

def test_nvidia_connection() -> str:
    """Test the NVIDIA LLM connection."""

    client = get_nvidia_client()

    response = client.chat.completions.create(
        model=NVIDIA_MODEL,
        messages=[
            {
                "role": "user",
                "content": "Say hello in one short sentence.",
            }
        ],
        temperature=0.2,
        max_tokens=100,
    )

    return (
        response.choices[0].message.content
        or "No response received."
    )


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    return str(value).strip()


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


# ============================================================
# RESTAURANT PREPARATION
# ============================================================

def _prepare_restaurant(
    restaurant: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Prepare one restaurant for the LLM.

    The current restaurant search provides distance from the
    attraction being searched. Preserve that relationship.
    """

    return {
        "name": _clean_text(
            restaurant.get("name"),
            "Restaurant",
        ),
        "category": _clean_text(
            restaurant.get("category"),
            "Restaurant",
        ),
        "distance_km": _safe_float(
            restaurant.get("distance_km"),
            0,
        ),
        "restaurant_quality_score": _safe_float(
            restaurant.get(
                "restaurant_quality_score"
            ),
            0,
        ),
        "cuisine": restaurant.get(
            "cuisine",
            restaurant.get(
                "cuisines",
                [],
            ),
        ),
        "address": _clean_text(
            restaurant.get("address")
        ),
        "latitude": restaurant.get("latitude"),
        "longitude": restaurant.get("longitude"),
    }


def _prepare_restaurant_group(
    group: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Prepare restaurants grouped around a specific attraction.

    Expected current backend structure:

    {
        "place_name": "...",
        "place_latitude": ...,
        "place_longitude": ...,
        "restaurant_count": 5,
        "restaurants": [...]
    }
    """

    prepared = {
        "place_name": _clean_text(
            group.get("place_name"),
            "Unknown attraction",
        ),
        "place_latitude": group.get(
            "place_latitude",
            group.get("latitude"),
        ),
        "place_longitude": group.get(
            "place_longitude",
            group.get("longitude"),
        ),
        "restaurant_count": _safe_int(
            group.get("restaurant_count"),
            len(
                _as_list(
                    group.get("restaurants")
                )
            ),
        ),
        "restaurants": [],
    }

    restaurants = group.get(
        "restaurants",
        [],
    )

    if isinstance(restaurants, list):
        prepared["restaurants"] = [
            _prepare_restaurant(item)
            for item in restaurants
            if isinstance(item, dict)
        ]

    return prepared


# ============================================================
# PLACE PREPARATION
# ============================================================

def _prepare_place(
    place: Dict[str, Any],
) -> Dict[str, Any]:
    """Prepare tourist-place information for the LLM."""

    return {
        "name": _clean_text(
            place.get("name"),
            "Unnamed place",
        ),
        "category": _clean_text(
            place.get("category"),
            "Tourist Attraction",
        ),
        "tourist_place_type": _clean_text(
            place.get("tourist_place_type")
        ),
        "distance_km": _safe_float(
            place.get("distance_km"),
            0,
        ),
        "tourist_quality_score": _safe_float(
            place.get(
                "tourist_quality_score"
            ),
            0,
        ),
        "preprocessing_score": _safe_float(
            place.get(
                "preprocessing_score"
            ),
            0,
        ),
        "description": _clean_text(
            place.get("description")
        ),
        "why_visit": _clean_text(
            place.get("why_visit")
        ),
        "wikipedia_title": _clean_text(
            place.get("wikipedia_title")
        ),
        "wikipedia_description": _clean_text(
            place.get(
                "wikipedia_description"
            )
        ),
        "wikipedia_url": _clean_text(
            place.get("wikipedia_url")
        ),
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude"),
    }


# ============================================================
# WEATHER PREPARATION
# ============================================================

def _prepare_weather(
    weather: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not weather:
        return {}

    daily = weather.get(
        "daily",
        {},
    )

    result = {
        "timezone": weather.get("timezone"),
        "current": weather.get(
            "current",
            {},
        ),
        "daily": [],
    }

    dates = _as_list(
        daily.get("time", [])
    )

    weather_codes = _as_list(
        daily.get("weather_code", [])
    )

    max_temperatures = _as_list(
        daily.get("temperature_2m_max", [])
    )

    min_temperatures = _as_list(
        daily.get("temperature_2m_min", [])
    )

    rain_probabilities = _as_list(
        daily.get(
            "precipitation_probability_max",
            [],
        )
    )

    precipitation = _as_list(
        daily.get(
            "precipitation_sum",
            [],
        )
    )

    sunrise = _as_list(
        daily.get("sunrise", [])
    )

    sunset = _as_list(
        daily.get("sunset", [])
    )

    for index, trip_date in enumerate(dates):
        result["daily"].append(
            {
                "date": trip_date,
                "weather_code": (
                    weather_codes[index]
                    if index < len(weather_codes)
                    else None
                ),
                "temperature_max": (
                    max_temperatures[index]
                    if index < len(max_temperatures)
                    else None
                ),
                "temperature_min": (
                    min_temperatures[index]
                    if index < len(min_temperatures)
                    else None
                ),
                "rain_probability": (
                    rain_probabilities[index]
                    if index < len(rain_probabilities)
                    else None
                ),
                "precipitation": (
                    precipitation[index]
                    if index < len(precipitation)
                    else None
                ),
                "sunrise": (
                    sunrise[index]
                    if index < len(sunrise)
                    else None
                ),
                "sunset": (
                    sunset[index]
                    if index < len(sunset)
                    else None
                ),
            }
        )

    return result


# ============================================================
# ROUTE PREPARATION
# ============================================================

def _prepare_route(
    route: Optional[Dict[str, Any]],
) -> Dict[str, Any]:

    if not route:
        return {}

    prepared_places = []

    for place in _as_list(
        route.get("places", [])
    ):
        if not isinstance(place, dict):
            continue

        prepared_places.append(
            {
                "route_order": place.get(
                    "route_order"
                ),
                "name": _clean_text(
                    place.get("name")
                ),
                "category": _clean_text(
                    place.get("category")
                ),
                "distance_from_previous_km":
                    _safe_float(
                        place.get(
                            "distance_from_previous_km"
                        ),
                        0,
                    ),
                "cumulative_route_distance_km":
                    _safe_float(
                        place.get(
                            "cumulative_route_distance_km"
                        ),
                        0,
                    ),
            }
        )

    return {
        "total_places": route.get(
            "total_places",
            len(prepared_places),
        ),
        "total_distance_km": _safe_float(
            route.get(
                "total_distance_km"
            ),
            0,
        ),
        "places": prepared_places,
    }


# ============================================================
# ITINERARY PREPARATION
# ============================================================

def _prepare_itinerary(
    itinerary: Optional[Dict[str, Any]],
) -> Dict[str, Any]:

    if not itinerary:
        return {}

    prepared_days = []

    for day in _as_list(
        itinerary.get("days", [])
    ):
        if not isinstance(day, dict):
            continue

        prepared_places = []

        for place in _as_list(
            day.get("places", [])
        ):
            if not isinstance(place, dict):
                continue

            prepared_places.append(
                {
                    "order": place.get("order"),
                    "name": _clean_text(
                        place.get("name")
                    ),
                    "category": _clean_text(
                        place.get("category")
                    ),
                    "distance_km": _safe_float(
                        place.get("distance_km"),
                        0,
                    ),
                    "why_visit": _clean_text(
                        place.get("why_visit")
                    ),
                    "tourist_quality_score":
                        _safe_float(
                            place.get(
                                "tourist_quality_score"
                            ),
                            0,
                        ),
                }
            )

        prepared_days.append(
            {
                "day": day.get("day"),
                "date": day.get("date"),
                "weather_suitability":
                    day.get(
                        "weather_suitability"
                    ),
                "recommendation":
                    day.get(
                        "recommendation"
                    ),
                "places": prepared_places,
            }
        )

    return {
        "total_days": itinerary.get(
            "total_days",
            len(prepared_days),
        ),
        "total_places": itinerary.get(
            "total_places",
            sum(
                len(day["places"])
                for day in prepared_days
            ),
        ),
        "days": prepared_days,
    }


# ============================================================
# RESTAURANT PREPARATION
# ============================================================

def _prepare_restaurants(
    restaurants: Optional[Dict[str, Any]],
) -> Dict[str, Any]:

    if not restaurants:
        return {
            "count": 0,
            "places_checked": 0,
            "restaurants_found": 0,
            "items": [],
        }

    raw_items = _as_list(
        restaurants.get("items", [])
    )

    prepared_items = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        # Current grouped structure.
        if isinstance(
            item.get("restaurants"),
            list,
        ):
            prepared_items.append(
                _prepare_restaurant_group(item)
            )

        # Backward compatibility with old flat structure.
        elif item.get("name"):
            prepared_items.append(
                _prepare_restaurant(item)
            )

    return {
        "count": restaurants.get(
            "count",
            len(prepared_items),
        ),
        "places_checked": restaurants.get(
            "places_checked",
            len(prepared_items),
        ),
        "restaurants_found": restaurants.get(
            "restaurants_found",
            sum(
                item.get(
                    "restaurant_count",
                    1,
                )
                for item in prepared_items
            ),
        ),
        "items": prepared_items,
    }


def _calculate_trip_days(
    start_date: str,
    end_date: str,
) -> int:
    """Return inclusive calendar-day count for the trip."""
    try:
        from datetime import date

        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        if end < start:
            return 0

        return (end - start).days + 1

    except (TypeError, ValueError):
        return 0


# ============================================================
# BUILD LLM CONTEXT
# ============================================================

def build_llm_context(
    destination: str,
    start_date: str,
    end_date: str,
    places: List[Dict[str, Any]],
    route: Optional[Dict[str, Any]],
    weather: Optional[Dict[str, Any]],
    itinerary: Optional[Dict[str, Any]],
    restaurants: Optional[Dict[str, Any]],
    user_query: str = "",
    travelers: Optional[int] = None,
    budget: Optional[str] = None,
    preferences: Optional[str] = None,
) -> Dict[str, Any]:

    return {
        "trip": {
            "destination": destination,
            "start_date": start_date,
            "end_date": end_date,
            "trip_days": _calculate_trip_days(start_date, end_date),
            "travelers": travelers,
            "budget": budget,
            "preferences": preferences,
            "user_query": user_query,
        },
        "places": [
            _prepare_place(place)
            for place in places
            if isinstance(place, dict)
        ],
        "route": _prepare_route(route),
        "weather": _prepare_weather(weather),
        "itinerary": _prepare_itinerary(itinerary),
        "restaurants": _prepare_restaurants(
            restaurants
        ),
    }


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an expert AI travel planner and travel-budget analyst.

Your job is to create a COMPLETE, detailed, readable, personalized travel plan.
Do not summarize away important information. The user explicitly wants useful
background, history, reasons to visit, what to see, nearby food, and realistic
approximate budget estimates.

The backend supplies:
- destination
- exact trip start and end dates
- exact number of trip days
- traveler count
- user budget
- user query and preferences
- selected tourist places
- descriptions and historical/background information
- route information
- weather information
- restaurants grouped by the attraction they are near
- a preliminary itinerary

============================================================
NON-NEGOTIABLE COMPLETENESS
============================================================

DO NOT remove important place information just to make the response shorter.

Every attraction that you place in the itinerary MUST contain:
1. place name
2. category
3. why_visit
4. background/history
5. what_to_see
6. practical/travel note when useful
7. estimated cost

The user specifically wants to understand:
- Why should I visit this place?
- What is its history?
- What is important about it?
- What should I see there?
- How much might it cost?

For historically important places, give a meaningful short history, normally
2-4 sentences, using backend information whenever supplied.

If backend historical information is available, preserve it and use it.
If backend data is incomplete, you may provide a clearly labeled planning
description based on generally known information, but NEVER claim an
unverified fact is verified backend data.

NEVER replace useful text with:
"..."
"Details not available"
or an empty field when the backend contains useful information.

If a specific fact genuinely cannot be established, say:
"Specific information is not available in the current data."
Then still provide all other useful information that is supported.

============================================================
TRIP-DAY ACCURACY
============================================================

The trip has an exact start date, end date, and exact number of calendar days.

Create EXACTLY one day object for each calendar date from start_date through
end_date, inclusive.

NEVER create an extra day.
NEVER skip a date.
NEVER invent dates.
NEVER create "Day 4" for a 3-day trip.

Each day must use its real calendar date.

============================================================
PLACE SELECTION
============================================================

Use the supplied tourist places and itinerary as the primary source for
attraction selection.

Respect the user's query and preferences.

If the user prefers historical places, prioritize historical places.
If the user wants less walking, avoid unnecessarily walking-heavy plans.
If the user asks for a relaxed trip, do not overcrowd a day.

Do not remove important attractions merely because a shorter answer is easier.

============================================================
RESTAURANT LOCATION RULE
============================================================

This is critical.

Restaurants are grouped around INDIVIDUAL ATTRACTIONS.

For every meal:
1. Identify the attraction the traveler has JUST finished.
2. Find the restaurant group whose "place_name" matches that attraction.
3. Recommend restaurants ONLY from that group.
4. State "Near <attraction>".
5. Give one best choice and up to two alternatives when available.

Example:

Golconda Fort
11:00 AM - 12:30 PM
finish sightseeing

Lunch
12:30 PM - 01:30 PM
Near Golconda Fort

Use ONLY the Golconda Fort restaurant group.

Do NOT use restaurants from the original map-selected Hyderabad location.

The same rule applies to evening snacks and dinner.

Prefer restaurant choices using:
1. compatibility with user's food preferences
2. shorter distance from the attraction
3. higher quality score
4. suitable category/cuisine if supplied

Do not claim a restaurant is near an attraction unless it belongs to that
attraction's restaurant group.

If no restaurants are available in that attraction's group, say:
"No suitable restaurant was identified near this attraction in the current
travel data."

============================================================
DETAILED PLACE CONTENT
============================================================

For every important attraction, write:

Why visit:
A concise but meaningful explanation of why the traveler should spend time
there and what makes it worth visiting.

History:
A short, readable historical background. Include known historical significance,
period, ruler/dynasty/architectural context when supported by the supplied
data or clearly established general knowledge.

What to see:
Give concrete things the traveler should look for at the attraction.

Practical note:
Mention walking difficulty, indoor/outdoor character, weather relevance,
or other useful planning information only when appropriate.

Do not repeat the same generic text for every place.

============================================================
APPROXIMATE BUDGET
============================================================

The user explicitly wants approximate costs.

ALWAYS provide a planning estimate for:
- attraction entry/tickets
- lunch
- evening snack
- dinner when included
- local transportation
- each day's total
- complete trip total
- comparison with user's budget

There is an important distinction:

1. VERIFIED COST
If the backend actually supplies an exact ticket/price, use it and label it
as verified/backend-provided.

2. APPROXIMATE COST
If the backend does not supply an exact price, provide a reasonable
PLANNING ESTIMATE or RANGE and clearly label it:
"Approximate"
or
"Planning estimate - not verified"

Do NOT invent an exact official ticket price.

For example, if the ticket price is not in the backend:
"Approximate entry: ₹20-₹50/person"
is acceptable.

"Entry fee: ₹25/person"
is NOT acceptable unless ₹25 came from the backend.

For food, estimate a realistic range based on the restaurant category,
location, traveler count and user's budget/preferences. Do not use the
restaurant quality score as a food price.

For transportation, estimate a reasonable local transportation range using
the route/trip context. Clearly label it approximate.

For accommodation:
- If the user provided accommodation cost, include it.
- If no accommodation information is provided, set accommodation to
  "Not included" and explain that lodging was not provided.
Do not invent a hotel booking.

Use traveler count when calculating totals.

If travelers = 2 and a meal estimate is ₹500-₹700, represent the cost as
₹500-₹700 FOR 2 PEOPLE.

============================================================
BUDGET MATH
============================================================

All numeric budget fields must be mathematically consistent.

For each day:

total_min =
attractions_min + food_min + transport_min + accommodation_min + other_min

total_max =
attractions_max + food_max + transport_max + accommodation_max + other_max

For the complete trip:

estimated_total.min =
sum of all day total_min

estimated_total.max =
sum of all day total_max

If a numeric user budget exists:

remaining_budget.min =
budget - estimated_total.max

remaining_budget.max =
budget - estimated_total.min

Budget status:
- "Within Budget" only when estimated maximum is <= budget.
- "May Exceed Budget" when the range crosses the budget.
- "Over Budget" when even the minimum estimate is above the budget.

Never call a trip "Within Budget" if its maximum estimated cost exceeds the
user's budget.

If accommodation is excluded, say so clearly in the budget summary so the user
does not mistake the estimate for a complete hotel-inclusive trip.

============================================================
WEATHER
============================================================

Use supplied weather to adjust the itinerary.

Do not produce a long weather report.

Mention weather only when it changes the plan, for example:
- move an outdoor fort before rain
- put a museum during a rain period
- suggest umbrella/rain protection

Never invent hourly weather.

============================================================
USER QUERY
============================================================

The user's query is a major planning constraint.

Respect:
- budget
- traveler count
- family/solo/couple/friends
- preferred places
- unwanted places
- food preferences
- restaurant preferences
- walking preferences
- transportation preferences
- relaxed/busy preference
- desired historical detail
- special requests

The query must affect actual itinerary choices.

============================================================
OUTPUT STRUCTURE
============================================================

Return ONLY valid JSON.
No Markdown.
No code fences.
No commentary.

Use exactly this structure:

{
  "title": "AI Travel Plan",
  "trip_overview": "2-4 sentence useful overview",
  "trip_summary": {
    "destination": "...",
    "start_date": "...",
    "end_date": "...",
    "travelers": 2,
    "budget": "...",
    "preferences": "..."
  },
  "highlights": [
    {
      "title": "...",
      "description": "..."
    }
  ],
  "days": [
    {
      "day": 1,
      "date": "...",
      "weather_note": "...",

      "morning": {
        "start_time": "...",
        "end_time": "...",
        "activities": [
          {
            "place": "...",
            "category": "...",
            "why_visit": "Meaningful explanation.",
            "background": "Useful history/background.",
            "what_to_see": "Specific things to see.",
            "travel_note": "Practical note.",
            "cost": {
              "type": "entry",
              "amount_per_person": 0,
              "total_for_travelers": 0,
              "min_total": 0,
              "max_total": 0,
              "currency": "INR",
              "label": "Approximate",
              "note": "Explain whether verified or approximate."
            }
          }
        ]
      },

      "lunch": {
        "start_time": "...",
        "end_time": "...",
        "near": "The attraction just completed",
        "recommendations": [
          {
            "rank": 1,
            "name": "...",
            "distance_km": 0,
            "category": "...",
            "quality_score": 0,
            "reason": "Why this restaurant fits.",
            "cost": {
              "min_total": 0,
              "max_total": 0,
              "currency": "INR",
              "label": "Approximate",
              "note": "Planning estimate for all travelers."
            }
          }
        ],
        "fallback_message": ""
      },

      "afternoon": {
        "start_time": "...",
        "end_time": "...",
        "activities": [
          {
            "place": "...",
            "category": "...",
            "why_visit": "...",
            "background": "...",
            "what_to_see": "...",
            "travel_note": "...",
            "cost": {
              "type": "entry",
              "amount_per_person": 0,
              "total_for_travelers": 0,
              "min_total": 0,
              "max_total": 0,
              "currency": "INR",
              "label": "Approximate",
              "note": "..."
            }
          }
        ]
      },

      "evening": {
        "start_time": "...",
        "end_time": "...",
        "activity": "...",
        "near": "..."
      },

      "evening_snack": {
        "start_time": "...",
        "end_time": "...",
        "near": "The attraction just completed",
        "recommendations": [
          {
            "rank": 1,
            "name": "...",
            "distance_km": 0,
            "category": "...",
            "quality_score": 0,
            "reason": "...",
            "cost": {
              "min_total": 0,
              "max_total": 0,
              "currency": "INR",
              "label": "Approximate",
              "note": "..."
            }
          }
        ],
        "fallback_message": ""
      },

      "dinner": {
        "start_time": "...",
        "end_time": "...",
        "near": "...",
        "recommendations": [],
        "fallback_message": ""
      },

      "day_cost": {
        "attractions_min": 0,
        "attractions_max": 0,
        "food_min": 0,
        "food_max": 0,
        "transport_min": 0,
        "transport_max": 0,
        "accommodation_min": 0,
        "accommodation_max": 0,
        "other_min": 0,
        "other_max": 0,
        "total_min": 0,
        "total_max": 0,
        "currency": "INR",
        "notes": "Explain important inclusions/exclusions."
      },

      "day_tip": "One useful practical tip."
    }
  ],

  "trip_budget": {
    "travelers": 2,
    "budget_amount": 10000,
    "currency": "INR",

    "attractions": {
      "min": 0,
      "max": 0
    },
    "food": {
      "min": 0,
      "max": 0
    },
    "transportation": {
      "min": 0,
      "max": 0
    },
    "accommodation": {
      "min": 0,
      "max": 0
    },
    "other": {
      "min": 0,
      "max": 0
    },
    "estimated_total": {
      "min": 0,
      "max": 0
    },
    "remaining_budget": {
      "min": 0,
      "max": 0
    },
    "budget_status": "Within Budget",
    "summary": "Clear explanation of estimated total and budget."
  },

  "important_places": [
    {
      "name": "...",
      "background": "...",
      "why_visit": "...",
      "what_to_see": "..."
    }
  ],

  "travel_tips": [
    "..."
  ]
}

============================================================
FINAL QUALITY CHECK BEFORE RETURNING JSON
============================================================

Before returning the JSON, verify all of these:

1. Number of days exactly matches the calendar date range.
2. No extra day exists.
3. Every selected attraction has why_visit.
4. Every selected attraction has meaningful background/history.
5. Every selected attraction has what_to_see.
6. Every selected attraction has a cost estimate.
7. Lunch is near the attraction just completed.
8. Evening snack is near the attraction just completed.
9. Restaurant names come from the matching attraction group.
10. Food costs are approximate and do not use quality score as price.
11. Daily totals are mathematically correct.
12. Complete-trip totals are mathematically correct.
13. Budget status matches the maximum/minimum estimates.
14. User preferences actually affect choices.
15. No useful backend information has been removed.
16. Do not use "..." as a substitute for missing detail.
17. Return JSON only.
"""


# ============================================================
# USER PROMPT BUILDER
# ============================================================

def _build_user_prompt(
    context: Dict[str, Any],
) -> str:
    """Convert backend context into a strict, completeness-focused prompt."""

    trip = context.get("trip", {})
    places = context.get("places", [])
    itinerary = context.get("itinerary", {})
    restaurants = context.get("restaurants", {})

    return f"""
Create the final COMPLETE personalized AI travel plan.

Do not shorten the response by removing history, reasons to visit, what to see,
or cost information. The user wants detailed but readable explanations.

MANDATORY:
- Use exactly the calendar dates from {trip.get("start_date")} through
  {trip.get("end_date")}.
- Create exactly {trip.get("trip_days")} day objects.
- Do not create any additional day.
- Use the user's query as a real constraint.
- Keep the itinerary chronological.
- Every attraction must contain why_visit, background, what_to_see, travel_note,
  and a cost object.
- Preserve useful historical/background information from backend data.
- Give a meaningful history for important historical attractions.
- Give a practical reason for visiting every selected attraction.
- Do not output "..." anywhere.
- Do not replace useful content with generic filler.
- The itinerary attractions must come from the supplied backend tourist places/itinerary.
- Prioritize strong historical/heritage places that satisfy the user preferences.
- If Golconda Fort is present in supplied tourist-place data, strongly prefer it over weak generic attractions.
- Highlights must only contain attractions that actually appear in the day-by-day itinerary.
- Never call the travelers a couple unless the user explicitly says they are a couple.
- Use practical meal times: lunch 12:00-14:00, evening snack 16:30-18:00, dinner 19:00-21:00.

RESTAURANT RULE:
- Restaurants are grouped by attraction.
- Lunch must use the restaurant group of the attraction just completed.
- Evening snack must use the restaurant group of the attraction just completed.
- Dinner must also use the group of the relevant nearby attraction when
  restaurants are available.
- Never use a generic city/original-map restaurant list when an attraction
  group is available.
- Recommend one best choice and up to two alternatives.
- State the attraction in the "near" field.
- Never claim a restaurant is near an attraction unless it is in that
  attraction's restaurant group.

BUDGET RULE:
- The user explicitly wants approximate budget information.
- Every attraction must have an entry-cost planning estimate.
- If an exact backend price exists, use it.
- Otherwise provide a reasonable APPROXIMATE RANGE and label it
  "Approximate" or "Planning estimate - not verified".
- Never invent an exact official ticket price.
- Every meal/snack/dinner should have an approximate cost range for all
  travelers.
- Estimate local transport from the route/trip context.
- Calculate every day total.
- Calculate the complete trip total.
- Compare the total with the user's budget.
- Do not mark the trip "Within Budget" if the maximum estimate exceeds the
  budget.
- Accommodation must be excluded/not included when no accommodation data was
  supplied.

COMPLETENESS RULE:
Do not omit an attraction simply because the answer becomes longer.
Do not summarize history into one vague sentence when backend information is
available.

BACKEND DATA:
{json.dumps(context, ensure_ascii=False, indent=2)}

Return valid JSON only.
"""

# ============================================================
# JSON EXTRACTION

# ============================================================

def _extract_json(
    text: str,
) -> Dict[str, Any]:
    """Safely extract a JSON object from an LLM response."""

    if not text:
        raise ValueError(
            "LLM returned an empty response."
        )

    cleaned = text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):]

    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)

        if not isinstance(result, dict):
            raise ValueError(
                "LLM JSON response is not an object."
            )

        return result

    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if (
            start == -1
            or end == -1
            or end <= start
        ):
            raise ValueError(
                "Could not find valid JSON in LLM response."
            )

        extracted = cleaned[
            start:end + 1
        ]

        try:
            result = json.loads(extracted)

            if not isinstance(result, dict):
                raise ValueError(
                    "Extracted LLM response is not an object."
                )

            return result

        except json.JSONDecodeError as error:
            raise ValueError(
                "LLM returned invalid JSON."
            ) from error


# ============================================================
# VALIDATION HELPERS
# ============================================================

def _ensure_dict(
    parent: Dict[str, Any],
    key: str,
) -> Dict[str, Any]:

    if not isinstance(
        parent.get(key),
        dict,
    ):
        parent[key] = {}

    return parent[key]


def _ensure_list(
    parent: Dict[str, Any],
    key: str,
) -> List[Any]:

    if not isinstance(
        parent.get(key),
        list,
    ):
        parent[key] = []

    return parent[key]


def _validate_cost(
    cost: Any,
) -> Dict[str, Any]:
    """Normalize numeric, string, and nested cost shapes."""
    import re

    original = cost
    if isinstance(cost, dict):
        # Older LLM responses sometimes nested the actual price under ticket,
        # entry_cost, approximate_cost, or price.
        nested = (
            cost.get("ticket")
            or cost.get("entry_cost")
            or cost.get("approximate_cost")
            or cost.get("price")
        )
        if isinstance(nested, dict) and not any(
            cost.get(k) is not None for k in ("min_total", "max_total", "total_for_travelers")
        ):
            cost = {**nested, **cost}
    else:
        cost = {"raw": cost}

    def number(value: Any) -> Optional[float]:
        if isinstance(value, (int, float)):
            return float(value)
        if value is None:
            return None
        match = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
        return float(match.group()) if match else None

    lo = number(cost.get("min_total"))
    hi = number(cost.get("max_total"))
    total = number(cost.get("total_for_travelers"))
    per_person = number(cost.get("amount_per_person"))

    if lo is None and hi is None:
        raw = cost.get("raw")
        if isinstance(raw, dict):
            lo = number(raw.get("min_total"))
            hi = number(raw.get("max_total"))
            total = total if total is not None else number(raw.get("total_for_travelers"))
            per_person = per_person if per_person is not None else number(raw.get("amount_per_person"))
        elif raw is not None:
            values = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(raw).replace(",", ""))]
            if len(values) >= 2:
                lo, hi = values[0], values[1]
            elif values:
                lo = hi = values[0]

    travelers_hint = 1
    if lo is None and hi is None and total is not None:
        lo = hi = total
    if lo is None and hi is None and per_person is not None:
        lo = hi = per_person * travelers_hint
    if lo is None:
        lo = 0.0
    if hi is None:
        hi = lo
    if hi < lo:
        lo, hi = hi, lo

    label = _clean_text(cost.get("label"), "Approximate")
    note = _clean_text(cost.get("note"), "Planning estimate - not verified by the current backend data.")

    return {
        "type": _clean_text(cost.get("type"), "entry"),
        "amount_per_person": round(per_person if per_person is not None else (lo + hi) / 2),
        "total_for_travelers": round(total if total is not None else (lo + hi) / 2),
        "min_total": round(lo),
        "max_total": round(hi),
        "currency": _clean_text(cost.get("currency"), "INR"),
        "label": label,
        "note": note,
    }


def _validate_restaurant_recommendations(
    section: Dict[str, Any],
) -> None:

    recommendations = _ensure_list(
        section,
        "recommendations",
    )

    for index, recommendation in enumerate(
        recommendations
    ):
        if not isinstance(
            recommendation,
            dict,
        ):
            recommendations[index] = {
                "rank": index + 1,
                "name": "Restaurant",
                "distance_km": 0,
                "category": "Restaurant",
                "quality_score": 0,
                "reason": "",
                "cost": _validate_cost({}),
            }
            continue

        recommendation.setdefault(
            "rank",
            index + 1,
        )

        recommendation.setdefault(
            "name",
            "Restaurant",
        )

        recommendation.setdefault(
            "distance_km",
            0,
        )

        recommendation.setdefault(
            "category",
            "Restaurant",
        )

        recommendation.setdefault(
            "quality_score",
            0,
        )

        recommendation.setdefault(
            "reason",
            "",
        )

        recommendation["cost"] = _validate_cost(
            recommendation.get("cost")
        )

    section.setdefault(
        "fallback_message",
        "",
    )


def _validate_activity(
    activity: Dict[str, Any],
) -> None:

    activity.setdefault(
        "place",
        "Unnamed place",
    )

    activity.setdefault(
        "category",
        "Tourist Attraction",
    )

    activity.setdefault(
        "why_visit",
        "",
    )

    activity.setdefault(
        "background",
        "",
    )

    activity.setdefault(
        "what_to_see",
        "",
    )

    activity.setdefault(
        "travel_note",
        "",
    )

    activity["cost"] = _validate_cost(
        activity.get("cost")
    )


# ============================================================
# RESPONSE VALIDATION
# ============================================================

def _validate_travel_plan(
    plan: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Ensure the structured travel plan always contains the
    fields required by the frontend.
    """

    if not isinstance(
        plan,
        dict,
    ):
        raise ValueError(
            "Travel plan must be a dictionary."
        )

    plan.setdefault(
        "title",
        "AI Travel Plan",
    )

    plan.setdefault(
        "trip_overview",
        "",
    )

    plan.setdefault(
        "trip_summary",
        {},
    )

    plan.setdefault(
        "highlights",
        [],
    )

    plan.setdefault(
        "days",
        [],
    )

    plan.setdefault(
        "trip_budget",
        {},
    )

    plan.setdefault(
        "important_places",
        [],
    )

    plan.setdefault(
        "travel_tips",
        [],
    )

    if not isinstance(
        plan["trip_summary"],
        dict,
    ):
        plan["trip_summary"] = {}

    if not isinstance(
        plan["highlights"],
        list,
    ):
        plan["highlights"] = []

    if not isinstance(
        plan["days"],
        list,
    ):
        plan["days"] = []

    if not isinstance(
        plan["important_places"],
        list,
    ):
        plan["important_places"] = []

    if not isinstance(
        plan["travel_tips"],
        list,
    ):
        plan["travel_tips"] = []

    # --------------------------------------------------------
    # Trip budget
    # --------------------------------------------------------

    trip_budget = _ensure_dict(
        plan,
        "trip_budget",
    )

    trip_budget.setdefault(
        "travelers",
        plan["trip_summary"].get(
            "travelers"
        ),
    )

    trip_budget.setdefault(
        "budget_amount",
        0,
    )

    trip_budget.setdefault(
        "currency",
        "INR",
    )

    for category in (
        "attractions",
        "food",
        "transportation",
        "accommodation",
        "other",
        "estimated_total",
        "remaining_budget",
    ):
        category_data = _ensure_dict(
            trip_budget,
            category,
        )

        category_data.setdefault(
            "min",
            0,
        )

        category_data.setdefault(
            "max",
            0,
        )

    trip_budget.setdefault(
        "budget_status",
        "Unknown",
    )

    trip_budget.setdefault(
        "summary",
        "",
    )

    # --------------------------------------------------------
    # Days
    # --------------------------------------------------------

    for day_index, day in enumerate(
        plan["days"]
    ):

        if not isinstance(
            day,
            dict,
        ):
            plan["days"][day_index] = {
                "day": day_index + 1,
                "date": "",
                "weather_note": "",
                "morning": {
                    "start_time": "",
                    "end_time": "",
                    "activities": [],
                },
                "lunch": {
                    "start_time": "",
                    "end_time": "",
                    "near": "",
                    "recommendations": [],
                    "fallback_message": "",
                },
                "afternoon": {
                    "start_time": "",
                    "end_time": "",
                    "activities": [],
                },
                "evening": {
                    "start_time": "",
                    "end_time": "",
                    "activity": "",
                    "near": "",
                },
                "evening_snack": {
                    "start_time": "",
                    "end_time": "",
                    "near": "",
                    "recommendations": [],
                    "fallback_message": "",
                },
                "dinner": {
                    "start_time": "",
                    "end_time": "",
                    "near": "",
                    "recommendations": [],
                    "fallback_message": "",
                },
                "day_cost": {
                    "attractions_min": 0,
                    "attractions_max": 0,
                    "food_min": 0,
                    "food_max": 0,
                    "transport_min": 0,
                    "transport_max": 0,
                    "accommodation_min": 0,
                    "accommodation_max": 0,
                    "other_min": 0,
                    "other_max": 0,
                    "total_min": 0,
                    "total_max": 0,
                    "currency": "INR",
                    "notes": "",
                },
                "day_tip": "",
            }
            continue

        day.setdefault(
            "day",
            day_index + 1,
        )

        day.setdefault(
            "date",
            "",
        )

        day.setdefault(
            "weather_note",
            "",
        )

        # ----------------------------------------------------
        # Morning
        # ----------------------------------------------------

        morning = _ensure_dict(
            day,
            "morning",
        )

        morning.setdefault(
            "start_time",
            "",
        )

        morning.setdefault(
            "end_time",
            "",
        )

        morning_activities = _ensure_list(
            morning,
            "activities",
        )

        for activity in morning_activities:
            if isinstance(
                activity,
                dict,
            ):
                _validate_activity(
                    activity
                )

        # ----------------------------------------------------
        # Lunch
        # ----------------------------------------------------

        lunch = _ensure_dict(
            day,
            "lunch",
        )

        lunch.setdefault(
            "start_time",
            "",
        )

        lunch.setdefault(
            "end_time",
            "",
        )

        lunch.setdefault(
            "near",
            "",
        )

        _validate_restaurant_recommendations(
            lunch
        )

        # ----------------------------------------------------
        # Afternoon
        # ----------------------------------------------------

        afternoon = _ensure_dict(
            day,
            "afternoon",
        )

        afternoon.setdefault(
            "start_time",
            "",
        )

        afternoon.setdefault(
            "end_time",
            "",
        )

        afternoon_activities = _ensure_list(
            afternoon,
            "activities",
        )

        for activity in afternoon_activities:
            if isinstance(
                activity,
                dict,
            ):
                _validate_activity(
                    activity
                )

        # ----------------------------------------------------
        # Evening
        # ----------------------------------------------------

        evening = _ensure_dict(
            day,
            "evening",
        )

        evening.setdefault(
            "start_time",
            "",
        )

        evening.setdefault(
            "end_time",
            "",
        )

        evening.setdefault(
            "activity",
            "",
        )

        evening.setdefault(
            "near",
            "",
        )

        # ----------------------------------------------------
        # Evening snack
        # ----------------------------------------------------

        evening_snack = _ensure_dict(
            day,
            "evening_snack",
        )

        evening_snack.setdefault(
            "start_time",
            "",
        )

        evening_snack.setdefault(
            "end_time",
            "",
        )

        evening_snack.setdefault(
            "near",
            "",
        )

        _validate_restaurant_recommendations(
            evening_snack
        )

        # ----------------------------------------------------
        # Dinner
        # ----------------------------------------------------

        dinner = _ensure_dict(
            day,
            "dinner",
        )

        dinner.setdefault(
            "start_time",
            "",
        )

        dinner.setdefault(
            "end_time",
            "",
        )

        dinner.setdefault(
            "near",
            "",
        )

        _validate_restaurant_recommendations(
            dinner
        )

        # ----------------------------------------------------
        # Day cost
        # ----------------------------------------------------

        day_cost = _ensure_dict(
            day,
            "day_cost",
        )

        for key in (
            "attractions_min",
            "attractions_max",
            "food_min",
            "food_max",
            "transport_min",
            "transport_max",
            "accommodation_min",
            "accommodation_max",
            "other_min",
            "other_max",
            "total_min",
            "total_max",
        ):
            day_cost.setdefault(
                key,
                0,
            )

        day_cost.setdefault(
            "currency",
            "INR",
        )

        day_cost.setdefault(
            "notes",
            "",
        )

        day.setdefault(
            "day_tip",
            "",
        )

    return plan


# ============================================================
# DETERMINISTIC BUDGET + CONTENT REPAIR
# ============================================================

def _parse_budget_amount(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    import re
    text = str(value).replace(",", "").replace("₹", "").replace("INR", "")
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def _money(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _cost_range(cost: Any) -> tuple[float, float]:
    if not isinstance(cost, dict):
        return 0.0, 0.0
    lo, hi = _money(cost.get("min_total")), _money(cost.get("max_total"))
    return (hi, lo) if hi < lo else (lo, hi)


def _all_activities(day: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = []
    for section in ("morning", "afternoon"):
        block = day.get(section)
        if isinstance(block, dict):
            result.extend(a for a in _as_list(block.get("activities")) if isinstance(a, dict))
    return result


def _parse_iso_date(value: Any):
    from datetime import datetime
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except Exception:
        return None


def _date_range(start_date: str, end_date: str) -> List[str]:
    from datetime import timedelta
    start = _parse_iso_date(start_date)
    end = _parse_iso_date(end_date)
    if not start or not end or end < start:
        return []
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def _repair_activity_content(
    activity: Dict[str, Any],
    source_places: Dict[str, Dict[str, Any]],
) -> None:
    """Restore missing factual place content from backend data."""
    name = _clean_text(activity.get("place"), "Unnamed place")
    source = source_places.get(name.casefold())

    if source:
        if not _clean_text(activity.get("category")):
            activity["category"] = source.get("category", "Tourist Attraction")
        if not _clean_text(activity.get("why_visit")):
            activity["why_visit"] = _clean_text(
                source.get("why_visit") or source.get("description")
            )
        if not _clean_text(activity.get("background")):
            activity["background"] = _clean_text(
                source.get("wikipedia_description") or source.get("description")
            )
        if not _clean_text(activity.get("what_to_see")):
            activity["what_to_see"] = _clean_text(source.get("description"))

    # Never allow placeholder text to reach the frontend.
    if not _clean_text(activity.get("why_visit")) or _clean_text(activity.get("why_visit")) == "...":
        activity["why_visit"] = (
            "Visit this place for its historical, architectural, cultural, "
            "or local significance."
        )
    if not _clean_text(activity.get("background")) or _clean_text(activity.get("background")) == "...":
        activity["background"] = (
            "Detailed historical background is not available in the current travel data."
        )
    if not _clean_text(activity.get("what_to_see")) or _clean_text(activity.get("what_to_see")) == "...":
        activity["what_to_see"] = (
            "See the main architectural features, heritage displays, and notable points of interest."
        )
    if not _clean_text(activity.get("travel_note")) or _clean_text(activity.get("travel_note")) == "...":
        activity["travel_note"] = "Plan at a comfortable pace and take breaks as needed."

    # LLM must not claim an unverified price is verified.
    cost = _validate_cost(activity.get("cost"))
    label = _clean_text(cost.get("label"), "Approximate").casefold()
    note = _clean_text(cost.get("note"))
    if "verified" in label or "confirmed" in note.casefold():
        # This project does not currently pass a verified ticket-price field
        # from the place search into the LLM context. Therefore keep all
        # generated ticket prices explicitly as planning estimates.
        cost["label"] = "Approximate"
        cost["note"] = "Planning estimate - not verified by the current backend data."
    elif not note:
        cost["label"] = "Approximate"
        cost["note"] = "Planning estimate - not verified by the current backend data."
    activity["cost"] = cost


def _matching_restaurant_group(
    near: str,
    groups: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    target = _clean_text(near).casefold()
    if not target:
        return None
    for group in groups:
        if not isinstance(group, dict):
            continue
        place = _clean_text(group.get("place_name")).casefold()
        if place == target:
            return group
    for group in groups:
        if not isinstance(group, dict):
            continue
        place = _clean_text(group.get("place_name")).casefold()
        if place and (place in target or target in place):
            return group
    return None


def _copy_restaurant_cost(rec: Dict[str, Any]) -> Dict[str, Any]:
    cost = _validate_cost(rec.get("cost"))
    # Restaurant search does not provide prices, so these are always planning estimates.
    cost["label"] = "Approximate"
    if not _clean_text(cost.get("note")):
        cost["note"] = "Planning estimate for all travelers."
    return cost


def _repair_restaurant_section(
    section: Dict[str, Any],
    groups: List[Dict[str, Any]],
    meal_type: str,
) -> None:
    """Ensure meal recommendations come from the attraction's restaurant group."""
    near = _clean_text(section.get("near"))
    group = _matching_restaurant_group(near, groups)

    if group:
        available = [r for r in _as_list(group.get("restaurants")) if isinstance(r, dict)]
        if available:
            existing = [r for r in _as_list(section.get("recommendations")) if isinstance(r, dict)]
            by_name = {_clean_text(r.get("name")).casefold(): r for r in available}
            repaired = []
            used = set()

            # Preserve the LLM's preference when its restaurant is actually in the group.
            for candidate in existing:
                name = _clean_text(candidate.get("name")).casefold()
                if name in by_name and name not in used:
                    src = by_name[name]
                    merged = dict(src)
                    merged.update(candidate)
                    merged["name"] = src.get("name", candidate.get("name", "Restaurant"))
                    merged["distance_km"] = src.get("distance_km", candidate.get("distance_km", 0))
                    merged["category"] = src.get("category", candidate.get("category", "Restaurant"))
                    merged["quality_score"] = src.get("restaurant_quality_score", candidate.get("quality_score", 0))
                    repaired.append(merged)
                    used.add(name)

            # Fill remaining slots from backend ranking.
            for src in available:
                name = _clean_text(src.get("name")).casefold()
                if name in used:
                    continue
                repaired.append(dict(src))
                used.add(name)
                if len(repaired) >= 3:
                    break

            repaired = repaired[:3]
            for i, rec in enumerate(repaired, 1):
                rec["rank"] = i
                rec["cost"] = _copy_restaurant_cost(rec)
                if not _clean_text(rec.get("reason")) or _clean_text(rec.get("reason")) == "...":
                    rec["reason"] = (
                        f"A practical {meal_type} option near {near}, "
                        "selected using proximity and the available restaurant quality score."
                    )
            section["recommendations"] = repaired
            section["fallback_message"] = ""
            return

    # No matching restaurants. Never invent one.
    section["recommendations"] = []
    section["fallback_message"] = (
        f"No suitable restaurant was identified near {near or 'this attraction'} "
        "in the current travel data."
    )


def _scheduled_activity_names(plan: Dict[str, Any]) -> List[str]:
    names = []
    seen = set()
    for day in _as_list(plan.get("days")):
        if not isinstance(day, dict):
            continue
        for activity in _all_activities(day):
            name = _clean_text(activity.get("place"))
            key = name.casefold()
            if name and key not in seen:
                names.append(name)
                seen.add(key)
    return names


def _build_activity_from_source(
    source: Dict[str, Any],
    travelers: int,
) -> Dict[str, Any]:
    """Create a complete activity when a priority attraction is missing."""
    return {
        "place": _clean_text(source.get("name"), "Tourist Attraction"),
        "category": _clean_text(source.get("category"), "Historical / Tourist Attraction"),
        "why_visit": _clean_text(source.get("why_visit") or source.get("description"),
                                  "Visit this attraction for its heritage and cultural significance."),
        "background": _clean_text(source.get("wikipedia_description") or source.get("description"),
                                  "Detailed historical background is not available in the current travel data."),
        "what_to_see": _clean_text(source.get("description"),
                                    "See the main architectural features and notable points of interest."),
        "travel_note": "Plan a comfortable pace with breaks because the trip preference is less walking.",
        "cost": {
            "type": "entry",
            "amount_per_person": 0,
            "total_for_travelers": 0,
            "min_total": 0,
            "max_total": 0,
            "currency": "INR",
            "label": "Approximate",
            "note": "No verified ticket price was supplied by the current backend data.",
        },
    }


def _force_priority_attractions(
    plan: Dict[str, Any],
    context: Dict[str, Any],
) -> None:
    """Ensure major historical attractions are not merely mentioned as highlights."""
    query = _clean_text(context.get("trip", {}).get("user_query")).casefold()
    places = [p for p in context.get("places", []) if isinstance(p, dict)]
    if not places or not plan.get("days"):
        return

    historical_request = any(word in query for word in ("historical", "history", "fort", "palace", "museum", "heritage"))
    if not historical_request:
        return

    # These are examples of high-priority Hyderabad heritage attractions. Only
    # force one when it is actually present in the backend place data.
    priority_terms = ("golconda fort", "salar jung museum", "charminar", "falaknuma palace")
    scheduled = {n.casefold() for n in _scheduled_activity_names(plan)}

    candidates = []
    for term in priority_terms:
        for place in places:
            name = _clean_text(place.get("name"))
            if term in name.casefold() and name.casefold() not in scheduled:
                candidates.append(place)
                break

    # Add at most two missing major attractions, replacing the lowest-priority
    # final activities so the requested number of days does not change.
    for source in candidates[:2]:
        target_day = None
        target_section = None
        for day in reversed(_as_list(plan.get("days"))):
            if not isinstance(day, dict):
                continue
            for section_name in ("afternoon", "morning"):
                block = day.get(section_name)
                if isinstance(block, dict) and _as_list(block.get("activities")):
                    target_day = day
                    target_section = block
                    break
            if target_day:
                break
        if not target_day:
            continue
        activities = [a for a in _as_list(target_section.get("activities")) if isinstance(a, dict)]
        if activities:
            activities[-1] = _build_activity_from_source(source, _safe_int(context.get("trip", {}).get("travelers"), 2))
            target_section["activities"] = activities
        scheduled.add(_clean_text(source.get("name")).casefold())


def _repair_schedule(plan: Dict[str, Any], dates: List[str]) -> None:
    """Normalize meal/attraction blocks to a non-overlapping practical order."""
    templates = [
        ("09:00", "11:30", "12:00", "13:00", "14:00", "16:00", "16:15", "17:00", "17:30", "19:00", "19:30", "21:00"),
    ]
    for i, day in enumerate(_as_list(plan.get("days"))):
        if not isinstance(day, dict):
            continue
        if i < len(dates):
            day["day"] = i + 1
            day["date"] = dates[i]
        t = templates[0]
        morning = _ensure_dict(day, "morning")
        morning["start_time"], morning["end_time"] = t[0], t[1]
        lunch = _ensure_dict(day, "lunch")
        lunch["start_time"], lunch["end_time"] = t[2], t[3]
        afternoon = _ensure_dict(day, "afternoon")
        afternoon["start_time"], afternoon["end_time"] = t[4], t[5]
        snack = _ensure_dict(day, "evening_snack")
        snack["start_time"], snack["end_time"] = t[6], t[7]
        evening = _ensure_dict(day, "evening")
        evening["start_time"], evening["end_time"] = t[8], t[9]
        dinner = _ensure_dict(day, "dinner")
        dinner["start_time"], dinner["end_time"] = t[10], t[11]


def _repair_budget_math(plan: Dict[str, Any], travelers: int, budget: Optional[float]) -> None:
    totals = {k: [0.0, 0.0] for k in ("attractions", "food", "transportation", "accommodation", "other")}

    for day in _as_list(plan.get("days")):
        if not isinstance(day, dict):
            continue

        attraction_lo = attraction_hi = 0.0
        for activity in _all_activities(day):
            lo, hi = _cost_range(activity.get("cost"))
            attraction_lo += lo
            attraction_hi += hi

        food_lo = food_hi = 0.0
        for key in ("lunch", "evening_snack", "dinner"):
            section = day.get(key)
            if not isinstance(section, dict):
                continue
            recs = [r for r in _as_list(section.get("recommendations")) if isinstance(r, dict)]
            # Only rank 1 is counted. Alternatives are choices, not additional meals.
            if recs:
                lo, hi = _cost_range(recs[0].get("cost"))
                food_lo += lo
                food_hi += hi

        dc = _ensure_dict(day, "day_cost")
        transport_lo = _money(dc.get("transport_min"))
        transport_hi = _money(dc.get("transport_max"))
        accommodation_lo = _money(dc.get("accommodation_min"))
        accommodation_hi = _money(dc.get("accommodation_max"))
        other_lo = _money(dc.get("other_min"))
        other_hi = _money(dc.get("other_max"))

        values = {
            "attractions": (attraction_lo, attraction_hi),
            "food": (food_lo, food_hi),
            "transportation": (transport_lo, transport_hi),
            "accommodation": (accommodation_lo, accommodation_hi),
            "other": (other_lo, other_hi),
        }
        for key, (lo, hi) in values.items():
            totals[key][0] += lo
            totals[key][1] += hi

        dc.update({
            "attractions_min": round(attraction_lo),
            "attractions_max": round(attraction_hi),
            "food_min": round(food_lo),
            "food_max": round(food_hi),
            "transport_min": round(transport_lo),
            "transport_max": round(transport_hi),
            "accommodation_min": round(accommodation_lo),
            "accommodation_max": round(accommodation_hi),
            "other_min": round(other_lo),
            "other_max": round(other_hi),
            "total_min": round(attraction_lo + food_lo + transport_lo + accommodation_lo + other_lo),
            "total_max": round(attraction_hi + food_hi + transport_hi + accommodation_hi + other_hi),
            "currency": "INR",
            "notes": "Food total counts only the best-choice restaurant for each meal; alternatives are not added. Accommodation is not included unless supplied.",
        })

    trip = _ensure_dict(plan, "trip_budget")
    estimated_min = sum(pair[0] for pair in totals.values())
    estimated_max = sum(pair[1] for pair in totals.values())
    trip["travelers"] = travelers
    trip["budget_amount"] = round(budget) if budget is not None else _money(trip.get("budget_amount"))
    trip["currency"] = "INR"

    for key, pair in totals.items():
        trip[key] = {"min": round(pair[0]), "max": round(pair[1])}
    trip["estimated_total"] = {"min": round(estimated_min), "max": round(estimated_max)}

    if budget is not None:
        remaining_min = budget - estimated_max
        remaining_max = budget - estimated_min
        trip["remaining_budget"] = {"min": round(remaining_min), "max": round(remaining_max)}
        if estimated_max <= budget:
            status = "Within Budget"
        elif estimated_min <= budget:
            status = "May Exceed Budget"
        else:
            status = "Over Budget"
        trip["budget_status"] = status
        trip["summary"] = (
            f"Estimated trip cost is ₹{estimated_min:,.0f}-₹{estimated_max:,.0f} "
            f"for {travelers} traveller(s), against a budget of ₹{budget:,.0f}. "
            "Accommodation is not included unless supplied."
        )


def _repair_plan(plan: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    trip = context.get("trip", {})
    travelers = _safe_int(trip.get("travelers"), 2)
    budget = _parse_budget_amount(trip.get("budget"))
    dates = _date_range(_clean_text(trip.get("start_date")), _clean_text(trip.get("end_date")))

    source_places = {
        _clean_text(p.get("name")).casefold(): p
        for p in context.get("places", [])
        if isinstance(p, dict) and _clean_text(p.get("name"))
    }
    restaurant_groups = [
        g for g in _as_list(context.get("restaurants", {}).get("items"))
        if isinstance(g, dict)
    ]

    # Exact number of calendar days. Never allow an extra LLM-created day.
    if dates:
        valid_days = [d for d in _as_list(plan.get("days")) if isinstance(d, dict)]
        plan["days"] = valid_days[:len(dates)]
        while len(plan["days"]) < len(dates):
            plan["days"].append({"day": len(plan["days"]) + 1, "date": dates[len(plan["days"])]})

    _force_priority_attractions(plan, context)
    _repair_schedule(plan, dates)

    for day in _as_list(plan.get("days")):
        if not isinstance(day, dict):
            continue
        for activity in _all_activities(day):
            _repair_activity_content(activity, source_places)

        # Set meal location from the attraction just completed when possible.
        afternoon_activities = _as_list(_ensure_dict(day, "afternoon").get("activities"))
        morning_activities = _as_list(_ensure_dict(day, "morning").get("activities"))
        last_morning = morning_activities[-1].get("place") if morning_activities else ""
        last_afternoon = afternoon_activities[-1].get("place") if afternoon_activities else ""

        lunch = _ensure_dict(day, "lunch")
        if last_morning:
            lunch["near"] = last_morning
        _repair_restaurant_section(lunch, restaurant_groups, "lunch")

        snack = _ensure_dict(day, "evening_snack")
        if last_afternoon:
            snack["near"] = last_afternoon
        elif last_morning:
            snack["near"] = last_morning
        _repair_restaurant_section(snack, restaurant_groups, "evening snack")

        dinner = _ensure_dict(day, "dinner")
        evening_near = _clean_text(_ensure_dict(day, "evening").get("near"))
        if not evening_near:
            evening_near = last_afternoon or last_morning
            dinner["near"] = evening_near
        _repair_restaurant_section(dinner, restaurant_groups, "dinner")

    # Highlights must come from places actually scheduled.
    scheduled = _scheduled_activity_names(plan)
    existing = {
        _clean_text(h.get("title")).casefold(): h
        for h in _as_list(plan.get("highlights"))
        if isinstance(h, dict) and _clean_text(h.get("title"))
    }
    highlights = []
    for name in scheduled[:5]:
        item = existing.get(name.casefold(), {})
        source = source_places.get(name.casefold(), {})
        highlights.append({
            "title": name,
            "description": _clean_text(
                item.get("description")
                or source.get("why_visit")
                or source.get("description")
                or "A selected attraction in the itinerary."
            ),
        })
    plan["highlights"] = highlights

    # Keep important places aligned with scheduled attractions.
    important = []
    for name in scheduled:
        source = source_places.get(name.casefold(), {})
        activity = next(
            (a for d in _as_list(plan.get("days")) for a in _all_activities(d)
             if _clean_text(a.get("place")).casefold() == name.casefold()),
            {},
        )
        important.append({
            "name": name,
            "background": _clean_text(activity.get("background") or source.get("wikipedia_description") or source.get("description")),
            "why_visit": _clean_text(activity.get("why_visit") or source.get("why_visit") or source.get("description")),
            "what_to_see": _clean_text(activity.get("what_to_see") or source.get("description")),
        })
    plan["important_places"] = important

    _repair_budget_math(plan, travelers, budget)
    return plan



# ============================================================
# LEGACY / ALTERNATE LLM SCHEMA NORMALIZATION
# ============================================================

def _normalize_legacy_day(day: Dict[str, Any], day_number: int) -> Dict[str, Any]:
    """Convert older LLM day schemas into the canonical frontend schema."""
    if not isinstance(day, dict):
        return {"day": day_number, "date": ""}

    # Canonical schema is already present only when its activity/recommendation
    # lists are actually present. Older responses sometimes used the same
    # section names but stored a single nested `attraction` object.
    if (
        isinstance(day.get("morning"), dict)
        and isinstance(day.get("afternoon"), dict)
        and isinstance(day.get("morning", {}).get("activities"), list)
        and isinstance(day.get("afternoon", {}).get("activities"), list)
    ):
        return day

    normalized: Dict[str, Any] = {
        "day": day_number,
        "date": _clean_text(day.get("date")),
        "weather_note": _clean_text(day.get("weather_note")),
        "morning": {"start_time": "09:00", "end_time": "11:30", "activities": []},
        "lunch": {"start_time": "12:00", "end_time": "13:00", "near": "", "recommendations": [], "fallback_message": ""},
        "afternoon": {"start_time": "14:00", "end_time": "17:00", "activities": []},
        "evening": {"start_time": "17:30", "end_time": "19:00", "activity": "", "near": ""},
        "evening_snack": {"start_time": "19:00", "end_time": "19:30", "near": "", "recommendations": [], "fallback_message": ""},
        "dinner": {"start_time": "19:30", "end_time": "21:00", "near": "", "recommendations": [], "fallback_message": ""},
        "day_cost": dict(day.get("day_cost") or {}),
        "day_tip": _clean_text(day.get("day_tip")),
    }

    attractions = [a for a in _as_list(day.get("attractions")) if isinstance(a, dict)]
    if not attractions:
        # Some earlier responses used a single attraction object inside each period.
        for section_name in ("morning", "afternoon", "evening"):
            section = day.get(section_name)
            if isinstance(section, dict) and isinstance(section.get("attraction"), dict):
                attractions.append(section["attraction"])

    midpoint = (len(attractions) + 1) // 2
    for index, attraction in enumerate(attractions):
        activity = dict(attraction)
        if "place" not in activity and attraction.get("name"):
            activity["place"] = attraction.get("name")
        if "cost" not in activity:
            activity["cost"] = attraction.get("ticket") or attraction.get("entry_cost") or {}
        target = normalized["morning"] if index < midpoint else normalized["afternoon"]
        target["activities"].append(activity)

    meals = [m for m in _as_list(day.get("meals")) if isinstance(m, dict)]
    for meal in meals:
        meal_type = _clean_text(meal.get("meal_type") or meal.get("type") or meal.get("name")).casefold()
        section = normalized["lunch"]
        if "dinner" in meal_type:
            section = normalized["dinner"]
        elif "snack" in meal_type or "evening" in meal_type:
            section = normalized["evening_snack"]

        name = _clean_text(meal.get("restaurant_name") or meal.get("restaurant"))
        if name and name.casefold() not in {"no restaurant data available", "restaurant"}:
            section["recommendations"].append({
                "rank": 1,
                "name": name,
                "distance_km": _safe_float(meal.get("distance_km") or meal.get("distance_from_attraction"), 0),
                "category": _clean_text(meal.get("category"), "Restaurant"),
                "quality_score": _safe_float(meal.get("quality_score"), 0),
                "reason": _clean_text(meal.get("reason_for_recommendation") or meal.get("reason")),
                "cost": meal.get("cost") or meal.get("approximate_cost") or {},
            })
        near = _clean_text(meal.get("near") or meal.get("attraction") or meal.get("near_attraction"))
        if near:
            section["near"] = near

    # A few historical outputs used one nested morning/afternoon attraction object.
    for section_name in ("morning", "afternoon"):
        source_section = day.get(section_name)
        if not isinstance(source_section, dict):
            continue
        attraction = source_section.get("attraction")
        if isinstance(attraction, dict):
            normalized[section_name]["activities"].append(attraction)
        if source_section.get("start_time"):
            normalized[section_name]["start_time"] = source_section["start_time"]
        if source_section.get("end_time"):
            normalized[section_name]["end_time"] = source_section["end_time"]

    # Determine meal locations from the last completed attraction.
    morning_activities = normalized["morning"]["activities"]
    afternoon_activities = normalized["afternoon"]["activities"]
    if morning_activities and not normalized["lunch"].get("near"):
        normalized["lunch"]["near"] = _clean_text(morning_activities[-1].get("place"))
    if afternoon_activities:
        near = _clean_text(afternoon_activities[-1].get("place"))
        if not normalized["evening_snack"].get("near"):
            normalized["evening_snack"]["near"] = near
        if not normalized["dinner"].get("near"):
            normalized["dinner"]["near"] = near
        normalized["evening"]["near"] = normalized["evening"].get("near") or near

    return normalized


def _normalize_llm_plan_schema(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize known historical LLM response shapes before validation/repair."""
    if not isinstance(plan, dict):
        return plan

    days = _as_list(plan.get("days"))
    if days:
        plan["days"] = [_normalize_legacy_day(day, index + 1) for index, day in enumerate(days)]

    # Historical trip summary fields are preserved but canonical fields are supplied.
    summary = _ensure_dict(plan, "trip_summary")
    if "budget" not in summary and plan.get("trip_budget", {}).get("budget_amount") is not None:
        summary["budget"] = plan["trip_budget"].get("budget_amount")

    return plan

# ============================================================
# NVIDIA TRAVEL-PLAN REQUEST
# ============================================================

def _request_travel_plan_from_nvidia(
    client: OpenAI,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Request the final JSON travel plan from NVIDIA NIM.

    GPT-OSS is a reasoning model. The previous implementation allowed an
    oversized 14,000-token completion, which is above NVIDIA's documented
    Chat Completions limit for this endpoint and can also spend too much time
    in reasoning before producing the JSON payload. Keep reasoning low and
    bound the completion so the application does not appear to hang.
    """

    user_prompt = _build_user_prompt(context)

    response = client.chat.completions.create(
        model=NVIDIA_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.2,
        reasoning_effort="low",
        max_tokens=4096,
        response_format={"type": "json_object"},
        stream=False,
    )

    if not response.choices:
        raise RuntimeError("NVIDIA returned no choices in the response.")

    message = response.choices[0].message
    content = getattr(message, "content", None)

    # GPT-OSS exposes reasoning separately. Never treat reasoning text as the
    # final travel plan, but report it when the model produced no answer.
    if not content or not str(content).strip():
        reasoning = getattr(message, "reasoning_content", None)
        if reasoning:
            raise RuntimeError(
                "NVIDIA returned reasoning content but no final JSON content. "
                "The completion limit was reached before the final answer."
            )
        raise RuntimeError("NVIDIA returned an empty final response.")

    return _extract_json(str(content))


# ============================================================
# GENERATE STRUCTURED TRAVEL PLAN
# ============================================================

def generate_travel_plan(
    destination: str,
    start_date: str,
    end_date: str,
    places: List[Dict[str, Any]],
    route: Optional[Dict[str, Any]] = None,
    weather: Optional[Dict[str, Any]] = None,
    itinerary: Optional[Dict[str, Any]] = None,
    restaurants: Optional[Dict[str, Any]] = None,
    user_query: str = "",
    travelers: Optional[int] = None,
    budget: Optional[str] = None,
    preferences: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate the final structured AI travel plan."""

    context = build_llm_context(
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        places=places,
        route=route,
        weather=weather,
        itinerary=itinerary,
        restaurants=restaurants,
        user_query=user_query,
        travelers=travelers,
        budget=budget,
        preferences=preferences,
    )

    client = get_nvidia_client()

    plan = _request_travel_plan_from_nvidia(
        client=client,
        context=context,
    )

    # NVIDIA responses seen in earlier project runs used a different
    # attractions/meals schema. Normalize it before validation so the
    # frontend always receives the canonical structure.
    plan = _normalize_llm_plan_schema(plan)
    plan = _validate_travel_plan(plan)
    return _repair_plan(plan, context)


# ============================================================
# BACKWARD-COMPATIBLE FUNCTION
# ============================================================

def generate_travel_recommendation(
    destination: str,
    start_date: str,
    end_date: str,
    places: List[Dict[str, Any]],
    route: Optional[Dict[str, Any]] = None,
    weather: Optional[Dict[str, Any]] = None,
    itinerary: Optional[Dict[str, Any]] = None,
    restaurants: Optional[Dict[str, Any]] = None,
    user_query: str = "",
    travelers: Optional[int] = None,
    budget: Optional[str] = None,
    preferences: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Backward-compatible wrapper.

    Existing travel_pipeline.py can continue to call this function.
    """

    return generate_travel_plan(
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        places=places,
        route=route,
        weather=weather,
        itinerary=itinerary,
        restaurants=restaurants,
        user_query=user_query,
        travelers=travelers,
        budget=budget,
        preferences=preferences,
    )
