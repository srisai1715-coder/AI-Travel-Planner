"""
Place filtering, deduplication and ranking for the AI Travel Planner.

Main goals:
1. Keep useful tourist destinations within the search radius.
2. Strongly prioritize historical and important attractions.
3. Do not let distance dominate quality.
4. Remove obvious infrastructure and low-value places.
5. Remove duplicate or near-duplicate places.
6. Keep the final list clean for the AI travel planner.
"""

import math
import re


# ============================================================
# CONFIGURATION
# ============================================================

MAX_DISTANCE_KM = 10.0

DEFAULT_TOP_LIMIT = 10

DUPLICATE_DISTANCE_KM = 0.20


# ============================================================
# CATEGORY SCORES
# ============================================================

CATEGORY_SCORES = {
    "historical": 50,
    "heritage": 50,
    "monument": 48,
    "tourist attraction": 45,
    "tourist_attraction": 45,
    "attraction": 40,
    "nature / recreation": 35,
    "nature": 35,
    "recreation": 32,
    "viewpoint": 38,
    "park": 25,
    "place_of_worship": 18,
    "religious": 18,
    "temple": 18,
    "church": 15,
    "mosque": 15,
    "masjid": 15,
    "other": 10,
}


# ============================================================
# HIGH VALUE KEYWORDS
# ============================================================

HIGH_VALUE_KEYWORDS = [
    "fort",
    "killa",
    "fortress",
    "palace",
    "castle",
    "heritage",
    "historical",
    "historic",
    "monument",
    "museum",
    "archaeological",
    "archaeology",
    "ruins",
    "royal",
    "king",
    "queen",
    "temple",
    "hill",
    "cave",
    "waterfall",
    "lake",
    "dam",
    "reservoir",
    "viewpoint",
    "heritage site",
]


# ============================================================
# VERY IMPORTANT KEYWORDS
# ============================================================

MAJOR_ATTRACTION_KEYWORDS = [
    "fort",
    "killa",
    "fortress",
    "palace",
    "castle",
    "heritage",
    "museum",
    "archaeological",
    "archaeology",
]


# ============================================================
# GENERIC NAMES
# ============================================================

GENERIC_NAME_EXACT = {
    "church",
    "temple",
    "mosque",
    "masjid",
    "park",
    "statue",
    "monument",
    "building",
    "school",
    "college",
    "hospital",
    "office",
    "road",
    "street",
    "junction",
    "tank",
    "water tank",
    "over head water tank",
}


GENERIC_NAME_KEYWORDS = [
    "water tank",
    "over head water tank",
    "party office",
    "police station",
    "police office",
    "government office",
    "municipality",
    "school",
    "college",
    "hospital",
    "bus stop",
    "railway signal",
    "parking",
]


# ============================================================
# USELESS INFRASTRUCTURE KEYWORDS
# ============================================================

USELESS_KEYWORDS = [
    "water tank",
    "over head water tank",
    "party office",
    "police station",
    "police office",
    "government office",
    "municipality",
    "school",
    "college",
    "hospital",
    "bus stop",
    "railway signal",
    "parking",
    "transformer",
    "substation",
]


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(value):
    """
    Normalize text for comparison.

    Example:
        "Khammam Fort" -> "khammam fort"
        "NTR st."       -> "ntr st"
    """

    if value is None:
        return ""

    text = str(value).strip().lower()

    text = text.replace(".", " ")
    text = text.replace("-", " ")
    text = text.replace("_", " ")

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# NAME NORMALIZATION
# ============================================================

def normalize_place_name(name):
    """
    Normalize place names so similar names can be detected.
    """

    text = normalize_text(name)

    replacements = {
        "st": "statue",
        "statue": "statue",
        "sri": "",
        "shri": "",
        "the": "",
        "temple": "temple",
    }

    words = text.split()

    normalized_words = []

    for word in words:

        replacement = replacements.get(
            word,
            word,
        )

        if replacement:
            normalized_words.append(
                replacement
            )

    text = " ".join(
        normalized_words
    )

    return text.strip()


# ============================================================
# COMBINED PLACE TEXT
# ============================================================

def place_text(place):
    """
    Combine name, category and descriptions.
    """

    name = normalize_text(
        place.get("name")
    )

    category = normalize_text(
        place.get("category")
    )

    description = normalize_text(
        place.get("description")
    )

    wikipedia_description = normalize_text(
        place.get("wikipedia_description")
    )

    return (
        f"{name} "
        f"{category} "
        f"{description} "
        f"{wikipedia_description}"
    ).strip()


# ============================================================
# CATEGORY SCORE
# ============================================================

def category_score(place):
    """
    Base score based on category.
    """

    category = normalize_text(
        place.get("category")
    )

    if category in CATEGORY_SCORES:
        return CATEGORY_SCORES[
            category
        ]

    if "histor" in category:
        return 50

    if "heritage" in category:
        return 50

    if "monument" in category:
        return 48

    if "tourist" in category:
        return 45

    if "attraction" in category:
        return 40

    if "nature" in category:
        return 35

    if "recreation" in category:
        return 32

    if "religious" in category:
        return 18

    if "worship" in category:
        return 18

    return 10


# ============================================================
# KEYWORD SCORE
# ============================================================

def keyword_score(place):
    """
    Score based on important words in the place information.
    """

    text = place_text(place)

    score = 0

    for keyword in HIGH_VALUE_KEYWORDS:

        if keyword in text:

            if keyword in {
                "fort",
                "killa",
                "fortress",
                "palace",
                "castle",
                "heritage",
                "archaeological",
                "archaeology",
            }:
                score += 25

            elif keyword in {
                "historical",
                "historic",
                "monument",
                "museum",
                "ruins",
                "royal",
                "king",
                "queen",
            }:
                score += 18

            else:
                score += 10

    return min(
        score,
        60,
    )


# ============================================================
# MAJOR ATTRACTION BONUS
# ============================================================

def major_attraction_bonus(place):
    """
    Give strong priority to important tourist structures.

    This is deliberately strong so that a major historical
    attraction 8 km away can beat a generic nearby place.
    """

    name = normalize_text(
        place.get("name")
    )

    category = normalize_text(
        place.get("category")
    )

    text = place_text(place)

    score = 0

    # Name is the strongest signal.
    for keyword in MAJOR_ATTRACTION_KEYWORDS:

        if keyword in name:
            score += 30

    # Historical category.
    if "histor" in category:
        score += 15

    if "heritage" in category:
        score += 15

    if "tourist" in category:
        score += 10

    # Check description as a secondary signal.
    if any(
        keyword in text
        for keyword in [
            "historical monument",
            "heritage site",
            "archaeological site",
            "historic fort",
        ]
    ):
        score += 10

    return min(
        score,
        55,
    )


# ============================================================
# DESCRIPTION QUALITY
# ============================================================

def description_score(place):
    """
    Give points when the place contains useful information.
    """

    description = normalize_text(
        place.get("description")
    )

    wikipedia_description = normalize_text(
        place.get("wikipedia_description")
    )

    combined = (
        description
        or wikipedia_description
    )

    if not combined:
        return 0

    length = len(combined)

    if length >= 500:
        return 15

    if length >= 250:
        return 12

    if length >= 100:
        return 8

    if length >= 40:
        return 5

    return 2


# ============================================================
# WIKIPEDIA / ENRICHMENT SCORE
# ============================================================

def enrichment_score(place):
    """
    Give additional score when useful external information
    exists for the place.
    """

    score = 0

    title = normalize_text(
        place.get("wikipedia_title")
    )

    description = normalize_text(
        place.get("wikipedia_description")
    )

    url = normalize_text(
        place.get("wikipedia_url")
    )

    match_score = place.get(
        "wikipedia_match_score",
        0,
    )

    if title:
        score += 12

    if description:
        score += 8

    if url:
        score += 3

    try:
        match_score = float(
            match_score
        )
    except (
        TypeError,
        ValueError,
    ):
        match_score = 0

    if match_score >= 0.90:
        score += 10

    elif match_score >= 0.70:
        score += 7

    elif match_score >= 0.50:
        score += 3

    return min(
        score,
        30,
    )


# ============================================================
# RELATED PLACE SCORE
# ============================================================

def related_place_score(place):
    """
    Reward attractions that have related places nearby.
    """

    related_places = place.get(
        "related_places",
        [],
    )

    if not isinstance(
        related_places,
        list,
    ):
        related_places = []

    group_size = place.get(
        "group_size",
        1,
    )

    try:
        group_size = int(
            group_size
        )
    except (
        TypeError,
        ValueError,
    ):
        group_size = 1

    if group_size >= 5:
        return 20

    if group_size >= 4:
        return 18

    if group_size >= 3:
        return 15

    if group_size >= 2:
        return 10

    if related_places:
        return 5

    return 0


# ============================================================
# DISTANCE SCORE
# ============================================================

def distance_score(place):
    """
    Distance provides a small bonus.

    Important:
    Distance does NOT dominate quality.

    0-1 km   -> +15
    1-2 km   -> +13
    2-3 km   -> +11
    3-5 km   -> +8
    5-7 km   -> +5
    7-10 km  -> +2

    Therefore a great historical place at 8 km
    can still outrank a generic place at 0.5 km.
    """

    distance = place.get(
        "distance_km",
        10,
    )

    try:
        distance = float(
            distance
        )
    except (
        TypeError,
        ValueError,
    ):
        distance = 10

    if distance < 0:
        distance = 0

    if distance <= 1:
        return 15

    if distance <= 2:
        return 13

    if distance <= 3:
        return 11

    if distance <= 5:
        return 8

    if distance <= 7:
        return 5

    if distance <= 10:
        return 2

    return -20


# ============================================================
# NAME QUALITY SCORE
# ============================================================

def name_quality_score(place):
    """
    Penalize extremely generic names.
    """

    name = normalize_text(
        place.get("name")
    )

    if not name:
        return -30

    if name in GENERIC_NAME_EXACT:
        return -30

    for keyword in GENERIC_NAME_KEYWORDS:

        if keyword in name:
            return -22

    # Very short names are often poor data.
    if len(name) <= 3:
        return -10

    return 0


# ============================================================
# SPECIAL QUALITY SCORE
# ============================================================

def special_quality_score(place):
    """
    Extra travel-quality rules.
    """

    name = normalize_text(
        place.get("name")
    )

    category = normalize_text(
        place.get("category")
    )

    score = 0

    if any(
        word in name
        for word in [
            "fort",
            "killa",
            "fortress",
            "palace",
            "castle",
            "heritage",
        ]
    ):
        score += 20

    if "histor" in category:
        score += 15

    if "tourist" in category:
        score += 10

    if any(
        word in name
        for word in [
            "waterfall",
            "lake",
            "dam",
            "hill",
            "cave",
            "viewpoint",
        ]
    ):
        score += 12

    return score


# ============================================================
# USELESS PLACE CHECK
# ============================================================

def is_useless_place(place):
    """
    Identify places that should not normally be shown to tourists.
    """

    name = normalize_text(
        place.get("name")
    )

    category = normalize_text(
        place.get("category")
    )

    text = place_text(place)

    # Strong infrastructure signals.
    for keyword in USELESS_KEYWORDS:

        if keyword in name:
            return True

    # Do not remove historical attractions simply because
    # their description contains a generic word.
    is_important = (
        "histor" in category
        or "heritage" in category
        or "tourist" in category
        or any(
            keyword in name
            for keyword in [
                "fort",
                "killa",
                "palace",
                "castle",
                "museum",
                "monument",
                "ruins",
                "waterfall",
                "dam",
                "lake",
            ]
        )
    )

    if not is_important:

        for keyword in USELESS_KEYWORDS:

            if keyword in text:
                return True

    return False


# ============================================================
# FINAL PLACE SCORE
# ============================================================

def calculate_place_score(place):
    """
    Calculate the complete preprocessing score.
    """

    score = 0

    score += category_score(
        place
    )

    score += keyword_score(
        place
    )

    score += major_attraction_bonus(
        place
    )

    score += description_score(
        place
    )

    score += enrichment_score(
        place
    )

    score += related_place_score(
        place
    )

    score += distance_score(
        place
    )

    score += name_quality_score(
        place
    )

    score += special_quality_score(
        place
    )

    return score


# ============================================================
# BASIC FILTER
# ============================================================

def filter_places(
    places,
    max_distance_km=MAX_DISTANCE_KM,
):
    """
    Remove invalid and clearly useless places.
    """

    if not places:
        return []

    filtered = []

    for place in places:

        if not isinstance(
            place,
            dict,
        ):
            continue

        name = normalize_text(
            place.get("name")
        )

        if not name:
            continue

        # ----------------------------------------------------
        # DISTANCE
        # ----------------------------------------------------

        distance = place.get(
            "distance_km"
        )

        try:
            distance = float(
                distance
            )
        except (
            TypeError,
            ValueError,
        ):
            distance = None

        if (
            distance is not None
            and distance > max_distance_km
        ):
            continue

        # ----------------------------------------------------
        # USELESS PLACE
        # ----------------------------------------------------

        if is_useless_place(
            place
        ):
            continue

        filtered.append(
            place
        )

    return filtered


# ============================================================
# DISTANCE BETWEEN TWO COORDINATES
# ============================================================

def coordinate_distance_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    """
    Calculate approximate distance between two coordinates.
    """

    try:
        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)
    except (
        TypeError,
        ValueError,
    ):
        return None

    radius = 6371.0

    phi1 = math.radians(
        lat1
    )

    phi2 = math.radians(
        lat2
    )

    delta_phi = math.radians(
        lat2 - lat1
    )

    delta_lambda = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(
            delta_phi / 2
        ) ** 2
        +
        math.cos(phi1)
        * math.cos(phi2)
        * math.sin(
            delta_lambda / 2
        ) ** 2
    )

    c = (
        2
        * math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a),
        )
    )

    return radius * c


# ============================================================
# DUPLICATE DETECTION
# ============================================================

def are_duplicate_places(
    place_a,
    place_b,
):
    """
    Determine whether two places are likely duplicates.
    """

    name_a = normalize_place_name(
        place_a.get("name")
    )

    name_b = normalize_place_name(
        place_b.get("name")
    )

    # --------------------------------------------------------
    # EXACT NORMALIZED NAME
    # --------------------------------------------------------

    if (
        name_a
        and name_b
        and name_a == name_b
    ):
        return True

    # --------------------------------------------------------
    # COORDINATE PROXIMITY
    # --------------------------------------------------------

    distance = coordinate_distance_km(
        place_a.get("latitude"),
        place_a.get("longitude"),
        place_b.get("latitude"),
        place_b.get("longitude"),
    )

    if (
        distance is not None
        and distance <= DUPLICATE_DISTANCE_KM
    ):

        # If they are extremely close and have
        # similar names, consider them duplicates.
        words_a = set(
            name_a.split()
        )

        words_b = set(
            name_b.split()
        )

        if words_a and words_b:

            overlap = (
                len(
                    words_a
                    & words_b
                )
                /
                max(
                    len(words_a),
                    len(words_b),
                )
            )

            if overlap >= 0.50:
                return True

    return False


# ============================================================
# CHOOSE BETTER DUPLICATE
# ============================================================

def choose_better_place(
    place_a,
    place_b,
):
    """
    When two places are duplicates, keep the better one.

    Preference:
    1. Higher score.
    2. Better description.
    3. More enrichment.
    4. Closer distance.
    """

    score_a = calculate_place_score(
        place_a
    )

    score_b = calculate_place_score(
        place_b
    )

    if score_a > score_b:
        return place_a

    if score_b > score_a:
        return place_b

    description_a = len(
        normalize_text(
            place_a.get(
                "description"
            )
        )
    )

    description_b = len(
        normalize_text(
            place_b.get(
                "description"
            )
        )
    )

    if description_a > description_b:
        return place_a

    if description_b > description_a:
        return place_b

    distance_a = place_a.get(
        "distance_km",
        999,
    )

    distance_b = place_b.get(
        "distance_km",
        999,
    )

    try:
        distance_a = float(
            distance_a
        )
    except (
        TypeError,
        ValueError,
    ):
        distance_a = 999

    try:
        distance_b = float(
            distance_b
        )
    except (
        TypeError,
        ValueError,
    ):
        distance_b = 999

    if distance_a <= distance_b:
        return place_a

    return place_b


# ============================================================
# DEDUPLICATE
# ============================================================

def deduplicate_places(
    places,
):
    """
    Remove duplicate or near-duplicate places.
    """

    if not places:
        return []

    unique_places = []

    for place in places:

        duplicate_index = None

        for index, existing in enumerate(
            unique_places
        ):

            if are_duplicate_places(
                place,
                existing,
            ):
                duplicate_index = index
                break

        if duplicate_index is None:

            unique_places.append(
                place
            )

        else:

            better = choose_better_place(
                place,
                unique_places[
                    duplicate_index
                ],
            )

            unique_places[
                duplicate_index
            ] = better

    return unique_places


# ============================================================
# RANK PLACES
# ============================================================

def rank_places(
    places,
):
    """
    Calculate scores and sort from best to worst.
    """

    ranked = []

    for place in places:

        item = dict(
            place
        )

        item[
            "preprocessing_score"
        ] = calculate_place_score(
            item
        )

        ranked.append(
            item
        )

    ranked.sort(
        key=lambda p: (
            p.get(
                "preprocessing_score",
                0,
            ),
            -float(
                p.get(
                    "distance_km",
                    999,
                )
                or 999
            ),
        ),
        reverse=True,
    )

    return ranked


# ============================================================
# FINAL FILTER + RANK
# ============================================================

def filter_and_rank_places(
    places,
    max_distance_km=MAX_DISTANCE_KM,
):
    """
    Complete place preprocessing pipeline.

    Steps:

    1. Basic validation.
    2. Remove useless infrastructure.
    3. Keep useful places within 10 km.
    4. Remove duplicates.
    5. Calculate quality scores.
    6. Rank best places first.
    """

    if not places:
        return []

    filtered = filter_places(
        places=places,
        max_distance_km=max_distance_km,
    )

    deduplicated = deduplicate_places(
        filtered
    )

    ranked = rank_places(
        deduplicated
    )

    return ranked


# ============================================================
# TOP PLACES
# ============================================================

def get_top_places(
    places,
    limit=DEFAULT_TOP_LIMIT,
    max_distance_km=MAX_DISTANCE_KM,
):
    """
    Return the best N places.
    """

    ranked = filter_and_rank_places(
        places=places,
        max_distance_km=max_distance_km,
    )

    try:
        limit = int(limit)
    except (
        TypeError,
        ValueError,
    ):
        limit = DEFAULT_TOP_LIMIT

    if limit <= 0:
        return []

    return ranked[
        :limit
    ]