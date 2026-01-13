from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_predict_damage():
    payload = {
        "magnitude": 6.5,
        "depth": 10,
        "distance_from_fault": 5,
        "soil_type": 2,
        "building_height": 5
    }

    response = client.post("/predict-damage", json=payload)

    assert response.status_code == 200
    assert "pga" in response.json()
    assert "damage_level" in response.json()
