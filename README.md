# 🤖 AI Travel Planner

An AI-powered travel planning application that creates personalized, budget-aware travel itineraries using real-time location data, weather information, route optimization, nearby restaurants, and a Groq-hosted LLM.

The application is designed to take a traveler's destination, dates, preferences, number of travelers, and budget, then generate a practical day-by-day travel plan.

---

## 🔗 Live Links & Demo

- **Frontend (Vercel):** [https://ai-travel-planner-five-theta.vercel.app](https://ai-travel-planner-five-theta.vercel.app)
- **Backend (Render):** [https://ai-travel-planner-1-qxvb.onrender.com](https://ai-travel-planner-1-qxvb.onrender.com)
- **Backend Health Check:** [https://ai-travel-planner-1-qxvb.onrender.com/health](https://ai-travel-planner-1-qxvb.onrender.com/health)


# 🎥 Project Demo

The uploaded screen recording demonstrates the AI Travel Planner interface and a **personalized budget-aware itinerary** workflow.

### Demo video

![AI Travel Planner Demo](VIDEO/ai-travel-planner-demo.gif)
[▶️ Watch the full-quality demo video](VIDEO/Watch%20Demo%20Video.mp4)

The demonstrated workflow includes:

1. User selects destination, travel dates, budget, and preferences.
2. Backend runs the 9-step travel pipeline (places, weather, route optimization, and nearby restaurants).
3. Groq LLM (`openai/gpt-oss-120b`) generates the structured day-by-day itinerary and cost breakdown.
---

## 📌 Project Overview

The AI Travel Planner combines traditional backend services with an LLM to produce a personalized itinerary.

The user provides:

- Destination
- Trip start and end dates
- Number of travelers
- Total budget
- Travel preferences
- Food preferences
- Walking/travel requirements
- Additional instructions in natural language

The backend then collects and processes travel data before sending the relevant information to the AI model.

The final response contains:

- Recommended attractions
- Historical/background information
- Reasons to visit
- Things to see
- Daily itinerary
- Nearby restaurants
- Approximate food costs
- Attraction costs
- Transportation costs
- Daily cost estimates
- Complete trip budget
- Remaining budget
- Budget status
- Practical travel tips

---

## 🏗️ System Architecture

![AI Travel Planner Architecture](AI-Travel-Planner-Architecture.png)

*High-level architecture of the AI Travel Planner, showing the frontend, FastAPI backend, travel pipeline, external services, Groq LLM, and final travel-plan response.*

### High-Level Flow

```text
                    ┌─────────────────────┐
                    │        USER         │
                    │ Destination         │
                    │ Dates               │
                    │ Preferences         │
                    │ Travelers + Budget  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ React + Vite        │
                    │ Frontend            │
                    │                     │
                    │ Map / Forms / Plan  │
                    │ Budget Display      │
                    └──────────┬──────────┘
                               │ HTTP / JSON
                               ▼
              ┌──────────────────────────────────┐
              │          FastAPI Backend         │
              │                                  │
              │          Travel Pipeline         │
              │                                  │
              │  1. Search Places                │
              │  2. Filter / Rank                │
              │  3. Select Attractions           │
              │  4. Enrich Place Information     │
              │  5. Get Weather                  │
              │  6. Optimize Route               │
              │  7. Find Restaurants             │
              │  8. Generate Itinerary           │
              │  9. Generate AI Travel Plan      │
              └──────────────┬───────────────────┘
                             │
             ┌───────────────┼──────────────────┐
             │               │                  │
             ▼               ▼                  ▼
      ┌────────────┐  ┌──────────────┐  ┌──────────────┐
      │ Overpass / │  │ Open-Meteo   │  │ OSRM         │
      │ Nominatim  │  │ Weather API  │  │ Route API    │
      │ OpenStreet │  │              │  │              │
      │ Map data   │  │              │  │              │
      └────────────┘  └──────────────┘  └──────────────┘
             │
             ▼
      ┌──────────────┐
      │ Wikipedia /  │
      │ fallback     │
      │ information  │
      └──────────────┘

                             │
                             ▼
                  ┌──────────────────────┐
                  │ Groq API             │
                  │                      │
                  │ openai/gpt-oss-120b  │
                  │                      │
                  │ Generates structured │
                  │ travel recommendation│
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ JSON Response        │
                  │                      │
                  │ Itinerary + Budget   │
                  │ Restaurants + Tips   │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ React Travel Plan UI │
                  └──────────────────────┘