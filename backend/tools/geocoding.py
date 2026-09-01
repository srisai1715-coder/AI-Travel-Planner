import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


def reverse_geocode(latitude: float, longitude: float) -> dict:
    """
    Convert latitude and longitude into a human-readable location.
    """

    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 18,
    }

    headers = {
        "User-Agent": "AI-Travel-Planner/1.0"
    }

    response = requests.get(
        NOMINATIM_URL,
        params=params,
        headers=headers,
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    address = data.get("address", {})

    return {
        "latitude": latitude,
        "longitude": longitude,

        "village": address.get("village"),
        "town": address.get("town"),
        "city": address.get("city"),

        "district": (
            address.get("county")
            or address.get("state_district")
        ),

        "state": address.get("state"),
        "country": address.get("country"),
        "country_code": address.get("country_code"),

        "display_name": data.get("display_name"),
    }