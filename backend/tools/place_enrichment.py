import re
import time
import requests
from difflib import SequenceMatcher


WIKIPEDIA_API_URL = (
    "https://en.wikipedia.org/w/api.php"
)

HEADERS = {
    "User-Agent": (
        "AI-Travel-Planner/1.0 "
        "(travel planning project)"
    )
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):
    if not text:
        return ""

    text = str(text).lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


# ============================================================
# TOKENIZATION
# ============================================================

def get_tokens(text):
    normalized = normalize_text(text)

    if not normalized:
        return set()

    return {
        token
        for token in normalized.split()
        if len(token) > 1
    }


# ============================================================
# NAME SIMILARITY
# ============================================================

def calculate_name_similarity(
    place_name,
    wikipedia_title,
):
    place = normalize_text(
        place_name
    )

    title = normalize_text(
        wikipedia_title
    )

    if not place or not title:
        return 0.0

    # Exact match
    if place == title:
        return 1.0

    place_tokens = get_tokens(place)
    title_tokens = get_tokens(title)

    if not place_tokens or not title_tokens:
        return 0.0

    common_tokens = (
        place_tokens & title_tokens
    )

    token_coverage = (
        len(common_tokens)
        / len(place_tokens)
    )

    sequence_score = SequenceMatcher(
        None,
        place,
        title,
    ).ratio()

    return max(
        token_coverage,
        sequence_score,
    )


# ============================================================
# SEARCH WIKIPEDIA
# ============================================================

def search_wikipedia(
    place_name,
    city,
):
    """
    Search Wikipedia using conservative queries.

    Only a small number of requests are made to reduce
    Wikipedia rate limiting.
    """

    queries = []

    if city:
        queries.append(
            f'"{place_name}" "{city}"'
        )

    queries.append(
        f'"{place_name}"'
    )

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
                timeout=10,
            )

            if response.status_code == 429:

                print(
                    "Wikipedia rate limited. "
                    "Using fallback information."
                )

                return []

            response.raise_for_status()

            data = response.json()

            results = (
                data
                .get("query", {})
                .get("search", [])
            )

            if results:
                return results

            time.sleep(0.5)

        except requests.RequestException as error:

            print(
                "Wikipedia search failed:",
                error,
            )

            return []

        except Exception as error:

            print(
                "Wikipedia processing failed:",
                error,
            )

            return []

    return []


# ============================================================
# GET WIKIPEDIA PAGE
# ============================================================

def get_wikipedia_page(
    title,
):
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
            timeout=10,
        )

        if response.status_code == 429:

            print(
                "Wikipedia rate limited while "
                "retrieving page."
            )

            return None

        response.raise_for_status()

        data = response.json()

        pages = (
            data
            .get("query", {})
            .get("pages", {})
        )

        if not pages:
            return None

        page = next(
            iter(pages.values())
        )

        if page.get("missing") is not None:
            return None

        return {
            "title": page.get(
                "title",
                "",
            ),
            "description": page.get(
                "extract",
                "",
            ),
            "url": page.get(
                "fullurl",
                "",
            ),
        }

    except requests.RequestException as error:

        print(
            "Wikipedia page request failed:",
            error,
        )

        return None

    except Exception as error:

        print(
            "Wikipedia processing failed:",
            error,
        )

        return None


# ============================================================
# VALIDATE WIKIPEDIA MATCH
# ============================================================

def validate_wikipedia_match(
    place_name,
    result,
):
    """
    Validate the Wikipedia result using the place name.

    IMPORTANT:
    We do not treat the city name in the description
    as proof that the Wikipedia article represents
    the exact physical place.
    """

    if not result:
        return None

    title = result.get(
        "title",
        "",
    )

    description = result.get(
        "description",
        "",
    )

    url = result.get(
        "url",
        "",
    )

    if not title:
        return None

    name_score = calculate_name_similarity(
        place_name,
        title,
    )

    # --------------------------------------------------------
    # STRICT MATCH
    # --------------------------------------------------------
    #
    # Only strong name matches are accepted.
    #
    # Example:
    #
    # Khammam Killa -> Khammam Fort
    #
    # may be accepted if the similarity is strong.
    #
    # NTR st -> NTR district
    #
    # must be rejected.
    #

    if name_score < 0.85:

        return None

    return {
        "title": title,
        "description": description,
        "url": url,
        "match_score": round(
            name_score,
            2,
        ),

        # IMPORTANT:
        # A name match does NOT prove exact coordinates.
        "location_match": False,
    }


# ============================================================
# FALLBACK WHY VISIT
# ============================================================

def create_why_visit(
    place,
):
    name = place.get(
        "name",
        "This place",
    )

    category = place.get(
        "category",
        "place",
    )

    distance = place.get(
        "distance_km"
    )

    if distance is not None:

        return (
            f"{name} is a "
            f"{category.lower()} "
            f"approximately "
            f"{distance:.2f} km "
            f"from the selected location."
        )

    return (
        f"{name} is a "
        f"{category.lower()} "
        f"near the selected location."
    )


# ============================================================
# ENRICH SINGLE PLACE
# ============================================================

def enrich_place(
    place,
    city,
):
    """
    Enrich a single place.

    Only strong Wikipedia name matches are accepted.
    """

    enriched = dict(place)

    place_name = place.get(
        "name",
        "",
    )

    # --------------------------------------------------------
    # Default values
    # --------------------------------------------------------

    enriched[
        "wikipedia_title"
    ] = ""

    enriched[
        "wikipedia_description"
    ] = ""

    enriched[
        "wikipedia_url"
    ] = ""

    enriched[
        "wikipedia_match_score"
    ] = 0.0

    enriched[
        "wikipedia_location_match"
    ] = False

    # --------------------------------------------------------
    # Search Wikipedia
    # --------------------------------------------------------

    search_results = search_wikipedia(
        place_name,
        city,
    )

    best_match = None

    # --------------------------------------------------------
    # Evaluate candidates
    # --------------------------------------------------------

    for search_result in search_results:

        title = search_result.get(
            "title",
            "",
        )

        if not title:
            continue

        # Quick validation before requesting
        # the full Wikipedia page.
        quick_score = calculate_name_similarity(
            place_name,
            title,
        )

        if quick_score < 0.85:
            continue

        page = get_wikipedia_page(
            title
        )

        if not page:
            continue

        validated = validate_wikipedia_match(
            place_name,
            page,
        )

        if validated is None:
            continue

        if (
            best_match is None
            or validated[
                "match_score"
            ]
            > best_match[
                "match_score"
            ]
        ):

            best_match = validated

        if validated[
            "match_score"
        ] >= 0.95:

            break

    # --------------------------------------------------------
    # Reliable Wikipedia name match
    # --------------------------------------------------------

    if best_match:

        enriched[
            "wikipedia_title"
        ] = best_match[
            "title"
        ]

        enriched[
            "wikipedia_description"
        ] = best_match[
            "description"
        ]

        enriched[
            "wikipedia_url"
        ] = best_match[
            "url"
        ]

        enriched[
            "wikipedia_match_score"
        ] = best_match[
            "match_score"
        ]

        # We deliberately keep this False because
        # we have not verified the physical coordinates.
        enriched[
            "wikipedia_location_match"
        ] = False

        enriched[
            "why_visit"
        ] = best_match[
            "description"
        ]

    # --------------------------------------------------------
    # No reliable Wikipedia match
    # --------------------------------------------------------

    else:

        enriched[
            "why_visit"
        ] = create_why_visit(
            place
        )

    return enriched


# ============================================================
# ENRICH MULTIPLE PLACES
# ============================================================

def enrich_places(
    places,
    location_name,
    max_places=10,
):
    """
    Enrich a limited number of places.

    Weak or unrelated Wikipedia matches are rejected.
    """

    if not places:
        return []

    selected_places = places[
        :max_places
    ]

    enriched_places = []

    for index, place in enumerate(
        selected_places
    ):

        try:

            enriched = enrich_place(
                place,
                location_name,
            )

            enriched_places.append(
                enriched
            )

        except Exception as error:

            print(
                "Place enrichment failed:",
                place.get("name", ""),
                error,
            )

            fallback = dict(place)

            fallback[
                "wikipedia_title"
            ] = ""

            fallback[
                "wikipedia_description"
            ] = ""

            fallback[
                "wikipedia_url"
            ] = ""

            fallback[
                "wikipedia_match_score"
            ] = 0.0

            fallback[
                "wikipedia_location_match"
            ] = False

            fallback[
                "why_visit"
            ] = create_why_visit(
                place
            )

            enriched_places.append(
                fallback
            )

        # Delay between requests to reduce
        # Wikipedia rate limiting.
        if index < len(
            selected_places
        ) - 1:

            time.sleep(1)

    return enriched_places