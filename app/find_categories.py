import joblib
import pandas as pd

model = joblib.load("app/models/trained_model.pkl")

print("=== Finding Model Categories ===")

test_variations = [
   
    "alluvial soil", "medium soil", "rock/stiff soil", "sandy soil", "soft soil",
    
    "Alluvial Soil", "Medium Soil", "Rock/Stiff Soil", "Sandy Soil", "Soft Soil",
    
    "Alluvial soil", "Medium soil", "Rock/stiff soil", "Sandy soil", "Soft soil",
    
    "alluvial", "medium", "rock", "sandy", "soft",
   
    0, 1, 2, 3, 4,
    
    "0", "1", "2", "3", "4",
]

successful = []
failed = []

for soil in test_variations:
    try:
        for cols in [
            ['mag', 'depth', 'distance_km', 'soil_type'],
            ['magnitude', 'depth', 'distance', 'soil_type'],
            ['Magnitude', 'Depth', 'Distance_km', 'Soil_Type']
        ]:
            df = pd.DataFrame([{
                cols[0]: 5.0,
                cols[1]: 10.0,
                cols[2]: 50.0,
                cols[3]: soil
            }])
            
            try:
                pred = model.predict(df)[0]
                successful.append((soil, cols, pred))
                print(f"✓ Soil: {soil} with cols {cols} -> {pred}")
                break
            except:
                continue
    except Exception as e:
        failed.append((soil, str(e)[:100]))

print(f"\nSuccessful: {len(successful)}")
print(f"Failed: {len(failed)}")

if successful:
    print("\nWorking combinations:")
    for soil, cols, pred in successful[:5]: 
        print(f"  {soil} with {cols}")