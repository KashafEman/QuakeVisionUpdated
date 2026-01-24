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


