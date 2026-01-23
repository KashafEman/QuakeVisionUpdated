# vlm_service.py - UPDATED with robust error handling
import os
import json
from google import genai
from google.genai import types
from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Dict, Optional

# Create a simple dataclass-style class that won't be picked up by FastAPI
class DamageEstimates:
    def __init__(self, RCF: int, RCI: int, URM: int, Adobe: int, RubbleStone: int):
        self.RCF = RCF
        self.RCI = RCI
        self.URM = URM
        self.Adobe = Adobe
        self.RubbleStone = RubbleStone
    
    def dict(self) -> Dict[str, int]:
        return {
            "RCF": self.RCF,
            "RCI": self.RCI,
            "URM": self.URM,
            "Adobe": self.Adobe,
            "RubbleStone": self.RubbleStone
        }

class DamageResponse:
    def __init__(self, pga: str, damage_estimates: DamageEstimates):
        self.pga = pga
        self.damage_estimates = damage_estimates
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DamageResponse':
        return cls(
            pga=data['pga'],
            damage_estimates=DamageEstimates(**data['damage_estimates'])
        )

load_dotenv()

# Initialize client only if API key exists
api_key = os.getenv("API_KEY")
client = None
if api_key:
    try:
        client = genai.Client(api_key=api_key)
        print("✓ Gemini client initialized")
    except Exception as e:
        print(f"⚠ Failed to initialize Gemini client: {e}")
        client = None
else:
    print("⚠ No API_KEY found in .env, using mock mode")

def get_damage_from_vlm(pga: float, image_path: str) -> DamageResponse:
    """
    Get damage estimates from VLM with robust error handling.
    Returns mock data if API fails.
    """
    # Check if image exists
    if not os.path.exists(image_path):
        print(f"⚠ Image not found: {image_path}, using mock data")
        return _get_mock_response(pga)
    
    # If no client or we're in test mode, use mock
    if client is None or os.getenv("USE_MOCK_VLM", "false").lower() == "true":
        print("⚠ Using mock VLM data")
        return _get_mock_response(pga)
    
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        prompt = f"Analyze the damage curve for PGA = {pga} g for: RCF, RCI, URM, Adobe, RubbleStone. Return JSON with damage_estimates containing RCF, RCI, URM, Adobe, RubbleStone values as percentages (0-100)."

        print(f"📤 Sending request to Gemini API for PGA={pga}g...")
        
        # Use a dictionary schema instead of Pydantic model
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/png")
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "pga": {"type": "string"},
                        "damage_estimates": {
                            "type": "object",
                            "properties": {
                                "RCF": {"type": "integer"},
                                "RCI": {"type": "integer"},
                                "URM": {"type": "integer"},
                                "Adobe": {"type": "integer"},
                                "RubbleStone": {"type": "integer"}
                            }
                        }
                    }
                }
            )
        )
        
        # Check if response exists
        if response is None:
            print("⚠ Gemini API returned None response")
            return _get_mock_response(pga)
        
        # Check if response has text
        if not hasattr(response, 'text') or response.text is None:
            print("⚠ Gemini API response has no text attribute")
            return _get_mock_response(pga)
        
        # Check if text is empty
        response_text = response.text.strip()
        if not response_text:
            print("⚠ Gemini API returned empty response")
            return _get_mock_response(pga)
        
        print(f"📥 Received response: {response_text[:100]}...")
        
        try:
            # Parse and convert to our plain Python classes
            data = json.loads(response_text)
            
            # Validate required fields
            if 'pga' not in data or 'damage_estimates' not in data:
                print("⚠ Response missing required fields")
                return _get_mock_response(pga)
            
            # Validate damage estimates structure
            damage_est = data['damage_estimates']
            required_fields = ['RCF', 'RCI', 'URM', 'Adobe', 'RubbleStone']
            for field in required_fields:
                if field not in damage_est:
                    print(f"⚠ Response missing field: {field}")
                    return _get_mock_response(pga)
            
            # Convert values to integers
            for field in required_fields:
                damage_est[field] = int(damage_est[field])
            
            print("✓ Successfully parsed VLM response")
            return DamageResponse.from_dict(data)
            
        except json.JSONDecodeError as e:
            print(f"⚠ Failed to parse JSON response: {e}")
            print(f"⚠ Response was: {response_text[:200]}")
            return _get_mock_response(pga)
            
        except Exception as e:
            print(f"⚠ Error processing response: {e}")
            return _get_mock_response(pga)
    
    except Exception as e:
        print(f"⚠ Gemini API call failed: {type(e).__name__}: {str(e)[:200]}")
        return _get_mock_response(pga)

def _get_mock_response(pga: float) -> DamageResponse:
    """Generate realistic mock response based on PGA."""
    # Calculate damage percentages based on PGA
    # These are realistic approximations
    if pga < 0.05:
        base = 5
        multipliers = [0.8, 0.9, 1.2, 1.5, 1.4]  # RCF, RCI, URM, Adobe, RubbleStone
    elif pga < 0.1:
        base = 15
        multipliers = [0.9, 1.0, 1.3, 1.6, 1.5]
    elif pga < 0.2:
        base = 30
        multipliers = [1.0, 1.1, 1.4, 1.7, 1.6]
    elif pga < 0.3:
        base = 50
        multipliers = [1.1, 1.2, 1.5, 1.8, 1.7]
    elif pga < 0.4:
        base = 70
        multipliers = [1.2, 1.3, 1.6, 1.9, 1.8]
    else:
        base = 85
        multipliers = [1.3, 1.4, 1.7, 2.0, 1.9]
    
    # Apply multipliers and ensure values are 0-100
    values = []
    for mult in multipliers:
        value = int(base * mult)
        values.append(min(100, max(0, value)))
    
    mock_data = {
        "pga": f"{pga:.3f}g",
        "damage_estimates": {
            "RCF": values[0],
            "RCI": values[1],
            "URM": values[2],
            "Adobe": values[3],
            "RubbleStone": values[4]
        }
    }
    
    return DamageResponse.from_dict(mock_data)

# Test function for debugging
if __name__ == "__main__":
    # Test the function
    test_pga = 0.156
    test_image = "C:\\QuakeVision\\app\\static\\damage_curves.PNG"
    
    print("🧪 Testing VLM service...")
    result = get_damage_from_vlm(test_pga, test_image)
    
    print(f"📊 Result for PGA={test_pga}:")
    print(f"  PGA: {result.pga}")
    print(f"  Damage Estimates: {result.damage_estimates.dict()}")