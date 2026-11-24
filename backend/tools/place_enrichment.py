import re
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import requests


WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"

HEADERS = {
    "User-Agent": "AI-Travel-Planner/2.0 (contact: srisai1715@gmail.com)",
    "Accept": "application/json",
}

CACHE_TTL_SECONDS = 3600

_SEARCH_CACHE: Dict[Tuple[str, str], Tuple[float, List[Dict[str, Any]]]] = {}
_PAGE_CACHE: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}


# ============================================================
# TEXT NORMALIZATION & SIMILARITY
# ============================================================

def normalize_text(text: Any) -> str:
    if not text:
        return ""

    value = str(text).lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def get_tokens(text: Any) -> set:
    normalized = normalize_text(text)
    if not normalized:
        return set()

    return {
        token
        for token in normalized.split()
        if len(token) > 1
    }


def calculate_name_similarity(
    place_name: str,
    wikipedia_title: str,
) -> float:
    place = normalize_text(place_name)
    title = normalize_text(wikipedia_title)

    if not place or not title:
        return 0.0

    if place == title:
        return 1.0

    place_tokens = get_tokens(place)
    title_tokens = get_tokens(title)

    if not place_tokens or not title_tokens:
        return 0.0

    common_tokens = place_tokens & title_tokens
    token_coverage = len(common_tokens) / len(place_tokens)
    sequence_score = SequenceMatcher(None, place, title).ratio()

    return max(token_coverage, sequence_score)


# ============================================================
# SEARCH & FETCH WIKIPEDIA (WITH CACHE & RATE-LIMIT GUARD)
# ============================================================

def search_wikipedia(
    place_name: str,
    city: str,
    rate_limited_flag: Optional[List[bool]] = None,
) -> List[Dict[str, Any]]:
    """
    Search Wikipedia using conservative queries with caching.
    Stops immediately if Wikipedia rate-limits (HTTP 429).
    """
    if rate_limited_flag and rate_limited_flag[0]:
        return []

    cache_key = (normalize_text(place_name), normalize_text(city))
    now = time.time()
    cached = _SEARCH_CACHE.get(cache_key)
    if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
        return [dict(item) for item in cached[1]]

    queries: List[str] = []
    if city:
        queries.append(f'"{place_name}" "{city}"')
    queries.append(f'"{place_name}"')

    for query in queries:
        try:
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srlimit": 5,
            }

            response = requests.get(
                WIKIPEDIA_API_URL,
                params=params,
                headers=HEADERS,
                timeout=8,
            )

            if response.status_code == 429:
                print("Wikipedia rate limited. Skipping remaining Wikipedia lookups for this request.")
                if rate_limited_flag is not None:
                    rate_limited_flag[0] = True
                return []

            response.raise_for_status()
            data = response.json()
            results = data.get("query", {}).get("search", [])

            if results:
                _SEARCH_CACHE[cache_key] = (now, [dict(item) for item in results])
                return results

        except requests.RequestException as error:
            print("Wikipedia search failed:", error)
            return []
        except Exception as error:
            print("Wikipedia processing failed:", error)
            return []

    _SEARCH_CACHE[cache_key] = (now, [])
    return []


def get_wikipedia_page(
    title: str,
    rate_limited_flag: Optional[List[bool]] = None,
) -> Optional[Dict[str, Any]]:
    if rate_limited_flag and rate_limited_flag[0]:
        return None

    cache_key = normalize_text(title)
    now = time.time()
    cached = _PAGE_CACHE.get(cache_key)
    if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
        return dict(cached[1]) if cached[1] else None

    try:
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts|info",
            "exintro": True,
            "explaintext": True,
            "inprop": "url",
            "redirects": 1,
            "titles": title,
        }

        response = requests.get(
            WIKIPEDIA_API_URL,
            params=params,
            headers=HEADERS,
            timeout=8,
        )

        if response.status_code == 429:
            print("Wikipedia rate limited while retrieving page.")
            if rate_limited_flag is not None:
                rate_limited_flag[0] = True
            return None

        response.raise_for_status()
        data = response.json()
        pages = data.get("query", {}).get("pages", {})

        if not pages:
            _PAGE_CACHE[cache_key] = (now, None)
            return None

        page = next(iter(pages.values()))
        if page.get("missing") is not None:
            _PAGE_CACHE[cache_key] = (now, None)
            return None

        result = {
            "title": page.get("title", ""),
            "description": page.get("extract", ""),
            "url": page.get("fullurl", ""),
        }
        _PAGE_CACHE[cache_key] = (now, result)
        return dict(result)

    except requests.RequestException as error:
        print("Wikipedia page request failed:", error)
        return None
    except Exception as error:
        print("Wikipedia processing failed:", error)
        return None


# ============================================================
# VALIDATE WIKIPEDIA MATCH
# ============================================================

def validate_wikipedia_match(
    place_name: str,
    result: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not result:
        return None

    title = result.get("title", "")
    description = result.get("description", "")
    url = result.get("url", "")

    if not title:
        return None

    name_score = calculate_name_similarity(place_name, title)
    if name_score < 0.85:
        return None

    return {
        "title": title,
        "description": description,
        "url": url,
        "match_score": round(name_score, 2),
        "location_match": False,
    }


# ============================================================
# FALLBACK DESCRIPTION & WHY VISIT
# ============================================================

def create_why_visit(
    place: Dict[str, Any],
    city: str = "",
) -> str:
    name = str(place.get("name") or "This place").strip()
    category = str(place.get("category") or "Tourist Attraction").strip()
    distance = place.get("distance_km")
    existing_desc = str(place.get("description") or "").strip()

    if existing_desc:
        return existing_desc

    location_part = f" in {city}" if city else ""
    if distance is not None:
        try:
            dist_val = float(distance)
            return (
                f"{name} is a {category.lower()} located approximately "
                f"{dist_val:.2f} km from the selected point{location_part}."
            )
        except (TypeError, ValueError):
            pass

    return f"{name} is a {category.lower()} near the selected destination{location_part}."


# ============================================================
# ENRICH SINGLE PLACE
# ============================================================

def enrich_place(
    place: Dict[str, Any],
    city: str,
    rate_limited_flag: Optional[List[bool]] = None,
) -> Dict[str, Any]:
    enriched = dict(place)
    place_name = str(place.get("name") or "").strip()

    enriched["wikipedia_title"] = ""
    enriched["wikipedia_description"] = ""
    enriched["wikipedia_url"] = ""
    enriched["wikipedia_match_score"] = 0.0
    enriched["wikipedia_location_match"] = False

    search_results = search_wikipedia(
        place_name,
        city,
        rate_limited_flag=rate_limited_flag,
    )

    best_match: Optional[Dict[str, Any]] = None

    for search_result in search_results:
        title = search_result.get("title", "")
        if not title:
            continue

        quick_score = calculate_name_similarity(place_name, title)
        if quick_score < 0.85:
            continue

        page = get_wikipedia_page(title, rate_limited_flag=rate_limited_flag)
        if not page:
            continue

        validated = validate_wikipedia_match(place_name, page)
        if validated is None:
            continue

        if best_match is None or validated["match_score"] > best_match["match_score"]:
            best_match = validated

        if validated["match_score"] >= 0.95:
            break

    if best_match:
        enriched["wikipedia_title"] = best_match["title"]
        enriched["wikipedia_description"] = best_match["description"]
        enriched["wikipedia_url"] = best_match["url"]
        enriched["wikipedia_match_score"] = best_match["match_score"]
        enriched["wikipedia_location_match"] = False
        enriched["why_visit"] = best_match["description"] or create_why_visit(place, city)
    else:
        enriched["why_visit"] = create_why_visit(place, city)

    if not str(enriched.get("description") or "").strip():
        enriched["description"] = enriched["why_visit"]

    return enriched


# ============================================================
# ENRICH MULTIPLE PLACES
# ============================================================

def enrich_places(
    places: List[Dict[str, Any]],
    location_name: str,
    max_places: int = 10,
) -> List[Dict[str, Any]]:
    if not places:
        return []

    selected_places = places[:max_places]
    enriched_places: List[Dict[str, Any]] = []
    rate_limited_flag = [False]

    for index, place in enumerate(selected_places):
        try:
            enriched = enrich_place(
                place,
                location_name,
                rate_limited_flag=rate_limited_flag,
            )
            enriched_places.append(enriched)
        except Exception as error:
            print("Place enrichment failed:", place.get("name", ""), error)
            fallback = dict(place)
            fallback["wikipedia_title"] = ""
            fallback["wikipedia_description"] = ""
            fallback["wikipedia_url"] = ""
            fallback["wikipedia_match_score"] = 0.0
            fallback["wikipedia_location_match"] = False
            fallback["why_visit"] = create_why_visit(place, location_name)
            if not str(fallback.get("description") or "").strip():
                fallback["description"] = fallback["why_visit"]
            enriched_places.append(fallback)

        if (
            not rate_limited_flag[0]
            and index < len(selected_places) - 1
        ):
            time.sleep(0.25)

    return enriched_places