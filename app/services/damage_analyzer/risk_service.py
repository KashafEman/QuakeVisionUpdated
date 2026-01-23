# services/risk_service.py
import firebase_admin
from firebase_admin import credentials, firestore

# 1. Setup Firebase Connection
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def calculate_city_wide_risk(city_name: str, damage_ratios: dict):
    """
    damage_ratios: dict from mapping_service (e.g., {'kacha': 85.0, 'pacca': 20.0, ...})
    """
    # 1. Fetch all UCs/Sectors for this city from Firebase
    # Path: City -> {city_name} -> UCs
    uc_ref = db.collection("City").document(city_name).collection("UCs")
    docs = uc_ref.stream()

    sector_results = []
    
    # Initialize City Totals
    # Initialize City Totals with new Percentage fields
    city_summary = {
        "city_name": city_name,
        "total_kacha_affected": 0.0,
        "total_semi_pacca_affected": 0.0,
        "total_pacca_affected": 0.0,
        "total_combined_affected": 0.0,
        "total_buildings_in_city": 0,
        # New Percentage Fields
        "city_risk_percentage": 0.0,
        "kacha_risk_percentage": 0.0,
        "semi_pacca_risk_percentage": 0.0,
        "pacca_risk_percentage": 0.0
    }

    # 2. Loop through each sector and calculate risk
    for doc in docs:
        sector = doc.to_dict()
        
        # Calculate expected damage for this sector
        # We divide by 100 because damage_ratios are percentages
        # Calculate totals
        total_in_sector = sector.get("Total", 0)
        k_risk = (damage_ratios["kacha"] / 100) * sector["kacha"]
        sp_risk = (damage_ratios["semi_pacca"] / 100) * sector["semi_pacca"]
        p_risk = (damage_ratios["pacca"] / 100) * sector["pacca"]
        s_total = k_risk + sp_risk + p_risk

        # Create sector dictionary with absolute numbers AND percentages
        sector_data = {
            "sector_name": sector["UC"],
            "total_buildings": total_in_sector,
            "kacha_affected": round(k_risk, 2),
            "semi_pacca_affected": round(sp_risk, 2),
            "pacca_affected": round(p_risk, 2),
            "total_sector_affected": round(s_total, 2),
            # Percentages relative to this specific sector
            "overall_percent": round((s_total / total_in_sector * 100), 2) if total_in_sector > 0 else 0,
            "kacha_percent": round((k_risk / total_in_sector * 100), 2) if total_in_sector > 0 else 0,
            "semi_pacca_percent": round((sp_risk / total_in_sector * 100), 2) if total_in_sector > 0 else 0,
            "pacca_percent": round((p_risk / total_in_sector * 100), 2) if total_in_sector > 0 else 0,
        }
        sector_results.append(sector_data)

        # 3. Aggregate into City Totals
        city_summary["total_kacha_affected"] += k_risk
        city_summary["total_semi_pacca_affected"] += sp_risk
        city_summary["total_pacca_affected"] += p_risk
        city_summary["total_combined_affected"] += s_total
        city_summary["total_buildings_in_city"] += sector["Total"]

    # Final rounding for the city summary
    for key in ["total_kacha_affected", "total_semi_pacca_affected", "total_pacca_affected", "total_combined_affected"]:
        city_summary[key] = round(city_summary[key], 2)

    total_buildings = city_summary["total_buildings_in_city"]
    
    if total_buildings > 0:
        city_summary["city_risk_percentage"] = round((city_summary["total_combined_affected"] / total_buildings) * 100, 2)
        city_summary["kacha_risk_percentage"] = round((city_summary["total_kacha_affected"] / total_buildings) * 100, 2)
        city_summary["semi_pacca_risk_percentage"] = round((city_summary["total_semi_pacca_affected"] / total_buildings) * 100, 2)
        city_summary["pacca_risk_percentage"] = round((city_summary["total_pacca_affected"] / total_buildings) * 100, 2)

    return {
        "city_summary": city_summary,
        "detailed_sectors": sector_results
    }


def calculate_sector_risk(city_name: str, sector_name: str, damage_ratios: dict):
    # Fetch only the requested sector
    sector_ref = (
        db.collection("City")
        .document(city_name)
        .collection("UCs")
        .document(sector_name)
        .get()
    )

    if not sector_ref.exists:
        raise ValueError(f"Sector {sector_name} not found in {city_name}")

    sector = sector_ref.to_dict()

    total = sector.get("Total", 0)

    k_risk = (damage_ratios["kacha"] / 100) * sector["kacha"]
    sp_risk = (damage_ratios["semi_pacca"] / 100) * sector["semi_pacca"]
    p_risk = (damage_ratios["pacca"] / 100) * sector["pacca"]
    s_total = k_risk + sp_risk + p_risk

    return {
        # "city": city_name,
        # "sector": sector_name,
        # "total_buildings": total,

        # "kacha_affected": round(k_risk, 2),
        # "semi_pacca_affected": round(sp_risk, 2),
        # "pacca_affected": round(p_risk, 2),
        # "total_affected": round(s_total, 2),

        "overall_percent": round((s_total / total * 100), 2) if total > 0 else 0,
        "kacha_percent": round((k_risk / total * 100), 2) if total > 0 else 0,
        "semi_pacca_percent": round((sp_risk / total * 100), 2) if total > 0 else 0,
        "pacca_percent": round((p_risk / total * 100), 2) if total > 0 else 0,
    }

def sector_risk(city_name: str, sector_name: str, damage_ratios: dict):
    # Fetch only the requested sector
    sector_ref = (
        db.collection("City")
        .document(city_name)
        .collection("UCs")
        .document(sector_name)
        .get()
    )

    if not sector_ref.exists:
        raise ValueError(f"Sector {sector_name} not found in {city_name}")

    sector = sector_ref.to_dict()

    total = sector.get("Total", 0)

    k_risk = (damage_ratios["kacha"] / 100) * sector["kacha"]
    sp_risk = (damage_ratios["semi_pacca"] / 100) * sector["semi_pacca"]
    p_risk = (damage_ratios["pacca"] / 100) * sector["pacca"]
    s_total = k_risk + sp_risk + p_risk

    return {
        # "city": city_name,
        # 
        # 

        # "kacha_affected": round(k_risk, 2),
        # "semi_pacca_affected": round(sp_risk, 2),
        # "pacca_affected": round(p_risk, 2),
        # "total_affected": round(s_total, 2),

        "sector_name": sector_name,
        "total_buildings": total,
        "overall_percent": round((s_total / total * 100), 2) if total > 0 else 0,
        "kacha_percent": round((k_risk / total * 100), 2) if total > 0 else 0,
        "semi_pacca_percent": round((sp_risk / total * 100), 2) if total > 0 else 0,
        "pacca_percent": round((p_risk / total * 100), 2) if total > 0 else 0,
    }



# damage_ratios = {
#     "kacha": 70.0,
#     "semi_pacca": 40.0,
#     "pacca": 15.0
# }

# city = "Islamabad"
# sector = "SECTOR D-13"

# try:
#     result = calculate_sector_risk(
#         city_name=city,
#         sector_name=sector,
#         damage_ratios=damage_ratios
#     )

#     print("\n--- Sector Risk Report ---")
#     print(f"City   : {result['city']}")
#     print(f"Sector : {result['sector']}")
#     print(f"Total Buildings: {result['total_buildings']}\n")

#     print("Affected Buildings:")
#     print(f"  Kacha       : {result['kacha_affected']}")
#     print(f"  Semi-Pacca  : {result['semi_pacca_affected']}")
#     print(f"  Pacca       : {result['pacca_affected']}")
#     print(f"  Total       : {result['total_affected']}\n")

#     print("Risk Percentages:")
#     print(f"  Overall     : {result['overall_percent']}%")
#     print(f"  Kacha       : {result['kacha_percent']}%")
#     print(f"  Semi-Pacca  : {result['semi_pacca_percent']}%")
#     print(f"  Pacca       : {result['pacca_percent']}%")

# except Exception as e:
#     print("Something went sideways:", e)









# final_mapping= {'kacha': 94.0, 'pacca': 55.0, 'semi_pacca': 70.0 }

# risk_report = calculate_city_wide_risk("Islamabad", final_mapping)

# #--- Printing the results ---
# summary = risk_report['city_summary']

# print(f"City: {summary['city_name']}")
# print("-" * 30)

# # Kacha Results
# print(f"Kacha Risk: {summary['kacha_risk_percentage']}%")
# print(f"Total Kacha Buildings Affected: {summary['total_kacha_affected']}")
# print("-" * 30)

# # Semi-Pacca Results
# print(f"Semi-Pacca Risk: {summary['semi_pacca_risk_percentage']}%")
# print(f"Total Semi-Pacca Buildings Affected: {summary['total_semi_pacca_affected']}")
# print("-" * 30)

# # Pacca Results
# print(f"Pacca Risk: {summary['pacca_risk_percentage']}%")
# print(f"Total Pacca Buildings Affected: {summary['total_pacca_affected']}")
# print("-" * 30)

# # Final Overall Summary
# print(f"OVERALL CITY RISK: {summary['city_risk_percentage']}%")
# print(f"OVERALL BUILDINGS AFFECTED: {summary['total_combined_affected']}")


# print("\n--- DETAILED SECTOR-WISE RISK REPORT ---")

# for sector in risk_report['detailed_sectors']:
#     print(f"\nUC/Sector: {sector['sector_name']}")
#     print(f"{'Category':<15} | {'Affected':<10} | {'Risk %':<10}")
#     print("-" * 40)
#     print(f"{'Kacha':<15} | {sector['kacha_affected']:<10} | {sector['kacha_percent']}%")
#     print(f"{'Semi-Pacca':<15} | {sector['semi_pacca_affected']:<10} | {sector['semi_pacca_percent']}%")
#     print(f"{'Pacca':<15} | {sector['pacca_affected']:<10} | {sector['pacca_percent']}%")
#     print("-" * 40)
#     print(f"{'OVERALL':<15} | {sector['total_sector_affected']:<10} | {sector['overall_percent']}%")
#     print("=" * 40)