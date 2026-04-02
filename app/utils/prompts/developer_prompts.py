from typing import Dict, List
from app.utils.normalizer import (
    normalize_material_name,
    normalize_sector_name,
    safe_float_conversion
)

def get_developer_generation_prompt(inputs, metadata: Dict, combined_context: str = "", extracted_costs: Dict = None) -> str:
    """
    Developer prompt that uses retrieved knowledge and web search data.
    NO hardcoded costs - uses context from knowledge retrieval.
    """
   
    site = metadata.get("normalized_site", "Unknown")
    project_type = metadata.get("project_type", "Building")
    building_type = metadata.get("building_type", "commercial")
    magnitude = metadata.get("target_magnitude", 7.5)
    project_name = metadata.get("project_name", site + " Project")

    # User constraints
    budget_level = metadata.get("budget_level", "moderate")
    timeline_months = metadata.get("timeline_months", 18)  # FIX: was defaulting to 12
    timeline_description = metadata.get("timeline_description", "standard timeline")

    # Project scale — use pre-calculated total_sqft from metadata
    project_size_sqft = metadata.get("project_size_sqft", 5000)
    floors = metadata.get("floors", 1)
    total_sqft = metadata.get("total_sqft", project_size_sqft * floors)  # FIX: use metadata value
    building_class = metadata.get("building_class", "Class B")

    # Risk data — now correctly populated
    risk_map = metadata.get("risk_scores", {})
    max_material = metadata.get("normalized_material", "Unknown")
    max_risk = risk_map.get(max_material, 50.0)
    survival = metadata.get("survival_probability", 50.0)

    # Cost resolution
    if extracted_costs and "base_cost_psf" in extracted_costs:
        base_cost_psf = extracted_costs.get("base_cost_psf", 8000)
        residential_cost = extracted_costs.get("residential", int(base_cost_psf * 0.9))
        commercial_cost = extracted_costs.get("commercial", int(base_cost_psf * 1.2))
        mixed_cost = extracted_costs.get("mixed_use", int(base_cost_psf * 1.3))
        industrial_cost = extracted_costs.get("industrial", int(base_cost_psf * 0.85))
        data_source = "Current market data (SerpAPI)"
    else:
        base_cost_psf = 8000
        residential_cost = 8000
        commercial_cost = 10000
        mixed_cost = 11000
        industrial_cost = 7000
        data_source = "Standard estimates (SerpAPI data unavailable)"

    # FIX: Select correct cost for this project's building type
    cost_for_type = {
        "residential": residential_cost,
        "commercial": commercial_cost,
        "mixed-use": mixed_cost,
        "industrial": industrial_cost
    }.get(building_type.lower(), commercial_cost)

    # FIX: Pre-calculate total costs so LLM gets concrete numbers
    base_total = total_sqft * cost_for_type
    seismic_premium_pct = 0.15 if budget_level == "moderate" else (0.10 if budget_level == "low" else 0.25)
    seismic_total = int(base_total * seismic_premium_pct)
    grand_total = base_total + seismic_total

    return f"""
You are a SENIOR STRUCTURAL ENGINEER advising a REAL ESTATE DEVELOPER in PAKISTAN.

Generate a BUSINESS-FOCUSED TECHNICAL FEASIBILITY REPORT with REAL-TIME DATA where available.

--------------------------------------------------
PROJECT CONSTRAINTS (MUST RESPECT THESE):
- Budget Level: {budget_level.upper()}
- Timeline: {timeline_description} ({timeline_months} months total)
- Project Scale: {total_sqft:,} sq ft ({floors} floors × {project_size_sqft:,} sq ft per floor)
- Building Class: {building_class}
--------------------------------------------------
PROJECT DATA:
- Project Name: {project_name}
- Site Location: {site} (Pakistan)
- Project Type: {project_type} ({building_type.upper()})
- Target Earthquake Magnitude: {magnitude}
- Primary Risk Material: {max_material} ({max_risk}% damage risk)
- Survival Probability: {survival}%
--------------------------------------------------
COST DATA SOURCE: {data_source}

Cost per sq ft by type:
- Residential: PKR {residential_cost:,}
- Commercial:  PKR {commercial_cost:,}
- Mixed-use:   PKR {mixed_cost:,}
- Industrial:  PKR {industrial_cost:,}

PRE-CALCULATED FOR THIS PROJECT ({building_type.upper()}, {total_sqft:,} sq ft):
- Base construction cost:     PKR {base_total:,}  (PKR {cost_for_type:,}/sqft × {total_sqft:,} sqft)
- Seismic upgrade ({int(seismic_premium_pct*100)}%):       PKR {seismic_total:,}
- Grand total estimate:       PKR {grand_total:,}

{combined_context if combined_context else "No additional market data retrieved. Use general Pakistani construction industry knowledge."}

--------------------------------------------------
REQUIRED SECTIONS (ALL MANDATORY):

1. EXECUTIVE SUMMARY (For Pakistani Investors)
   - GO/NO-GO Decision: [MUST be explicit: GO / CONDITIONAL GO / NO-GO]
   - ROI Outlook: [Excellent/Good/Moderate/Poor]
   - Key Risk: {max_material} structure with {max_risk}% damage probability
   - Survival Rate: {survival}%
   - Budget Strategy: [Aligned to {budget_level} budget]
   - Timeline Strategy: [Aligned to {timeline_months} months]

2. RISK ASSESSMENT SUMMARY (5 Bullet Points)
   [Generate exactly 5 clear, actionable risk points about:]
   - Seismic hazards specific to {site}
   - Structural vulnerabilities ({max_material})
   - Financial risks
   - Timeline risks
   - Market/compliance risks

3. ACTION RECOMMENDATIONS (5 Bullet Points)
   [Generate exactly 5 specific, prioritized actions:]
   - Immediate steps (Month 1)
   - Design phase requirements
   - Construction adaptations for {budget_level} budget
   - Quality control measures
   - Compliance/certification steps

4. COST IMPLICATIONS (PAKISTAN PKR - USE RETRIEVED DATA)
   [Use market data from context above if available, otherwise state "Based on current market analysis"]
   
   For {total_sqft:,} sq ft {building_type} project:
   - Base construction cost per sq ft: [PKR amount from context or "consult current rates"]
   - Seismic upgrade premium: [% and PKR amount]
   - Total seismic investment: [PKR amount]
   - Budget-tier adjustment: [{budget_level} tier implications]

5. TIMELINE ANALYSIS ({timeline_months} Months)
   [MUST respect the {timeline_months}-month constraint]
   
   Phase breakdown:
   - Investigation & Design: [X months]
   - Foundation: [X months]  
   - Superstructure: [X months]
   - Seismic features integration: [X months]
   - Certification: [X months]
   
   Critical path for {budget_level} budget:
   - {"Fast-track premium required" if timeline_months <= 6 else "Standard sequencing" if timeline_months <= 18 else "Extended optimization possible"}

6. ROI ANALYSIS (MANDATORY)
   [Calculate based on project scale and retrieved market data]
   
   Investment:
   - Total seismic upgrade: [PKR amount]
   - Per sq ft premium: [PKR amount]
   
   Returns:
   - Insurance reduction: [% annually]
   - Resale premium: [% over market]
   - Marketing advantage: [description]
   - Payback period: [years]
   - 10-year NPV: [positive/negative estimate]

7. GO/NO-GO DECISION MATRIX
   DECISION: [GO / CONDITIONAL GO / NO-GO]
   
   Justification:
   - Technical viability: [assessment]
   - Financial viability: [assessment for {budget_level} budget]
   - Timeline feasibility: [assessment for {timeline_months} months]
   - Risk-adjusted return: [assessment]
   
   Conditions if GO:
   - [Specific conditions for {budget_level} budget tier]
   - [Timeline-critical items for {timeline_months} months]
   
   Deal-breakers if NO-GO:
   - [Specific thresholds crossed]

--------------------------------------------------
OUTPUT FORMAT RULES:
1. Use EXACT section headers as shown above
2. For sections 2 and 3, use bullet points (•) not tables
3. Each bullet should be 1-2 sentences maximum
4. Use PKR for all costs (reference retrieved data if available)
5. Explicitly mention how {budget_level} budget affects recommendations
6. Explicitly mention how {timeline_months}-month timeline affects scheduling
7. DO NOT include JSON, code blocks, or visualization data in this output
8. DO NOT use markdown tables
9. Keep total length 800-1000 words

FAIL IF:
- Missing explicit GO/NO-GO decision
- Missing 5 risk bullet points
- Missing 5 action bullet points
- Missing ROI analysis
- Ignoring budget/timeline constraints
- Using generic cost data when retrieved context provides specific data
"""

def get_developer_regeneration_prompt(
    inputs,
    metadata: Dict,
    previous_report: str,
    feedback: str,
    missing_elements: List[str],
    combined_context: str = ""
) -> str:
    """
    Regeneration prompt that addresses validation feedback.
    Uses same structure as generation but with correction focus.
    """
    
    site = metadata.get("normalized_site", "Unknown")
    project_type = metadata.get("project_type", "Building")
    survival = metadata.get("survival_probability", 50.0)
    budget_level = metadata.get("budget_level", "moderate")
    timeline_months = metadata.get("timeline_months", 12)
    
    # Format missing elements for clarity
    formatted_issues = "\n".join([f"- {m}" for m in missing_elements]) if missing_elements else "- Address validation feedback"
    
    return f"""
You are correcting a developer feasibility report that FAILED VALIDATION.

--------------------------------------------------
VALIDATION FEEDBACK (MUST FIX THESE):
{feedback}

SPECIFIC ISSUES:
{formatted_issues}

PROJECT CONTEXT:
- Site: {site}
- Type: {project_type}
- Survival Probability: {survival}%
- Budget: {budget_level}
- Timeline: {timeline_months} months

{combined_context if combined_context else ""}
--------------------------------------------------

ORIGINAL REPORT TO FIX:
{previous_report[:2000]}
--------------------------------------------------

CORRECTION REQUIREMENTS:

1. FIX STRUCTURE:
   - Ensure EXACT section headers from original format
   - Ensure 5 bullet points in Risk Assessment Summary
   - Ensure 5 bullet points in Action Recommendations
   - NO tables, only bullet points

2. FIX CONTENT:
   - Add explicit GO/NO-GO decision if missing
   - Add PKR cost estimates if missing (use context data)
   - Add ROI calculations if missing
   - Respect {budget_level} budget constraints
   - Respect {timeline_months}-month timeline

3. ENHANCE CLARITY:
   - Make bullets actionable (start with verbs: "Install", "Conduct", "Verify")
   - Quantify risks where possible
   - Quantify costs in PKR

4. VALIDATION CHECKLIST:
   [ ] GO/NO-GO decision stated clearly
   [ ] 5 risk assessment bullets
   [ ] 5 action recommendation bullets  
   [ ] PKR costs provided
   [ ] ROI analysis included
   [ ] Budget/timeline constraints addressed

OUTPUT: Complete corrected report (800-1000 words) with all fixes applied.
"""


# ==========================================
# NEW: VISUALIZATION DATA EXTRACTION PROMPT
# ==========================================

def get_developer_visualization_prompt(report_text: str, metadata: Dict) -> str:
    """
    Separate prompt to extract structured data from generated report.
    Called AFTER report generation to create clean JSON for frontend charts.
    """
    
    return f"""
Extract data from this report and return ONLY valid JSON. No markdown, no explanation.

STRICT RULES:
- NO field should be null or empty string
- For numeric fields: calculate or estimate a reasonable value if not explicitly stated
- For timeline phases: all 5 phases MUST have a number, they must ADD UP to {metadata.get('timeline_months', 18)} months total
- For risk_level: must be one of "Low", "Moderate", "High", "Very High"
- For verdict: must be exactly "GO", "CONDITIONAL GO", or "NO-GO"
- floors must be {metadata.get('floors', 1)}
- total_sqft must be {metadata.get('total_sqft', 5000)}

REPORT:
{report_text}

Return exactly this JSON filled with values from the report (use null if not found):
{{

   "project_info": {{
    "site": "{metadata.get('normalized_site', 'Unknown')}",
    "project_type": "{metadata.get('project_type', 'Unknown')}",
    "building_type": "{metadata.get('building_type', 'commercial')}",
    "total_sqft": {metadata.get('total_sqft', metadata.get('project_size_sqft', 5000))},
    "floors": {metadata.get('floors', 1)},
    "budget_level": "{metadata.get('budget_level', 'moderate')}",
    "timeline_months": {metadata.get('timeline_months', 12)}
  }},

  "risk_metrics": {{
    "survival_probability": {metadata.get('survival_probability', 50.0)},
    "damage_risk_percent": null,
    "risk_level": ""
  }},
  "decision": {{
    "verdict": "",
    "conditions": []
  }},
  "costs": {{
    "base_construction_psf": null,
    "seismic_premium_psf": null,
    "total_project_cost": null,
    "seismic_upgrade_total": null,
    "contingency_percent": null
  }},
  "timeline": {{
    "total_months": {metadata.get('timeline_months', 12)},
    "phases": {{
      "investigation": null,
      "design": null,
      "foundation": null,
      "superstructure": null,
      "certification": null
    }}
  }},
  "roi": {{
    "payback_years": null,
    "insurance_savings_percent": null,
    "resale_premium_percent": null
  }}
}}
"""



