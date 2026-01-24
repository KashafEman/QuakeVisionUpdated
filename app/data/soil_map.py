KNOWN_CITY_SOILS = [
    # Existing cities
    {"city": "Islamabad", "lat": 33.6844, "lon": 73.0479, "soil": "Rock/Stiff Soil"},
    {"city": "Peshawar", "lat": 34.0151, "lon": 71.5249, "soil": "Soft Soil"},
    {"city": "Lahore", "lat": 31.5497, "lon": 74.3436, "soil": "Soft Soil"},
    {"city": "Karachi", "lat": 24.8607, "lon": 67.0011, "soil": "Soft Soil"},
    {"city": "Quetta", "lat": 30.1798, "lon": 66.9750, "soil": "Rock/Stiff Soil"},

    # Punjab
    {"city": "Faisalabad", "lat": 31.4187, "lon": 73.0791, "soil": "Soft Soil"},
    {"city": "Multan", "lat": 30.1575, "lon": 71.5249, "soil": "Soft Soil"},
    {"city": "Rawalpindi", "lat": 33.5651, "lon": 73.0169, "soil": "Rock/Stiff Soil"},
    {"city": "Gujranwala", "lat": 32.1877, "lon": 74.1945, "soil": "Soft Soil"},
    {"city": "Sialkot", "lat": 32.4945, "lon": 74.5229, "soil": "Soft Soil"},

    # Sindh
    {"city": "Hyderabad", "lat": 25.3960, "lon": 68.3578, "soil": "Soft Soil"},
    {"city": "Sukkur", "lat": 27.7052, "lon": 68.8574, "soil": "Soft Soil"},

    # KPK
    {"city": "Abbottabad", "lat": 34.1688, "lon": 73.2215, "soil": "Rock/Stiff Soil"},
    {"city": "Mardan", "lat": 34.1986, "lon": 72.0404, "soil": "Soft Soil"},
    {"city": "Swat", "lat": 34.7717, "lon": 72.3604, "soil": "Rock/Stiff Soil"},

    # Balochistan
    {"city": "Gwadar", "lat": 25.1216, "lon": 62.3254, "soil": "Soft Soil"},
    {"city": "Khuzdar", "lat": 27.8116, "lon": 66.6100, "soil": "Rock/Stiff Soil"},

    # Azad Kashmir
    {"city": "Muzaffarabad", "lat": 34.3700, "lon": 73.4708, "soil": "Rock/Stiff Soil"},
    {"city": "Mirpur", "lat": 33.1478, "lon": 73.7516, "soil": "Soft Soil"},
    {"city": "Rawalakot", "lat": 33.8578, "lon": 73.7604, "soil": "Rock/Stiff Soil"},

    # Gilgit-Baltistan
    {"city": "Gilgit", "lat": 35.9208, "lon": 74.3146, "soil": "Rock/Stiff Soil"},
    {"city": "Skardu", "lat": 35.2971, "lon": 75.6333, "soil": "Rock/Stiff Soil"},
    {"city": "Hunza", "lat": 36.3167, "lon": 74.6500, "soil": "Rock/Stiff Soil"},
]

def get_soil_type_by_city(city_name: str) -> str:
    """
    Returns soil type for a given city.
    Defaults to 'Rock/Stiff Soil' if city is not found.
    """
    for entry in KNOWN_CITY_SOILS:
        if entry["city"].lower() == city_name.lower():
            return entry["soil"]

    # Safe conservative default
    return "Rock/Stiff Soil"