# test_model_directly.py
import joblib
import pandas as pd

# Load the model
model = joblib.load("app/models/trained_model.pkl")  # Update path if needed

print("=== Testing Model Directly ===")

# Test 1: What happens with different soil inputs
test_cases = [
    # (soil_input, description)
    (0, "Numeric code 0"),
    (1, "Numeric code 1"),
    (2, "Numeric code 2"),
    (3, "Numeric code 3"),
    (4, "Numeric code 4"),
    ("0", "String '0'"),
    ("1", "String '1'"),
    ("Alluvial Soil", "String 'Alluvial Soil'"),
    ("Medium Soil", "String 'Medium Soil'"),
]

for soil_input, desc in test_cases:
    try:
        df = pd.DataFrame([{
            'mag': 5.0,
            'depth': 10.0,
            'distance_km': 50.0,
            'soil_type': soil_input
        }])
        
        prediction = model.predict(df)[0]
        print(f"✓ {desc}: Success - Prediction: {prediction}")
    except Exception as e:
        error_msg = str(e)
        if "unknown categories" in error_msg:
            # Extract the problematic value from error message
            import re
            match = re.search(r'\[(.*?)\]', error_msg)
            if match:
                problematic = match.group(1)
                print(f"✗ {desc}: Unknown category [{problematic}]")
            else:
                print(f"✗ {desc}: {error_msg[:100]}")
        else:
            print(f"✗ {desc}: {error_msg[:100]}")

print("\n=== Model Structure ===")
if hasattr(model, 'named_steps'):
    for name, step in model.named_steps.items():
        print(f"Step: {name} -> {type(step)}")
        if hasattr(step, 'categories_'):
            print(f"  Categories: {step.categories_}")