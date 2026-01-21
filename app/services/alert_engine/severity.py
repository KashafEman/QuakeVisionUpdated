
def calculate_severity(magnitude: float) -> str:
    if magnitude >= 6:
        return "CRITICAL"
    if magnitude >= 5:
        return "HIGH"
    if magnitude >= 4:
        return "MODERATE"
    return "LOW"
