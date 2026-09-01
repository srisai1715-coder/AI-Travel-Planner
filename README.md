# 🤖 AI Travel Planner

An AI-powered travel planning application that creates personalized, budget-aware travel itineraries using real-time location data, weather information, route optimization, nearby restaurants, and an NVIDIA-hosted LLM.

The application is designed to take a traveler's destination, dates, preferences, number of travelers, and budget, then generate a practical day-by-day travel plan.

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

*High-level architecture of the AI Travel Planner, showing the frontend, FastAPI backend, travel pipeline, external services, NVIDIA LLM, and final travel-plan response.*

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
                    │ Frontend             │
                    │                     │
                    │ Map / Forms / Plan   │
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
              │  6. Optimize Route              │
              │  7. Find Restaurants             │
              │  8. Generate Itinerary            │
              │  9. Generate AI Travel Plan      │
              └──────────────┬───────────────────┘
                             │
             ┌───────────────┼──────────────────┐
             │               │                  │
             ▼               ▼                  ▼
      ┌────────────┐  ┌──────────────┐  ┌──────────────┐
      │ Overpass / │  │ Open-Meteo   │  │ OSRM         │
      │ OpenStreet │  │ Weather API  │  │ Route API    │
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
                  │ NVIDIA AI API        │
                  │                      │
                  │ openai/gpt-oss-20b   │
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
```

---

## 🧩 Main Components

### 1. Frontend

The frontend is built using:

- React
- Vite
- JavaScript
- Leaflet map integration

The frontend is responsible for:

- Destination selection
- Interactive map
- Date selection
- Travel request form
- User preferences
- Budget input
- Sending requests to the backend
- Displaying the generated itinerary
- Showing attraction details
- Showing restaurant recommendations
- Displaying the complete budget

---

### 2. FastAPI Backend

The backend exposes API endpoints and coordinates the travel-planning workflow.

The backend is responsible for:

- Receiving user input
- Calling external APIs
- Processing travel data
- Ranking attractions
- Enriching place information
- Finding restaurants
- Optimizing routes
- Passing structured data to the LLM
- Validating the AI response
- Returning JSON to the frontend

---

## 🔄 Travel Pipeline

The main travel pipeline follows this sequence:

```text
User Request
     │
     ▼
Search Nearby Places
     │
     ▼
Filter & Rank Places
     │
     ▼
Select Suitable Attractions
     │
     ▼
Enrich Place Information
     │
     ▼
Get Weather
     │
     ▼
Optimize Route
     │
     ▼
Search Nearby Restaurants
     │
     ▼
Generate Itinerary
     │
     ▼
Generate AI Travel Plan
     │
     ▼
Validate JSON
     │
     ▼
Return Final Plan
```

This separation is important because the LLM is not responsible for discovering all raw travel information by itself. The backend first gathers useful data and then provides that data to the model.

---

## 🛠️ Tools and External Services

### OpenStreetMap / Overpass API

Used for:

- Finding nearby attractions
- Finding places of interest
- Finding nearby restaurants

### Wikipedia

Used for:

- Historical information
- Place background
- Additional descriptions

A fallback mechanism is used when Wikipedia cannot be accessed or is rate-limited.

### Open-Meteo

Used for:

- Weather forecasts
- Weather-related travel notes

### OSRM

Used for:

- Route optimization
- Distance estimation
- Travel route information

### NVIDIA API

Used for the AI generation layer.

Current model:

```text
openai/gpt-oss-20b
```

The NVIDIA API is accessed through an OpenAI-compatible client.

---

## 🤖 AI / LLM Layer

The LLM receives structured travel information together with the user's natural-language request.

For example:

```text
Destination:
Hyderabad

Dates:
2026-08-29 to 2026-08-31

Travelers:
2

Budget:
₹10,000

Preferences:
Historical places, forts, palaces, museums,
less walking and local food
```

The model is instructed to produce a structured travel plan rather than an ordinary conversational answer.

The generated response is expected to contain JSON fields such as:

```text
title
trip_overview
trip_summary
highlights
days
trip_budget
important_places
travel_tips
```

Each day can contain:

```text
morning
lunch
afternoon
evening
evening_snack
dinner
day_cost
day_tip
```

---

## 💰 Budget Calculation

The planner tracks the main trip-cost categories:

```text
Attractions
Food
Transportation
Accommodation
Other
```

The final budget contains:

```text
Total Budget
Estimated Trip Cost
Remaining Budget
Budget Status
```

Example:

```text
Budget:              ₹5,000
Estimated Cost:      ₹1,150 - ₹1,750
Remaining Budget:    ₹3,250 - ₹3,850
Status:              Within Budget
```

Accommodation is not included unless accommodation data is supplied.

---

## 🍽️ Restaurant Recommendations

Restaurants are searched near the selected attraction.

The objective is to keep meals geographically close to the itinerary instead of recommending restaurants randomly across the city.

The generated plan can include:

- Restaurant name
- Location/address
- Approximate cost
- Meal timing
- Attraction the restaurant is near

---

## 🗺️ Route Optimization

The route service helps arrange attractions in a practical order.

The goal is to reduce unnecessary travel between selected places.

This is especially useful when the user specifies requirements such as:

```text
Less walking
Traveling with parents
Comfortable itinerary
Avoid too many places in one day
```

---

## 📁 Project Structure

A typical project structure is:

```text
AI-Travel-Planner/
│
├── backend/
│   ├── services/
│   │   ├── itinerary_generator.py
│   │   ├── llm_service.py
│   │   └── travel_pipeline.py
│   │
│   ├── tools/
│   │   ├── geocoding.py
│   │   ├── place_enrichment.py
│   │   ├── place_filter.py
│   │   ├── places.py
│   │   ├── restaurant_search.py
│   │   ├── route_optimizer.py
│   │   ├── tourist_selector.py
│   │   └── weather.py
│   │
│   └── main.py
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   └── App.jsx
│   │
│   ├── package.json
│   └── vite.config.*
│
├── .env
├── .gitignore
└── README.md
```

---

## 🔌 Important Backend Modules

### `llm_service.py`

Responsible for:

- Creating the NVIDIA/OpenAI-compatible client
- Sending prompts to the LLM
- Generating the travel recommendation
- Parsing the model response
- Validating the generated JSON
- Handling LLM errors

### `travel_pipeline.py`

Responsible for coordinating the complete travel-data workflow.

It connects:

```text
Places
   ↓
Filtering
   ↓
Enrichment
   ↓
Weather
   ↓
Route
   ↓
Restaurants
   ↓
LLM
```

### `places.py`

Handles place discovery.

### `place_filter.py`

Filters and ranks places according to relevance.

### `place_enrichment.py`

Adds additional information to selected attractions.

### `tourist_selector.py`

Selects suitable tourist attractions.

### `restaurant_search.py`

Searches for restaurants close to attractions.

### `route_optimizer.py`

Calculates practical routes.

### `weather.py`

Gets weather information.

### `itinerary_generator.py`

Helps organize selected places into an itinerary.

---

## ▶️ How to Run the Project

### 1. Clone or open the project

Open the project folder in VS Code.

### 2. Create and activate the Python environment

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install backend dependencies

```powershell
pip install -r requirements.txt
```

If your project uses a different dependency file, install the dependencies specified by that file.

### 4. Configure environment variables

Create a `.env` file in the project root.

Example:

```env
NVIDIA_API_KEY=your_nvidia_api_key
```

Do not commit the real API key to GitHub.

---

## ▶️ Start the Backend

From the project root:

```powershell
uvicorn backend.main:app --reload
```

The FastAPI backend should then be available on the configured local server.

---

## ▶️ Start the Frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Vite will provide the local frontend URL.

Open that URL in your browser.

---

## 🧪 Testing the NVIDIA Connection

A simple connection test can be performed with:

```powershell
python -c "from backend.services.llm_service import test_nvidia_connection; print(test_nvidia_connection())"
```

A successful response confirms that the NVIDIA API connection is working.

---

## 🧪 Testing the LLM Travel Recommendation

A small one-day test is recommended before testing a larger trip.

Example:

```powershell
python -c "from backend.services.llm_service import generate_travel_recommendation; print(generate_travel_recommendation(destination='Hyderabad',start_date='2026-08-29',end_date='2026-08-29',places=[{'name':'Charminar','category':'Monument','description':'Historic monument in Hyderabad'}],user_query='Create a simple 1-day Hyderabad travel plan for 2 people. Include Charminar, why to visit, short history, one nearby local restaurant and approximate costs.',travelers=2,budget='₹3000',preferences='Historical places, less walking, local food'))"
```

Testing one day first is useful because a large multi-day response requires considerably more output from the LLM.

---

## ⚠️ Common Problems

### 1. `LLM returned invalid JSON`

This means the model responded, but the response could not be parsed as the JSON structure expected by the backend.

Possible causes:

- Model returned markdown
- Model added explanatory text
- Response was truncated
- Response structure did not match the expected schema
- The request was too large

The application should validate and handle the response instead of assuming every LLM response is valid.

---

### 2. `LLM returned an empty response`

This means the API call completed but no usable text was available in the response.

Check:

- NVIDIA API availability
- Model response
- `max_tokens`
- request size
- timeout settings

---

### 3. `ReadTimeout`

Example:

```text
httpx.ReadTimeout
```

This means the client waited for the NVIDIA API response longer than the configured timeout.

Large travel-plan requests can take longer because the model has to generate a much larger structured response.

A small request may succeed while a large three-day request times out.

---

### 4. Overpass timeout

Example:

```text
504 Server Error: Gateway Timeout
```

Overpass is an external service. It can occasionally be slow or unavailable.

The project already uses retry behavior for Overpass requests.

---

### 5. Wikipedia rate limiting

Wikipedia may temporarily reject or slow down repeated requests.

The project uses fallback information when Wikipedia cannot be accessed.

---

## 🔐 Security

Never commit API keys.

Add `.env` to `.gitignore`:

```gitignore
.env
venv/
__pycache__/
node_modules/
```

Use environment variables for API credentials.

---

## 🧠 Is This an AI Agent or Agentic AI?

The project is best described as an **AI-powered travel planning system with an agentic-style workflow**, rather than claiming it is a fully autonomous multi-agent system.

The backend performs multiple sequential tasks:

```text
Search
→ Filter
→ Enrich
→ Weather
→ Route
→ Restaurants
→ Itinerary
→ LLM Planning
```

These components work together to solve the user's travel-planning task.

However, the current architecture does **not** require several independent autonomous agents communicating with each other.

### Current architecture

```text
User
 ↓
FastAPI
 ↓
Travel Pipeline
 ├── Places Tool
 ├── Filtering
 ├── Enrichment
 ├── Weather Tool
 ├── Route Tool
 ├── Restaurant Tool
 └── LLM
      ↓
   Travel Plan
```

So for a project presentation, a technically accurate description is:

> **"An AI-powered travel planner that uses an agentic workflow, external tools, real-time travel data, and an LLM to generate personalized itineraries."**

---

## 🧰 Tools Used

The major tools/services are:

| Tool / Service | Purpose |
|---|---|
| React | Frontend UI |
| Vite | Frontend development/build |
| Leaflet | Interactive map |
| FastAPI | Backend API |
| Python | Backend implementation |
| Overpass API | Places and restaurant discovery |
| OpenStreetMap | Location/place data |
| Wikipedia | Historical/background information |
| Open-Meteo | Weather information |
| OSRM | Route optimization |
| NVIDIA API | LLM inference |
| `openai/gpt-oss-20b` | AI model |

---

## 📊 Data Flow

```text
                    USER
                     │
                     ▼
              React Frontend
                     │
                     ▼
               FastAPI API
                     │
                     ▼
             Travel Pipeline
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
     Places       Weather       Route
        │            │            │
        └────────────┼────────────┘
                     ▼
                Restaurants
                     │
                     ▼
              Enriched Data
                     │
                     ▼
                NVIDIA LLM
                     │
                     ▼
              Structured JSON
                     │
                     ▼
              Budget + Itinerary
                     │
                     ▼
               React UI
```

---

## 🎯 Main Features

- 📍 Interactive destination selection
- 📅 Flexible trip dates
- 👨‍👩‍👧 Traveler count
- 💰 Budget-aware planning
- 🏛️ Historical and cultural attraction recommendations
- 🍽️ Nearby restaurant recommendations
- 🌦️ Weather-aware planning
- 🗺️ Route optimization
- 🚶 Less-walking preferences
- 📊 Daily cost breakdown
- 💵 Complete trip budget
- 🤖 LLM-generated personalized itinerary
- 📱 Responsive frontend interface

---

## 🚀 Example User Request

```text
I am travelling with my parents.

My total budget is ₹5,000 for the entire trip.

I prefer historical places, forts, palaces and museums.

We prefer less walking because I am travelling with my parents.

Keep the itinerary comfortable and realistic.

For every important place, explain its history,
why it is important, what I should see,
interesting facts and approximate costs.

Recommend nearby local restaurants and include
food, transportation and attraction costs.
```

The system converts this natural-language request into structured planning requirements.

---

## 📋 Expected Output

The final travel plan can contain:

```text
Trip Overview

Trip Highlights

Day 1
 ├── Morning
 ├── Lunch
 ├── Afternoon
 ├── Evening Snack
 ├── Evening
 └── Dinner

Day 2
 └── ...

Day 3
 └── ...

Complete Trip Budget
 ├── Attractions
 ├── Food
 ├── Transportation
 ├── Accommodation
 ├── Other
 ├── Estimated Total
 ├── Remaining Budget
 └── Budget Status

Practical Travel Tips
```

---

## 🔮 Future Improvements

Possible improvements include:

- More reliable structured-output validation
- Streaming LLM responses
- Better retry and fallback handling
- Persistent trip storage
- Hotel/accommodation search
- Flight and train integration
- Real-time ticket-price APIs
- User accounts and saved trips
- Multi-language support
- Better accessibility options
- More advanced route optimization
- Dedicated autonomous planning agents
- Tool-calling based LLM orchestration
- Cost verification using live pricing sources

---

## 👨‍💻 Project Goal

The goal of this project is to build a practical AI travel assistant that does more than provide generic tourist suggestions.

It combines:

```text
Natural Language Understanding
+
Real-Time Travel Data
+
External Tools/APIs
+
Route Optimization
+
Weather Information
+
Restaurant Discovery
+
Budget Calculation
+
LLM Reasoning
```

to create a personalized travel plan based on the user's actual requirements.

---

## 📄 License

This project is intended for educational and project-demonstration purposes.
