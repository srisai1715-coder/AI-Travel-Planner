"""
LLM Service
Uses Groq with an OpenAI-compatible API.

Responsibilities:
1. Load Groq API configuration.
2. Test Groq connection.
3. Send compact, grounded travel data to the LLM within TPM limits.
4. Generate a structured AI travel plan.
5. Include nearby restaurants inside the relevant itinerary day.
6. Include attraction, meal, daily, and complete-trip budget estimates.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)

GROQ_BASE_URL = os.getenv(
    "GROQ_BASE_URL",
    "https://api.groq.com/openai/v1",
)


# ============================================================
# GROQ CLIENT
# ============================================================

def get_groq_client() -> OpenAI:
    """Create and return the Groq OpenAI-compatible client."""

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. "
            "Check your .env file."
        )

    return OpenAI(
        base_url=GROQ_BASE_URL,
        api_key=GROQ_API_KEY,
        timeout=120.0,
        max_retries=1,
    )


# ============================================================
# CONNECTION TEST
# ============================================================

def test_groq_connection() -> str:
    """Test the Groq LLM connection."""

    client = get_groq_client()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
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


def _truncate_text(
    value: Any,
    max_chars: int = 240,
    default: str = "",
) -> str:
    text = _clean_text(value, default)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


# ============================================================
# RESTAURANT PREPARATION
# ============================================================

def _prepare_restaurant(
    restaurant: Dict[str, Any],
) -> Dict[str, Any]:
    """Prepare one restaurant concisely for the LLM."""
    cuisine = restaurant.get("cuisine", restaurant.get("cuisines", []))
    if isinstance(cuisine, list):
        cuisine = cuisine[:3]

    return {
        "name": _clean_text(restaurant.get("name"), "Restaurant"),
        "category": _clean_text(restaurant.get("category"), "Restaurant"),
        "distance_km": round(_safe_float(restaurant.get("distance_km"), 0), 2),
        "quality_score": round(_safe_float(restaurant.get("restaurant_quality_score"), 0), 2),
        "cuisine": cuisine,
    }


def _prepare_restaurant_group(
    group: Dict[str, Any],
    max_restaurants: int = 3,
) -> Dict[str, Any]:
    """Prepare restaurants grouped around a specific attraction."""
    restaurants = [
        _prepare_restaurant(item)
        for item in _as_list(group.get("restaurants", []))
        if isinstance(item, dict)
    ][:max_restaurants]

    return {
        "place_name": _clean_text(group.get("place_name"), "Unknown attraction"),
        "restaurants": restaurants,
    }


# ============================================================
# PLACE PREPARATION
# ============================================================

def _prepare_place(
    place: Dict[str, Any],
) -> Dict[str, Any]:
    """Prepare tourist-place information concisely for the LLM."""
    history_or_desc = _truncate_text(
        place.get("wikipedia_description") or place.get("description"),
        max_chars=240,
    )
    return {
        "name": _clean_text(place.get("name"), "Unnamed place"),
        "category": _clean_text(place.get("category"), "Tourist Attraction"),
        "distance_km": round(_safe_float(place.get("distance_km"), 0), 2),
        "quality_score": round(_safe_float(place.get("tourist_quality_score"), 0), 2),
        "why_visit": _truncate_text(place.get("why_visit"), max_chars=160),
        "info": history_or_desc,
    }


# ============================================================
# WEATHER PREPARATION
# ============================================================

def _prepare_weather(
    weather: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not weather:
        return {}

    daily = weather.get("daily", {})
    dates = _as_list(daily.get("time", []))
    max_temps = _as_list(daily.get("temperature_2m_max", []))
    min_temps = _as_list(daily.get("temperature_2m_min", []))
    rain_probs = _as_list(daily.get("precipitation_probability_max", []))

    compact_daily = []
    for index, trip_date in enumerate(dates):
        compact_daily.append({
            "date": trip_date,
            "max_c": max_temps[index] if index < len(max_temps) else None,
            "min_c": min_temps[index] if index < len(min_temps) else None,
            "rain_pct": rain_probs[index] if index < len(rain_probs) else None,
        })

    return {"daily": compact_daily}


# ============================================================
# ROUTE PREPARATION
# ============================================================

def _prepare_route(
    route: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not route:
        return {}

    places = []
    for place in _as_list(route.get("places", []))[:8]:
        if isinstance(place, dict):
            places.append({
                "order": place.get("route_order"),
                "name": _clean_text(place.get("name")),
                "km_from_prev": round(_safe_float(place.get("distance_from_previous_km"), 0), 2),
            })

    return {
        "total_distance_km": round(_safe_float(route.get("total_distance_km"), 0), 2),
        "places": places,
    }


# ============================================================
# ITINERARY PREPARATION
# ============================================================

def _prepare_itinerary(
    itinerary: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not itinerary:
        return {}

    days = []
    for day in _as_list(itinerary.get("days", [])):
        if not isinstance(day, dict):
            continue
        place_names = [
            _clean_text(p.get("name"))
            for p in _as_list(day.get("places", []))
            if isinstance(p, dict) and _clean_text(p.get("name"))
        ]
        days.append({
            "day": day.get("day"),
            "date": day.get("date"),
            "places": place_names,
        })

    return {"days": days}


# ============================================================
# RESTAURANTS COLLECTION PREPARATION
# ============================================================

def _prepare_restaurants(
    restaurants: Optional[Dict[str, Any]],
    max_groups: int = 6,
) -> Dict[str, Any]:
    if not restaurants:
        return {"items": []}

    prepared_items = []
    for item in _as_list(restaurants.get("items", [])):
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("restaurants"), list):
            group = _prepare_restaurant_group(item, max_restaurants=3)
            if group["restaurants"]:
                prepared_items.append(group)
        elif item.get("name"):
            prepared_items.append(_prepare_restaurant(item))

    return {"items": prepared_items[:max_groups]}


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

    compact_places = [
        _prepare_place(place)
        for place in places
        if isinstance(place, dict)
    ][:6]

    return {
        "trip": {
            "destination": destination,
            "start_date": start_date,
            "end_date": end_date,
            "trip_days": _calculate_trip_days(start_date, end_date),
            "travelers": travelers,
            "budget": budget,
            "preferences": _truncate_text(preferences, 200),
            "user_query": _truncate_text(user_query, 300),
        },
        "places": compact_places,
        "route": _prepare_route(route),
        "weather": _prepare_weather(weather),
        "itinerary": _prepare_itinerary(itinerary),
        "restaurants": _prepare_restaurants(restaurants, max_groups=6),
    }


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an expert AI travel planner and travel-budget analyst.
Create a complete, personalized travel plan in valid JSON only (no Markdown, no code fences, no commentary).

Rules:
1. Dates & Days: Create EXACTLY one day object per calendar date from start_date through end_date inclusive. Never add extra days or invent dates.
2. Attractions: Use supplied places/itinerary and respect user preferences/query. Every activity must include place, category, why_visit (2-3 sentences), background (2-4 sentences of history/context), what_to_see, travel_note, and cost object. Never use "..." as placeholder text.
3. Restaurants: For lunch, evening_snack, and dinner, pick ONLY from the restaurant group matching the attraction just completed ("near": "<attraction>"). Give 1 best choice + up to 2 alternatives. If none exist in that group, set recommendations to [] and explain in fallback_message.
4. Budget: Provide approximate planning estimates labeled "Approximate" (never claim unverified prices are official/verified). Include costs for all travelers. Accommodation is excluded/not included unless supplied. Keep daily and trip totals mathematically consistent. Budget status is "Within Budget" (max <= budget), "May Exceed Budget" (min <= budget < max), or "Over Budget" (min > budget).
5. Weather: Mention weather only when it shifts outdoor/indoor timing or packing.

JSON Schema:
{
  "title": "AI Travel Plan",
  "trip_overview": "2-4 sentence overview",
  "trip_summary": {"destination":"","start_date":"","end_date":"","travelers":2,"budget":"","preferences":""},
  "highlights": [{"title":"","description":""}],
  "days": [
    {
      "day": 1,
      "date": "YYYY-MM-DD",
      "weather_note": "",
      "morning": {"start_time":"09:00","end_time":"11:30","activities":[{"place":"","category":"","why_visit":"","background":"","what_to_see":"","travel_note":"","cost":{"type":"entry","amount_per_person":0,"total_for_travelers":0,"min_total":0,"max_total":0,"currency":"INR","label":"Approximate","note":""}}]},
      "lunch": {"start_time":"12:00","end_time":"13:00","near":"","recommendations":[{"rank":1,"name":"","distance_km":0,"category":"","quality_score":0,"reason":"","cost":{"min_total":0,"max_total":0,"currency":"INR","label":"Approximate","note":""}}],"fallback_message":""},
      "afternoon": {"start_time":"14:00","end_time":"16:00","activities":[]},
      "evening": {"start_time":"17:30","end_time":"19:00","activity":"","near":""},
      "evening_snack": {"start_time":"16:15","end_time":"17:00","near":"","recommendations":[],"fallback_message":""},
      "dinner": {"start_time":"19:30","end_time":"21:00","near":"","recommendations":[],"fallback_message":""},
      "day_cost": {"attractions_min":0,"attractions_max":0,"food_min":0,"food_max":0,"transport_min":0,"transport_max":0,"accommodation_min":0,"accommodation_max":0,"other_min":0,"other_max":0,"total_min":0,"total_max":0,"currency":"INR","notes":""},
      "day_tip": ""
    }
  ],
  "trip_budget": {"travelers":2,"budget_amount":10000,"currency":"INR","attractions":{"min":0,"max":0},"food":{"min":0,"max":0},"transportation":{"min":0,"max":0},"accommodation":{"min":0,"max":0},"other":{"min":0,"max":0},"estimated_total":{"min":0,"max":0},"remaining_budget":{"min":0,"max":0},"budget_status":"Within Budget","summary":""},
  "important_places": [{"name":"","background":"","why_visit":"","what_to_see":""}],
  "travel_tips": [""]
}
""".strip()


# ============================================================
# USER PROMPT BUILDER
# ============================================================

def _build_user_prompt(
    context: Dict[str, Any],
) -> str:
    """Convert compact backend context into a focused prompt."""
    trip = context.get("trip", {})
    compact_json = json.dumps(context, ensure_ascii=False, separators=(",", ":"))

    return (
        f"Generate the complete JSON travel plan from {trip.get('start_date')} to "
        f"{trip.get('end_date')} ({trip.get('trip_days')} days). "
        f"Honor user query/preferences strictly, use only matching attraction restaurant groups, "
        f"include approximate INR costs for all travelers, and return valid JSON only.\n"
        f"DATA:{compact_json}"
    )


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
    if isinstance(cost, dict):
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

        recommendation.setdefault("rank", index + 1)
        recommendation.setdefault("name", "Restaurant")
        recommendation.setdefault("distance_km", 0)
        recommendation.setdefault("category", "Restaurant")
        recommendation.setdefault("quality_score", 0)
        recommendation.setdefault("reason", "")
        recommendation["cost"] = _validate_cost(recommendation.get("cost"))

    section.setdefault("fallback_message", "")


def _validate_activity(
    activity: Dict[str, Any],
) -> None:

    activity.setdefault("place", "Unnamed place")
    activity.setdefault("category", "Tourist Attraction")
    activity.setdefault("why_visit", "")
    activity.setdefault("background", "")
    activity.setdefault("what_to_see", "")
    activity.setdefault("travel_note", "")
    activity["cost"] = _validate_cost(activity.get("cost"))


# ============================================================
# RESPONSE VALIDATION
# ============================================================

def _validate_travel_plan(
    plan: Dict[str, Any],
) -> Dict[str, Any]:
    """Ensure the structured travel plan contains required fields."""

    if not isinstance(plan, dict):
        raise ValueError("Travel plan must be a dictionary.")

    plan.setdefault("title", "AI Travel Plan")
    plan.setdefault("trip_overview", "")
    plan.setdefault("trip_summary", {})
    plan.setdefault("highlights", [])
    plan.setdefault("days", [])
    plan.setdefault("trip_budget", {})
    plan.setdefault("important_places", [])
    plan.setdefault("travel_tips", [])

    if not isinstance(plan["trip_summary"], dict):
        plan["trip_summary"] = {}
    if not isinstance(plan["highlights"], list):
        plan["highlights"] = []
    if not isinstance(plan["days"], list):
        plan["days"] = []
    if not isinstance(plan["important_places"], list):
        plan["important_places"] = []
    if not isinstance(plan["travel_tips"], list):
        plan["travel_tips"] = []

    trip_budget = _ensure_dict(plan, "trip_budget")
    trip_budget.setdefault("travelers", plan["trip_summary"].get("travelers"))
    trip_budget.setdefault("budget_amount", 0)
    trip_budget.setdefault("currency", "INR")

    for category in (
        "attractions",
        "food",
        "transportation",
        "accommodation",
        "other",
        "estimated_total",
        "remaining_budget",
    ):
        category_data = _ensure_dict(trip_budget, category)
        category_data.setdefault("min", 0)
        category_data.setdefault("max", 0)

    trip_budget.setdefault("budget_status", "Unknown")
    trip_budget.setdefault("summary", "")

    for day_index, day in enumerate(plan["days"]):
        if not isinstance(day, dict):
            plan["days"][day_index] = {
                "day": day_index + 1,
                "date": "",
                "weather_note": "",
                "morning": {"start_time": "", "end_time": "", "activities": []},
                "lunch": {"start_time": "", "end_time": "", "near": "", "recommendations": [], "fallback_message": ""},
                "afternoon": {"start_time": "", "end_time": "", "activities": []},
                "evening": {"start_time": "", "end_time": "", "activity": "", "near": ""},
                "evening_snack": {"start_time": "", "end_time": "", "near": "", "recommendations": [], "fallback_message": ""},
                "dinner": {"start_time": "", "end_time": "", "near": "", "recommendations": [], "fallback_message": ""},
                "day_cost": {
                    "attractions_min": 0, "attractions_max": 0,
                    "food_min": 0, "food_max": 0,
                    "transport_min": 0, "transport_max": 0,
                    "accommodation_min": 0, "accommodation_max": 0,
                    "other_min": 0, "other_max": 0,
                    "total_min": 0, "total_max": 0,
                    "currency": "INR", "notes": "",
                },
                "day_tip": "",
            }
            continue

        day.setdefault("day", day_index + 1)
        day.setdefault("date", "")
        day.setdefault("weather_note", "")

        morning = _ensure_dict(day, "morning")
        morning.setdefault("start_time", "")
        morning.setdefault("end_time", "")
        for activity in _ensure_list(morning, "activities"):
            if isinstance(activity, dict):
                _validate_activity(activity)

        lunch = _ensure_dict(day, "lunch")
        lunch.setdefault("start_time", "")
        lunch.setdefault("end_time", "")
        lunch.setdefault("near", "")
        _validate_restaurant_recommendations(lunch)

        afternoon = _ensure_dict(day, "afternoon")
        afternoon.setdefault("start_time", "")
        afternoon.setdefault("end_time", "")
        for activity in _ensure_list(afternoon, "activities"):
            if isinstance(activity, dict):
                _validate_activity(activity)

        evening = _ensure_dict(day, "evening")
        evening.setdefault("start_time", "")
        evening.setdefault("end_time", "")
        evening.setdefault("activity", "")
        evening.setdefault("near", "")

        evening_snack = _ensure_dict(day, "evening_snack")
        evening_snack.setdefault("start_time", "")
        evening_snack.setdefault("end_time", "")
        evening_snack.setdefault("near", "")
        _validate_restaurant_recommendations(evening_snack)

        dinner = _ensure_dict(day, "dinner")
        dinner.setdefault("start_time", "")
        dinner.setdefault("end_time", "")
        dinner.setdefault("near", "")
        _validate_restaurant_recommendations(dinner)

        day_cost = _ensure_dict(day, "day_cost")
        for key in (
            "attractions_min", "attractions_max",
            "food_min", "food_max",
            "transport_min", "transport_max",
            "accommodation_min", "accommodation_max",
            "other_min", "other_max",
            "total_min", "total_max",
        ):
            day_cost.setdefault(key, 0)
        day_cost.setdefault("currency", "INR")
        day_cost.setdefault("notes", "")
        day.setdefault("day_tip", "")

    return plan


# ============================================================
# DETERMINISTIC BUDGET + CONTENT REPAIR
# ============================================================

def _parse_budget_amount(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
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

    cost = _validate_cost(activity.get("cost"))
    label = _clean_text(cost.get("label"), "Approximate").casefold()
    note = _clean_text(cost.get("note"))
    if "verified" in label or "confirmed" in note.casefold() or not note:
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
        "why_visit": _clean_text(
            source.get("why_visit") or source.get("description"),
            "Visit this attraction for its heritage and cultural significance.",
        ),
        "background": _clean_text(
            source.get("wikipedia_description") or source.get("description"),
            "Detailed historical background is not available in the current travel data.",
        ),
        "what_to_see": _clean_text(
            source.get("description"),
            "See the main architectural features and notable points of interest.",
        ),
        "travel_note": "Plan a comfortable pace with breaks as needed.",
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
    """Ensure major historical attractions are scheduled when requested."""
    query = _clean_text(context.get("trip", {}).get("user_query")).casefold()
    places = [p for p in context.get("places", []) if isinstance(p, dict)]
    if not places or not plan.get("days"):
        return

    historical_request = any(
        word in query for word in ("historical", "history", "fort", "palace", "museum", "heritage")
    )
    if not historical_request:
        return

    priority_terms = ("golconda fort", "salar jung museum", "charminar", "falaknuma palace")
    scheduled = {n.casefold() for n in _scheduled_activity_names(plan)}

    candidates = []
    for term in priority_terms:
        for place in places:
            name = _clean_text(place.get("name"))
            if term in name.casefold() and name.casefold() not in scheduled:
                candidates.append(place)
                break

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
            activities[-1] = _build_activity_from_source(
                source, _safe_int(context.get("trip", {}).get("travelers"), 2)
            )
            target_section["activities"] = activities
        scheduled.add(_clean_text(source.get("name")).casefold())


def _repair_schedule(plan: Dict[str, Any], dates: List[str]) -> None:
    """Normalize meal/attraction blocks to a non-overlapping practical order."""
    t = ("09:00", "11:30", "12:00", "13:00", "14:00", "16:00", "16:15", "17:00", "17:30", "19:00", "19:30", "21:00")
    for i, day in enumerate(_as_list(plan.get("days"))):
        if not isinstance(day, dict):
            continue
        if i < len(dates):
            day["day"] = i + 1
            day["date"] = dates[i]
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
                or source.get("info")
                or "A selected attraction in the itinerary."
            ),
        })
    plan["highlights"] = highlights

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
            "background": _clean_text(activity.get("background") or source.get("info")),
            "why_visit": _clean_text(activity.get("why_visit") or source.get("why_visit") or source.get("info")),
            "what_to_see": _clean_text(activity.get("what_to_see") or source.get("info")),
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

    summary = _ensure_dict(plan, "trip_summary")
    if "budget" not in summary and plan.get("trip_budget", {}).get("budget_amount") is not None:
        summary["budget"] = plan["trip_budget"].get("budget_amount")

    return plan


# ============================================================
# GROQ TRAVEL-PLAN REQUEST
# ============================================================

def _request_travel_plan_from_groq(
    client: OpenAI,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Request the final JSON travel plan from Groq within TPM limits."""

    user_prompt = _build_user_prompt(context)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
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
        max_tokens=3500,
        response_format={"type": "json_object"},
        stream=False,
    )

    if not response.choices:
        raise RuntimeError("Groq returned no choices in the response.")

    message = response.choices[0].message
    content = getattr(message, "content", None)

    if not content or not str(content).strip():
        reasoning = getattr(message, "reasoning_content", None)
        if reasoning:
            raise RuntimeError(
                "Groq returned reasoning content but no final JSON content. "
                "The completion limit was reached before the final answer."
            )
        raise RuntimeError("Groq returned an empty final response.")

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

    client = get_groq_client()

    plan = _request_travel_plan_from_groq(
        client=client,
        context=context,
    )

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