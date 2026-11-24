"""
AI Travel Planner - FastAPI Backend

This is the main API entry point.

Flow:

Frontend
    ↓
Location
Dates
Travelers
Budget
Preferences
User Query
    ↓
FastAPI
    ↓
Reverse Geocoding
    ↓
Travel Pipeline
    ├── Places
    ├── Filtering
    ├── Tourist Selection
    ├── Enrichment
    ├── Weather
    ├── Route
    ├── Itinerary
    └── Restaurants
    ↓
Groq LLM
    ↓
Structured AI Travel Plan
    ↓
Frontend
"""

from datetime import date
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.tools.geocoding import reverse_geocode
from backend.services.travel_pipeline import (
    build_travel_place_dataset,
)

load_dotenv()


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AI Travel Planner API",
    description=(
        "Backend API for an AI-powered travel planner "
        "using places, weather, routes, restaurants "
        "and a Groq-hosted LLM."
    ),
    version="2.0.0",
)


# ============================================================
# CORS (VERCEL + EXTERNAL WEBSITES + LOCAL DEV)
# ============================================================
# Set ALLOWED_ORIGINS in .env or Render as a comma-separated list, e.g.:
# ALLOWED_ORIGINS=https://your-app.vercel.app,https://other-site.com,http://localhost:5173
# Or set ALLOWED_ORIGINS=* to allow any website to call the API.

_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

_raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip()

if _raw_origins == "*":
    allowed_origins = ["*"]
    allow_credentials = False
elif _raw_origins:
    allowed_origins = list(
        dict.fromkeys(
            [
                origin.strip().rstrip("/")
                for origin in _raw_origins.split(",")
                if origin.strip()
            ]
            + _default_origins
        )
    )
    allow_credentials = True
else:
    allowed_origins = _default_origins
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class LocationRequest(BaseModel):
    """
    Data received from the React frontend.
    """

    # --------------------------------------------------------
    # LOCATION
    # --------------------------------------------------------

    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Destination latitude",
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Destination longitude",
    )

    # --------------------------------------------------------
    # TRIP DATES
    # --------------------------------------------------------

    start_date: str = Field(
        ...,
        description="Trip start date in YYYY-MM-DD format",
    )

    end_date: str = Field(
        ...,
        description="Trip end date in YYYY-MM-DD format",
    )

    # --------------------------------------------------------
    # TRAVELERS
    # --------------------------------------------------------

    travelers: Optional[int] = Field(
        default=1,
        ge=1,
        le=50,
        description="Number of travelers",
    )

    # --------------------------------------------------------
    # BUDGET
    # --------------------------------------------------------

    budget: Optional[str] = Field(
        default="",
        max_length=500,
        description="User's travel budget",
    )

    # --------------------------------------------------------
    # PREFERENCES
    # --------------------------------------------------------

    preferences: Optional[str] = Field(
        default="",
        max_length=2000,
        description=(
            "Travel preferences such as "
            "historical places, less walking, "
            "family friendly places, etc."
        ),
    )

    # --------------------------------------------------------
    # USER QUERY
    # --------------------------------------------------------

    user_query: Optional[str] = Field(
        default="",
        max_length=5000,
        description=(
            "Natural-language request from the traveler"
        ),
    )


# ============================================================
# DATE VALIDATION
# ============================================================

def validate_trip_dates(
    start_date: str,
    end_date: str,
) -> None:
    """
    Validate that dates use YYYY-MM-DD format
    and that the end date is not before the start date.
    """

    try:

        start = date.fromisoformat(
            start_date
        )

        end = date.fromisoformat(
            end_date
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid date format. "
                "Use YYYY-MM-DD."
            ),
        ) from error

    if end < start:

        raise HTTPException(
            status_code=400,
            detail=(
                "End date must be on or after "
                "the start date."
            ),
        )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "message": "AI Travel Planner API is running",
        "version": "2.0.0",
        "provider": "groq",
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        "status": "healthy",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():

    return {
        "status": "healthy",
        "provider": "groq",
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        "groq_api_key_configured": bool(os.getenv("GROQ_API_KEY")),
    }


# ============================================================
# COMPLETE TRAVEL DATA ENDPOINT
# ============================================================

@app.post("/location")
def receive_location(
    location: LocationRequest,
):
    """
    Generate complete travel information.

    The frontend sends:

        latitude
        longitude
        start_date
        end_date
        travelers
        budget
        preferences
        user_query

    The backend then builds the complete travel dataset
    and generates the structured AI travel plan.
    """

    # ========================================================
    # 1. VALIDATE DATES
    # ========================================================

    validate_trip_dates(
        location.start_date,
        location.end_date,
    )


    # ========================================================
    # 2. CLEAN USER INPUT
    # ========================================================

    travelers = (
        location.travelers
        if location.travelers is not None
        else 1
    )

    budget = (
        location.budget.strip()
        if location.budget
        else ""
    )

    preferences = (
        location.preferences.strip()
        if location.preferences
        else ""
    )

    user_query = (
        location.user_query.strip()
        if location.user_query
        else ""
    )


    # ========================================================
    # 3. PROCESS TRAVEL REQUEST
    # ========================================================

    try:

        # ====================================================
        # REVERSE GEOCODING
        # ====================================================

        location_data = reverse_geocode(
            location.latitude,
            location.longitude,
        )

        if not isinstance(
            location_data,
            dict,
        ):
            location_data = {}


        # ====================================================
        # DETERMINE LOCATION NAME
        # ====================================================

        location_name = (
            location_data.get("city")
            or location_data.get("town")
            or location_data.get("village")
            or location_data.get("municipality")
            or "Selected destination"
        )


        # ====================================================
        # BUILD COMPLETE TRAVEL DATASET
        # ====================================================

        travel_data = build_travel_place_dataset(

            latitude=location.latitude,

            longitude=location.longitude,

            location_name=location_name,

            max_places=10,

            itinerary_places=10,

            start_date=location.start_date,

            end_date=location.end_date,

            user_query=user_query,

            travelers=travelers,

            budget=budget,

            preferences=preferences,
        )


        # ====================================================
        # RETURN RESPONSE
        # ====================================================

        return {

            "message": (
                "Travel data and AI travel plan "
                "generated successfully."
            ),


            # ==================================================
            # TRIP
            # ==================================================

            "trip": {

                "start_date":
                    location.start_date,

                "end_date":
                    location.end_date,

                "travelers":
                    travelers,

                "budget":
                    budget,

                "preferences":
                    preferences,

                "user_query":
                    user_query,
            },


            # ==================================================
            # LOCATION
            # ==================================================

            "location":
                location_data,


            # ==================================================
            # WEATHER
            #
            # Kept in backend response because the frontend
            # may need it later, but it does not have to be
            # displayed as a large weather section.
            # ==================================================

            "weather":
                travel_data.get(
                    "weather"
                ),


            # ==================================================
            # PLACES
            # ==================================================

            "places": {

                "search_radius_km":
                    travel_data.get(
                        "search_radius_km",
                        10,
                    ),

                "raw_place_count":
                    travel_data.get(
                        "raw_place_count",
                        0,
                    ),

                "filtered_place_count":
                    travel_data.get(
                        "filtered_place_count",
                        0,
                    ),

                "tourist_selected_count":
                    travel_data.get(
                        "tourist_selected_count",
                        0,
                    ),

                "enriched_place_count":
                    travel_data.get(
                        "enriched_place_count",
                        0,
                    ),

                "final_place_count":
                    travel_data.get(
                        "final_place_count",
                        0,
                    ),

                "items":
                    travel_data.get(
                        "places",
                        [],
                    ),
            },


            # ==================================================
            # ROUTE
            # ==================================================

            "route":
                travel_data.get(
                    "route",
                    {},
                ),


            # ==================================================
            # ITINERARY
            # ==================================================

            "itinerary":
                travel_data.get(
                    "itinerary",
                    {},
                ),


            # ==================================================
            # RESTAURANTS
            #
            # This remains available to the frontend/backend,
            # but the final UI will not need to display all
            # restaurants separately.
            # ==================================================

            "restaurants":
                travel_data.get(
                    "restaurants",
                    {
                        "count": 0,
                        "items": [],
                    },
                ),


            # ==================================================
            # AI TRAVEL PLAN
            #
            # This is the main user-facing result.
            # ==================================================

            "ai_recommendation":
                travel_data.get(
                    "ai_recommendation"
                ),
        }


    # ========================================================
    # HTTP ERRORS
    # ========================================================

    except HTTPException:

        raise


    # ========================================================
    # GENERAL ERRORS
    # ========================================================

    except Exception as error:

        print(
            "Travel data error:",
            repr(error),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not generate the complete "
                "travel plan. Check the backend "
                "terminal for details."
            ),
        ) from error