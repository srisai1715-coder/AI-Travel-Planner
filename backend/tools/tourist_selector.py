"""
Tourist Place Selector

Selects the most useful places for a travel itinerary.

Main principle:
Distance <= 10 km is a hard requirement.

Quality is determined mainly by:
1. Major historical places
2. Forts / killa
3. Palaces
4. Museums
5. Heritage / monuments
6. Lakes / waterfalls / dams / hills
7. Important religious attractions
8. Other genuine tourist attractions
9. Parks / recreation
10. Generic statues and ordinary landmarks

The selector also:
- removes duplicates
- avoids infrastructure
- avoids too many similar places
- keeps strong tourist places even when they are farther away
- prefers genuinely interesting destinations over merely nearby ones
"""

from typing import List, Dict


# ============================================================
# CONSTANTS
# ============================================================

MAX_DISTANCE_KM = 10.0


# ============================================================
# CATEGORY PRIORITY
# ============================================================

CATEGORY_PRIORITY = {
    "Historical": 45,
    "Tourist Attraction": 38,
    "Nature / Recreation": 32,
    "Religious": 24,
}


# ============================================================
# HIGH-VALUE TOURIST TYPES
# ============================================================

MAJOR_PLACE_KEYWORDS = {
    "fort": 70,
    "killa": 70,
    "palace": 70,
    "museum": 65,
    "heritage": 65,
    "monument": 60,
    "ruins": 55,
    "archaeological": 60,
    "historic": 55,
    "historical": 55,
    "lake": 55,
    "waterfall": 60,
    "dam": 50,
    "hill": 42,
    "cave": 50,
    "gateway": 45,
    "darwaza": 45,
    "dharvazaa": 45,
    "memorial": 35,
}


# ============================================================
# MEDIUM-VALUE KEYWORDS
# ============================================================

MEDIUM_PLACE_KEYWORDS = {
    "temple": 28,
    "church": 18,
    "mosque": 20,
    "shrine": 24,
    "beach": 55,
    "viewpoint": 40,
    "garden": 18,
    "park": 15,
    "sanctuary": 45,
    "forest": 42,
    "wildlife": 45,
    "zoo": 40,
    "reservoir": 45,
    "river": 30,
    "lake": 55,
}


# ============================================================
# LOW-VALUE KEYWORDS
# ============================================================

LOW_VALUE_KEYWORDS = {
    "statue": 45,
    "ntr st": 50,
    "ntr street": 50,
    "street": 45,
    "road": 45,
    "office": 50,
    "municipality": 50,
    "muncipality": 50,
    "police": 40,
    "water tank": 70,
    "over head water tank": 80,
    "tower": 30,
    "tv tower": 60,
    "bus stand": 60,
    "railway station": 55,
    "school": 60,
    "college": 60,
    "hospital": 60,
    "market": 45,
}


# ============================================================
# GENERIC NAMES
# ============================================================

GENERIC_NAMES = {
    "church",
    "park",
    "temple",
    "statue",
    "tower",
    "office",
    "road",
    "street",
}


# ============================================================
# PLACE TYPE
# ============================================================

def determine_tourist_place_type(place: Dict) -> str:

    name = str(
        place.get("name", "")
    ).strip().lower()

    category = str(
        place.get("category", "")
    ).strip().lower()

    if any(
        keyword in name
        for keyword in [
            "fort",
            "killa",
            "palace",
            "museum",
            "heritage",
            "monument",
            "ruins",
            "archaeological",
            "darwaza",
            "dharvazaa",
            "gateway",
        ]
    ):
        return "major_historical"

    if (
        "historical" in category
        or "historic" in name
    ):
        return "historical"

    if any(
        keyword in name
        for keyword in [
            "lake",
            "waterfall",
            "dam",
            "hill",
            "forest",
            "sanctuary",
            "wildlife",
            "reservoir",
            "viewpoint",
        ]
    ):
        return "nature"

    if "park" in name:
        return "park"

    if (
        "religious" in category
        or any(
            keyword in name
            for keyword in [
                "temple",
                "church",
                "mosque",
                "shrine",
            ]
        )
    ):
        return "religious"

    if any(
        keyword in name
        for keyword in [
            "statue",
            "memorial",
        ]
    ):
        return "statue"

    if category == "tourist attraction":
        return "tourist_attraction"

    return "other"


# ============================================================
# CALCULATE TOURIST QUALITY
# ============================================================

def calculate_tourist_quality_score(
    place: Dict,
) -> float:

    name = str(
        place.get("name", "")
    ).strip().lower()

    category = str(
        place.get("category", "")
    ).strip()

    score = 0.0

    # ========================================================
    # 1. CATEGORY
    # ========================================================

    score += CATEGORY_PRIORITY.get(
        category,
        10,
    )

    # ========================================================
    # 2. PLACE TYPE
    # ========================================================

    place_type = determine_tourist_place_type(
        place
    )

    if place_type == "major_historical":
        score += 30

    elif place_type == "historical":
        score += 10

    elif place_type == "nature":
        score += 18

    elif place_type == "religious":
        score += 8

    elif place_type == "park":
        score += 2

    elif place_type == "statue":
        score -= 15

    # ========================================================
    # 3. MAJOR TOURIST KEYWORDS
    # ========================================================

    for keyword, bonus in MAJOR_PLACE_KEYWORDS.items():

        if keyword in name:
            score += bonus

    # ========================================================
    # 4. MEDIUM TOURIST KEYWORDS
    # ========================================================

    for keyword, bonus in MEDIUM_PLACE_KEYWORDS.items():

        if keyword in name:
            score += bonus

    # ========================================================
    # 5. LOW VALUE KEYWORDS
    # ========================================================

    for keyword, penalty in LOW_VALUE_KEYWORDS.items():

        if keyword in name:
            score -= penalty

    # ========================================================
    # 6. PREPROCESSING SCORE
    # ========================================================

    preprocessing_score = place.get(
        "preprocessing_score",
        0,
    )

    try:
        preprocessing_score = float(
            preprocessing_score
        )
    except (
        TypeError,
        ValueError,
    ):
        preprocessing_score = 0

    score += min(
        preprocessing_score * 0.12,
        25,
    )

    # ========================================================
    # 7. DESCRIPTION QUALITY
    # ========================================================

    description = str(
        place.get("description", "")
    ).strip()

    if len(description) >= 200:
        score += 15

    elif len(description) >= 100:
        score += 10

    elif len(description) >= 50:
        score += 5

    # ========================================================
    # 8. RELATED PLACES
    # ========================================================

    related_places = place.get(
        "related_places",
        [],
    )

    if isinstance(
        related_places,
        list,
    ):

        related_count = len(
            related_places
        )

        if related_count >= 3:
            score += 12

        elif related_count == 2:
            score += 8

        elif related_count == 1:
            score += 4

    # ========================================================
    # 9. DISTANCE
    # ========================================================

    distance = place.get(
        "distance_km",
        999,
    )

    try:
        distance = float(distance)
    except (
        TypeError,
        ValueError,
    ):
        distance = 999

    # Distance is useful, but should NOT dominate quality.

    if distance <= 1:
        score += 8

    elif distance <= 3:
        score += 6

    elif distance <= 5:
        score += 4

    elif distance <= 8:
        score += 2

    # ========================================================
    # 10. GENERIC PLACE PENALTY
    # ========================================================

    if name in GENERIC_NAMES:
        score -= 25

    # ========================================================
    # 11. STRONG STATUE PENALTY
    # ========================================================

    if "statue" in name:

        # Statues should only survive when
        # there are not enough better attractions.

        score -= 25

    # ========================================================
    # FINAL
    # ========================================================

    return round(
        score,
        1,
    )


# ============================================================
# SELECT TOURIST PLACES
# ============================================================

def select_tourist_places(
    places: List[Dict],
    max_places: int = 10,
) -> List[Dict]:

    if not places:
        return []

    scored_places = []

    # ========================================================
    # SCORE + DISTANCE FILTER
    # ========================================================

    for place in places:

        if not isinstance(
            place,
            dict,
        ):
            continue

        candidate = dict(place)

        distance = candidate.get(
            "distance_km",
            999,
        )

        try:
            distance = float(distance)
        except (
            TypeError,
            ValueError,
        ):
            continue

        # HARD 10 KM LIMIT

        if distance > MAX_DISTANCE_KM:
            continue

        candidate[
            "tourist_place_type"
        ] = determine_tourist_place_type(
            candidate
        )

        candidate[
            "tourist_quality_score"
        ] = calculate_tourist_quality_score(
            candidate
        )

        scored_places.append(
            candidate
        )

    # ========================================================
    # REMOVE VERY LOW QUALITY PLACES
    # ========================================================

    filtered_places = []

    for place in scored_places:

        name = str(
            place.get("name", "")
        ).strip().lower()

        score = float(
            place.get(
                "tourist_quality_score",
                0,
            )
        )

        place_type = place.get(
            "tourist_place_type",
            "other",
        )

        # Infrastructure

        infrastructure_keywords = [
            "water tank",
            "over head water tank",
            "office",
            "municipality",
            "school",
            "college",
            "hospital",
            "bus stand",
        ]

        if any(
            keyword in name
            for keyword in infrastructure_keywords
        ):
            continue

        # Very low quality generic places

        if (
            place_type == "statue"
            and score < 70
        ):
            continue

        if (
            place_type == "other"
            and score < 55
        ):
            continue

        if (
            name in GENERIC_NAMES
            and score < 70
        ):
            continue

        filtered_places.append(
            place
        )

    # ========================================================
    # SORT
    # ========================================================

    filtered_places.sort(
        key=lambda item: (
            float(
                item.get(
                    "tourist_quality_score",
                    0,
                )
            ),
            -float(
                item.get(
                    "distance_km",
                    999,
                )
            ),
        ),
        reverse=True,
    )

    # ========================================================
    # DEDUPLICATION
    # ========================================================

    selected = []

    seen_names = set()
    seen_coordinates = set()

    for place in filtered_places:

        name = str(
            place.get("name", "")
        ).strip().lower()

        latitude = place.get(
            "latitude"
        )

        longitude = place.get(
            "longitude"
        )

        # ----------------------------------------------------
        # NAME DUPLICATE
        # ----------------------------------------------------

        if name in seen_names:
            continue

        # ----------------------------------------------------
        # COORDINATE DUPLICATE
        # ----------------------------------------------------

        coordinate_key = None

        try:

            coordinate_key = (
                round(
                    float(latitude),
                    4,
                ),
                round(
                    float(longitude),
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

        selected.append(
            place
        )

        seen_names.add(
            name
        )

        if coordinate_key is not None:
            seen_coordinates.add(
                coordinate_key
            )

        if len(selected) >= max_places:
            break

    # ========================================================
    # FALLBACK
    # ========================================================

    # If there are fewer than max_places,
    # don't invent places. Return only genuine candidates.

    return selected