# project_size_sqft → average building size in the sector (per-building estimate)
# floors → average floors across sector buildings
# total_sqft → retrofit_capacity × project_size_sqft × floors (sector-wide aggregate)

from typing import Dict, List


# ==========================================
# HELPERS
# ==========================================

def _get_allocation(priority_metric: str, retrofit_capacity: int) -> Dict:
    """Calculate building allocation by typology based on priority metric."""
    pm = priority_metric.lower()
    if "lives" in pm:
        kacha_pct, semi_pct = 0.70, 0.20
    elif "vulnerability" in pm or "reduce" in pm:
        kacha_pct, semi_pct = 0.50, 0.30
    else:  # cost-optimized / resource allocation
        kacha_pct, semi_pct = 0.40, 0.40

    kacha_alloc = int(retrofit_capacity * kacha_pct)
    semi_alloc  = int(retrofit_capacity * semi_pct)
    pacca_alloc = retrofit_capacity - kacha_alloc - semi_alloc

    return {
        "kacha": kacha_alloc,
        "semi":  semi_alloc,
        "pacca": pacca_alloc,
    }


def _get_costs(retrofit_style: str) -> Dict:
    """
    PKR per-building costs by retrofit style.
    Low-cost uses cheaper materials; Structural is comprehensive; Hybrid is balanced.
    """
    style = retrofit_style.lower()
    if "low" in style:
        return {"kacha": 180_000, "semi": 350_000, "pacca": 700_000}
    elif "structural" in style:
        return {"kacha": 320_000, "semi": 650_000, "pacca": 1_300_000}
    else:  # Hybrid (default)
        return {"kacha": 250_000, "semi": 500_000, "pacca": 1_000_000}


def _calc_budget(alloc: Dict, costs: Dict) -> Dict:
    """Calculate full budget breakdown including overhead lines."""
    retrofit_total = (
        alloc["kacha"] * costs["kacha"]
        + alloc["semi"]  * costs["semi"]
        + alloc["pacca"] * costs["pacca"]
    )
    engineering  = int(retrofit_total * 0.10)
    qc           = int(retrofit_total * 0.05)
    awareness    = int(retrofit_total * 0.05)
    grand_total  = retrofit_total + engineering + qc + awareness

    return {
        "kacha_cost":    alloc["kacha"] * costs["kacha"],
        "semi_cost":     alloc["semi"]  * costs["semi"],
        "pacca_cost":    alloc["pacca"] * costs["pacca"],
        "retrofit_total": retrofit_total,
        "engineering":   engineering,
        "qc":            qc,
        "awareness":     awareness,
        "grand_total":   grand_total,
    }


def _calc_impact(alloc: Dict, overall_risk: float, total_buildings: int, budget: Dict) -> Dict:
    """Calculate lives saved, risk reduction, and economic benefit."""
    lives_kacha = int(alloc["kacha"] * 0.30)
    lives_semi  = int(alloc["semi"]  * 0.20)
    lives_pacca = int(alloc["pacca"] * 0.10)
    total_lives = lives_kacha + lives_semi + lives_pacca

    risk_reduction = int(overall_risk * 0.60)
    target_risk    = max(20, overall_risk - risk_reduction)

    # Economic benefit in PKR millions
    econ_base      = int(total_buildings * overall_risk / 100 * 0.5)
    econ_total     = int(econ_base * 1.8)
    bcr_raw        = (econ_total) / (budget["grand_total"] / 1_000_000)
    bcr            = round(bcr_raw, 1) if budget["grand_total"] > 0 else 0.0

    return {
        "lives_kacha":   lives_kacha,
        "lives_semi":    lives_semi,
        "lives_pacca":   lives_pacca,
        "total_lives":   total_lives,
        "risk_reduction": risk_reduction,
        "target_risk":   target_risk,
        "econ_base":     econ_base,
        "econ_continuity": int(econ_base * 0.5),
        "econ_health":   int(econ_base * 0.3),
        "econ_total":    econ_total,
        "bcr":           bcr,
    }


def _timeline_phases(alloc: Dict, timeline_months: int) -> Dict:
    """
    Distribute work across 3 phases proportional to the actual timeline.
    Phase 1 (pilot):      ~25% of timeline
    Phase 2 (scale-up):   ~42% of timeline
    Phase 3 (completion): remaining
    """
    p1 = max(1, int(timeline_months * 0.25))
    p2 = max(1, int(timeline_months * 0.42))
    p3 = max(1, timeline_months - p1 - p2)

    return {
        "p1_months": p1,
        "p1_end":    p1,
        "p2_start":  p1 + 1,
        "p2_end":    p1 + p2,
        "p3_start":  p1 + p2 + 1,
        "p3_end":    timeline_months,
        "p1_kacha":  int(alloc["kacha"] * 0.25),
        "p2_kacha":  alloc["kacha"] - int(alloc["kacha"] * 0.25),
        "p2_semi":   int(alloc["semi"] * 0.50),
        "p3_semi":   alloc["semi"] - int(alloc["semi"] * 0.50),
        "p3_pacca":  alloc["pacca"],
    }


def _budget_level_note(budget_level: str, retrofit_style: str) -> str:
    notes = {
        "low":      "Prioritise Kacha structures only — defer Semi-Pacca to next fiscal cycle if funds are insufficient.",
        "moderate": "Standard scope: retrofit all three typologies within the allocated capacity.",
        "high":     "Full scope with contingency reserve — include quality audits and community drills.",
    }
    style_note = {
        "low-cost":   "Low-cost methods (wire mesh + cement plaster) keep per-building costs minimal.",
        "structural": "Full structural retrofit methods — higher unit cost but maximum seismic performance.",
        "hybrid":     "Hybrid approach balances cost-effectiveness with meaningful risk reduction.",
    }
    bl   = notes.get(budget_level.lower(), notes["moderate"])
    rs   = style_note.get(retrofit_style.lower(), style_note["hybrid"])
    return f"{bl} {rs}"


# ==========================================
# 1. GENERATION PROMPT
# ==========================================

def get_gov_generation_prompt(inputs, metadata: Dict, combined_context: str = "") -> str:
    """
    Government sector retrofit action plan generation prompt.
    All numbers are pre-calculated in Python — the LLM only fills narrative.
    """
    # ── Pull from metadata ──────────────────────────────────────────────────
    sector_name      = metadata.get("sector_name", "Unknown Sector")
    priority_metric  = metadata.get("priority_metric", "Save Maximum Lives")
    retrofit_capacity= metadata.get("retrofit_capacity", 100)
    retrofit_style   = metadata.get("retrofit_style", "Hybrid")
    budget_level     = metadata.get("budget_level", "moderate")
    timeline_months  = metadata.get("timeline_months", 12)
    magnitude        = metadata.get("magnitude", 7.5)
    avg_building_sqft= metadata.get("avg_building_sqft", 1500)
    avg_floors       = metadata.get("avg_floors", 2)
    total_sqft       = metadata.get("total_sqft", retrofit_capacity * avg_building_sqft * avg_floors)

    sector_data      = getattr(inputs, "sector_data", {})
    total_buildings  = sector_data.get("total_buildings", 1000)
    overall_risk     = sector_data.get("overall_percent", 50.0)
    kacha_pct        = sector_data.get("kacha_percent", 0)
    semi_pct         = sector_data.get("semi_pacca_percent", 0)
    pacca_pct        = sector_data.get("pacca_percent", 0)
    population       = sector_data.get("population", 0)

    # ── Pre-calculate everything ────────────────────────────────────────────
    alloc  = _get_allocation(priority_metric, retrofit_capacity)
    costs  = _get_costs(retrofit_style)
    budget = _calc_budget(alloc, costs)
    impact = _calc_impact(alloc, overall_risk, total_buildings, budget)
    phases = _timeline_phases(alloc, timeline_months)
    bl_note= _budget_level_note(budget_level, retrofit_style)

    kacha_buildings = int(total_buildings * kacha_pct / 100)
    semi_buildings  = int(total_buildings * semi_pct  / 100)
    pacca_buildings = total_buildings - kacha_buildings - semi_buildings

    coverage_pct = round(retrofit_capacity / total_buildings * 100, 1) if total_buildings else 0

    return f"""
You are a LICENSED STRUCTURAL ENGINEER advising NDMA Pakistan on a government-scale seismic retrofit programme.

Generate a COMPLETE GOVERNMENT ACTION PLAN that a policy maker can present to cabinet.

--------------------------------------------------
SECTOR DATA:
- Sector: {sector_name}
- Target Earthquake: Mw {magnitude}
- Total Buildings in Sector: {total_buildings:,}
- Retrofit Target (this programme): {retrofit_capacity:,} buildings ({coverage_pct}% of sector)
- Population Affected: {population:,}

BUILDING STOCK (Pakistan typology → international equivalent):
| Local Term  | International Equivalent          | Sector Count    | % of Sector |
|-------------|-----------------------------------|-----------------|-------------|
| KACHA       | Adobe & Rubble Stone              | {kacha_buildings:,} buildings | {kacha_pct}% |
| SEMI-PACCA  | URM (Unreinforced Masonry)        | {semi_buildings:,} buildings | {semi_pct}% |
| PACCA       | RCF/RCI (Reinforced Concrete)     | {pacca_buildings:,} buildings | {pacca_pct}% |

PROGRAMME PARAMETERS:
- Priority Metric:  {priority_metric}
- Retrofit Style:   {retrofit_style}
- Budget Level:     {budget_level.upper()} — {bl_note}
- Timeline:         {timeline_months} months
- Avg Building:     {avg_building_sqft:,} sq ft × {avg_floors} floor(s)
- Total Sector Sqft Being Retrofitted: {total_sqft:,} sq ft
--------------------------------------------------

{f"RETRIEVED KNOWLEDGE CONTEXT:{combined_context[:1500]}" if combined_context else ""}

--------------------------------------------------
REQUIRED SECTIONS (ALL MANDATORY — USE EXACT PRE-CALCULATED NUMBERS BELOW):

1. EXECUTIVE SUMMARY
   Write 3–4 sentences:
   - What this programme will do (retrofit {retrofit_capacity:,} buildings in {sector_name})
   - The priority ({priority_metric}) and approach ({retrofit_style})
   - The headline outcome ({impact['total_lives']:,} lives protected, {impact['risk_reduction']} percentage-point risk reduction)
   - Total investment required (PKR {budget['grand_total']:,})

2. RISK ASSESSMENT SUMMARY
   Generate exactly 5 bullet points covering:
   • Seismic hazard: Mw {magnitude} ground motion implications for {sector_name}
   • KACHA structural vulnerabilities: why Adobe & Rubble Stone fails in earthquakes
   • SEMI-PACCA structural vulnerabilities: why Unreinforced Masonry (URM) fails
   • PACCA relative strength: why RCF/RCI performs better but still needs attention
   • Sector-level collapse scenario: {overall_risk}% current collapse risk, {kacha_buildings:,} highest-risk buildings

3. ACTION RECOMMENDATIONS
   Generate exactly 5 bullet points covering:
   • Immediate action (first {phases['p1_months']} months): pilot {phases['p1_kacha']} Kacha buildings
   • Design phase: engineering assessments, drawings, community engagement
   • Construction adaptations for each typology (Kacha / Semi-Pacca / Pacca methods)
   • Quality control: inspection regime, third-party audits
   • Compliance: BCP 2007 / NBC Pakistan certification and handover

4. RETROFIT ALLOCATION
   Use THESE EXACT NUMBERS — allocate EXACTLY {retrofit_capacity:,} buildings:

   | Typology                          | Int'l Equivalent       | Allocation              | % of Programme | Cost per Building |
   |-----------------------------------|------------------------|-------------------------|----------------|-------------------|
   | KACHA (Adobe & Rubble Stone)      | Adobe & Rubble Stone   | {alloc['kacha']:,} bldgs | {alloc['kacha']*100//retrofit_capacity}%  | PKR {costs['kacha']:,} |
   | SEMI-PACCA (Unreinforced Masonry) | URM                    | {alloc['semi']:,} bldgs  | {alloc['semi']*100//retrofit_capacity}%   | PKR {costs['semi']:,} |
   | PACCA (Reinforced Concrete)       | RCF/RCI                | {alloc['pacca']:,} bldgs | {alloc['pacca']*100//retrofit_capacity}%  | PKR {costs['pacca']:,} |
   | TOTAL                             |                        | {retrofit_capacity:,}   | 100%           |                   |

   Justify this allocation in 2 sentences based on: {priority_metric}

5. PKR BUDGET BREAKDOWN
   Use THESE EXACT NUMBERS:

   | Line Item                       | Calculation                          | Amount (PKR)            |
   |---------------------------------|--------------------------------------|-------------------------|
   | KACHA retrofit                  | {alloc['kacha']:,} × PKR {costs['kacha']:,}   | {budget['kacha_cost']:,} |
   | SEMI-PACCA retrofit             | {alloc['semi']:,} × PKR {costs['semi']:,}     | {budget['semi_cost']:,}  |
   | PACCA retrofit                  | {alloc['pacca']:,} × PKR {costs['pacca']:,}   | {budget['pacca_cost']:,} |
   | Engineering & Design (10%)      | 10% of retrofit subtotal             | {budget['engineering']:,} |
   | Quality Control & Inspection (5%)| 5% of retrofit subtotal             | {budget['qc']:,}          |
   | Community Awareness (5%)        | 5% of retrofit subtotal              | {budget['awareness']:,}   |
   | GRAND TOTAL                     |                                      | PKR {budget['grand_total']:,} |

   Add 1 sentence on {budget_level.upper()} budget implications.

6. IMPACT ESTIMATES — LIVES SAVED
   Use THESE EXACT NUMBERS:
   Formula: Lives Saved = Buildings Retrofitted × Lives-Saved-per-Building Factor

   | Typology       | Int'l Equivalent | Buildings | Factor | Lives Saved |
   |----------------|------------------|-----------|--------|-------------|
   | KACHA          | Adobe/Rubble Stone| {alloc['kacha']:,} | 0.30 | {impact['lives_kacha']:,} |
   | SEMI-PACCA     | URM              | {alloc['semi']:,}  | 0.20 | {impact['lives_semi']:,}  |
   | PACCA          | RCF/RCI          | {alloc['pacca']:,} | 0.10 | {impact['lives_pacca']:,} |
   | TOTAL          |                  | {retrofit_capacity:,} |  | {impact['total_lives']:,} LIVES |

7. RISK REDUCTION IMPACT
   Use THESE EXACT NUMBERS:
   - Current Sector Collapse Risk:  {overall_risk}%
   - Post-Retrofit Target Risk:     {impact['target_risk']}%
   - Absolute Reduction:            {impact['risk_reduction']} percentage points
   - Relative Improvement:          {int(impact['risk_reduction'] / overall_risk * 100) if overall_risk else 0}%

   Write 2 sentences explaining what this means for residents.

8. ECONOMIC BENEFIT ANALYSIS
   Use THESE EXACT NUMBERS:
   - Direct Damage Avoided:   PKR {impact['econ_base']:,} million
   - Business Continuity:     PKR {impact['econ_continuity']:,} million
   - Healthcare Savings:      PKR {impact['econ_health']:,} million
   - TOTAL ECONOMIC BENEFIT:  PKR {impact['econ_total']:,} million
   - Benefit-Cost Ratio:      {impact['bcr']}

   A BCR > 1.0 means the programme pays for itself. Write 1 sentence on what BCR {impact['bcr']} means.

9. IMPLEMENTATION TIMELINE ({timeline_months} MONTHS)
   Use THESE EXACT PHASE BOUNDARIES:

   | Phase                | Months                         | Key Activities                                      | Buildings Completed                          |
   |----------------------|--------------------------------|-----------------------------------------------------|----------------------------------------------|
   | Phase 1 — Pilot      | Months 1–{phases['p1_end']}   | Structural surveys, contractor training, pilot retrofits | {phases['p1_kacha']} KACHA buildings       |
   | Phase 2 — Scale-Up   | Months {phases['p2_start']}–{phases['p2_end']} | Bulk KACHA + first SEMI-PACCA batch | {phases['p2_kacha']} KACHA + {phases['p2_semi']} SEMI-PACCA |
   | Phase 3 — Completion | Months {phases['p3_start']}–{phases['p3_end']} | Remaining SEMI-PACCA + all PACCA + certification | {phases['p3_semi']} SEMI-PACCA + {phases['p3_pacca']} PACCA |

10. TECHNICAL RETROFIT METHODS
    List methods for all three typologies using BOTH local and international names:

    KACHA (Adobe & Rubble Stone) — highest vulnerability:
    • Wire mesh wrapping with 1-inch cement plaster (both faces)
    • Seismic bands at plinth, lintel, and roof levels (BCP 2007 Cl. 4.3)
    • Corner strengthening with steel angles (150×150×10mm)
    • Grout injection in hollow stone cavities
    • Roof-to-wall connections with M12 anchor bolts at 600mm c/c

    SEMI-PACCA (URM — Unreinforced Masonry) — moderate vulnerability:
    • Ferro-cement coating with 6mm welded wire mesh (both faces)
    • RC bands at each floor level (150mm deep × full wall width)
    • Steel frames around all openings (200×200×10mm angles)
    • Through-stone installation for transverse wall bonding
    • Foundation grade beams (300×600mm RC)

    PACCA (RCF/RCI — Reinforced Concrete Frame/Industrial) — lower vulnerability:
    • Concrete jacketing of weak columns (300mm thick, min. 4×16mm bars)
    • Shear wall infill in critical bays (200mm RC, double mesh)
    • Steel bracing for soft-storey frames (HSS 150×150×8)
    • Foundation underpinning where bearing capacity is insufficient

11. COMPLIANCE & CERTIFICATION
    List 3 mandatory standards:
    • BCP 2007 (Building Code of Pakistan) — seismic zone requirements
    • NBC Pakistan (National Building Code) — structural safety
    • NDMA Guidelines — post-retrofit inspection and certification
    State who signs off and what documentation is required for handover.

--------------------------------------------------
OUTPUT RULES:
1. Use ALL pre-calculated numbers exactly as shown — do NOT recalculate or round differently
2. All costs in PKR — no USD
3. Always write BOTH local term AND international equivalent (e.g. "KACHA (Adobe & Rubble Stone)")
4. 900–1200 words of narrative (tables are additional)
5. DO NOT include any JSON block in this output — visualization data is extracted separately
6. DO NOT use "see above" — repeat numbers in each section

FAIL IF:
- Any of the 11 sections is missing
- Numbers differ from the pre-calculated values above
- Local building terms appear without their international equivalents
- Budget total does not equal PKR {budget['grand_total']:,}
- Timeline phases do not cover all {timeline_months} months
"""


# ==========================================
# 2. REGENERATION PROMPT
# ==========================================

def get_gov_regeneration_prompt(
    inputs,
    metadata: Dict,
    previous_report: str,
    feedback: str,
    missing_elements: List[str],
    combined_context: str = ""
) -> str:
    """
    Government action plan regeneration — fixes validation failures.
    Mirrors the structure of get_home_regeneration_prompt.
    """
    sector_name      = metadata.get("sector_name", "Unknown Sector")
    priority_metric  = metadata.get("priority_metric", "Save Maximum Lives")
    retrofit_capacity= metadata.get("retrofit_capacity", 100)
    retrofit_style   = metadata.get("retrofit_style", "Hybrid")
    budget_level     = metadata.get("budget_level", "moderate")
    timeline_months  = metadata.get("timeline_months", 12)
    magnitude        = metadata.get("magnitude", 7.5)

    sector_data      = getattr(inputs, "sector_data", {})
    total_buildings  = sector_data.get("total_buildings", 1000)
    overall_risk     = sector_data.get("overall_percent", 50.0)
    kacha_pct        = sector_data.get("kacha_percent", 0)
    semi_pct         = sector_data.get("semi_pacca_percent", 0)
    pacca_pct        = sector_data.get("pacca_percent", 0)

    alloc  = _get_allocation(priority_metric, retrofit_capacity)
    costs  = _get_costs(retrofit_style)
    budget = _calc_budget(alloc, costs)
    impact = _calc_impact(alloc, overall_risk, total_buildings, budget)
    phases = _timeline_phases(alloc, timeline_months)

    formatted_issues = "\n".join([f"- {m}" for m in missing_elements]) if missing_elements else "- See feedback below"

    return f"""
You are a SENIOR GOVERNMENT ENGINEER correcting an action plan that FAILED VALIDATION.

--------------------------------------------------
VALIDATION FEEDBACK (MUST FIX):
{feedback}

SPECIFIC ISSUES TO FIX:
{formatted_issues}

SECTOR DATA:
- Sector: {sector_name} | Magnitude: Mw {magnitude}
- Total Buildings: {total_buildings:,} | Retrofit Target: {retrofit_capacity:,}
- Building Mix: KACHA {kacha_pct}% / SEMI-PACCA {semi_pct}% / PACCA {pacca_pct}%
- Priority: {priority_metric} | Style: {retrofit_style}
- Budget: {budget_level.upper()} | Timeline: {timeline_months} months
--------------------------------------------------

ORIGINAL REPORT TO FIX:
{previous_report[:2500]}
--------------------------------------------------

CORRECTION CHECKLIST — fix ALL items that are missing or wrong:

[ ] 1. EXECUTIVE SUMMARY — 3–4 sentences with programme scope and headline numbers
[ ] 2. RISK ASSESSMENT SUMMARY — 5 bullets (hazard, KACHA, SEMI-PACCA, PACCA, sector scenario)
[ ] 3. ACTION RECOMMENDATIONS — 5 bullets (pilot, design, construction, QC, compliance)
[ ] 4. RETROFIT ALLOCATION — table with EXACT split:
       KACHA {alloc['kacha']:,} | SEMI-PACCA {alloc['semi']:,} | PACCA {alloc['pacca']:,} (total = {retrofit_capacity:,})
       Always write local term + international equivalent side by side
[ ] 5. PKR BUDGET — table with EXACT grand total: PKR {budget['grand_total']:,}
       KACHA {budget['kacha_cost']:,} | SEMI {budget['semi_cost']:,} | PACCA {budget['pacca_cost']:,}
       + Engineering {budget['engineering']:,} + QC {budget['qc']:,} + Awareness {budget['awareness']:,}
[ ] 6. LIVES SAVED — table with EXACT total: {impact['total_lives']:,} lives
       KACHA {impact['lives_kacha']:,} | SEMI {impact['lives_semi']:,} | PACCA {impact['lives_pacca']:,}
[ ] 7. RISK REDUCTION — current {overall_risk}% → target {impact['target_risk']}% (−{impact['risk_reduction']} pts)
[ ] 8. ECONOMIC BENEFIT — BCR {impact['bcr']} | Total benefit PKR {impact['econ_total']:,}M
[ ] 9. IMPLEMENTATION TIMELINE — {timeline_months} months across 3 phases:
       Phase 1 (months 1–{phases['p1_end']}): {phases['p1_kacha']} KACHA pilot
       Phase 2 (months {phases['p2_start']}–{phases['p2_end']}): {phases['p2_kacha']} KACHA + {phases['p2_semi']} SEMI-PACCA
       Phase 3 (months {phases['p3_start']}–{phases['p3_end']}): {phases['p3_semi']} SEMI-PACCA + {phases['p3_pacca']} PACCA
[ ] 10. TECHNICAL METHODS — for all 3 typologies with local + international names
[ ] 11. COMPLIANCE — BCP 2007, NBC Pakistan, NDMA sign-off

KEEP: All correct content from the original report
ADD: Every checklist item that is missing
FIX: Any numbers that differ from the values above

OUTPUT: Complete corrected report (900–1200 words + tables), all costs in PKR.
FAIL IF: Any checklist item remains missing or any number differs from the pre-calculated values.
"""


# ==========================================
# 3. VISUALIZATION EXTRACTION PROMPT
# ==========================================

def get_gov_visualization_prompt(report_text: str, metadata: Dict) -> str:
    """
    Extracts structured JSON from the generated gov report for frontend charts.
    Called AFTER report generation — separate from the report itself.
    Mirrors get_home_visualization_prompt structure.
    """
    sector_name      = metadata.get("sector_name", "Unknown Sector")
    priority_metric  = metadata.get("priority_metric", "Save Maximum Lives")
    retrofit_capacity= metadata.get("retrofit_capacity", 100)
    retrofit_style   = metadata.get("retrofit_style", "Hybrid")
    budget_level     = metadata.get("budget_level", "moderate")
    timeline_months  = metadata.get("timeline_months", 12)
    magnitude        = metadata.get("magnitude", 7.5)
    avg_building_sqft= metadata.get("avg_building_sqft", 1500)
    avg_floors       = metadata.get("avg_floors", 2)
    total_sqft       = metadata.get("total_sqft", 0)

    sector_data_ref  = {}  # not passed here — use metadata fallbacks
    total_buildings  = metadata.get("total_buildings", 1000)
    overall_risk     = metadata.get("overall_risk", 50.0)
    kacha_pct        = metadata.get("kacha_percent", 0)
    semi_pct         = metadata.get("semi_pacca_percent", 0)
    pacca_pct        = metadata.get("pacca_percent", 0)
    population       = metadata.get("affected_population", 0)
    overall_risk = metadata.get("overall_risk", 50.0)

    alloc  = _get_allocation(priority_metric, retrofit_capacity)
    costs  = _get_costs(retrofit_style)
    budget = _calc_budget(alloc, costs)
    impact = _calc_impact(alloc, overall_risk, total_buildings, budget)
    phases = _timeline_phases(alloc, timeline_months)

    return f"""
Extract structured data from this government retrofit action plan and return ONLY valid JSON.
No markdown, no explanation, no code fences. No null values — use the fallback numbers below if not stated.

STRICT RULES:
- NO field may be null or empty string
- All numeric fields must have a number (use fallback values below if report is ambiguous)
- timeline phases must cover exactly {timeline_months} months total
- priority_metric must be one of: "Save Maximum Lives", "Reduce Sector Vulnerability", "Optimize Resource Allocation"
- retrofit_style must be one of: "Low-cost", "Structural", "Hybrid"

REPORT TO PARSE:
{report_text[:2000]}

FALLBACK VALUES (use if report is unclear):
- Allocation: KACHA={alloc['kacha']}, SEMI={alloc['semi']}, PACCA={alloc['pacca']}
- Budget total: {budget['grand_total']}
- Lives saved: {impact['total_lives']}
- Risk: {overall_risk}% → {impact['target_risk']}%
- BCR: {impact['bcr']}

Return this JSON with ALL fields filled:
{{
  "project_info": {{
    "sector_name": "{sector_name}",
    "magnitude": {magnitude},
    "total_buildings": {total_buildings},
    "retrofit_capacity": {retrofit_capacity},
    "population": {population},
    "avg_building_sqft": {avg_building_sqft},
    "floors": {avg_floors}, #avg building floors
    "total_sqft": {total_sqft},
    "budget_level": "{budget_level}",
    "timeline_months": {timeline_months},
    "priority_metric": "{priority_metric}",
    "retrofit_style": "{retrofit_style}"
    
  }},
  "building_stock": {{
    "kacha_percent": {kacha_pct},
    "semi_pacca_percent": {semi_pct},
    "pacca_percent": {pacca_pct},
    "kacha_label": "KACHA (Adobe & Rubble Stone)",
    "semi_label": "SEMI-PACCA (URM)",
    "pacca_label": "PACCA (RCF/RCI)"
  }},
  "allocation": {{
    "kacha": {alloc['kacha']},
    "semi_pacca": {alloc['semi']},
    "pacca": {alloc['pacca']},
    "total": {retrofit_capacity}
  }},
  "budget_pkr": {{
    "kacha": {budget['kacha_cost']},
    "semi_pacca": {budget['semi_cost']},
    "pacca": {budget['pacca_cost']},
    "engineering": {budget['engineering']},
    "quality_control": {budget['qc']},
    "awareness": {budget['awareness']},
    "grand_total": {budget['grand_total']}
  }},
  "impact": {{
    "lives_saved_kacha": {impact['lives_kacha']},
    "lives_saved_semi": {impact['lives_semi']},
    "lives_saved_pacca": {impact['lives_pacca']},
    "total_lives_saved": {impact['total_lives']},
    "current_risk_percent": {overall_risk},
    "target_risk_percent": {impact['target_risk']},
    "risk_reduction_points": {impact['risk_reduction']},
    "economic_benefit_millions": {impact['econ_total']},
    "benefit_cost_ratio": {impact['bcr']}
  }},
  "timeline": {{
    "total_months": {timeline_months},
    "phases": {{
      "phase1_months": {phases['p1_months']},
      "phase1_buildings": {phases['p1_kacha']},
      "phase1_label": "Pilot — KACHA",
      "phase2_months": {phases['p2_end'] - phases['p1_end']},
      "phase2_buildings": {phases['p2_kacha'] + phases['p2_semi']},
      "phase2_label": "Scale-up — KACHA + SEMI-PACCA",
      "phase3_months": {timeline_months - phases['p2_end']},
      "phase3_buildings": {phases['p3_semi'] + phases['p3_pacca']},
      "phase3_label": "Completion — SEMI-PACCA + PACCA"
    }}
  }}
}}
"""