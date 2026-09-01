import { useEffect, useMemo, useState } from "react";

import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap,
  useMapEvents,
} from "react-leaflet";

import L from "leaflet";

import "leaflet/dist/leaflet.css";

// ============================================================
// LEAFLET MARKER FIX
// ============================================================

delete L.Icon.Default.prototype._getIconUrl;

L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// ============================================================
// MAP LOCATION SELECTOR
// ============================================================

function LocationSelector({ onLocationSelect, disabled }) {
  useMapEvents({
    click(event) {
      if (disabled) return;

      onLocationSelect({
        latitude: event.latlng.lat,
        longitude: event.latlng.lng,
      });
    },
  });

  return null;
}

// ============================================================
// MAP VIEW CONTROLLER
// ============================================================

function MapViewController({ location }) {
  const map = useMap();

  useEffect(() => {
    if (!location) return;

    map.flyTo(
      [Number(location.latitude), Number(location.longitude)],
      13,
      { duration: 1.2 }
    );
  }, [location, map]);

  return null;
}

// ============================================================
// HELPERS
// ============================================================

function formatDate(dateString) {
  if (!dateString) return "";

  const parts = String(dateString).split("-");

  if (parts.length !== 3) return dateString;

  const date = new Date(
    Number(parts[0]),
    Number(parts[1]) - 1,
    Number(parts[2])
  );

  return date.toLocaleDateString("en-IN", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

function calculateTripDays(startDate, endDate) {
  if (!startDate || !endDate) return 0;

  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);

  const difference = end.getTime() - start.getTime();

  if (difference < 0) return 0;

  return Math.floor(difference / (1000 * 60 * 60 * 24)) + 1;
}

function getCategoryIcon(category) {
  const value = String(category || "").toLowerCase();

  if (
    value.includes("historical") ||
    value.includes("fort") ||
    value.includes("palace")
  ) {
    return "🏛️";
  }

  if (value.includes("museum") || value.includes("culture")) {
    return "🏺";
  }

  if (
    value.includes("nature") ||
    value.includes("park") ||
    value.includes("zoo")
  ) {
    return "🌳";
  }

  if (
    value.includes("religious") ||
    value.includes("temple") ||
    value.includes("mosque") ||
    value.includes("church")
  ) {
    return "🛕";
  }

  return "📍";
}

function getTouristPlaceTypeLabel(type) {
  if (!type) return "";

  const labels = {
    major_historical: "Major Historical Place",
    historical: "Historical Place",
    nature: "Nature Place",
    park: "Park / Recreation",
    religious: "Religious Place",
    tourist_attraction: "Tourist Attraction",
    statue: "Statue / Landmark",
  };

  return labels[type] || String(type).replaceAll("_", " ");
}

function displayValue(value, fallback = "") {
  if (value === null || value === undefined) return fallback;

  if (typeof value === "string") {
    return value.trim() || fallback;
  }

  return String(value);
}

function firstValue(object, keys, fallback = "") {
  if (!object || typeof object !== "object") return fallback;

  for (const key of keys) {
    const value = object[key];

    if (
      value !== undefined &&
      value !== null &&
      String(value).trim() !== ""
    ) {
      return value;
    }
  }

  return fallback;
}

function getArray(value) {
  return Array.isArray(value) ? value : [];
}

function formatINR(value) {
  if (value === null || value === undefined || value === "") return "";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return `₹${number.toLocaleString("en-IN")}`;
}

function formatCostRange(cost) {
  if (!cost || typeof cost !== "object") return "";

  const min = firstValue(cost, ["min", "minimum", "min_total"]);
  const max = firstValue(cost, ["max", "maximum", "max_total"]);

  if (min !== "" && max !== "") {
    return `${formatINR(min)}–${formatINR(max)}`;
  }

  if (min !== "") return formatINR(min);
  if (max !== "") return formatINR(max);

  const amount = firstValue(cost, [
    "amount",
    "amount_per_person",
    "total",
    "total_cost",
    "estimated_cost",
    "price",
  ]);

  return amount !== "" ? formatINR(amount) : "";
}

function restaurantCost(restaurant) {
  if (!restaurant || typeof restaurant !== "object") return "";

  const direct = firstValue(restaurant, [
    "approximate_cost",
    "approx_cost",
    "estimated_cost",
    "cost",
    "price",
    "price_range",
    "food_cost",
    "meal_cost",
  ]);

  if (direct && typeof direct === "object") {
    return formatCostRange(direct);
  }

  if (direct !== "") {
    const text = String(direct).trim();
    return text.startsWith("₹") ? text : formatINR(text);
  }

  return "";
}

function getBudgetObject(plan) {
  if (!plan || typeof plan !== "object") return null;

  return (
    plan.trip_budget ||
    plan.budget ||
    plan.budget_summary ||
    plan.cost_summary ||
    null
  );
}

function budgetStatusLabel(status) {
  const value = String(status || "").toLowerCase();

  if (value.includes("within")) return "Within Budget";
  if (value.includes("over")) return "Over Budget";
  if (value.includes("warning")) return "Budget Warning";

  return status ? String(status) : "";
}

// ============================================================
// STRUCTURED AI DATA NORMALIZATION
// ============================================================

function normalizeAIRecommendation(value) {
  if (!value) return null;

  if (typeof value === "object") {
    return value;
  }

  if (typeof value !== "string") {
    return null;
  }

  const text = value.trim();

  if (!text) return null;

  try {
    const parsed = JSON.parse(text);

    if (parsed && typeof parsed === "object") {
      return parsed;
    }
  } catch {
    // The response may be normal markdown/text.
  }

  return {
    title: "AI Travel Plan",
    trip_overview: text,
    highlights: [],
    days: [],
    important_places: [],
    travel_tips: [],
  };
}

// ============================================================
// TIME HELPERS
// ============================================================

function getTimeText(item) {
  if (!item || typeof item !== "object") return "";

  const direct = firstValue(item, [
    "time",
    "time_range",
    "time_slot",
    "timing",
    "schedule",
    "duration",
  ]);

  if (direct) return String(direct);

  const start = firstValue(item, [
    "start_time",
    "from",
    "start",
  ]);

  const end = firstValue(item, [
    "end_time",
    "to",
    "end",
  ]);

  if (start && end) {
    return `${start} → ${end}`;
  }

  if (start) return String(start);

  return "";
}

function getActivityName(activity) {
  if (!activity || typeof activity !== "object") return "";

  return firstValue(activity, [
    "place_name",
    "place",
    "name",
    "attraction",
    "location",
    "site",
    "title",
  ]);
}

function getActivityCategory(activity) {
  return firstValue(activity, [
    "category",
    "type",
    "place_type",
    "tourist_place_type",
  ]);
}

function getActivityText(activity, keys) {
  return firstValue(activity, keys, "");
}

// ============================================================
// RESTAURANT NORMALIZATION
// ============================================================

function normalizeRestaurantList(source) {
  if (!source) return [];

  if (Array.isArray(source)) {
    return source;
  }

  if (typeof source !== "object") {
    return [];
  }

  const candidates = [
    source.restaurants,
    source.options,
    source.items,
    source.recommendations,
    source.restaurant_options,
  ];

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate;
    }
  }

  if (source.best_choice) {
    const alternatives = getArray(source.alternatives);

    return [
      source.best_choice,
      ...alternatives,
    ];
  }

  return [];
}

function restaurantName(restaurant) {
  return firstValue(restaurant, [
    "name",
    "restaurant_name",
    "place_name",
    "title",
  ], "Restaurant");
}

function restaurantDistance(restaurant) {
  const value = firstValue(restaurant, [
    "distance_km",
    "distance",
  ]);

  if (value === "") return "";

  return `${value} km`;
}

function restaurantScore(restaurant) {
  const value = firstValue(restaurant, [
    "restaurant_quality_score",
    "quality_score",
    "score",
    "rating",
  ]);

  return value === "" ? "" : value;
}

function restaurantCategory(restaurant) {
  return firstValue(restaurant, [
    "category",
    "type",
    "cuisine",
  ]);
}

function restaurantReason(restaurant) {
  return firstValue(restaurant, [
    "why",
    "reason",
    "recommendation_reason",
    "why_recommended",
    "notes",
  ]);
}

function restaurantRank(index) {
  if (index === 0) return "🥇 Best Choice";
  if (index === 1) return "🥈 Alternative";
  if (index === 2) return "🥉 Alternative";
  return "🍽️ Alternative";
}

// ============================================================
// DAY DATA HELPERS
// ============================================================

function getDayNumber(day, index) {
  const value = firstValue(day, [
    "day",
    "day_number",
    "day_index",
  ]);

  if (value !== "") return value;

  return index + 1;
}

function getDayDate(day, fallbackDate) {
  return firstValue(day, [
    "date",
    "day_date",
    "trip_date",
  ], fallbackDate);
}

function getDayActivities(day) {
  if (!day || typeof day !== "object") return [];

  const candidates = [
    day.activities,
    day.attractions,
    day.places,
    day.visits,
    day.schedule,
  ];

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) return candidate;
  }

  return [];
}

function getSectionObject(day, keys) {
  if (!day || typeof day !== "object") return null;

  for (const key of keys) {
    const value = day[key];

    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value)
    ) {
      return value;
    }
  }

  return null;
}

function getSectionRestaurants(section) {
  return normalizeRestaurantList(section);
}

function activityHour(activity) {
  const text = getTimeText(activity).toLowerCase();

  const match = text.match(
    /(?:^|[^0-9])([0-2]?[0-9])(?::([0-5][0-9]))?\s*(am|pm)?/
  );

  if (!match) return null;

  let hour = Number(match[1]);
  const meridiem = match[3];

  if (meridiem === "pm" && hour < 12) hour += 12;
  if (meridiem === "am" && hour === 12) hour = 0;

  return hour;
}

function classifyActivity(activity) {
  const explicit = String(
    firstValue(activity, [
      "period",
      "section",
      "time_of_day",
      "part_of_day",
    ])
  ).toLowerCase();

  if (explicit.includes("morning")) return "morning";
  if (explicit.includes("afternoon")) return "afternoon";
  if (explicit.includes("evening")) return "evening";

  const hour = activityHour(activity);

  if (hour === null) return "morning";

  if (hour < 12) return "morning";
  if (hour < 17) return "afternoon";

  return "evening";
}

function sortActivitiesByTime(activities) {
  return [...activities].sort((a, b) => {
    const hourA = activityHour(a);
    const hourB = activityHour(b);

    if (hourA === null && hourB === null) return 0;
    if (hourA === null) return 1;
    if (hourB === null) return -1;

    return hourA - hourB;
  });
}

function getActivityDescription(activity) {
  return getActivityText(activity, [
    "description",
    "background",
    "details",
  ]);
}

function getWhyVisit(activity) {
  return getActivityText(activity, [
    "why_visit",
    "why",
    "reason",
  ]);
}

function getHistory(activity) {
  return getActivityText(activity, [
    "history",
    "historical_background",
    "background",
    "wikipedia_description",
  ]);
}

function getWhatToSee(activity) {
  return getActivityText(activity, [
    "what_to_see",
    "highlights",
    "things_to_see",
    "key_highlights",
  ]);
}

function getActivityTip(activity) {
  return getActivityText(activity, [
    "tip",
    "travel_tip",
    "notes",
  ]);
}

// ============================================================
// RESTAURANT SECTION
// ============================================================

function RestaurantOptions({
  restaurants,
  mealTitle,
  nearbyPlace,
  timeText,
}) {
  const list = normalizeRestaurantList(restaurants);

  if (list.length === 0) {
    return (
      <div className="restaurant-empty">
        <div className="restaurant-empty-title">
          🍽️ No nearby restaurant found
        </div>

        <div>
          No suitable restaurant was returned near{" "}
          <strong>{nearbyPlace || "your current attraction"}</strong>.
          The AI can use the nearest practical option if one is
          available in the travel data.
        </div>
      </div>
    );
  }

  return (
    <div className="meal-section">
      <div className="meal-heading-row">
        <div>
          <div className="meal-title">{mealTitle}</div>

          {timeText && (
            <div className="meal-time">
              🕐 {timeText}
            </div>
          )}
        </div>

        {nearbyPlace && (
          <div className="nearby-badge">
            📍 Near {nearbyPlace}
          </div>
        )}
      </div>

      <div className="restaurant-grid">
        {list.slice(0, 3).map((restaurant, index) => {
          const distance = restaurantDistance(restaurant);
          const score = restaurantScore(restaurant);
          const category = restaurantCategory(restaurant);
          const reason = restaurantReason(restaurant);

          return (
            <div className="restaurant-card" key={`${restaurantName(restaurant)}-${index}`}>
              <div className="restaurant-rank">
                {restaurantRank(index)}
              </div>

              <h4>{restaurantName(restaurant)}</h4>

              <div className="restaurant-meta">
                {distance && <span>📍 {distance}</span>}
                {category && <span>🍴 {category}</span>}
                {score !== "" && (
                  <span>⭐ Quality: {score}/100</span>
                )}
                {restaurantCost(restaurant) && (
                  <span>💰 Approx. food cost: {restaurantCost(restaurant)}</span>
                )}
              </div>

              {reason && (
                <p className="restaurant-reason">
                  <strong>Why:</strong> {reason}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div className="restaurant-recommendation">
        <strong>Recommended:</strong>{" "}
        {restaurantName(list[0])}
      </div>
    </div>
  );
}

// ============================================================
// ACTIVITY CARD
// ============================================================

function ActivityCard({ activity }) {
  if (!activity || typeof activity !== "object") return null;

  const name = getActivityName(activity) || "Attraction";
  const category = getActivityCategory(activity);
  const timeText = getTimeText(activity);

  const whyVisit = getWhyVisit(activity);
  const history = getHistory(activity);
  const whatToSee = getWhatToSee(activity);
  const description = getActivityDescription(activity);
  const tip = getActivityTip(activity);

  return (
    <div className="activity-card">
      <div className="activity-time">
        {timeText || "Suggested time"}
      </div>

      <div className="activity-title">
        {getCategoryIcon(category)} {name}
      </div>

      {category && (
        <div className="activity-type">
          {getTouristPlaceTypeLabel(category)}
        </div>
      )}

      {description && (
        <div className="activity-block">
          <div className="activity-label">About</div>
          <p>{description}</p>
        </div>
      )}

      {whyVisit && (
        <div className="activity-block">
          <div className="activity-label">Why visit</div>
          <p>{whyVisit}</p>
        </div>
      )}

      {history && (
        <div className="activity-block">
          <div className="activity-label">History</div>
          <p>{history}</p>
        </div>
      )}

      {whatToSee && (
        <div className="activity-block">
          <div className="activity-label">What to see</div>
          <p>{whatToSee}</p>
        </div>
      )}

      {tip && (
        <div className="activity-tip">
          💡 {tip}
        </div>
      )}
    </div>
  );
}

// ============================================================
// DAY PLAN
// ============================================================

function DayPlan({
  day,
  index,
  startDate,
  destination,
}) {
  const dayNumber = getDayNumber(day, index);

  const fallbackDate = (() => {
    if (!startDate) return "";

    const date = new Date(`${startDate}T00:00:00`);
    date.setDate(date.getDate() + index);

    return date.toISOString().split("T")[0];
  })();

  const date = getDayDate(day, fallbackDate);

  const activities = sortActivitiesByTime(
    getDayActivities(day)
  );

  const morningActivities = activities.filter(
    (activity) => classifyActivity(activity) === "morning"
  );

  const afternoonActivities = activities.filter(
    (activity) => classifyActivity(activity) === "afternoon"
  );

  const eveningActivities = activities.filter(
    (activity) => classifyActivity(activity) === "evening"
  );

  const lunch = getSectionObject(day, [
    "lunch",
    "lunch_recommendation",
    "lunch_plan",
  ]);

  const eveningSnack = getSectionObject(day, [
    "evening_snack",
    "snacks",
    "evening_snacks",
    "snack",
  ]);

  const dinner = getSectionObject(day, [
    "dinner",
    "dinner_recommendation",
    "dinner_plan",
  ]);

  const dayTip = firstValue(day, [
    "day_tip",
    "tip",
    "travel_tip",
    "notes",
  ]);

  const dayCost =
    day?.day_cost ||
    day?.daily_cost ||
    day?.cost_summary ||
    null;

  // ----------------------------------------------------------
  // If backend did not separate activities into morning/
  // afternoon/evening, use explicit sections when available.
  // ----------------------------------------------------------

  const morningSection = getSectionObject(day, [
    "morning",
    "morning_plan",
  ]);

  const afternoonSection = getSectionObject(day, [
    "afternoon",
    "afternoon_plan",
  ]);

  const eveningSection = getSectionObject(day, [
    "evening",
    "evening_plan",
  ]);

  const finalMorning =
    morningActivities.length > 0
      ? morningActivities
      : getArray(morningSection?.activities);

  const finalAfternoon =
    afternoonActivities.length > 0
      ? afternoonActivities
      : getArray(afternoonSection?.activities);

  const finalEvening =
    eveningActivities.length > 0
      ? eveningActivities
      : getArray(eveningSection?.activities);

  const lunchRestaurants =
    getSectionRestaurants(lunch);

  const snackRestaurants =
    getSectionRestaurants(eveningSnack);

  const dinnerRestaurants =
    getSectionRestaurants(dinner);

  // ----------------------------------------------------------
  // If the backend stores restaurants directly on an activity,
  // the activity itself can still expose them.
  // ----------------------------------------------------------

  function activityRestaurants(activity) {
    return normalizeRestaurantList(
      activity?.restaurants ||
      activity?.nearby_restaurants ||
      activity?.restaurant_options
    );
  }

  return (
    <section className="day-card">
      <div className="day-header">
        <div className="day-number">
          Day {dayNumber}
        </div>

        {date && (
          <div className="day-date">
            {formatDate(date)}
          </div>
        )}
      </div>

      <div className="day-content">
        {/* ==================================================
            MORNING
        ================================================== */}

        {(finalMorning.length > 0 || morningSection) && (
          <div className="day-section">
            <div className="section-heading">
              <span>🌅</span>
              <span>Morning</span>
            </div>

            {finalMorning.map((activity, activityIndex) => (
              <div key={`morning-${activityIndex}`}>
                <ActivityCard activity={activity} />

                {activityRestaurants(activity).length > 0 && (
                  <RestaurantOptions
                    restaurants={activityRestaurants(activity)}
                    mealTitle="🍽️ Nearby Food"
                    nearbyPlace={getActivityName(activity)}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* ==================================================
            LUNCH
        ================================================== */}

        {lunch && (
          <div className="day-section">
            <RestaurantOptions
              restaurants={lunchRestaurants}
              mealTitle="🍽️ Lunch"
              nearbyPlace={
                firstValue(lunch, [
                  "nearby_place",
                  "near_place",
                  "location",
                  "after_place",
                  "attraction",
                  "place_visited_before",
                ]) ||
                (finalMorning.length > 0
                  ? getActivityName(
                      finalMorning[finalMorning.length - 1]
                    )
                  : destination)
              }
              timeText={getTimeText(lunch)}
            />
          </div>
        )}

        {/* ==================================================
            AFTERNOON
        ================================================== */}

        {(finalAfternoon.length > 0 || afternoonSection) && (
          <div className="day-section">
            <div className="section-heading">
              <span>🌇</span>
              <span>Afternoon</span>
            </div>

            {finalAfternoon.map((activity, activityIndex) => (
              <div key={`afternoon-${activityIndex}`}>
                <ActivityCard activity={activity} />

                {activityRestaurants(activity).length > 0 && (
                  <RestaurantOptions
                    restaurants={activityRestaurants(activity)}
                    mealTitle="🍽️ Nearby Food"
                    nearbyPlace={getActivityName(activity)}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* ==================================================
            EVENING
        ================================================== */}

        {(finalEvening.length > 0 || eveningSection) && (
          <div className="day-section">
            <div className="section-heading">
              <span>🌆</span>
              <span>Evening</span>
            </div>

            {finalEvening.map((activity, activityIndex) => (
              <div key={`evening-${activityIndex}`}>
                <ActivityCard activity={activity} />

                {activityRestaurants(activity).length > 0 && (
                  <RestaurantOptions
                    restaurants={activityRestaurants(activity)}
                    mealTitle="🍽️ Nearby Food"
                    nearbyPlace={getActivityName(activity)}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* ==================================================
            EVENING SNACK
        ================================================== */}

        {eveningSnack && (
          <div className="day-section">
            <RestaurantOptions
              restaurants={snackRestaurants}
              mealTitle="☕ Evening Snack"
              nearbyPlace={
                firstValue(eveningSnack, [
                  "nearby_place",
                  "near_place",
                  "location",
                  "after_place",
                  "attraction",
                  "place_visited_before",
                ]) ||
                (finalEvening.length > 0
                  ? getActivityName(
                      finalEvening[finalEvening.length - 1]
                    )
                  : finalAfternoon.length > 0
                  ? getActivityName(
                      finalAfternoon[finalAfternoon.length - 1]
                    )
                  : destination)
              }
              timeText={getTimeText(eveningSnack)}
            />
          </div>
        )}

        {/* ==================================================
            DINNER
        ================================================== */}

        {dinner && (
          <div className="day-section">
            <RestaurantOptions
              restaurants={dinnerRestaurants}
              mealTitle="🍴 Dinner"
              nearbyPlace={
                firstValue(dinner, [
                  "nearby_place",
                  "near_place",
                  "location",
                  "after_place",
                  "attraction",
                  "place_visited_before",
                ]) ||
                destination
              }
              timeText={getTimeText(dinner)}
            />
          </div>
        )}

        {/* ==================================================
            DAY BUDGET
        ================================================== */}

        {dayCost && (
          <div className="day-budget-card">
            <div className="plan-section-title">💰 Day Budget</div>

            <div className="day-budget-grid">
              <div className="budget-item">
                <span>Attractions</span>
                <strong>
                  {formatCostRange({
                    min: dayCost.attractions_min,
                    max: dayCost.attractions_max,
                  }) || "₹0"}
                </strong>
              </div>

              <div className="budget-item">
                <span>Food</span>
                <strong>
                  {formatCostRange({
                    min: dayCost.food_min,
                    max: dayCost.food_max,
                  }) || "₹0"}
                </strong>
              </div>

              <div className="budget-item">
                <span>Transportation</span>
                <strong>
                  {formatCostRange({
                    min: dayCost.transport_min,
                    max: dayCost.transport_max,
                  }) || "₹0"}
                </strong>
              </div>

              <div className="budget-item">
                <span>Accommodation</span>
                <strong>
                  {formatCostRange({
                    min: dayCost.accommodation_min,
                    max: dayCost.accommodation_max,
                  }) || "₹0"}
                </strong>
              </div>

              <div className="budget-item budget-total">
                <span>Daily Total</span>
                <strong>
                  {formatCostRange({
                    min: dayCost.total_min,
                    max: dayCost.total_max,
                  }) || "₹0"}
                </strong>
              </div>
            </div>

            {dayCost.notes && (
              <div className="budget-note">{dayCost.notes}</div>
            )}
          </div>
        )}

        {/* ==================================================
            DAY TIP
        ================================================== */}

        {dayTip && (
          <div className="day-tip">
            <strong>💡 Day Tip</strong>
            <p>{dayTip}</p>
          </div>
        )}
      </div>
    </section>
  );
}


// ============================================================
// TRIP BUDGET
// ============================================================

function TripBudget({ plan }) {
  const budget = getBudgetObject(plan);

  if (!budget) return null;

  const estimated = budget.estimated_total || budget.total_trip_cost;
  const remaining = budget.remaining_budget;

  const categories = [
    ["Attractions", budget.attractions],
    ["Food", budget.food],
    ["Transportation", budget.transportation],
    ["Accommodation", budget.accommodation],
    ["Other", budget.other],
  ];

  return (
    <div className="trip-budget-card">
      <div className="plan-section-title">💰 Complete Trip Budget</div>

      <div className="budget-top-row">
        <div className="budget-highlight">
          <span>Total Budget</span>
          <strong>
            {budget.budget_amount !== undefined
              ? formatINR(budget.budget_amount)
              : "Not specified"}
          </strong>
        </div>

        {estimated && (
          <div className="budget-highlight">
            <span>Estimated Trip Cost</span>
            <strong>{formatCostRange(estimated)}</strong>
          </div>
        )}

        {remaining && (
          <div className="budget-highlight">
            <span>Remaining Budget</span>
            <strong>{formatCostRange(remaining)}</strong>
          </div>
        )}

        {budgetStatusLabel(budget.budget_status || budget.status) && (
          <div className="budget-highlight">
            <span>Status</span>
            <strong>{budgetStatusLabel(budget.budget_status || budget.status)}</strong>
          </div>
        )}
      </div>

      <div className="budget-category-grid">
        {categories.map(([label, value]) => (
          <div className="budget-category" key={label}>
            <span>{label}</span>
            <strong>{formatCostRange(value) || "₹0"}</strong>
          </div>
        ))}
      </div>

      {budget.summary && (
        <div className="budget-summary">
          <strong>Budget Summary</strong>
          <p>{budget.summary}</p>
        </div>
      )}
    </div>
  );
}

// ============================================================
// AI TRAVEL PLAN
// ============================================================

function StructuredAIPlan({
  recommendation,
  startDate,
  endDate,
  destination,
}) {
  const plan = normalizeAIRecommendation(recommendation);

  if (!plan) return null;

  const highlights = getArray(plan.highlights);
  const days = getArray(plan.days);

  const overview =
    firstValue(plan, [
      "trip_overview",
      "overview",
      "summary",
      "description",
    ]);

  const travelTips = getArray(
    plan.travel_tips || plan.tips
  );

  const planError = firstValue(plan, ["error", "message"], "");

  return (
    <section className="ai-plan-section">
      <div className="ai-plan-header">
        <div className="ai-plan-icon">🤖</div>

        <div>
          <h2>
            {firstValue(
              plan,
              ["title"],
              "Your AI Travel Plan"
            )}
          </h2>

          <p>
            Your itinerary is personalized using your
            destination, dates, travel preferences,
            weather, route and nearby restaurants.
          </p>
        </div>
      </div>

      {/* ======================================================
          TRIP OVERVIEW
      ====================================================== */}

      {planError && (
        <div className="error-message">
          <strong>Travel plan generation issue:</strong> {planError}
        </div>
      )}

      {overview && (
        <div className="overview-card">
          <div className="plan-section-title">
            🧳 Trip Overview
          </div>

          <p>{overview}</p>
        </div>
      )}

      {/* ======================================================
          HIGHLIGHTS
      ====================================================== */}

      {highlights.length > 0 && (
        <div className="highlights-card">
          <div className="plan-section-title">
            ✨ Trip Highlights
          </div>

          <div className="highlight-grid">
            {highlights.map((item, index) => {
              const text =
                typeof item === "string"
                  ? item
                  : firstValue(item, [
                      "name",
                      "place",
                      "title",
                      "text",
                      "description",
                    ]);

              return (
                <div
                  className="highlight-item"
                  key={`highlight-${index}`}
                >
                  <span>✓</span>
                  <span>{text}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ======================================================
          DAYS
      ====================================================== */}

      {days.length > 0 ? (
        <div className="days-container">
          {days.map((day, index) => (
            <DayPlan
              key={`day-${getDayNumber(day, index)}`}
              day={day}
              index={index}
              startDate={startDate}
              destination={destination}
            />
          ))}
        </div>
      ) : (
        <div className="text-plan-fallback">
          <pre>{String(recommendation)}</pre>
        </div>
      )}

      {/* ======================================================
          COMPLETE TRIP BUDGET
      ====================================================== */}

      <TripBudget plan={plan} />

      {/* ======================================================
          TRAVEL TIPS
      ====================================================== */}

      {travelTips.length > 0 && (
        <div className="tips-card">
          <div className="plan-section-title">
            🧭 Practical Travel Tips
          </div>

          <ul>
            {travelTips.map((tip, index) => (
              <li key={`tip-${index}`}>
                {typeof tip === "string"
                  ? tip
                  : firstValue(tip, [
                      "text",
                      "tip",
                      "description",
                    ])}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

// ============================================================
// PLACE MARKER
// ============================================================

function PlaceMarker({ place }) {
  if (
    place?.latitude === undefined ||
    place?.longitude === undefined
  ) {
    return null;
  }

  return (
    <Marker
      position={[
        Number(place.latitude),
        Number(place.longitude),
      ]}
    >
      <Popup>
        <strong>{place.name}</strong>

        <br />

        {place.category && (
          <>
            {getCategoryIcon(place.category)}{" "}
            {place.category}
            <br />
          </>
        )}

        {place.distance_km !== undefined && (
          <>
            📍 {place.distance_km} km away
            <br />
          </>
        )}

        {place.tourist_place_type && (
          <>
            ⭐{" "}
            {getTouristPlaceTypeLabel(
              place.tourist_place_type
            )}
          </>
        )}
      </Popup>
    </Marker>
  );
}

// ============================================================
// MAIN APP
// ============================================================

function App() {
  // ==========================================================
  // LOCATION
  // ==========================================================

  const [selectedLocation, setSelectedLocation] = useState(null);
  const [lockedLocation, setLockedLocation] = useState(null);
  const [locationDetails, setLocationDetails] = useState(null);

  // ==========================================================
  // TRAVEL DATA
  // ==========================================================

  const [places, setPlaces] = useState(null);
  const [route, setRoute] = useState(null);
  const [itinerary, setItinerary] = useState(null);
  const [aiRecommendation, setAiRecommendation] = useState(null);

  // ==========================================================
  // DATES
  // ==========================================================

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // ==========================================================
  // USER QUERY
  // ==========================================================

  const [userQuery, setUserQuery] = useState("");

  // ==========================================================
  // UI
  // ==========================================================

  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  // ==========================================================
  // TODAY
  // ==========================================================

  const today = new Date().toISOString().split("T")[0];

  const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

  // ==========================================================
  // QUERY PLACEHOLDER
  // ==========================================================

  const userQueryPlaceholder = `Tell the AI exactly what you want from your trip.

Example:

My total budget is ₹10,000 for the whole trip.

I am travelling with my parents.

I prefer historical places, museums and famous landmarks.

I prefer less walking and a relaxed itinerary.

I want good local food within my budget.

If I visit Golconda Fort from 10:00 AM to 12:00 PM,
find lunch restaurants near Golconda Fort.
Do not send me back to the original destination just
for lunch.

For every lunch, recommend 2 or 3 nearby restaurants
and clearly tell me which one is the best choice.

After lunch, continue with the next suitable attraction.

For evening snacks, search near the attraction I have
just visited and recommend suitable cafes or restaurants.

Do not use one restaurant list for the entire city.
Restaurant recommendations must be based on the attraction
I am currently visiting.

Use the weather information from the backend.

If rain is expected, adjust outdoor and indoor activities
accordingly.

For important historical places, explain:
• why I should visit
• history/background
• what I should see
• interesting facts

Create a practical day-by-day itinerary in chronological
order with exact suggested times.

Keep lunch immediately after the relevant morning attraction,
and keep evening snacks near the attraction visited before
the snack.

Do not show unnecessary backend or technical data in the
final travel plan.`;

  // ==========================================================
  // LOCATION SELECT
  // ==========================================================

  const handleLocationSelect = (location) => {
    if (lockedLocation) return;

    setSelectedLocation(location);

    setLocationDetails(null);
    setPlaces(null);
    setRoute(null);
    setItinerary(null);
    setAiRecommendation(null);

    setMessage(
      "Destination selected. Choose your trip dates and tell the AI what you want."
    );
  };

  // ==========================================================
  // START DATE
  // ==========================================================

  const handleStartDateChange = (event) => {
    const value = event.target.value;

    setStartDate(value);

    setAiRecommendation(null);
    setItinerary(null);
    setRoute(null);

    if (value && endDate && endDate < value) {
      setMessage(
        "The selected end date is before the new start date. Please choose a valid end date."
      );
    } else {
      setMessage("");
    }
  };

  // ==========================================================
  // END DATE
  // ==========================================================

  const handleEndDateChange = (event) => {
    const value = event.target.value;

    setEndDate(value);

    setAiRecommendation(null);
    setItinerary(null);
    setRoute(null);

    if (!value) {
      setMessage("");
      return;
    }

    if (startDate && value < startDate) {
      setMessage(
        `End date cannot be before the start date. Please select ${formatDate(
          startDate
        )} or a later date.`
      );
      return;
    }

    setMessage("");
  };

  // ==========================================================
  // GENERATE PLAN
  // ==========================================================

  const handleGeneratePlan = async () => {
    if (!selectedLocation) {
      setMessage("Please select a destination on the map first.");
      return;
    }

    if (!startDate) {
      setMessage("Please select your trip start date.");
      return;
    }

    if (!endDate) {
      setMessage("Please select your trip end date.");
      return;
    }

    if (endDate < startDate) {
      setMessage("End date must be on or after the start date.");
      return;
    }

    if (!userQuery.trim()) {
      setMessage(
        "Please tell the AI what you want from your trip."
      );
      return;
    }

    setLoading(true);

    setMessage(
      "AI is analyzing your destination, attractions, route, nearby restaurants, weather and travel preferences..."
    );

    setAiRecommendation(null);
    setItinerary(null);
    setRoute(null);
    setPlaces(null);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180000);

    try {
      const response = await fetch(
        `${API_BASE_URL}/location`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            latitude: Number(selectedLocation.latitude),
            longitude: Number(selectedLocation.longitude),
            start_date: startDate,
            end_date: endDate,
            user_query: userQuery.trim(),
          }),
          signal: controller.signal,
        }
      );

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => null);

        throw new Error(
          errorData?.detail ||
            "Failed to generate the AI travel plan."
        );
      }

      const data = await response.json();

      console.log("Complete backend response:", data);

      // --------------------------------------------------------
      // LOCK DESTINATION
      // --------------------------------------------------------

      setLockedLocation(selectedLocation);

      // --------------------------------------------------------
      // STORE BACKEND DATA
      // --------------------------------------------------------

      setLocationDetails(data.location || null);
      setPlaces(data.places || null);
      setRoute(data.route || null);
      setItinerary(data.itinerary || null);

      // --------------------------------------------------------
      // AI RESULT
      // --------------------------------------------------------

      setAiRecommendation(
        data.ai_recommendation ??
          data.ai_plan ??
          data.recommendation ??
          null
      );

      setMessage(
        "AI travel plan generated successfully."
      );
    } catch (error) {
      console.error("Travel planning error:", error);

      if (error?.name === "AbortError") {
        setMessage(
          "The travel plan is taking too long. The backend request was stopped after 3 minutes. Check the backend terminal for the actual error."
        );
      } else {
        setMessage(
          error?.message ||
            "Could not connect to the backend."
        );
      }
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
    }
  };

  // ==========================================================
  // UNLOCK
  // ==========================================================

  const handleUnlockLocation = () => {
    setLockedLocation(null);

    setLocationDetails(null);
    setPlaces(null);
    setRoute(null);
    setItinerary(null);
    setAiRecommendation(null);

    setStartDate("");
    setEndDate("");

    setMessage(
      "Destination unlocked. Select another location on the map."
    );
  };

  // ==========================================================
  // DATA
  // ==========================================================

  const placeItems = Array.isArray(places?.items)
    ? places.items
    : [];

  const tripDays = useMemo(
    () => calculateTripDays(startDate, endDate),
    [startDate, endDate]
  );

  // ==========================================================
  // STYLES
  // ==========================================================

  const styles = {
    page: {
      width: "100%",
      maxWidth: "1250px",
      margin: "0 auto",
      padding: "32px 20px 50px",
      boxSizing: "border-box",
      fontFamily:
        "Inter, Arial, Helvetica, sans-serif",
      color: "#0f172a",
    },

    header: {
      marginBottom: "28px",
    },

    section: {
      width: "100%",
      marginBottom: "28px",
      padding: "24px",
      boxSizing: "border-box",
      borderRadius: "18px",
      background: "#ffffff",
      border: "1px solid #e2e8f0",
      boxShadow:
        "0 8px 25px rgba(15, 23, 42, 0.06)",
    },

    map: {
      height: "500px",
      width: "100%",
      borderRadius: "14px",
      overflow: "hidden",
      marginTop: "18px",
    },

    dateGrid: {
      display: "grid",
      gridTemplateColumns:
        "repeat(2, minmax(0, 1fr))",
      gap: "20px",
      marginTop: "20px",
    },

    dateField: {
      display: "flex",
      flexDirection: "column",
      gap: "9px",
    },

    dateLabel: {
      fontSize: "16px",
      fontWeight: "700",
    },

    dateInput: {
      width: "100%",
      height: "52px",
      padding: "10px 14px",
      border: "2px solid #cbd5e1",
      borderRadius: "10px",
      fontSize: "16px",
      boxSizing: "border-box",
      background: "#ffffff",
      color: "#0f172a",
    },

    querySection: {
      width: "100%",
      marginBottom: "28px",
      padding: "30px",
      boxSizing: "border-box",
      borderRadius: "20px",
      background:
        "linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)",
      border: "1px solid #dbe3ef",
      boxShadow:
        "0 10px 30px rgba(15, 23, 42, 0.07)",
    },

    textarea: {
      width: "100%",
      minWidth: "100%",
      maxWidth: "100%",
      minHeight: "360px",
      padding: "18px",
      boxSizing: "border-box",
      resize: "vertical",
      border: "2px solid #cbd5e1",
      borderRadius: "14px",
      outline: "none",
      fontSize: "16px",
      lineHeight: "1.65",
      fontFamily:
        "Inter, Arial, Helvetica, sans-serif",
      color: "#1e293b",
      background: "#ffffff",
    },

    generateButton: {
      width: "100%",
      marginTop: "24px",
      padding: "17px 24px",
      border: "none",
      borderRadius: "12px",
      background:
        "linear-gradient(135deg, #2563eb, #1d4ed8)",
      color: "#ffffff",
      fontSize: "17px",
      fontWeight: "700",
      cursor: loading
        ? "not-allowed"
        : "pointer",
      opacity: loading ? 0.7 : 1,
    },

    message: {
      padding: "15px 18px",
      marginBottom: "25px",
      borderRadius: "12px",
      background: "#eff6ff",
      border: "1px solid #bfdbfe",
      color: "#1e3a8a",
      fontWeight: "600",
    },
  };

  // ==========================================================
  // RESPONSIVE CSS + PLAN UI
  // ==========================================================

  const css = `
    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: #f1f5f9;
    }

    .travel-page {
      min-height: 100vh;
    }

    .query-help {
      margin-top: 20px;
      padding: 18px 20px;
      border-radius: 12px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
    }

    .query-help ul {
      margin: 10px 0 0;
      padding-left: 22px;
      line-height: 1.8;
      color: #334155;
    }

    .trip-summary {
      margin-top: 20px;
      padding: 20px;
      border-radius: 12px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
    }

    .ai-plan-section {
      width: 100%;
      margin: 28px 0;
      padding: 0;
      border-radius: 22px;
      overflow: hidden;
      background: #ffffff;
      border: 1px solid #dbe3ef;
      box-shadow: 0 12px 35px rgba(15, 23, 42, 0.08);
    }

    .ai-plan-header {
      display: flex;
      gap: 18px;
      align-items: flex-start;
      padding: 28px;
      background: linear-gradient(135deg, #eff6ff, #f8fafc);
      border-bottom: 1px solid #e2e8f0;
    }

    .ai-plan-icon {
      width: 54px;
      height: 54px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 54px;
      border-radius: 15px;
      background: #ffffff;
      font-size: 28px;
      box-shadow: 0 5px 18px rgba(15, 23, 42, 0.08);
    }

    .ai-plan-header h2 {
      margin: 0 0 7px;
      font-size: 29px;
    }

    .ai-plan-header p {
      margin: 0;
      color: #475569;
      line-height: 1.6;
    }

    .overview-card,
    .highlights-card,
    .tips-card {
      margin: 24px;
      padding: 22px;
      border-radius: 16px;
      border: 1px solid #e2e8f0;
      background: #ffffff;
    }

    .overview-card p {
      margin: 12px 0 0;
      line-height: 1.75;
      color: #334155;
      white-space: pre-line;
    }

    .plan-section-title {
      font-size: 21px;
      font-weight: 800;
      color: #0f172a;
    }

    .highlight-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }

    .highlight-item {
      display: flex;
      gap: 10px;
      align-items: flex-start;
      padding: 13px 15px;
      border-radius: 11px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      line-height: 1.5;
    }

    .highlight-item span:first-child {
      font-weight: 800;
      color: #2563eb;
    }

    .days-container {
      padding: 0 24px 24px;
    }

    .day-card {
      margin-top: 24px;
      border: 1px solid #dbe3ef;
      border-radius: 18px;
      overflow: hidden;
      background: #ffffff;
      box-shadow: 0 6px 20px rgba(15, 23, 42, 0.05);
    }

    .day-header {
      padding: 22px 24px;
      background: linear-gradient(135deg, #f8fafc, #eff6ff);
      border-bottom: 1px solid #dbe3ef;
    }

    .day-number {
      font-size: 25px;
      font-weight: 850;
      color: #0f172a;
    }

    .day-date {
      margin-top: 5px;
      color: #475569;
      font-size: 16px;
      font-weight: 600;
    }

    .day-content {
      padding: 24px;
    }

    .day-section {
      margin-bottom: 28px;
    }

    .day-section:last-child {
      margin-bottom: 0;
    }

    .section-heading {
      display: flex;
      gap: 9px;
      align-items: center;
      margin-bottom: 14px;
      font-size: 20px;
      font-weight: 800;
      color: #0f172a;
    }

    .activity-card {
      margin-bottom: 16px;
      padding: 20px;
      border-radius: 15px;
      background: #ffffff;
      border: 1px solid #dbe3ef;
      box-shadow: 0 3px 12px rgba(15, 23, 42, 0.04);
    }

    .activity-time {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 8px;
      background: #eff6ff;
      color: #1d4ed8;
      font-weight: 750;
      font-size: 14px;
      margin-bottom: 11px;
    }

    .activity-title {
      font-size: 21px;
      font-weight: 800;
      color: #0f172a;
    }

    .activity-type {
      display: inline-block;
      margin-top: 8px;
      padding: 5px 9px;
      border-radius: 7px;
      background: #f1f5f9;
      color: #475569;
      font-size: 13px;
      font-weight: 700;
    }

    .activity-block {
      margin-top: 16px;
    }

    .activity-label {
      font-weight: 800;
      color: #334155;
      margin-bottom: 4px;
    }

    .activity-block p {
      margin: 0;
      color: #475569;
      line-height: 1.7;
      white-space: pre-line;
    }

    .activity-tip {
      margin-top: 16px;
      padding: 12px 14px;
      border-radius: 10px;
      background: #fffbeb;
      border: 1px solid #fde68a;
      color: #92400e;
      line-height: 1.6;
    }

    .meal-section {
      margin: 16px 0;
      padding: 20px;
      border-radius: 15px;
      background: #f8fafc;
      border: 1px solid #dbe3ef;
    }

    .meal-heading-row {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }

    .meal-title {
      font-size: 21px;
      font-weight: 850;
      color: #0f172a;
    }

    .meal-time {
      margin-top: 5px;
      color: #475569;
      font-size: 14px;
      font-weight: 650;
    }

    .nearby-badge {
      padding: 8px 11px;
      border-radius: 9px;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      color: #334155;
      font-size: 14px;
      font-weight: 700;
    }

    .restaurant-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 13px;
    }

    .restaurant-card {
      padding: 16px;
      border-radius: 13px;
      background: #ffffff;
      border: 1px solid #dbe3ef;
    }

    .restaurant-rank {
      color: #1d4ed8;
      font-size: 14px;
      font-weight: 800;
      margin-bottom: 8px;
    }

    .restaurant-card h4 {
      margin: 0 0 10px;
      font-size: 17px;
      color: #0f172a;
    }

    .restaurant-meta {
      display: flex;
      flex-direction: column;
      gap: 5px;
      color: #475569;
      font-size: 13px;
    }

    .restaurant-reason {
      margin: 12px 0 0;
      color: #475569;
      font-size: 14px;
      line-height: 1.55;
    }

    .restaurant-recommendation {
      margin-top: 14px;
      padding: 11px 13px;
      border-radius: 9px;
      background: #eff6ff;
      color: #1e3a8a;
    }

    .restaurant-empty {
      padding: 16px;
      border-radius: 12px;
      background: #fff7ed;
      border: 1px solid #fed7aa;
      color: #9a3412;
      line-height: 1.55;
    }

    .restaurant-empty-title {
      font-weight: 800;
      margin-bottom: 5px;
    }

    .day-tip {
      margin-top: 22px;
      padding: 17px;
      border-radius: 13px;
      background: #f0fdf4;
      border: 1px solid #bbf7d0;
      color: #166534;
    }

    .day-tip p {
      margin: 7px 0 0;
      line-height: 1.65;
      white-space: pre-line;
    }

    .tips-card ul {
      margin: 14px 0 0;
      padding-left: 23px;
      line-height: 1.8;
      color: #475569;
    }

    .trip-budget-card,
    .day-budget-card {
      margin: 24px;
      padding: 22px;
      border-radius: 16px;
      border: 1px solid #dbe3ef;
      background: #f8fafc;
    }

    .day-budget-card {
      margin: 22px 0;
    }

    .budget-top-row,
    .day-budget-grid,
    .budget-category-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }

    .budget-highlight,
    .budget-category,
    .budget-item {
      padding: 15px;
      border-radius: 12px;
      background: #ffffff;
      border: 1px solid #e2e8f0;
    }

    .budget-highlight span,
    .budget-category span,
    .budget-item span {
      display: block;
      color: #64748b;
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 7px;
    }

    .budget-highlight strong,
    .budget-category strong,
    .budget-item strong {
      display: block;
      color: #0f172a;
      font-size: 18px;
    }

    .budget-total {
      border: 2px solid #bfdbfe;
      background: #eff6ff;
    }

    .budget-summary,
    .budget-note {
      margin-top: 16px;
      padding: 14px 16px;
      border-radius: 11px;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      color: #475569;
      line-height: 1.6;
    }

    .budget-summary p {
      margin: 6px 0 0;
    }

    .text-plan-fallback {
      margin: 24px;
      padding: 24px;
      border-radius: 14px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      overflow-x: auto;
    }

    .text-plan-fallback pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: inherit;
      line-height: 1.7;
    }

    .backend-summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }

    .summary-card {
      padding: 17px;
      border-radius: 11px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
    }

    .summary-number {
      display: block;
      margin-top: 7px;
      font-size: 23px;
      font-weight: 800;
    }

    .place-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }

    .place-card {
      padding: 18px;
      border-radius: 13px;
      border: 1px solid #e2e8f0;
      background: #ffffff;
    }

    .place-card h3 {
      margin-top: 0;
    }

    .route-item {
      padding: 12px 0;
      border-bottom: 1px solid #e2e8f0;
    }

    .error-message {
      margin-top: 10px;
      padding: 10px 12px;
      border-radius: 8px;
      background: #fef2f2;
      border: 1px solid #fecaca;
      color: #b91c1c;
      font-size: 14px;
    }

    @media (max-width: 900px) {
      .restaurant-grid {
        grid-template-columns: 1fr 1fr;
      }

      .backend-summary {
        grid-template-columns: 1fr 1fr;
      }
    }

    @media (max-width: 768px) {
      .travel-date-grid {
        grid-template-columns: 1fr !important;
      }

      .highlight-grid,
      .place-grid {
        grid-template-columns: 1fr;
      }

      .restaurant-grid {
        grid-template-columns: 1fr;
      }

      .travel-page {
        padding: 15px !important;
      }

      .ai-plan-header {
        padding: 20px;
      }

      .ai-plan-header h2 {
        font-size: 23px;
      }

      .days-container,
      .day-content {
        padding: 16px;
      }

      .overview-card,
      .highlights-card,
      .tips-card {
        margin: 16px;
      }

      .meal-heading-row {
        flex-direction: column;
      }

      .nearby-badge {
        width: fit-content;
      }

      .backend-summary {
        grid-template-columns: 1fr 1fr;
      }

      .budget-top-row,
      .day-budget-grid,
      .budget-category-grid {
        grid-template-columns: 1fr 1fr;
      }
    }

    @media (max-width: 480px) {
      .backend-summary {
        grid-template-columns: 1fr;
      }

      .day-number {
        font-size: 22px;
      }

      .budget-top-row,
      .day-budget-grid,
      .budget-category-grid {
        grid-template-columns: 1fr;
      }

      .activity-title {
        font-size: 18px;
      }
    }
  `;

  // ==========================================================
  // RENDER
  // ==========================================================

  return (
    <div className="travel-page" style={styles.page}>
      <style>{css}</style>

      {/* ======================================================
          HEADER
      ====================================================== */}

      <header style={styles.header}>
        <h1>🤖 AI Travel Planner</h1>

        <p>
          Select your destination, choose your dates,
          tell the AI what you want, and get a
          personalized travel plan.
        </p>
      </header>

      {/* ======================================================
          MAP
      ====================================================== */}

      <section style={styles.section}>
        <h2>🗺️ Select Your Destination</h2>

        <p>
          Click anywhere on the map to select your
          destination.
        </p>

        <MapContainer
          center={[20.5937, 78.9629]}
          zoom={5}
          style={styles.map}
        >
          <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <LocationSelector
            onLocationSelect={handleLocationSelect}
            disabled={Boolean(lockedLocation)}
          />

          <MapViewController
            location={selectedLocation}
          />

          {selectedLocation && (
            <Marker
              position={[
                Number(selectedLocation.latitude),
                Number(selectedLocation.longitude),
              ]}
            >
              <Popup>
                <strong>
                  Selected Destination
                </strong>

                <br />

                Latitude:{" "}
                {Number(
                  selectedLocation.latitude
                ).toFixed(6)}

                <br />

                Longitude:{" "}
                {Number(
                  selectedLocation.longitude
                ).toFixed(6)}
              </Popup>
            </Marker>
          )}

          {lockedLocation &&
            placeItems.map((place, index) => (
              <PlaceMarker
                key={`${place.name}-${index}`}
                place={place}
              />
            ))}
        </MapContainer>
      </section>

      {/* ======================================================
          DESTINATION
      ====================================================== */}

      <section style={styles.section}>
        <h2>📍 Destination</h2>

        {!selectedLocation && (
          <p>
            Click anywhere on the map to select a
            destination.
          </p>
        )}

        {selectedLocation && !lockedLocation && (
          <div>
            <p>
              <strong>Latitude:</strong>{" "}
              {Number(
                selectedLocation.latitude
              ).toFixed(6)}
            </p>

            <p>
              <strong>Longitude:</strong>{" "}
              {Number(
                selectedLocation.longitude
              ).toFixed(6)}
            </p>
          </div>
        )}

        {lockedLocation && (
          <div>
            <h3>🔒 Destination Locked</h3>

            {locationDetails && (
              <div>
                <p>
                  <strong>Village:</strong>{" "}
                  {locationDetails.village ||
                    "Not available"}
                </p>

                <p>
                  <strong>Town:</strong>{" "}
                  {locationDetails.town ||
                    "Not available"}
                </p>

                <p>
                  <strong>City:</strong>{" "}
                  {locationDetails.city ||
                    "Not available"}
                </p>

                <p>
                  <strong>District:</strong>{" "}
                  {locationDetails.district ||
                    "Not available"}
                </p>

                <p>
                  <strong>State:</strong>{" "}
                  {locationDetails.state ||
                    "Not available"}
                </p>

                <p>
                  <strong>Country:</strong>{" "}
                  {locationDetails.country ||
                    "Not available"}
                </p>
              </div>
            )}

            <button
              type="button"
              onClick={handleUnlockLocation}
              style={{
                padding: "11px 16px",
                border: "none",
                borderRadius: "9px",
                background: "#0f172a",
                color: "#ffffff",
                cursor: "pointer",
                fontWeight: "700",
              }}
            >
              🔓 Unlock Destination
            </button>
          </div>
        )}
      </section>

      {/* ======================================================
          DATES
      ====================================================== */}

      {selectedLocation && (
        <section style={styles.section}>
          <h2>📅 Trip Dates</h2>

          <p>
            Select your start and end dates.
          </p>

          <div
            className="travel-date-grid"
            style={styles.dateGrid}
          >
            <div style={styles.dateField}>
              <label
                htmlFor="start-date"
                style={styles.dateLabel}
              >
                Trip Start Date
              </label>

              <input
                id="start-date"
                type="date"
                value={startDate}
                min={today}
                onChange={handleStartDateChange}
                style={styles.dateInput}
              />
            </div>

            <div style={styles.dateField}>
              <label
                htmlFor="end-date"
                style={styles.dateLabel}
              >
                Trip End Date
              </label>

              <input
                id="end-date"
                type="date"
                value={endDate}
                min={startDate || today}
                onChange={handleEndDateChange}
                style={styles.dateInput}
              />

              {startDate &&
                endDate &&
                endDate < startDate && (
                  <div className="error-message">
                    End date must be on or after{" "}
                    {formatDate(startDate)}.
                  </div>
                )}
            </div>
          </div>

          {startDate &&
            endDate &&
            endDate >= startDate && (
              <div className="trip-summary">
                <h3>🧳 Trip Summary</h3>

                <p>
                  <strong>Start:</strong>{" "}
                  {formatDate(startDate)}
                </p>

                <p>
                  <strong>End:</strong>{" "}
                  {formatDate(endDate)}
                </p>

                <p>
                  <strong>Duration:</strong>{" "}
                  {tripDays}{" "}
                  {tripDays === 1
                    ? "day"
                    : "days"}
                </p>
              </div>
            )}
        </section>
      )}

      {/* ======================================================
          USER QUERY
      ====================================================== */}

      {selectedLocation && (
        <section
          className="travel-query-section"
          style={styles.querySection}
        >
          <h2>
            ✨ Tell the AI About Your Trip
          </h2>

          <p
            style={{
              color: "#475569",
              lineHeight: "1.6",
            }}
          >
            Tell the AI what you actually want.
            Your budget, interests, food preferences,
            travel style and restaurant requirements
            will be used to personalize the itinerary.
          </p>

          <label
            htmlFor="user-query"
            style={{
              display: "block",
              marginBottom: "10px",
              fontSize: "17px",
              fontWeight: "750",
            }}
          >
            Your Travel Request
          </label>

          <textarea
            id="user-query"
            value={userQuery}
            onChange={(event) =>
              setUserQuery(event.target.value)
            }
            placeholder={userQueryPlaceholder}
            rows={16}
            style={styles.textarea}
          />

          <div className="query-help">
            <h3>💡 You can tell the AI:</h3>

            <ul>
              <li>Your total budget</li>
              <li>Number of travellers</li>
              <li>Family, friends, solo or couple</li>
              <li>Places you prefer</li>
              <li>Places you do not want</li>
              <li>Food preferences</li>
              <li>Restaurant preferences</li>
              <li>Lunch timing</li>
              <li>Evening snack timing</li>
              <li>Walking preferences</li>
              <li>Transportation preferences</li>
              <li>Relaxed or busy itinerary</li>
              <li>Historical information you want</li>
              <li>What you want to do if it rains</li>
              <li>Any special requirements</li>
            </ul>
          </div>

          <button
            type="button"
            onClick={handleGeneratePlan}
            disabled={loading}
            style={styles.generateButton}
          >
            {loading
              ? "🤖 AI is Planning..."
              : "✨ Generate AI Travel Plan"}
          </button>
        </section>
      )}

      {/* ======================================================
          MESSAGE
      ====================================================== */}

      {message && (
        <div style={styles.message}>
          {message}
        </div>
      )}

      {/* ======================================================
          AI PLAN
      ====================================================== */}

      {aiRecommendation && (
        <StructuredAIPlan
          recommendation={aiRecommendation}
          startDate={startDate}
          endDate={endDate}
          destination={
            locationDetails?.city ||
            locationDetails?.town ||
            "your destination"
          }
        />
      )}

      {/* ======================================================
          FOOTER
      ====================================================== */}

      <footer
        style={{
          marginTop: "40px",
          padding: "25px",
          textAlign: "center",
          borderTop: "1px solid #e2e8f0",
          color: "#475569",
        }}
      >
        <h3>🤖 AI Travel Planner</h3>

        <p>
          Places • Routes • Weather • Restaurants • NVIDIA AI
        </p>
      </footer>
    </div>
  );
}

export default App;
