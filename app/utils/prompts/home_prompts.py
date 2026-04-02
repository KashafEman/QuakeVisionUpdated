from typing import Dict, List


# ==========================================
# HELPERS
# ==========================================

def _get_risk_profile(survival: float) -> Dict:
    """Return risk tier data based on survival probability."""
    if survival >= 85:
        return {
            "risk_level": "Low",
            "collapse_prob": round(100 - survival, 1),
            "focus": "minor preventive upgrades",
            "urgency": "Plan within 6 months"
        }
    elif survival >= 60:
        return {
            "risk_level": "Moderate",
            "collapse_prob": round(100 - survival, 1),
            "focus": "selective structural strengthening",
            "urgency": "Complete within 3 months"
        }
    elif survival >= 40:
        return {
            "risk_level": "High",
            "collapse_prob": round(100 - survival, 1),
            "focus": "urgent structural intervention",
            "urgency": "Begin immediately"
        }
    elif survival >= 25:
        return {
            "risk_level": "Very High",
            "collapse_prob": round(100 - survival, 1),
            "focus": "emergency retrofit or relocation",
            "urgency": "Evacuate if possible — act within weeks"
        }
    else:
        return {
            "risk_level": "Extreme",
            "collapse_prob": round(100 - survival, 1),
            "focus": "immediate collapse prevention",
            "urgency": "Do NOT occupy — emergency action required"
        }


def _get_cost_ranges(survival: float, budget_level: str, total_sqft: int) -> Dict:
    """
    Calculate PKR cost ranges based on survival probability, budget, and size.
    Base cost per sqft varies by risk level and budget.
    """
    # Base cost per sqft (PKR) by risk level
    if survival >= 85:
        base_low, base_high = 150, 300
    elif survival >= 60:
        base_low, base_high = 300, 550
    elif survival >= 40:
        base_low, base_high = 550, 900
    elif survival >= 25:
        base_low, base_high = 900, 1400
    else:
        base_low, base_high = 1400, 2200

    # Budget multiplier
    multiplier = {"low": 0.7, "moderate": 1.0, "high": 1.4}.get(budget_level, 1.0)

    basic_low = int(total_sqft * base_low * multiplier * 0.5)
    basic_high = int(total_sqft * base_low * multiplier * 0.8)
    standard_low = int(total_sqft * base_low * multiplier)
    standard_high = int(total_sqft * base_high * multiplier)
    comprehensive_low = int(total_sqft * base_high * multiplier)
    comprehensive_high = int(total_sqft * base_high * multiplier * 1.5)

    def fmt(n):
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        return f"{n:,}"

    return {
        "basic": f"PKR {fmt(basic_low)} – {fmt(basic_high)}",
        "standard": f"PKR {fmt(standard_low)} – {fmt(standard_high)}",
        "comprehensive": f"PKR {fmt(comprehensive_low)} – {fmt(comprehensive_high)}",
        "basic_total": int((basic_low + basic_high) / 2),
        "standard_total": int((standard_low + standard_high) / 2),
        "comprehensive_total": int((comprehensive_low + comprehensive_high) / 2),
    }


def _building_type_description(building_type: str) -> str:
    descriptions = {
        "single_story": "single-storey residential house",
        "multi_story": "multi-storey residential building",
        "apartment": "apartment / flat",
        "townhouse": "townhouse / row house"
    }
    return descriptions.get(building_type, "residential building")


def _timeline_note(timeline_months: int, budget_level: str) -> str:
    if timeline_months <= 3:
        return f"Accelerated {timeline_months}-month schedule — prioritize life-safety measures only, defer cosmetic work"
    elif timeline_months <= 6:
        return f"Standard {timeline_months}-month schedule — sufficient for complete Basic or Standard retrofit"
    elif timeline_months <= 12:
        return f"Extended {timeline_months}-month schedule — allows phased Comprehensive retrofit with budget spreading"
    else:
        return f"Long-term {timeline_months}-month plan — full phased retrofit possible, costs can be spread across phases"


# ==========================================
# 1. GENERATION PROMPT
# ==========================================

def get_home_generation_prompt(inputs, metadata: Dict, combined_context: str = "") -> str:
    """
    Homeowner retrofit report generation prompt.
    Uses full metadata including budget, timeline, building_type, sqft.
    """
    material = metadata.get("normalized_material", "Unknown")
    magnitude = metadata.get("magnitude", 7.0)
    floors = metadata.get("floors", 1)
    total_sqft = metadata.get("total_sqft", floors * metadata.get("project_size_sqft", 1000))
    building_type = metadata.get("building_type", "single_story")
    budget_level = metadata.get("budget_level", "moderate")
    timeline_months = metadata.get("timeline_months", 12)
    survival = metadata.get("survival_probability", 50.0)

    risk = _get_risk_profile(survival)
    costs = _get_cost_ranges(survival, budget_level, total_sqft)
    building_desc = _building_type_description(building_type)
    timeline_note = _timeline_note(timeline_months, budget_level)

    risk_map = metadata.get("risk_scores", {})
    risk_map_str = ", ".join([f"{k}: {v:.2f}%" for k, v in risk_map.items()]) if risk_map else "Not provided"

    return f"""
You are a LICENSED STRUCTURAL ENGINEER advising a HOMEOWNER in PAKISTAN about seismic safety.

Generate a PRACTICAL, PLAIN-LANGUAGE RETROFIT REPORT that a non-engineer can understand and act on.

--------------------------------------------------
PROPERTY DATA:
- Building Type: {building_desc} ({building_type})
- Primary Material: {material}
- Floors: {floors}
- Total Area: {total_sqft:,} sq ft
- Target Earthquake Magnitude: Mw {magnitude}
- Survival Probability: {survival:.1f}%
- Risk Level: {risk['risk_level']}
- Collapse Probability: {risk['collapse_prob']:.1f}%
- Risk Scores by Material: {risk_map_str}

OWNER CONSTRAINTS:
- Budget Level: {budget_level.upper()}
  * LOW: Essential life-safety only, minimal finishing, cheapest materials
  * MODERATE: Balanced protection, standard materials, good workmanship
  * HIGH: Premium retrofit, best materials, full certification
- Timeline: {timeline_note}
- Urgency: {risk['urgency']}
--------------------------------------------------

{f"RETRIEVED KNOWLEDGE CONTEXT:{combined_context[:1500]}" if combined_context else ""}

--------------------------------------------------
REQUIRED SECTIONS (ALL MANDATORY):

1. RISK SUMMARY (Plain Language)
   - What {survival:.1f}% survival means for this family in a Mw {magnitude} earthquake
   - What damage to expect: cracks, leaning walls, roof, foundation
   - Collapse probability: {risk['collapse_prob']:.1f}% — explain in simple words
   - Is it safe to live in right now? Be direct.
   - One sentence verdict: SAFE TO OCCUPY / OCCUPY WITH CAUTION / DO NOT OCCUPY

2. WHY {material.upper()} IS RISKY IN EARTHQUAKES (5 Specific Weaknesses)
   Tailor these to {material} construction — do NOT use generic points:
   • Weakness 1: [specific to {material}]
   • Weakness 2: [specific to {material}]
   • Weakness 3: [specific to {material}]
   • Weakness 4: [specific to {material}]
   • Weakness 5: [specific to {material}]

3. RETROFIT ACTION PLAN (7 Steps — ALL MANDATORY)
   For each step include: what to do, why it matters, who does it, timeline, PKR cost.
   Scale costs to {total_sqft:,} sq ft {building_desc}.

   STEP 1: Professional Assessment
   - Hire structural engineer, get drawings, document cracks
   - Timeline: 1–2 weeks | Cost: PKR 15,000 – 35,000

   STEP 2: Roof-to-Wall Connections
   - Install anchor bolts, steel rods at each floor level
   - Timeline: 1–2 weeks | Cost: [calculate for {total_sqft:,} sqft]

   STEP 3: Wall Strengthening
   - Ferro-cement coating, wire mesh, grout injection for {material}
   - Timeline: 2–4 weeks | Cost: [calculate for {total_sqft:,} sqft at PKR 250–450/sqft]

   STEP 4: Corner & Junction Reinforcement
   - Steel angles at all corners, cross-bracing
   - Timeline: 1 week | Cost: [per corner × number of corners in {floors}-floor building]

   STEP 5: Door & Window Opening Reinforcement
   - RC lintels, steel frames, lintel bands
   - Timeline: 1 week | Cost: [per opening]

   STEP 6: Foundation Check & Improvement
   - Excavate, add RC grade beams, improve drainage
   - Timeline: 2–3 weeks | Cost: [for {total_sqft:,} sqft footprint]

   STEP 7: Final Inspection & Safety Certificate
   - Structural engineer sign-off, load test if needed
   - Timeline: 1 week | Cost: PKR 10,000 – 25,000

   DIY vs Professional:
   - DIY OK: Visual inspection, crack photos, painting after work
   - Always hire professional: All 7 steps above

4. COST ESTIMATE (PKR — {budget_level.upper()} BUDGET)
   Scaled to {total_sqft:,} sq ft:

   A) BASIC RETROFIT (Life Safety Only) — Recommended for LOW budget:
      {costs['basic']}
      Includes: Roof connections, corner reinforcement, basic grouting
      Timeline: 4–6 weeks

   B) STANDARD RETROFIT (Full Protection) — Recommended for MODERATE budget:
      {costs['standard']}
      Includes: All basic work + wall strengthening + openings + foundation
      Timeline: 8–12 weeks

   C) COMPREHENSIVE RETROFIT (Maximum Safety) — Recommended for HIGH budget:
      {costs['comprehensive']}
      Includes: Everything + base isolation option + full certification + finishing
      Timeline: 12–18 weeks

   Add 15–20% contingency for unexpected issues.

   BUDGET GUIDANCE for {budget_level.upper()} budget:
   [Explain which option fits {budget_level} budget and what compromises if any]

5. TIMELINE PLAN ({timeline_months} Months Available)
   {timeline_note}
   Month-by-month schedule fitting {timeline_months} months:
   [Break down the 7 steps across {timeline_months} months]

6. SAFETY RULES
   5 THINGS TO DO BEFORE STARTING:
   1. Relocate family during structural work
   2. Remove heavy furniture from walls
   3. Photograph all existing cracks
   4. Get 3 contractor quotes
   5. Verify contractor license with PEC

   5 THINGS TO NEVER DO:
   1. Never remove walls without engineer approval
   2. Never add floors without foundation assessment
   3. Never use substandard materials to save cost
   4. Never skip curing time (minimum 28 days for concrete)
   5. Never ignore diagonal cracks wider than 6mm

   CALL A STRUCTURAL ENGINEER IF:
   - Diagonal cracks wider than 6mm appear
   - Walls are bulging or leaning
   - After any earthquake above Mw 5.0

--------------------------------------------------
OUTPUT RULES:
1. Write in plain Urdu-friendly English (simple sentences, no jargon)
2. Use PKR for ALL costs — no USD
3. All 7 retrofit steps MUST be present with costs
4. Explicitly mention {budget_level} budget implications
5. Explicitly mention {timeline_months}-month timeline in the plan
6. 800–1000 words total
7. DO NOT include any JSON, code blocks, or visualization data in this output
8. DO NOT use markdown tables

FAIL IF:
- Missing any of the 7 retrofit steps
- Missing PKR costs
- Missing budget/timeline guidance
- Report is generic and not tailored to {material} and {building_type}
"""


# ==========================================
# 2. REGENERATION PROMPT
# ==========================================

def get_home_regeneration_prompt(
    inputs,
    metadata: Dict,
    previous_report: str,
    feedback: str,
    missing_elements: List[str],
    combined_context: str = ""
) -> str:
    """
    Homeowner retrofit report regeneration — fixes validation failures.
    """
    material = metadata.get("normalized_material", "Unknown")
    magnitude = metadata.get("magnitude", 7.0)
    floors = metadata.get("floors", 1)
    total_sqft = metadata.get("total_sqft", 1000)
    building_type = metadata.get("building_type", "single_story")
    budget_level = metadata.get("budget_level", "moderate")
    timeline_months = metadata.get("timeline_months", 12)
    survival = metadata.get("survival_probability", 50.0)

    risk = _get_risk_profile(survival)
    costs = _get_cost_ranges(survival, budget_level, total_sqft)
    building_desc = _building_type_description(building_type)

    formatted_issues = "\n".join([f"- {m}" for m in missing_elements]) if missing_elements else "- See feedback below"

    return f"""
You are a SENIOR STRUCTURAL ENGINEER correcting a homeowner retrofit report that FAILED VALIDATION.

--------------------------------------------------
VALIDATION FEEDBACK (MUST FIX):
{feedback}

SPECIFIC ISSUES TO FIX:
{formatted_issues}

PROPERTY DATA:
- Material: {material}
- Building: {floors}-floor {building_desc}
- Total Area: {total_sqft:,} sq ft
- Magnitude: Mw {magnitude}
- Survival: {survival:.1f}% | Risk: {risk['risk_level']}
- Budget: {budget_level.upper()} | Timeline: {timeline_months} months
--------------------------------------------------

ORIGINAL REPORT TO FIX:
{previous_report[:2500]}
--------------------------------------------------

CORRECTION CHECKLIST (Fix ALL that are missing):

[ ] 1. RISK SUMMARY in plain language with survival % explained simply
[ ] 2. 5 weaknesses specific to {material} (NOT generic)
[ ] 3. ALL 7 RETROFIT STEPS with timelines and PKR costs:
       Step 1: Assessment | Step 2: Roof-Wall | Step 3: Wall Strengthening
       Step 4: Corners | Step 5: Openings | Step 6: Foundation | Step 7: Inspection
[ ] 4. 3 cost tiers (Basic/Standard/Comprehensive) in PKR scaled to {total_sqft:,} sqft:
       Basic: {costs['basic']}
       Standard: {costs['standard']}
       Comprehensive: {costs['comprehensive']}
[ ] 5. {budget_level.upper()} budget guidance — which tier fits, what compromises
[ ] 6. {timeline_months}-month schedule breakdown
[ ] 7. Safety rules (5 do's, 5 don'ts, when to call engineer)

KEEP: All correct content from original report
ADD: Everything in the checklist that is missing
IMPROVE: Any section that got low marks in feedback

OUTPUT: Complete corrected report (800–1000 words), plain language, PKR costs throughout.
FAIL IF: Any checklist item is still missing after correction.
"""


# ==========================================
# 3. VISUALIZATION EXTRACTION PROMPT
# ==========================================

def get_home_visualization_prompt(report_text: str, metadata: Dict) -> str:
    """
    Extracts structured JSON from the generated home report for frontend charts.
    Called AFTER report generation — separate from the report itself.
    """
    material = metadata.get("normalized_material", "Unknown")
    survival = metadata.get("survival_probability", 50.0)
    floors = metadata.get("floors", 1)
    total_sqft = metadata.get("total_sqft", 1000)
    building_type = metadata.get("building_type", "single_story")
    budget_level = metadata.get("budget_level", "moderate")
    timeline_months = metadata.get("timeline_months", 12)
    magnitude = metadata.get("magnitude", 7.0)

    risk = _get_risk_profile(survival)
    costs = _get_cost_ranges(survival, budget_level, total_sqft)

    return f"""
Extract structured data from this homeowner retrofit report and return ONLY valid JSON.
No markdown, no explanation, no code fences. No null values — estimate if not stated.

STRICT RULES:
- NO field may be null or empty string
- All numeric fields must have a number
- timeline phases must ADD UP to {timeline_months} weeks total (approximately)
- risk_level must be one of: "Low", "Moderate", "High", "Very High", "Extreme"
- occupancy_status must be one of: "Safe to Occupy", "Occupy with Caution", "Do Not Occupy"

REPORT TO PARSE:
{report_text[:2000]}

Return this JSON with ALL fields filled:
{{
  "project_info": {{
    "material": "{material}",
    "building_type": "{building_type}",
    "floors": {floors},
    "total_sqft": {total_sqft},
    "budget_level": "{budget_level}",
    "timeline_months": {timeline_months},
    "magnitude": {magnitude}
  }},
  "risk_assessment": {{
    "survival_probability": {survival},
    "collapse_probability": {risk['collapse_prob']},
    "risk_level": "{risk['risk_level']}",
    "occupancy_status": "",
    "damage_risk_percent": {round(100 - survival, 2)}
  }},
  "retrofit_steps": {{
    "assessment": {{ "weeks": 2, "cost_pkr": 25000 }},
    "roof_wall_connection": {{ "weeks": 2, "cost_pkr": 0 }},
    "wall_strengthening": {{ "weeks": 3, "cost_pkr": 0 }},
    "corner_reinforcement": {{ "weeks": 1, "cost_pkr": 0 }},
    "opening_reinforcement": {{ "weeks": 1, "cost_pkr": 0 }},
    "foundation": {{ "weeks": 3, "cost_pkr": 0 }},
    "final_inspection": {{ "weeks": 1, "cost_pkr": 20000 }}
  }},
  "cost_options": {{
    "basic": {{
      "label": "Basic Retrofit",
      "total_pkr": {costs['basic_total']},
      "range_str": "{costs['basic']}",
      "weeks": 6
    }},
    "standard": {{
      "label": "Standard Retrofit",
      "total_pkr": {costs['standard_total']},
      "range_str": "{costs['standard']}",
      "weeks": 10
    }},
    "comprehensive": {{
      "label": "Comprehensive Retrofit",
      "total_pkr": {costs['comprehensive_total']},
      "range_str": "{costs['comprehensive']}",
      "weeks": 16
    }},
    "recommended": "{budget_level}"
  }},
  "timeline": {{
    "total_months": {timeline_months},
    "phases": {{
      "assessment": 0,
      "roof_and_walls": 0,
      "corners_and_openings": 0,
      "foundation": 0,
      "inspection_certification": 0
    }}
  }},
  "risk_scores_by_material": {str(metadata.get('risk_scores', {})).replace("'", '"')},
  "safety_summary": {{
    "top_risks": [],
    "immediate_actions": []
  }}
}}
"""