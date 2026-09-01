import math
import time
import requests


# ============================================================
# OPENSTREETMAP OVERPASS API
# ============================================================

# Multiple public Overpass servers.
# If one server is unavailable or times out, the next one
# will be tried automatically.

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


# ============================================================
# SEARCH SETTINGS
# ============================================================

DEFAULT_RADIUS = 10000

MAX_PLACES = 30

REQUEST_TIMEOUT = 45

MAX_RETRIES_PER_SERVER = 2


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def calculate_distance_km(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
):
    """
    Calculate the straight-line distance between
    two latitude/longitude coordinates.

    Returns:
        Distance in kilometres.
    """

    earth_radius_km = 6371.0

    lat1 = math.radians(latitude1)
    lat2 = math.radians(latitude2)

    delta_lat = math.radians(
        latitude2 - latitude1
    )

    delta_lon = math.radians(
        longitude2 - longitude1
    )

    a = (
        math.sin(delta_lat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return earth_radius_km * c


# ============================================================
# CLASSIFY PLACE
# ============================================================

def classify_place(tags):
    """
    Convert OpenStreetMap tags into a
    travel-friendly category.
    """

    tourism = tags.get(
        "tourism",
        ""
    ).lower()

    historic = tags.get(
        "historic",
        ""
    ).lower()

    leisure = tags.get(
        "leisure",
        ""
    ).lower()

    amenity = tags.get(
        "amenity",
        ""
    ).lower()


    # --------------------------------------------------------
    # HISTORICAL
    # --------------------------------------------------------

    if historic in {
        "castle",
        "fort",
        "ruins",
        "monument",
        "memorial",
        "archaeological_site",
        "heritage",
    }:

        return "Historical"


    # --------------------------------------------------------
    # MUSEUM / CULTURE
    # --------------------------------------------------------

    if tourism in {
        "museum",
        "gallery",
    }:

        return "Museum / Culture"


    # --------------------------------------------------------
    # NATURE / RECREATION
    # --------------------------------------------------------

    if tourism in {
        "viewpoint",
        "picnic_site",
        "zoo",
        "theme_park",
        "aquarium",
        "nature_reserve",
    }:

        return "Nature / Recreation"


    if leisure in {
        "park",
        "garden",
        "nature_reserve",
    }:

        return "Nature / Recreation"


    # --------------------------------------------------------
    # RELIGIOUS
    # --------------------------------------------------------

    if tourism == "place_of_worship":

        return "Religious"


    if amenity == "place_of_worship":

        return "Religious"


    # --------------------------------------------------------
    # TOURIST ATTRACTION
    # --------------------------------------------------------

    if tourism in {
        "attraction",
        "artwork",
    }:

        return "Tourist Attraction"


    # --------------------------------------------------------
    # OTHER
    # --------------------------------------------------------

    return "Other"


# ============================================================
# PLACE RELEVANCE SCORE
# ============================================================

def calculate_relevance_score(
    place,
    distance_km,
):
    """
    Give each place a preprocessing relevance score.

    This is NOT the final AI ranking.

    It is used to reduce unnecessary places
    before sending data to the AI agent.
    """

    score = 0


    # --------------------------------------------------------
    # CATEGORY SCORE
    # --------------------------------------------------------

    category_scores = {

        "Historical": 100,

        "Museum / Culture": 90,

        "Nature / Recreation": 85,

        "Tourist Attraction": 80,

        "Religious": 65,

        "Other": 10,
    }


    score += category_scores.get(
        place["category"],
        10,
    )


    # --------------------------------------------------------
    # DISTANCE SCORE
    # --------------------------------------------------------

    if distance_km <= 2:

        score += 30

    elif distance_km <= 5:

        score += 20

    elif distance_km <= 10:

        score += 10


    # --------------------------------------------------------
    # INFORMATION SCORE
    # --------------------------------------------------------

    if place["description"]:

        score += 10


    if place["wikipedia"]:

        score += 15


    if place["website"]:

        score += 5


    if place["opening_hours"]:

        score += 5


    return score


# ============================================================
# BUILD OVERPASS QUERY
# ============================================================

def build_overpass_query(
    latitude: float,
    longitude: float,
    radius: int,
):
    """
    Build the Overpass query.
    """

    query = f"""
    [out:json][timeout:40];

    (
        node["tourism"](around:{radius},{latitude},{longitude});
        way["tourism"](around:{radius},{latitude},{longitude});
        relation["tourism"](around:{radius},{latitude},{longitude});

        node["historic"](around:{radius},{latitude},{longitude});
        way["historic"](around:{radius},{latitude},{longitude});
        relation["historic"](around:{radius},{latitude},{longitude});

        node["leisure"="park"](around:{radius},{latitude},{longitude});
        way["leisure"="park"](around:{radius},{latitude},{longitude});
        relation["leisure"="park"](around:{radius},{latitude},{longitude});

        node["amenity"="place_of_worship"](around:{radius},{latitude},{longitude});
        way["amenity"="place_of_worship"](around:{radius},{latitude},{longitude});
        relation["amenity"="place_of_worship"](around:{radius},{latitude},{longitude});
    );

    out center tags;
    """

    return query


# ============================================================
# REQUEST HEADERS
# ============================================================

def get_request_headers():

    return {
        "User-Agent":
            "AI-Travel-Planner/1.0"
    }


# ============================================================
# CALL OVERPASS WITH FALLBACK
# ============================================================

def request_overpass(
    query: str,
):
    """
    Call Overpass using multiple servers.

    Strategy:

        Server 1
            ↓
        retry
            ↓
        Server 2
            ↓
        retry
            ↓
        Server 3
    """

    headers = get_request_headers()

    errors = []


    for server_url in OVERPASS_URLS:

        for attempt in range(
            1,
            MAX_RETRIES_PER_SERVER + 1,
        ):

            try:

                print(
                    f"Trying Overpass server: "
                    f"{server_url} "
                    f"(attempt {attempt})"
                )


                response = requests.post(
                    server_url,
                    data=query,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )


                response.raise_for_status()


                data = response.json()


                print(
                    f"Overpass request successful: "
                    f"{server_url}"
                )


                return data


            except requests.exceptions.RequestException as error:

                error_message = (
                    f"{server_url} "
                    f"attempt {attempt}: "
                    f"{error}"
                )

                print(
                    f"Overpass request failed: "
                    f"{error_message}"
                )


                errors.append(
                    error_message
                )


                if attempt < MAX_RETRIES_PER_SERVER:

                    time.sleep(2)


        # Try next server after retries.


    # --------------------------------------------------------
    # ALL SERVERS FAILED
    # --------------------------------------------------------

    error_summary = "\n".join(
        errors
    )


    raise RuntimeError(
        "All Overpass API servers failed.\n"
        + error_summary
    )


# ============================================================
# SEARCH NEARBY PLACES
# ============================================================

def search_nearby_places(
    latitude: float,
    longitude: float,
    radius: int = DEFAULT_RADIUS,
):
    """
    Search for useful tourist attractions
    around the selected coordinates.
    """


    # ========================================================
    # BUILD QUERY
    # ========================================================

    query = build_overpass_query(
        latitude,
        longitude,
        radius,
    )


    # ========================================================
    # CALL OVERPASS
    # ========================================================

    data = request_overpass(
        query
    )


    # ========================================================
    # PROCESS RAW RESULTS
    # ========================================================

    places = []


    for element in data.get(
        "elements",
        [],
    ):

        tags = element.get(
            "tags",
            {}
        )


        # ----------------------------------------------------
        # PLACE NAME
        # ----------------------------------------------------

        name = (
            tags.get("name:en")
            or tags.get("name")
        )


        if not name:

            continue


        # ----------------------------------------------------
        # GET COORDINATES
        # ----------------------------------------------------

        if element["type"] == "node":

            place_latitude = element.get(
                "lat"
            )

            place_longitude = element.get(
                "lon"
            )

        else:

            center = element.get(
                "center",
                {}
            )

            place_latitude = center.get(
                "lat"
            )

            place_longitude = center.get(
                "lon"
            )


        if (
            place_latitude is None
            or place_longitude is None
        ):

            continue


        # ----------------------------------------------------
        # CATEGORY
        # ----------------------------------------------------

        category = classify_place(
            tags
        )


        # ----------------------------------------------------
        # REMOVE IRRELEVANT RECORDS
        # ----------------------------------------------------

        if category == "Other":

            continue


        # ----------------------------------------------------
        # DISTANCE
        # ----------------------------------------------------

        distance_km = calculate_distance_km(
            latitude,
            longitude,
            place_latitude,
            place_longitude,
        )


        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        description = (
            tags.get("description:en")
            or tags.get("description")
            or ""
        )


        # ----------------------------------------------------
        # WIKIPEDIA
        # ----------------------------------------------------

        wikipedia = (
            tags.get("wikipedia")
            or ""
        )


        # ----------------------------------------------------
        # WEBSITE
        # ----------------------------------------------------

        website = (
            tags.get("website")
            or tags.get("contact:website")
            or ""
        )


        # ----------------------------------------------------
        # OPENING HOURS
        # ----------------------------------------------------

        opening_hours = (
            tags.get("opening_hours")
            or ""
        )


        # ----------------------------------------------------
        # CREATE PLACE OBJECT
        # ----------------------------------------------------

        place = {

            "name":
                name,

            "category":
                category,

            "latitude":
                place_latitude,

            "longitude":
                place_longitude,

            "distance_km":
                round(
                    distance_km,
                    2,
                ),

            "description":
                description,

            "wikipedia":
                wikipedia,

            "website":
                website,

            "opening_hours":
                opening_hours,
        }


        # ----------------------------------------------------
        # RELEVANCE SCORE
        # ----------------------------------------------------

        place["relevance_score"] = (
            calculate_relevance_score(
                place,
                distance_km,
            )
        )


        places.append(
            place
        )


    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    unique_places = {}


    for place in places:

        key = (
            place["name"].strip().lower(),
            round(
                place["latitude"],
                5,
            ),
            round(
                place["longitude"],
                5,
            ),
        )


        if key not in unique_places:

            unique_places[key] = place

        else:

            existing = unique_places[key]


            if (
                place["relevance_score"]
                >
                existing["relevance_score"]
            ):

                unique_places[key] = place


    places = list(
        unique_places.values()
    )


    # ========================================================
    # SORT BY RELEVANCE
    # ========================================================

    places.sort(
        key=lambda place: (
            place["relevance_score"],
            -place["distance_km"],
        ),
        reverse=True,
    )


    # ========================================================
    # LIMIT RESULTS
    # ========================================================

    places = places[
        :MAX_PLACES
    ]


    # ========================================================
    # REMOVE INTERNAL SCORE
    # ========================================================

    for place in places:

        place.pop(
            "relevance_score",
            None,
        )


    # ========================================================
    # RETURN
    # ========================================================

    return places