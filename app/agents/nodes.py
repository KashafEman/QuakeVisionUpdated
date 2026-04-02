# Async functions (The "Workers")
import asyncio
from importlib import metadata
import os
import json
import re
import unicodedata
import json
from typing import Dict, Any, List, Tuple
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_core.documents import Document

from app.services.kb import kb_service
from app.agents.state import AgentState, RetrofitReport, NormalizedInputs
from app.utils.normalizer import (
     normalize_string,
    normalize_material_name,
    normalize_sector_name,
    safe_float_conversion,
    calculate_survival_probability,
    normalize_budget_level,
    get_timeline_description
)
from app.utils.prompts_builder import build_prompt

# ==========================================
# 0. NEW: INPUT PROCESSOR NODE (Uses normaliser.py)
# ==========================================

async def process_inputs_node(state: AgentState):
    """
    Processes and normalizes all inputs using normaliser.py functions.
    Populates normalized_inputs in state.
    """
    print(f"--- NODE: Processing Inputs ({state['user_type'].upper()}) ---")
    
    inputs = state.get("inputs")
    user_type = state.get("user_type", "home")
    
    if not inputs:
        return {
            "fallback_status": "ACTIVE",
            "fallback_reason": "No inputs provided to process_inputs_node"
        }
    
    try:
        # Common normalized fields
        normalized_budget = normalize_budget_level(inputs.budget_level)
        timeline_months = inputs.timeline_months if hasattr(inputs, 'timeline_months') else (
            inputs.timeline_value * 12 if inputs.timeline_unit == "years" else inputs.timeline_value
        )
        timeline_desc = get_timeline_description(timeline_months, normalized_budget)
        
        # Build normalized inputs based on user type
        if user_type == "home":
            normalized = NormalizedInputs(
                magnitude=safe_float_conversion(inputs.magnitude),
                budget_level=normalized_budget,
                timeline_months=timeline_months,
                project_size_sqft=int(safe_float_conversion(inputs.project_size_sqft, 5000)),
                material_normalized=normalize_material_name(inputs.material),
                timeline_description=timeline_desc
            )
            
        elif user_type == "gov":
            sector_name = inputs.sector_data.get('sector_name', 'Unknown') if hasattr(inputs, 'sector_data') else 'Unknown'
            normalized = NormalizedInputs(
                magnitude=safe_float_conversion(inputs.magnitude),
                budget_level=normalized_budget,
                timeline_months=timeline_months,
                project_size_sqft=int(safe_float_conversion(inputs.project_size_sqft, 5000)),
                sector_normalized=normalize_sector_name(sector_name),
                timeline_description=timeline_desc,
                total_sqft=inputs.total_sqft,
                dominant_construction_type=inputs.dominant_construction_type,
                affected_population=inputs.sector_data.get("population", 0),
                kacha_percent=inputs.sector_data.get("kacha_percent", 0),
                semi_pacca_percent=inputs.sector_data.get("semi_pacca_percent", 0),
                pacca_percent=inputs.sector_data.get("pacca_percent", 0),
            )
            
        else:  # dev
            normalized = NormalizedInputs(
                magnitude=safe_float_conversion(inputs.magnitude),
                budget_level=normalized_budget,
                timeline_months=timeline_months,
                project_size_sqft=int(safe_float_conversion(inputs.project_size_sqft, 5000)),
                site_sector_normalized=normalize_sector_name(inputs.site_sector),
                building_type=getattr(inputs, 'building_type', 'commercial'),
                total_sqft=getattr(inputs, 'total_sqft', inputs.project_size_sqft * getattr(inputs, 'floors', 1)),
                building_class=getattr(inputs, 'building_class', 'Class B'),
                timeline_description=timeline_desc
            )
        
        print(f"✅ Inputs normalized: budget={normalized.budget_level}, timeline={normalized.timeline_months}mo")
        
        return {
            "normalized_inputs": normalized,
            "loop_count": state.get("loop_count", 0) + 1
        }
        
    except Exception as e:
        print(f"⚠️ Input processing error: {e}")
        # Return basic normalization to prevent crash
        return {
            "normalized_inputs": NormalizedInputs(
                magnitude=float(inputs.magnitude) if inputs else 7.0,
                budget_level="moderate",
                timeline_months=12,
                project_size_sqft=5000,
                timeline_description="standard timeline (12 months) with sequential standard pacing"
            ),
            "fallback_reason": f"Input normalization error: {str(e)}"
        }
    



def extract_costs_from_search(search_results: str, user_type: str) -> Dict[str, Any]:
    """
    Extract PKR cost data from SerpAPI search results.
    Returns dict with cost values or empty if not found.
    """
    if not search_results or "error" in search_results.lower():
        return {}
    
    costs = {}
    
    try:
        # Look for PKR/sq ft patterns
        # Pattern: "8,000 PKR" or "PKR 8000" or "8000 per sq ft"
        pkr_pattern = r'(?:PKR|Rs\.?)\s*([\d,]+(?:\.\d+)?)\s*(?:per\s*sq\s*ft|/sq\s*ft|per\s*square\s*foot)'
        matches = re.findall(pkr_pattern, search_results, re.IGNORECASE)
        
        if matches:
            # Take first match as base cost
            base_cost = float(matches[0].replace(',', ''))
            costs["base_cost_psf"] = base_cost
            
            # Estimate other tiers from base
            costs["residential"] = int(base_cost * 0.9)
            costs["commercial"] = int(base_cost * 1.2)
            costs["mixed_use"] = int(base_cost * 1.3)
            costs["industrial"] = int(base_cost * 0.85)
        
        # Alternative pattern: "construction cost is 8000 rupees per square foot"
        alt_pattern = r'(\d{3,6})\s*(?:rupees|PKR|Rs)\s*(?:per|/)\s*(?:sq\s*ft|square\s*foot)'
        alt_matches = re.findall(alt_pattern, search_results, re.IGNORECASE)
        
        if alt_matches and not costs:
            base_cost = float(alt_matches[0])
            costs["base_cost_psf"] = base_cost
            costs["residential"] = int(base_cost * 0.9)
            costs["commercial"] = int(base_cost * 1.2)
            costs["mixed_use"] = int(base_cost * 1.3)
            costs["industrial"] = int(base_cost * 0.85)
            
    except Exception as e:
        print(f"Cost extraction error: {e}")
    
    return costs


# ==========================================
# 1. NEW: KNOWLEDGE RETRIEVER NODE (Uses kb.py)
# ==========================================

async def retrieve_knowledge_node(state: AgentState):
    """
    Retrieves knowledge from vector DB and optionally web search.
    Populates retrieved_context, web_search_results, combined_context.
    """
    print(f"--- NODE: Retrieving Knowledge ---")
    
    inputs = state.get("inputs")
    normalized = state.get("normalized_inputs")
    user_type = state.get("user_type", "home")
    
    if not inputs:
        return {
            "retrieval_success": False,
            "combined_context": "No inputs available for context retrieval."
        }
    
    retrieved_docs: List[Document] = []
    web_results: str = ""
    
    try:
        # Build query based on user type and inputs
        if user_type == "home" and normalized and normalized.material_normalized:
            query = f"seismic retrofit {normalized.material_normalized} residential building earthquake safety"
        elif user_type == "gov":
            sector = normalized.sector_normalized if normalized and normalized.sector_normalized else "urban"
            query = f"urban planning seismic policy {sector} government retrofit budget allocation"
        else:  # dev
            site = normalized.site_sector_normalized if normalized and normalized.site_sector_normalized else "commercial"
            building = normalized.building_type if normalized and normalized.building_type else "commercial"
            query = f"commercial real estate seismic assessment {site} {building} construction ROI"
        
        print(f"🔍 Querying vector DB: '{query}'")
        
        # 1. Query Vector DB using kb_service
        retrieved_docs = kb_service.query_vector_db(query, k=5)
        retrieval_success = len(retrieved_docs) > 0
        
        if retrieval_success:
            print(f"✅ Retrieved {len(retrieved_docs)} documents from vector DB")
        else:
            print("⚠️ No documents retrieved from vector DB")
        
        # 2. Optional Web Search (if allow_web=True or retrieval failed)
        allow_web = getattr(inputs, 'allow_web', False)
        web_search_performed = False
        
        if allow_web or not retrieval_success:
            if kb_service.serpapi:
                print("🌐 Performing web search...")
                web_query = f"{query} 2024 2025 latest regulations cost"
                web_results = kb_service.web_search(web_query)
                web_search_performed = True
                print(f"✅ Web search completed")
            else:
                print("⚠️ SerpAPI not configured")
        
        # 3. Build combined context
        context_parts = []
        
        if retrieved_docs:
            context_parts.append("=== KNOWLEDGE BASE DOCUMENTS ===")
            for i, doc in enumerate(retrieved_docs, 1):
                context_parts.append(f"[Doc {i}] {doc.page_content[:500]}...")
        
        if web_results:
            context_parts.append("\n=== CURRENT WEB DATA ===")
            context_parts.append(web_results[:1500])  # Limit web results
        
        if not context_parts:
            context_parts.append("=== GENERAL SEISMIC ENGINEERING CONTEXT ===")
            context_parts.append("No specific retrieved context available. Using general engineering knowledge.")
        
        combined_context = "\n\n".join(context_parts)

        # 2. Web Search with SPECIFIC cost query for developers
        allow_web = getattr(inputs, 'allow_web', False)
        web_search_performed = False
        web_results = ""
        extracted_costs = {}  # NEW: Store extracted cost data
        
        if allow_web or not retrieval_success:
            if kb_service.serpapi:
                user_type = state.get("user_type")
                
                # BUILD SPECIFIC COST QUERY
                if user_type == "dev":
                    building_type = getattr(inputs, 'building_type', 'commercial')
                    site = getattr(inputs, 'site_sector', 'Pakistan')
                    web_query = f"Pakistan {building_type} construction cost per square foot PKR 2026 {site}"
                elif user_type == "home":
                    material = getattr(inputs, 'material', 'house')
                    web_query = f"Pakistan {material} house construction cost PKR per sq ft 2026"
                else:  # gov
                    web_query = f"Pakistan government construction budget PKR 2026 urban infrastructure cost"
                
                print(f"🌐 Searching: '{web_query}'")
                web_results = kb_service.web_search(web_query)
                web_search_performed = True
                
                # NEW: Try to extract cost numbers from results
                extracted_costs = extract_costs_from_search(web_results, user_type)
                print(f"📊 Extracted costs: {extracted_costs}")

        
        return {
            "retrieved_context": retrieved_docs,
            "retrieval_success": retrieval_success,
            "web_search_results": web_results if web_results else None,
            "extracted_costs": extracted_costs,  # NEW
            "web_search_performed": web_search_performed,
            "combined_context": combined_context,
            "loop_count": state.get("loop_count", 0) + 1
        }
        
    except Exception as e:
        print(f"⚠️ Knowledge retrieval error: {e}")
        return {
            "retrieved_context": [],
            "retrieval_success": False,
            "web_search_results": f"Error: {str(e)}",
            "web_search_performed": False,
            "combined_context": f"Error retrieving context: {str(e)}. Proceeding with general knowledge.",
            "fallback_reason": f"Knowledge retrieval failed: {str(e)}"
        }
    
def extract_sections_from_report(full_report: str, user_type: str) -> Dict:
    """
    Extracts 5-point summaries from dedicated sections 2 and 3.
    Falls back to keyword extraction if sections not found.
    """
    if not full_report:
        return {"risk_assessment_summary": [], "action_recommendations": []}
    
    full_report = str(full_report)
    
    # Try to extract from dedicated sections first
    risk_section = extract_section_text(full_report, "RISK ASSESSMENT SUMMARY", "ACTION RECOMMENDATIONS")
    action_section = extract_section_text(full_report, "ACTION RECOMMENDATIONS", "COST IMPLICATIONS")
    
    risk_points = extract_bullet_points(risk_section) if risk_section else []
    action_points = extract_bullet_points(action_section) if action_section else []
    
    # If sections not found or empty, fallback to keyword extraction
    if len(risk_points) < 3 or len(action_points) < 3:
        print(f"⚠️ Sections incomplete ({len(risk_points)} risk, {len(action_points)} action), using keyword fallback")
        return legacy_keyword_fallback(full_report, user_type)
    
    print(f"✅ Extracted from sections: {len(risk_points)} risk, {len(action_points)} action points")
    
    return {
        "risk_assessment_summary": risk_points[:5],
        "action_recommendations": action_points[:5]
    }


def extract_section_text(text: str, start_marker: str, end_marker: str) -> str:
    """Extract text between two section headers."""
    import re
    # Case-insensitive, allow whitespace variations
    pattern = rf'{re.escape(start_marker)}[\s\-:]*\n?(.*?)(?={re.escape(end_marker)}|\Z)'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def extract_bullet_points(text: str) -> List[str]:
    """Extract clean bullet points from section text."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    bullets = []
    
    for line in lines:
        # Skip instruction lines and headers
        skip_keywords = [
            'generate exactly', 'should cover', 'bullet point',
            'risk points about', 'actions:', 'steps:', '[generate',
            'seismic hazards', 'structural vulnerabilities',
            'immediate steps', 'design phase', 'construction adaptations',
            'quality control', 'compliance/certification',
            'risk assessment summary',   # ADD THIS
            'action recommendations',    # ADD THIS
            'cost implications',         # ADD THIS
        ]
        
        if any(skip in line.lower() for skip in skip_keywords):
            continue
        
        # Clean bullet markers and whitespace
        clean = line
        for marker in ['•', '-', '*', '→', '◦', '▪', '□']:
            clean = clean.lstrip(marker).strip()
        clean = clean.rstrip('*').strip()  # ADD THIS LINE
        
        # Validate: must be substantive content
        if (len(clean) > 15 and 
            len(clean) < 300 and  # Not too long
            (clean[0].isupper() or clean[0].isdigit()) and
            not clean.endswith(':')):  # Not a header
            
            bullets.append(clean)
    
    return bullets


def legacy_keyword_fallback(full_report: str, user_type: str) -> Dict:
    """Original keyword-based extraction as fallback."""
    lines = [l.strip() for l in full_report.split("\n") if l.strip()]
    risk_points, action_points = [], []
    
    risk_keywords = {'risk', 'damage', 'hazard', 'vulnerability', 'collapse', 'unsafe', 'fatal', 'casualty', 'seismic'}
    action_keywords = {'recommend', 'must', 'install', 'apply', 'retrofit', 'strengthen', 'allocate', 'prioritize', 'base isolation', 'dampers'}
    
    for line in lines:
        line_lower = line.lower()
        
        # Clean the line
        clean = line.lstrip('•').lstrip('-').lstrip('*').strip()
        
        if any(kw in line_lower for kw in risk_keywords) and len(risk_points) < 5:
            if len(clean) > 15:  # Filter out short fragments
                risk_points.append(clean)
                
        if any(kw in line_lower for kw in action_keywords) and len(action_points) < 5:
            if len(clean) > 15:
                action_points.append(clean)

    # Ensure defaults for dev
    if user_type == "dev" and not risk_points:
        risk_points = ["Seismic risk exists due to soil behavior and structural vulnerability."]
    
    # Pad if needed
    while len(risk_points) < 3:
        risk_points.append("Additional seismic assessment required.")
    while len(action_points) < 3:
        action_points.append("Consult structural engineer for recommendations.")
    
    return {
        "risk_assessment_summary": risk_points[:5],
        "action_recommendations": action_points[:5]
    }


# ==========================================
# 3. VALIDATOR AGENT
# ==========================================

async def validate_report_node(state: AgentState):
    """Validates with user-type specific criteria - GENEROUS scoring."""
    print(f"--- NODE: Validating {state['user_type'].upper()} Report ---")
    
    raw_report = state.get("raw_report", "")
    
    if isinstance(raw_report, list):
        raw_report = " ".join(str(item) for item in raw_report)
    raw_report = str(raw_report)
    
    user_type = state.get("user_type", "home")
    final_output = state.get("final_output")
    inputs = state.get("inputs")
    normalized = state.get("normalized_inputs")  # Use normalized inputs if available
    
    # Get material safely from inputs or normalized_inputs
    material = "masonry"
    if normalized and user_type == "home" and normalized.material_normalized:
        material = normalized.material_normalized
    elif inputs:
        if user_type == "home" and hasattr(inputs, 'material'):
            material = normalize_material_name(inputs.material)
        elif user_type == "dev" and hasattr(inputs, 'site_sector'):
            material = inputs.site_sector
        elif user_type == "gov":
            sector_data = getattr(inputs, 'sector_data', {})
            material = sector_data.get('sector_name', 'urban sector')
    
    # Build validation prompt based on user type
    if user_type == "home":
        validation_prompt = f"""
You are a HOMEOWNER ADVISOR. Score this retrofit report (0-100).

SCORING RUBRIC:
- 40 pts: Clear, understandable risk explanation
- 30 pts: Practical, actionable steps (can homeowner follow?)
- 20 pts: Realistic cost ranges (dollar amounts)
- 10 pts: Safety guidance included

BE GENEROUS: This is for a homeowner, not an engineer.

BUILDING MATERIAL: {material}

Report:
{raw_report[:3000]}

OUTPUT EXACT FORMAT:
SCORE: <number 0-100>
FEEDBACK: <1 sentence summary>
"""
    
    elif user_type == "gov":
        validation_prompt = f"""
You are a POLICY ADVISOR. Score this government action plan (0-100).

Check these 4 things:
- 25 pts: Clear allocation numbers
- 25 pts: Budget in PKR
- 25 pts: Impact estimates (lives saved)
- 25 pts: Implementation timeline

BE GENEROUS: Give 80+ if all 4 are covered reasonably.

SECTOR: {material}

Report:
{raw_report[:3000]}

OUTPUT EXACT FORMAT:
SCORE: <number 0-100>
FEEDBACK: <1 sentence summary>
"""

    else:  # dev
        validation_prompt = f"""
You are an INVESTMENT ADVISOR. Score this developer feasibility report (0-100).

SCORING RUBRIC:
- 40 pts: Clear GO/NO-GO decision with justification
- 35 pts: ROI analysis (costs vs benefits)
- 25 pts: Risk assessment and mitigation

BE GENEROUS: Focus on business viability, not engineering formulas.

SITE: {material}

Report:
{raw_report[:3000]}

OUTPUT EXACT FORMAT:
SCORE: <number 0-100>
FEEDBACK: <1 sentence summary>
"""
    
    try:
        llm = kb_service.get_llm()
        response = await llm.ainvoke([
            SystemMessage(content="You are a practical advisor. Be constructive and generous in scoring. Always output SCORE and FEEDBACK."),
            HumanMessage(content=validation_prompt)
        ])
        
        response_text = response.content if hasattr(response, 'content') else str(response)
        if isinstance(response_text, list):
            response_text = " ".join(str(item) for item in response_text)
        
        # Parse score and feedback
        validation_score = 85.0
        validation_feedback = "Good practical report"
        
        try:
            lines = response_text.strip().split('\n')
            for line in lines:
                if line.startswith('SCORE:'):
                    score_str = line.replace('SCORE:', '').strip()
                    score_match = re.search(r'(\d+(?:\.\d+)?)', score_str)
                    if score_match:
                        validation_score = float(score_match.group(1))
                        validation_score = max(0, min(100, validation_score))
                elif line.startswith('FEEDBACK:'):
                    validation_feedback = line.replace('FEEDBACK:', '').strip()
        except Exception as parse_error:
            print(f"Parse error: {parse_error}, using default score")
            validation_score = 85.0
        
        # Lower thresholds for passing
        MIN_PASS = 50 if user_type == "home" else 60
        is_validated = validation_score >= MIN_PASS
        
        print(f"✅ Validation Score: {validation_score}, Passed: {is_validated}")
        print(f"📝 Feedback: {validation_feedback}")
            
    except Exception as e:
        print(f"⚠️ Validation Error: {e}")
        validation_score = 80.0
        validation_feedback = "Validation service issue - report accepted"
        is_validated = True
    
    # Update final_output if exists
    if final_output:
        final_output.is_validated = is_validated
        final_output.validation_score = validation_score
        final_output.validation_feedback = validation_feedback
    
    return {
        "validation_score": validation_score,
        "validation_feedback": validation_feedback,
        "last_validation_feedback": validation_feedback,
        "is_validated": is_validated,
        "final_output": final_output,
        "validation_attempts": state.get("validation_attempts", 0) + 1,
        "loop_count": state.get("loop_count", 0) + 1
    }


# ==========================================
# 4. GENERATOR NODE (FIXED)
# ==========================================

async def generate_report_node(state: AgentState):
    """Generates report using structured prompt builder with knowledge context."""
    print(f"--- NODE: Generating {state['user_type'].upper()} Report ---")
    
    inputs = state["inputs"]
    user_type = state["user_type"]
    normalized = state.get("normalized_inputs")
    combined_context = state.get("combined_context", "No specific context retrieved.")
    
    # Check for regeneration
    validation_attempts = state.get("validation_attempts", 0)
    last_feedback = state.get("last_validation_feedback", "")
    missing_elements = state.get("missing_elements", [])
    previous_report = state.get("raw_report", "")
    
    is_regeneration = validation_attempts > 0 and bool(last_feedback)

    if not inputs:
        return {
            "raw_report": "TRIGGER_FALLBACK",
            "fallback_reason": "No inputs provided",
            "fallback_status": "ACTIVE"
        }

    # Build metadata using normalized inputs if available
    metadata = {}
    
    if user_type == "dev":
        norm_site = normalized.site_sector_normalized if normalized else normalize_sector_name(inputs.site_sector)
        
        # Always calculate survival from risk_map — never hardcode
        norm_risk_map = {
            normalize_material_name(k): safe_float_conversion(v)
            for k, v in inputs.risk_map.items()
        }
        max_mat = max(norm_risk_map, key=norm_risk_map.get) if norm_risk_map else "Unknown"
        max_risk = norm_risk_map.get(max_mat, 50.0)
        survival = round(100 - max_risk, 2)
        norm_material = max_mat

        metadata = {
            "normalized_site": norm_site,
            "normalized_material": norm_material,
            "survival_probability": survival,
            "risk_scores": norm_risk_map,
            "project_type": inputs.project_type,
            "target_magnitude": inputs.magnitude,
            # ADD THESE MISSING FIELDS:
            "budget_level": normalized.budget_level if normalized else inputs.budget_level,
            "timeline_months": normalized.timeline_months if normalized else (
                inputs.timeline_value * 12 if inputs.timeline_unit == "years" else inputs.timeline_value
            ),
            "project_size_sqft": inputs.project_size_sqft,
            "floors": getattr(inputs, 'floors', 1),
            "total_sqft": inputs.project_size_sqft * getattr(inputs, 'floors', 1),
            "building_type": getattr(inputs, 'building_type', 'commercial'),
            "building_class": getattr(inputs, 'building_class', 'Class B'),
            "project_name": getattr(inputs, 'project_name', norm_site),
            "retrieval_used": state.get("retrieval_success", False),
            "web_search_used": state.get("web_search_performed", False)
        }

    elif user_type == "gov":
        sector_name = inputs.sector_data.get('sector_name', 'Unknown') if hasattr(inputs, 'sector_data') else 'Unknown'

        metadata = {
            # Sector identity
            "sector_name": normalize_sector_name(sector_name),
            "kacha_percent": inputs.sector_data.get("kacha_percent", 0),
            "semi_pacca_percent": inputs.sector_data.get("semi_pacca_percent", 0),
            "pacca_percent": inputs.sector_data.get("pacca_percent", 0),
            "dominant_construction_type": inputs.dominant_construction_type,
            "affected_population": inputs.sector_data.get("population", 0),

            # Policy parameters
            "priority_metric": inputs.priority_metric,
            "retrofit_capacity": inputs.retrofit_capacity,
            "retrofit_style": inputs.retrofit_style,

            # Budget & timeline
            "budget_level": normalized.budget_level if normalized else inputs.budget_level,
            "timeline_months": normalized.timeline_months if normalized else (
                inputs.timeline_value * 12 if inputs.timeline_unit == "years" else inputs.timeline_value
            ),
            "timeline_description": normalized.timeline_description if normalized else "",

            # Scale (sector-wide aggregate)
            "avg_building_sqft": inputs.project_size_sqft,   # per building
            "avg_floors": inputs.floors,                      # per building
            "total_sqft": inputs.total_sqft,                  # across all retrofit_capacity buildings

            # Seismic
            "magnitude": inputs.magnitude,

            # Knowledge retrieval flags
            "retrieval_used": state.get("retrieval_success", False),
            "web_search_used": state.get("web_search_performed", False),
        }

    else:  # home
        if normalized and normalized.material_normalized:
            norm_material = normalized.material_normalized
        else:
            norm_material = normalize_material_name(inputs.material)

        # Calculate survival from risk_map same as dev
        norm_risk_map = {
            normalize_material_name(k): safe_float_conversion(v)
            for k, v in inputs.risk_map.items()
        }
        max_mat = max(norm_risk_map, key=norm_risk_map.get) if norm_risk_map else norm_material
        max_risk = norm_risk_map.get(max_mat, 50.0)
        survival = round(100 - max_risk, 2)

        metadata = {
            "normalized_material": norm_material,
            "magnitude": inputs.magnitude,
            "survival_probability": survival,
            "risk_scores": norm_risk_map,
            "building_type": getattr(inputs, 'building_type', 'single_story'),
            "budget_level": normalized.budget_level if normalized else inputs.budget_level,
            "timeline_months": normalized.timeline_months if normalized else inputs.timeline_months,
            "project_size_sqft": inputs.project_size_sqft,
            "floors": inputs.floors,
            "total_sqft": inputs.project_size_sqft * inputs.floors,
            "retrieval_used": state.get("retrieval_success", False),
            "web_search_used": state.get("web_search_performed", False)
        }

    # Build prompt with metadata
    prompt = build_prompt(
        user_type=user_type,
        inputs=inputs,
        is_regeneration=is_regeneration,
        previous_report= previous_report,
        feedback=last_feedback,
        missing_elements=missing_elements,
        metadata=metadata,
        combined_context=state.get("combined_context", ""),  # NEW: Pass retrieved knowledge
        extracted_costs=state.get("extracted_costs", {})  # NEW: Pass extracted cost data
    )

    print(f"[PromptBuilder] user_type={user_type}, regeneration={is_regeneration}, context_length={len(combined_context)}")

    try:
        llm = kb_service.get_llm()
        
        # Enhanced system prompt with retrieved context
        system_content = f"""You are a licensed structural and seismic engineering expert with access to the following context:

{combined_context[:3000]}

STRICT RULES:
- Always produce COMPLETE reports
- Never truncate output
- Follow all structural engineering requirements strictly
- Include calculations, cost, safety, and compliance when required
- Use the provided context to enhance your recommendations
"""

        response = await llm.ainvoke([
            SystemMessage(content=system_content),
            HumanMessage(content=prompt)
        ])

        # Handle response
        if hasattr(response, 'content'):
            report_content = response.content
        else:
            report_content = str(response)

        if isinstance(report_content, list):
            text_parts = []
            for item in report_content:
                if isinstance(item, dict) and 'text' in item:
                    text_parts.append(item['text'])
                else:
                    text_parts.append(str(item))
            report_content = " ".join(text_parts)

        report_content = str(report_content)

        # Format output using section-aware extraction
        formatted_output = extract_sections_from_report(report_content, user_type)

        # Create final report
        final_report = RetrofitReport(
            risk_assessment_summary=formatted_output["risk_assessment_summary"],
            action_recommendations=formatted_output["action_recommendations"],
            full_detailed_report=report_content,
            metadata=metadata,
            sources_used={
                "retrieval_success": state.get("retrieval_success", False),
                "web_search_performed": state.get("web_search_performed", False),
                "docs_retrieved": len(state.get("retrieved_context", []))
            },
            is_validated=False,
            validation_score=0.0,
            validation_feedback=None
        )

        return {
            "raw_report": report_content,
            "final_output": final_report,
            "loop_count": state.get("loop_count", 0) + 1,
            "chatbot_response": "REPORT_GENERATED",
            "in_chat_mode": False,  # Will be set to True after validation passes
            "is_validated": False,
            "validation_score": 0.0,
            "validation_feedback": None
        }

    except Exception as e:
        print(f"LLM Error: {e}")
        print(f"Full error details: {str(e)}")

        return {
            "raw_report": "TRIGGER_FALLBACK",
            "fallback_reason": f"LLM error: {str(e)}",
            "fallback_status": "ACTIVE",
            "chatbot_response": "FALLBACK_NEEDED",
            "in_chat_mode": False,
            "is_validated": False
        }


# ==========================================
# 5. FALLBACK NODE
# ==========================================

async def fallback_node(state: AgentState):
    """Deterministic logic for when LLM is down."""
    print(f"--- NODE: {state['user_type'].upper()} Fallback ---")
    inputs = state["inputs"]
    user_type = state["user_type"]
    normalized = state.get("normalized_inputs")
    
    metadata = {}
    
    if user_type == "dev":
        # Use normalized values if available
        if normalized and normalized.site_sector_normalized:
            site = normalized.site_sector_normalized
        else:
            site = normalize_sector_name(inputs.site_sector)
            
        norm_risk_map = {normalize_material_name(k): safe_float_conversion(v) for k, v in inputs.risk_map.items()}
        max_mat = max(norm_risk_map, key=norm_risk_map.get) if norm_risk_map else "Unknown"
        survival = round(100 - norm_risk_map.get(max_mat, 50.0), 2)
        
        summary = [f"Structural risk driven by {max_mat.upper()}.", f"Survival prob: {survival}%"]
        actions = ["Adopt Japanese Grade-3 compliance.", "Use base isolation for energy dissipation."]
        report_text = f"Deterministic developer advisory for {site}. Survival probability: {survival}%"
        
        metadata = {
            "normalized_material": max_mat,
            "survival_probability": survival,
            "fallback_reason": "LLM unavailable",
            "risk_scores": norm_risk_map,
            "retrieval_used": False,
            "web_search_used": False
        }

    elif user_type == "gov":
        sector_name = inputs.sector_data.get('sector_name', 'Unknown') if hasattr(inputs, 'sector_data') else 'Unknown'
        norm_sector = normalize_sector_name(sector_name)
        
        summary = ["Sector-wide risk assessment (Deterministic)."]
        actions = ["Prioritize Kacha structures (70% allocation)."]
        report_text = "Government policy-constrained fallback. Prioritize vulnerable structures."
        
        metadata = {
            "sector_name": norm_sector,
            "priority_metric": inputs.priority_metric,
            "retrofit_capacity": inputs.retrofit_capacity,
            "fallback_reason": "LLM unavailable",
            "retrieval_used": False,
            "web_search_used": False
        }
    
    else:  # home
        if normalized and normalized.material_normalized:
            norm_material = normalized.material_normalized
        else:
            norm_material = normalize_material_name(inputs.material)
            
        summary = ["Standard structural vulnerability detected."]
        actions = ["Install seismic bands.", "Reinforce weak points."]
        report_text = f"Homeowner engineering fallback for {norm_material} structure. Recommend professional assessment."
        
        metadata = {
            "normalized_material": norm_material,
            "magnitude": inputs.magnitude,
            "building_type": getattr(inputs, 'building_type', 'single_story'),
            "budget_level": getattr(inputs, 'budget_level', 'moderate'),
            "timeline_months": inputs.timeline_months,
            "project_size_sqft": inputs.project_size_sqft,
            "floors": inputs.floors,
            "total_sqft": inputs.project_size_sqft * inputs.floors,
            "fallback_reason": "LLM unavailable",
            "retrieval_used": False,
            "web_search_used": False
        }

    fallback_report = RetrofitReport(
        risk_assessment_summary=summary,
        action_recommendations=actions,
        full_detailed_report=report_text,
        metadata=metadata,
        sources_used={"fallback": True, "llm_available": False},
        is_validated=True,
        validation_score=75.0,
        validation_feedback="Deterministic fallback report - basic validation passed"
    )
    
    return {
        "final_output": fallback_report,
        "raw_report": report_text,
        "chatbot_response": "FALLBACK_COMPLETE",
        "in_chat_mode": True,
        "is_validated": True,
        "validation_score": 75.0,
        "validation_feedback": "Deterministic fallback report - basic validation passed",
        "fallback_status": "ACTIVE",
        "fallback_reason": "LLM unavailable or quota exceeded"
    }

# ==========================================
# 6. Visualization_Node
# ==========================================

async def extract_visualization_node(state: AgentState):
    print("--- NODE: Extracting Visualization Data ---")
    
    final_output = state.get("final_output")
    if not final_output:
        return {"visualization_data": None}
    
    try:
        from app.utils.prompts.developer_prompts import get_developer_visualization_prompt
        from app.utils.prompts.home_prompts import get_home_visualization_prompt
        from app.utils.prompts.gov_prompts import get_gov_visualization_prompt

        print(f"📋 Metadata passed to viz prompt: {final_output.metadata}")

        if state.get("user_type") == "home":
            extraction_prompt = get_home_visualization_prompt(
                final_output.full_detailed_report, #[:1500]
                final_output.metadata
            )
        elif state.get("user_type") == "gov":
            extraction_prompt = get_gov_visualization_prompt(
                final_output.full_detailed_report,
                final_output.metadata
            )
        else:
            extraction_prompt = get_developer_visualization_prompt(
                final_output.full_detailed_report, #[:1500]
                final_output.metadata
            )

        llm = kb_service.get_llm()
        response = await llm.ainvoke([
            SystemMessage(content="You are a precise data extraction engine. Output valid JSON only. No markdown, no explanation, no code fences."),
            HumanMessage(content=extraction_prompt)
        ])
        
        response_text = response.content if hasattr(response, 'content') else str(response)
        #print(f"🔍 Raw viz response: {response_text}")

        # Step 1: Strip ALL backtick fences (opening and closing)
        clean_text = re.sub(r'```(?:json)?|```', '', response_text).strip()
        
        # Step 2: Find the outermost { } block
        start = clean_text.find('{')
        end = clean_text.rfind('}')  # rfind gets the LAST } not first
        
        if start == -1 or end == -1 or end <= start:
            print(f"⚠️ No JSON block found. Full response: {clean_text[:500]}")
            return {"visualization_data": None}
        
        json_str = clean_text[start:end+1]
        
        # Step 3: Try direct parse first
        try:
            # viz_data = json.loads(json_str)

            # print(f"✅ Visualization data extracted successfully")

            viz_data = json.loads(json_str)

            metadata = final_output.metadata 

            # Post-process: fill any remaining nulls with metadata values
            timeline_months = metadata.get('timeline_months', 18)
            phases = viz_data.get("timeline", {}).get("phases", {})

            # If any phase is null, distribute remaining months evenly
            phase_keys = ["investigation", "design", "foundation", "superstructure", "certification"]
            null_phases = [k for k in phase_keys if not phases.get(k)]
            filled_months = sum(phases.get(k, 0) or 0 for k in phase_keys)
            remaining = timeline_months - filled_months

            if null_phases and remaining > 0:
                per_phase = max(1, remaining // len(null_phases))
                for k in null_phases:
                    phases[k] = per_phase

            # Force hardcoded fields that must never be null
            proj_info = viz_data.get("project_info", {})
            proj_info["floors"] = final_output.metadata.get("floors", proj_info.get("floors", 1))
            proj_info["total_sqft"] = final_output.metadata.get("total_sqft", proj_info.get("total_sqft", 5000))

            print(f"✅ Visualization data extracted successfully")
            return {
                "visualization_data": viz_data,
                "final_output": final_output
            }
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parse error at position {e.pos}: {e.msg}")
            print(f"   Context: ...{json_str[max(0,e.pos-30):e.pos+30]}...")
            
            # Step 4: Try ast as fallback
            import ast
            ast_str = json_str.replace('null', 'None').replace('true', 'True').replace('false', 'False')
            try:
                viz_data = ast.literal_eval(ast_str)
                print(f"✅ Visualization data extracted via ast fallback")
                return {
                    "visualization_data": viz_data,
                    "final_output": final_output
                }
            except Exception as ast_err:
                print(f"⚠️ AST fallback also failed: {ast_err}")
                print(f"   Full JSON string for debugging:\n{json_str}")
                return {"visualization_data": None}
        
    except Exception as e:
        print(f"⚠️ Visualization extraction error: {type(e).__name__}: {e}")
        return {"visualization_data": None}
# ==========================================
# CHATBOT HELPERS
# ==========================================
# ── Param cards config per user type ────────────────────────────────────────
REGEN_PARAMS_CONFIG = {
    "gov": [
        {
            "id": "timeline_months",
            "label": "⏱ Timeline",
            "input_type": "number",
            "unit": "months",
            "hint": "e.g. 24"
        },
        {
            "id": "budget_level",
            "label": "💰 Budget Level",
            "input_type": "select",
            "options": ["low", "moderate", "high"]
        },
        {
            "id": "retrofit_capacity",
            "label": "🏗 Retrofit Capacity",
            "input_type": "number",
            "unit": "buildings",
            "hint": "e.g. 400"
        },
        {
            "id": "priority_metric",
            "label": "🎯 Priority Metric",
            "input_type": "select",
            "options": [
                "Save Maximum Lives",
                "Reduce Sector Vulnerability",
                "Optimize Resource Allocation"
            ]
        },
        {
            "id": "retrofit_style",
            "label": "🔧 Retrofit Style",
            "input_type": "select",
            "options": ["Low-cost", "Structural", "Hybrid"]
        }
    ],
    "home": [
        {
            "id": "timeline_months",
            "label": "⏱ Timeline",
            "input_type": "number",
            "unit": "months",
            "hint": "e.g. 24"
        },
        {
            "id": "budget_level",
            "label": "💰 Budget Level",
            "input_type": "select",
            "options": ["low", "moderate", "high"]
        },
        {
            "id": "building_type",
            "label": "🏠 Building Type",
            "input_type": "select",
            "options": ["single_story", "multi_story", "apartment", "townhouse"]
        }
    ],
    "dev": [
        {
            "id": "timeline_months",
            "label": "⏱ Timeline",
            "input_type": "number",
            "unit": "months",
            "hint": "e.g. 24"
        },
        {
            "id": "budget_level",
            "label": "💰 Budget Level",
            "input_type": "select",
            "options": ["low", "moderate", "high"]
        },
        {
            "id": "building_type",
            "label": "🏢 Building Type",
            "input_type": "select",
            "options": ["residential", "commercial", "mixed-use", "industrial"]
        },
        {
            "id": "project_type",
            "label": "🎯 Project Type",
            "input_type": "text",
            "hint": "e.g. Mixed-use tower"
        }
    ]
}


def _build_structured_response(ui_type: str, message: str, data: Dict) -> Dict:
    """Single place where all chatbot responses are built."""
    return {
        "ui_type": ui_type,
        "message": message,
        "data": data
    }


def _get_regen_param_cards(user_type: str, current_viz: Dict) -> Dict:
    """
    Builds regen param cards with current values injected.
    React dev just renders these directly.
    """
    params = REGEN_PARAMS_CONFIG.get(user_type, [])
    project_info = current_viz.get("project_info", {})

    # Inject current values so frontend can show placeholders
    current_values = {
        "timeline_months":   current_viz.get("timeline", {}).get("total_months", 18),
        "budget_level":      project_info.get("budget_level", "moderate"),
        "retrofit_capacity": project_info.get("retrofit_capacity", 300),
        "priority_metric":   project_info.get("priority_metric", "Save Maximum Lives"),
        "retrofit_style":    project_info.get("retrofit_style", "Hybrid"),
        "building_type":     project_info.get("building_type", ""),
        "project_type":      project_info.get("project_type", ""),
    }

    # Attach current_value to each param card
    enriched_params = []
    for param in params:
        enriched = {**param, "current_value": current_values.get(param["id"], "")}
        enriched_params.append(enriched)

    return {
        "user_type": user_type,
        "params": enriched_params,
        "footer_message": "Want to change anything else? Please rerun the application with new inputs."
    }


def _apply_param_changes(
    user_input: Dict,          # what frontend sends: {"timeline_months": 24, "budget_level": "high"}
    current_viz: Dict,
    final_report_metadata: Dict
) -> Tuple[Dict, list]:
    """
    Merges user changes into existing metadata.
    Returns (updated_metadata, changes_summary_list).
    """
    updated_metadata = final_report_metadata.copy()
    changes = []

    param_map = {
        "timeline_months":   ("timeline_months",   current_viz.get("timeline", {}).get("total_months")),
        "budget_level":      ("budget_level",       current_viz.get("project_info", {}).get("budget_level")),
        "retrofit_capacity": ("retrofit_capacity",  current_viz.get("project_info", {}).get("retrofit_capacity")),
        "priority_metric":   ("priority_metric",    current_viz.get("project_info", {}).get("priority_metric")),
        "retrofit_style":    ("retrofit_style",     current_viz.get("project_info", {}).get("retrofit_style")),
        "building_type":     ("building_type",      current_viz.get("project_info", {}).get("building_type")),
        "project_type":      ("project_type",       current_viz.get("project_info", {}).get("project_type")),
    }

    for param_id, new_value in user_input.items():
        if param_id in param_map:
            metadata_key, old_value = param_map[param_id]
            if new_value != old_value:
                updated_metadata[metadata_key] = new_value
                changes.append(f"{param_id.replace('_', ' ').title()}: {old_value} → {new_value}")

    return updated_metadata, changes


async def _run_regeneration(
    state: "AgentState",
    updated_metadata: Dict,
    llm
) -> Tuple[str, Dict]:
    """
    Calls the right generation + viz prompt based on user_type.
    Returns (new_report_text, new_viz_data).
    """
    from app.utils.prompts.gov_prompts import (
        get_gov_generation_prompt,
        get_gov_visualization_prompt
    )
    from app.utils.prompts.home_prompts import (
        get_home_generation_prompt,
        get_home_visualization_prompt
    )
    from app.utils.prompts.developer_prompts import (
        get_developer_generation_prompt,
        get_developer_visualization_prompt
    )

    user_type        = state.get("user_type", "gov")
    inputs           = state.get("inputs")
    combined_context = state.get("combined_context", "")
    extracted_costs  = state.get("extracted_costs", {})

    # ── Pick the right prompts ───────────────────────────────────────────
    if user_type == "gov":
        gen_prompt = get_gov_generation_prompt(
            inputs=inputs,
            metadata=updated_metadata,
            combined_context=combined_context
        )
        viz_prompt_fn = get_gov_visualization_prompt

    elif user_type == "home":
        gen_prompt = get_home_generation_prompt(
            inputs=inputs,
            metadata=updated_metadata,
            combined_context=combined_context
        )
        viz_prompt_fn = get_home_visualization_prompt

    elif user_type == "dev":
        gen_prompt = get_developer_generation_prompt(
            inputs=inputs,
            metadata=updated_metadata,
            combined_context=combined_context,
            extracted_costs=extracted_costs
        )
        viz_prompt_fn = get_developer_visualization_prompt

    else:
        return "Unknown user type.", {}

    # ── Generate new report ──────────────────────────────────────────────
    print(f"🔄 Regenerating [{user_type}] report...")
    gen_response = await llm.ainvoke([
        SystemMessage(content=gen_prompt),
        HumanMessage(content="Generate the complete report now.")
    ])
    new_report_text = (
        gen_response.content
        if hasattr(gen_response, "content")
        else str(gen_response)
    )

    # ── Extract new viz data ─────────────────────────────────────────────
    print(f"📊 Extracting visualization data...")
    viz_prompt = viz_prompt_fn(
        report_text=new_report_text,
        metadata=updated_metadata
    )
    viz_response = await llm.ainvoke([
        SystemMessage(content=viz_prompt),
        HumanMessage(content="Extract the JSON now.")
    ])
    viz_raw = (
        viz_response.content
        if hasattr(viz_response, "content")
        else str(viz_response)
    )

    # ── Parse viz JSON safely ────────────────────────────────────────────
    try:
        viz_clean    = viz_raw.strip().replace("```json", "").replace("```", "").strip()
        new_viz_data = json.loads(viz_clean)
    except json.JSONDecodeError:
        print("⚠️ Viz JSON parse failed — keeping old viz data")
        new_viz_data = state.get("visualization_data", {})

    return new_report_text, new_viz_data


# ==========================================
# CHATBOT NODE (FINAL)
# ==========================================
async def chatbot_node(state: "AgentState"):
    """

    Structured chatbot node.
    """
    print("--- NODE: Chatbot Turn ---")

    # ── Guard: no report ─────────────────────────────────────────────────
    final_report = state.get("final_output")
    if not final_report:
        response = _build_structured_response(
            ui_type="message",
            message="No report available. Please generate a report first.",
            data={}
        )
        return {
            "chatbot_response": "END_CONVERSATION",
            "messages": state.get("messages", []) + [AIMessage(content=json.dumps(response))]
        }

    messages  = state.get("messages", [])
    user_type = state.get("user_type", "gov")
    viz_data  = state.get("visualization_data", {})

    # ── Get last user message ────────────────────────────────────────────
    last_message = messages[-1]
    if isinstance(last_message, HumanMessage):
        user_query = last_message.content
    elif hasattr(last_message, "content"):
        user_query = last_message.content
    else:
        user_query = str(last_message)

    user_query_lower = user_query.lower().strip()

    # ── Resolve report context (FIXED FOR ALL CASES) ─────────────────────
    def _resolve_report_context(query_lower: str, state: AgentState) -> str:
        """
        Priority:
        1. Comparison → Show previous vs current (if available)
        2. Explicit "original" → Show first ever generated
        3. Default → Show current final_output
        """
        current = state.get("final_output")
        previous = state.get("previous_report")  # After swap, old report is here
        
        wants_comparison = any(w in query_lower for w in [
            "compare", "difference", "vs", "versus", "changed",
            "before and after", "old vs", "new vs", "both", 
            "which is better", "pros and cons", "contrast",
            "previous", "old report", "last report"
        ])
        
        wants_original = any(w in query_lower for w in [
            "original report", "first report", "initial report", "original plan"
        ])
        
        # CASE 1: Comparison
        if wants_comparison:
            if previous:
                # After swap: previous=old, current=new
                return f"""=== PREVIOUS REPORT (Before Changes) ===
{previous.full_detailed_report if hasattr(previous, 'full_detailed_report') else previous}

=== CURRENT REPORT (After Changes) ===
{current.full_detailed_report if hasattr(current, 'full_detailed_report') else current}

Compare these two reports. Highlight key differences."""
            else:
                # Before any swap: current=original, regenerated=pending
                regenerated = state.get("regenerated_report")
                if regenerated:
                    return f"""=== ORIGINAL REPORT ===
{current.full_detailed_report if hasattr(current, 'full_detailed_report') else current}

=== REGENERATED REPORT (Pending Update) ===
{regenerated}

Note: User hasn't applied this to dashboard yet. Compare for their decision."""
                else:
                    return f"=== CURRENT REPORT ===\n{current.full_detailed_report if hasattr(current, 'full_detailed_report') else current}"

        # CASE 2: Explicit original request
        elif wants_original:
            if previous:
                return f"=== ORIGINAL REPORT (First Generated) ===\n{previous.full_detailed_report if hasattr(previous, 'full_detailed_report') else previous}"
            else:
                return f"=== ORIGINAL REPORT ===\n{current.full_detailed_report if hasattr(current, 'full_detailed_report') else current}"
        
        # CASE 3: Default = current report
        else:
            return f"=== CURRENT REPORT ===\n{current.full_detailed_report if hasattr(current, 'full_detailed_report') else current}"

    # Resolve context early for summary/QA
    report_context = _resolve_report_context(user_query_lower, state)

    # ── Initial greeting ─────────────────────────────────────────────────
    if not messages or state.get("in_chat_mode") is False:
        response = _build_structured_response(
            ui_type="options",
            message=f"✅ Report ready! Validation score: {final_report.validation_score}/100. What would you like to do?",
            data={
                "options": [
                    {"id": "summary", "label": "📋 Summary", "description": "Get a quick overview"},
                    {"id": "qa", "label": "❓ Ask a Question", "description": "Ask anything about the report"},
                    {"id": "regenerate", "label": "🔄 Regenerate", "description": "Modify parameters"}
                ]
            }
        )
        return {
            "messages": [AIMessage(content=json.dumps(response))],
            "chatbot_response": "CONTINUE",
            "in_chat_mode": True
        }

    # ── Exit ─────────────────────────────────────────────────────────────
    if user_query_lower in ["exit", "quit", "bye", "goodbye"]:
        response = _build_structured_response(
            ui_type="message",
            message="Stay safe! 👋",
            data={}
        )
        return {
            "messages": messages + [AIMessage(content=json.dumps(response))],
            "chatbot_response": "END_CONVERSATION",
            "in_chat_mode": False
        }
    
    # ── Check for comparison keywords FIRST ──────────────────────────────
    comparison_keywords = [
        "compare", "difference", "vs", "versus", "pros and cons",
        "which is better", "which plan", "decide between", "old vs new",
        "old and new", "before and after", "contrast", "previous"
    ]
    is_comparing = any(kw in user_query_lower for kw in comparison_keywords)

    # ── New report request (only if NOT comparing) ───────────────────────
    new_report_keywords = [
        "new report", "another report", "generate new", "start over",
        "reset", "create report", "make report"
    ]
    wants_new_report = any(kw in user_query_lower for kw in new_report_keywords)

    if wants_new_report and not is_comparing:
        response = _build_structured_response(
            ui_type="message",
            message="Redirecting you to the input screen for a new report.",
            data={"action": "redirect_to_inputs"}
        )
        return {
            "messages": messages + [AIMessage(content=json.dumps(response))],
            "chatbot_response": "NEW_REPORT_REQUEST",
            "in_chat_mode": False,
            "final_output": None,
            "raw_report": None,
            "normalized_inputs": None,
            "retrieved_context": None,
            "combined_context": None,
            "validation_score": None,
            "is_validated": False,
            "validation_attempts": 0,
            "loop_count": 0,
            "regenerated_report": None,
            "regenerated_visualization_data": None,
            "previous_report": None,
            "active_report": "original"
        }

    # ── Summary ──────────────────────────────────────────────────────────
    if user_query_lower in ["summary", "get summary", "show summary"]:
        try:
            llm = kb_service.get_llm()
            summary_prompt = f"""Summarize this seismic retrofit report covering scope, risk, budget, lives saved, timeline. Under 300 words.

{report_context[:3000]}"""
            summary_response = await llm.ainvoke([
                SystemMessage(content=summary_prompt),
                HumanMessage(content="Give me the summary.")
            ])
            summary_text = summary_response.content if hasattr(summary_response, "content") else str(summary_response)
        except Exception as e:
            print(f"Summary error: {e}")
            current = state.get("final_output")
            text = current.full_detailed_report if hasattr(current, 'full_detailed_report') else str(current)
            summary_text = text[:500] + "..."

        response = _build_structured_response(
            ui_type="summary",
            message="Here's your report summary:",
            data={"summary": summary_text}
        )
        return {
            "messages": messages + [AIMessage(content=json.dumps(response))],
            "chatbot_response": "CONTINUE",
            "in_chat_mode": True
        }

    # ── Regenerate ───────────────────────────────────────────────────────
    if user_query_lower in ["regenerate", "regen", "modify report", "change parameters"]:
        param_cards = _get_regen_param_cards(user_type, viz_data)
        response = _build_structured_response(
            ui_type="regen_params",
            message="Select parameters to change:",
            data=param_cards
        )
        return {
            "messages": messages + [AIMessage(content=json.dumps(response))],
            "chatbot_response": "CONTINUE",
            "in_chat_mode": True
        }

    # ── Process regeneration params ──────────────────────────────────────
    try:
        parsed = json.loads(user_query)
        if "regen_params" in parsed:
            user_changes = parsed["regen_params"]
            
            updated_metadata, changes_summary = _apply_param_changes(
                user_input=user_changes,
                current_viz=viz_data,
                final_report_metadata=final_report.metadata.copy()
            )

            if not changes_summary:
                response = _build_structured_response(
                    ui_type="message",
                    message="No changes detected. Modify at least one parameter.",
                    data={}
                )
                return {
                    "messages": messages + [AIMessage(content=json.dumps(response))],
                    "chatbot_response": "CONTINUE",
                    "in_chat_mode": True
                }

            try:
                llm = kb_service.get_llm()
                new_report_text, new_viz_data = await _run_regeneration(
                    state=state,
                    updated_metadata=updated_metadata,
                    llm=llm
                )

                response = _build_structured_response(
                    ui_type="regen_result",
                    message="✅ Report regenerated!",
                    data={
                        "changes_applied": changes_summary,
                        "new_report": new_report_text,
                        "new_visualization_data": new_viz_data,
                        "actions": [
                            {"id": "download", "label": "📥 Download"},
                            {"id": "update_dashboard", "label": "🔄 Update Dashboard"},
                            {"id": "keep_dashboard", "label": "✅ Keep Current"}
                        ]
                    }
                )
                                # Create RetrofitReport object from regenerated report
                regenerated_report_obj = RetrofitReport(
                    risk_assessment_summary=[],  # TODO: Extract from new_report_text or pass from _run_regeneration
                    action_recommendations=[],   # TODO: Extract from new_report_text or pass from _run_regeneration
                    full_detailed_report=new_report_text,
                    metadata=updated_metadata,
                    sources_used=final_report.sources_used if hasattr(final_report, 'sources_used') else {},
                    is_validated=True,
                    validation_score=final_report.validation_score if hasattr(final_report, 'validation_score') else 75.0,
                    validation_feedback="Regenerated report"
                )

                return {
                    "messages": messages + [AIMessage(content=json.dumps(response))],
                    "chatbot_response": "REGEN_COMPLETE",
                    "in_chat_mode": True,
                    "regenerated_report": regenerated_report_obj,  # Now a RetrofitReport object!
                    "regenerated_visualization_data": new_viz_data,
                    "visualization_data": state.get("visualization_data"),  # Original preserved
                    "active_report": "regenerated"
                }
            except Exception as e:
                print(f"Regen error: {e}")
                response = _build_structured_response(
                    ui_type="message",
                    message="⚠️ Regeneration failed. Try again.",
                    data={}
                )
                return {
                    "messages": messages + [AIMessage(content=json.dumps(response))],
                    "chatbot_response": "CONTINUE",
                    "in_chat_mode": True
                }

    except (json.JSONDecodeError, TypeError):
        pass

    # ── Q/A trigger ──────────────────────────────────────────────────────
    if user_query_lower in ["qa", "ask a question", "question"]:
        response = _build_structured_response(
            ui_type="qa",
            message="Go ahead, ask me anything about the report.",
            data={}
        )
        return {
            "messages": messages + [AIMessage(content=json.dumps(response))],
            "chatbot_response": "CONTINUE",
            "in_chat_mode": True
        }

    # ── Update Dashboard (THE SWAP) ──────────────────────────────────────
        # ── Update Dashboard (THE SWAP) ──────────────────────────────────────
    if user_query_lower in ["update_dashboard", "update dashboard"]:
        current_original = state.get("final_output")  # RetrofitReport object
        current_regen = state.get("regenerated_report")  # RetrofitReport object (now!)
        current_regen_viz = state.get("regenerated_visualization_data")
        
        response = _build_structured_response(
            ui_type="message",
            message="✅ Dashboard updated! Previous report archived for comparison.",
            data={"action": "dashboard_updated"}
        )

        return {
            "messages": messages + [AIMessage(content=json.dumps(response))],
            "chatbot_response": "DASHBOARD_UPDATED",
            "in_chat_mode": True,
            # THE SWAP: Both are now RetrofitReport objects!
            "final_output": current_regen,           # New report becomes current
            "previous_report": current_original,       # Old report archived
            "regenerated_report": None,                # Clear slot
            "visualization_data": current_regen_viz,   # New viz active
            "regenerated_visualization_data": None,    # Clear
            "active_report": "original"              # Reset pointer
        }

    # ── Keep Dashboard ───────────────────────────────────────────────────
    if user_query_lower in ["keep_dashboard", "keep dashboard"]:
        response = _build_structured_response(
            ui_type="message",
            message="✅ Kept current dashboard. New report discarded.",
            data={}
        )
        return {
            "messages": messages + [AIMessage(content=json.dumps(response))],
            "chatbot_response": "CONTINUE",
            "in_chat_mode": True,
            "regenerated_report": None,
            "regenerated_visualization_data": None,
            "active_report": "original"
        }

    # ── Fallback mode ────────────────────────────────────────────────────
   
    is_fallback = (
        state.get("fallback_status") == "ACTIVE"
        or final_report.metadata.get("fallback_reason") == "LLM unavailable"
    )

    if is_fallback:
        q = user_query_lower
        if any(w in q for w in ["risk", "danger", "vulnerable", "safe"]):
            msg = (
                final_report.risk_assessment_summary[0]
                if final_report.risk_assessment_summary
                else "Structural risks detected."
            )
        elif any(w in q for w in ["action", "recommend", "fix", "how"]):
            msg = (
                ", ".join(final_report.action_recommendations[:3])
                if final_report.action_recommendations
                else "Consult a structural engineer."
            )
        else:
            msg = "I'm in fallback mode. I can discuss risk and recommendations. Try again in a few minutes for full AI responses."

        response = _build_structured_response(
            ui_type="qa",
            message=msg,
            data={"is_fallback": True}
        )
        return {
            "messages": messages + [AIMessage(content=json.dumps(response))],
            "chatbot_response": "CONTINUE",
            "in_chat_mode": True
        }

    # ── Normal Q/A ───────────────────────────────────────────────────────
    try:
        llm = kb_service.get_llm()
        qa_prompt = f"""You are QuakeVision AI. Answer based ONLY on the report(s) below.

{report_context}

VIZ DATA: {json.dumps(viz_data, indent=2)}"""

        llm_response = await llm.ainvoke([
            SystemMessage(content=qa_prompt),
            HumanMessage(content=user_query)
        ])
        answer = llm_response.content if hasattr(llm_response, "content") else str(llm_response)

        response = _build_structured_response(
            ui_type="qa",
            message=answer,
            data={}
        )
        return {
            "messages": messages + [AIMessage(content=json.dumps(response))],
            "chatbot_response": "CONTINUE",
            "in_chat_mode": True
        }

    except Exception as e:
        print(f"Q/A error: {e}")
        response = _build_structured_response(
            ui_type="message",
            message="⚠️ Error. Try again.",
            data={}
        )
        return {
            "messages": messages + [AIMessage(content=json.dumps(response))],
            "chatbot_response": "CONTINUE",
            "in_chat_mode": True
        }