import numpy as np

# Encoding MUST match training
SOIL_TYPE_MAPPING = {
    "rock": 0,
    "stiff": 1,
    "soft": 2
}

def preprocess_input(input_data):
    """
    Converts API input into ML model-ready numerical format
    """

    soil_type = input_data.soil_type.lower()
    soil_encoded = SOIL_TYPE_MAPPING.get(soil_type, 1)  # default: stiff

    features = [
        input_data.magnitude,
        input_data.depth,
        input_data.distance_from_fault,
        soil_encoded
    ]

    # sklearn expects 2D array
    return np.array(features).reshape(1, -1)
