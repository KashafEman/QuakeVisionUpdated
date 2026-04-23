---
title: QuakeVision Backend
emoji: 🌍
colorFrom: red
colorTo: orange
sdk: docker
pinned: false
---
# QuakeVision - Earthquake Damage Prediction API

An API for predicting earthquake damage based on seismic parameters and soil type.

## Features

- Predict Peak Ground Acceleration (PGA) using Random Forest model
- Analyze potential damage levels based on PGA
- Support for 5 soil types: Alluvial, Medium, Rock/Stiff, Sandy, Soft
- RESTful API with FastAPI
- Automatic OpenAPI documentation

## API Endpoints

### 1. GET `/soil-types`
Get all valid soil types for frontend dropdown.

### 2. POST `/predict-damage`
Predict earthquake damage based on seismic parameters.

**Request Body:**
```json
{
  "magnitude": 6.5,
  "depth": 15.0,
  "distance_from_fault": 25.0,
  "soil_type": "rock/stiff soil"
}
```

### 3. POST `/urban_planning/home-safety-retrofit`
"Home Safety & Retrofit Guide"- Personalized safety scores and Japanese-standard retrofit recipes.

**Request Body:**
```json
{
  "city_name": "string",
  "sector_name": "string",
  "material": "string",
  "magnitude": 0,
  "height": 0
}
```

### 4. POST `/urban_planning/developer-site-planner`
 " Developer Site & Safety Planner"- Compliance, safety grades, and land-use advisory for new projects.

**Request Body:**
```json
{
  "city_name": "string",
  "site_sector": "string",
  "project_type": "string",
  "target_magnitude": 0
}
```

### 5. POST `/urban_planning/regional-retrofit-strategist`
 "Regional Retrofit Strategist" - Data-driven resource allocation and priority-based mitigation plans.

**Request Body:**
```json
{
  "city_name": "string",
  "sector_name": "string",
  "retrofit_capacity": 0,
  "priority_metric": "string",
  "retrofit_style": "string"
  "target_magnitude": 0
}
```




