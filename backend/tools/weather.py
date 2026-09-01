import requests


# ============================================================
# OPEN-METEO WEATHER API
# ============================================================

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


# ============================================================
# GET WEATHER FOR EXACT TRAVEL DATES
# ============================================================

def get_weather(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
):
    """
    Get weather for the exact travel dates.

    Parameters
    ----------
    latitude : float
        Destination latitude.

    longitude : float
        Destination longitude.

    start_date : str
        Trip start date in YYYY-MM-DD format.

    end_date : str
        Trip end date in YYYY-MM-DD format.

    Returns
    -------
    dict
        Weather information for the requested travel period.
    """

    params = {
        # ----------------------------------------------------
        # LOCATION
        # ----------------------------------------------------

        "latitude": latitude,
        "longitude": longitude,


        # ----------------------------------------------------
        # EXACT TRAVEL DATE RANGE
        # ----------------------------------------------------

        "start_date": start_date,
        "end_date": end_date,


        # ----------------------------------------------------
        # CURRENT WEATHER
        # ----------------------------------------------------

        "current": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "weather_code",
            "precipitation",
            "wind_speed_10m",
        ]),


        # ----------------------------------------------------
        # HOURLY WEATHER
        # ----------------------------------------------------

        "hourly": ",".join([
            "temperature_2m",
            "precipitation_probability",
            "precipitation",
            "weather_code",
            "wind_speed_10m",
        ]),


        # ----------------------------------------------------
        # DAILY WEATHER
        # ----------------------------------------------------

        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
            "precipitation_sum",
            "sunrise",
            "sunset",
        ]),


        # ----------------------------------------------------
        # DESTINATION LOCAL TIMEZONE
        # ----------------------------------------------------

        "timezone": "auto",
    }


    try:

        response = requests.get(
            OPEN_METEO_URL,
            params=params,
            timeout=15,
        )


        # ----------------------------------------------------
        # IMPORTANT:
        # If Open-Meteo returns an error, print its
        # actual response so debugging is easier.
        # ----------------------------------------------------

        if not response.ok:

            print(
                "Open-Meteo status:",
                response.status_code
            )

            print(
                "Open-Meteo response:",
                response.text
            )

            response.raise_for_status()


        data = response.json()


        # ----------------------------------------------------
        # RETURN WEATHER DATA
        # ----------------------------------------------------

        return data


    except requests.exceptions.RequestException as error:

        raise RuntimeError(
            f"Weather API request failed: {error}"
        )