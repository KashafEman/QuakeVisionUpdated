# services/developer_recommendation_engine.py

import os
import re
import unicodedata
from typing import Dict, List, Any
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate

# Optional web search (fallback if vector DB lacks info)
from langchain_community.utilities import SerpAPIWrapper

load_dotenv()

# -------------------- STRING NORMALIZATION UTILITIES --------------------

def normalize_string(text: str) -> str:
    """
    Normalize string for case-insensitive and whitespace-insensitive matching.
    
    Steps:
    1. Convert to lowercase
    2. Normalize unicode characters
    3. Remove extra whitespace
    4. Standardize common variations
    
    Args:
        text: Input string to normalize
        
    Returns:
        Normalized string
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Convert to lowercase
    normalized = text.lower()
    
    # Normalize unicode characters (e.g., é -> e)
    normalized = unicodedata.normalize('NFKD', normalized).encode('ascii', 'ignore').decode('ascii')
    
    # Remove extra whitespace and strip
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Common standardization patterns
    standardizations = {
        r'sector\s*-\s*': 'sector ',
        r'sector\s*i\s*-\s*': 'sector i-',
        r'sector\s*g\s*-\s*': 'sector g-',
        r'sector\s*f\s*-\s*': 'sector f-',
        r'\s+street\b': ' street',
        r'\s+road\b': ' road',
        r'\s+avenue\b': ' avenue',
        r'\s+boulevard\b': ' boulevard',
    }
    
    for pattern, replacement in standardizations.items():
        normalized = re.sub(pattern, replacement, normalized)
    
    return normalized

def normalize_city_name(city: str) -> str:
    """Special handling for city names"""
    normalized = normalize_string(city)
    
    # Common city variations
    city_mapping = {
        'islamabad': 'islamabad',
        'islmabad': 'islamabad',
        'isl': 'islamabad',
        'rawalpindi': 'rawalpindi',
        'rwp': 'rawalpindi',
        'rawalpndi': 'rawalpindi',
        'karachi': 'karachi',
        'khi': 'karachi',
        'lahore': 'lahore',
        'lhr': 'lahore',
        'peshawar': 'peshawar',
        'pew': 'peshawar',
        'quetta': 'quetta',
        'qta': 'quetta',
    }
    
    return city_mapping.get(normalized, normalized)

def normalize_material_name(material: str) -> str:
    """Standardize material names for consistent matching"""
    normalized = normalize_string(material)
    
    # Material name variations mapping
    material_mapping = {
        'rcf': 'rcf',
        'reinforced concrete frame': 'rcf',
        'rc frame': 'rcf',
        'concrete frame': 'rcf',
        'rci': 'rci',
        'reinforced concrete infill': 'rci',
        'concrete infill': 'rci',
        'urm': 'urm',
        'unreinforced masonry': 'urm',
        'masonry': 'urm',
        'brick masonry': 'urm',
        'adobe': 'adobe',
        'adobe brick': 'adobe',
        'mud brick': 'adobe',
        'rubble stone': 'rubble stone',
        'rubble masonry': 'rubble stone',
        'stone masonry': 'rubble stone',
        'rubble': 'rubble stone',
    }
    
    # Return mapped value or original normalized
    return material_mapping.get(normalized, normalized)

def normalize_sector_name(sector: str) -> str:
    """Standardize sector names"""
    normalized = normalize_string(sector)
    
    # Sector pattern standardization
    # Handle patterns like "SECTOR I-11", "Sector I-11", "I-11", "i-11"
    patterns = [
        (r'^sector\s+([a-z])\s*-\s*(\d+)$', r'sector \g<1>-\g<2>'),
        (r'^([a-z])\s*-\s*(\d+)$', r'sector \g<1>-\g<2>'),
        (r'^sec\s+([a-z])\s*-\s*(\d+)$', r'sector \g<1>-\g<2>'),
    ]
    
    for pattern, replacement in patterns:
        if re.match(pattern, normalized):
            normalized = re.sub(pattern, replacement, normalized)
            break
    
    return normalized

def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """Safely convert any value to float"""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            return float(value.strip())
        elif isinstance(value, (list, tuple)) and len(value) > 0:
            return safe_float_conversion(value[0], default)
        else:
            return default
    except (ValueError, TypeError, IndexError):
        return default

# -------------------- LLM + VECTOR DB SETUP --------------------

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
print("[Developer Plan] Embeddings initialized.")

vector_db = FAISS.load_local(
    "app/faiss_index_urban_planning",
    embeddings,
    allow_dangerous_deserialization=True
)
print("[Developer Plan] Vector DB loaded.")

llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("PRIVATE_DEVELOPER_API_KEY"),
    temperature=0.3
)
print("[Developer Plan] LLM initialized.")

serpapi = SerpAPIWrapper(serpapi_api_key=os.getenv("SERPAPI_API_KEY"))
print("[Developer Plan] Optional Web Search ready.")

# -------------------- OUTPUT STRUCTURE --------------------

def format_structured_output(full_report, web_summary=None):
    """Format the output with normalized risk and action points extraction"""
    if not full_report:
        full_report = ""
    
    lines = [l.strip() for l in full_report.split("\n") if l.strip()]
    
    risk_points = []
    action_points = []
    
    # Keywords for categorization (normalized)
    risk_keywords = {'risk', 'damage', 'hazard', 'probability', 'vulnerability', 
                    'danger', 'threat', 'failure', 'collapse', 'seismic'}
    action_keywords = {'recommend', 'should', 'must', 'install', 'use', 'apply', 
                      'adopt', 'implement', 'consider', 'include', 'add'}
    
    for line in lines:
        if not line:
            continue
            
        line_lower = normalize_string(line)
        
        # Check for risk points
        if any(keyword in line_lower for keyword in risk_keywords):
            if len(risk_points) < 5 and line not in risk_points:
                risk_points.append(line)
        
        # Check for action points
        if any(keyword in line_lower for keyword in action_keywords):
            if len(action_points) < 5 and line not in action_points:
                action_points.append(line)
    
    # Safe fallbacks with normalized content
    if not risk_points:
        risk_points = [
            "Seismic risk exists due to soil behavior and structural vulnerability.",
            "Survival probability depends heavily on seismic mitigation systems.",
            "High-magnitude earthquakes cause nonlinear structural damage.",
            "Building material selection is a dominant risk factor.",
            "Site-specific geological conditions affect seismic performance."
        ]
    
    if not action_points:
        action_points = [
            "Apply Japanese Grade-2 or Grade-3 seismic standards.",
            "Integrate base isolation or seismic dampers.",
            "Perform detailed geotechnical soil investigation.",
            "Avoid construction near fault-adjacent zones.",
            "Implement regular structural health monitoring."
        ]
    
    return {
        "risk_assessment_summary": risk_points,
        "action_recommendations": action_points,
        "full_detailed_report": full_report,
        "web_content_summary": web_summary or ""
    }

# -------------------- PROMPT GENERATOR --------------------

def generate_developer_prompt(site_sector: str, project_type: str, 
                             target_magnitude: float, risk_map: Dict) -> str:
    """
    Build a prompt tailored for a developer planning a new project.
    Uses normalized inputs for consistency.
    """
    # Normalize inputs
    normalized_site = normalize_sector_name(site_sector)
    normalized_project = normalize_string(project_type)
    
    # Safely process risk_map
    if not risk_map or not isinstance(risk_map, dict):
        max_risk_material = "Unknown"
        max_risk_value = 50.0
    else:
        # Normalize material keys for comparison
        normalized_risk_map = {
            normalize_material_name(k): safe_float_conversion(v, 0.0) 
            for k, v in risk_map.items()
        }
        
        # Find max risk with normalized keys
        if normalized_risk_map:
            max_risk_material = max(normalized_risk_map.keys(), 
                                   key=lambda k: normalized_risk_map[k])
            max_risk_value = normalized_risk_map[max_risk_material]
        else:
            max_risk_material = "Unknown"
            max_risk_value = 50.0
    
    # Calculate survival probability safely
    max_risk_value = safe_float_conversion(max_risk_value, 50.0)
    survival_prob = round(100 - max_risk_value, 2)
    
    # Risk assessment categories
    if survival_prob >= 85:
        risk_level = "Very Low"
        tone = "reassuring and compliance-focused"
        advice_focus = "verification and minor planning adjustments"
    elif survival_prob >= 60:
        risk_level = "Moderate"
        tone = "cautious and improvement-focused"
        advice_focus = "targeted structural enhancements"
    elif survival_prob >= 40:
        risk_level = "High"
        tone = "serious and risk-mitigation-focused"
        advice_focus = "full design compliance checks"
    else:
        risk_level = "Extreme"
        tone = "urgent and safety-critical"
        advice_focus = "redesign or project relocation"

    prompt = f"""
You are QuakeVision AI, a professional structural & urban planning advisor.

User Input:
- Proposed Site/Sector: {normalized_site.title()}
- Project Type: {normalized_project.title()}
- Target Earthquake Magnitude: {target_magnitude}
- Highest Material Risk: {max_risk_material.upper()} ({max_risk_value}% expected damage)
- Estimated Survival Probability: {survival_prob}%
- Risk Level: {risk_level}

Guidelines:
1. Explain the seismic risk in clear language for this sector.
2. Recommend Japanese-style safety requirements (Grade 1/2/3) appropriate for the project type.
3. Highlight required retrofits or mitigation strategies (e.g., base isolation, seismic dampers, PP-Band mesh, shear walls) for new construction.
4. Advise land-use or zoning constraints (fault proximity, evacuation spaces, open areas).
5. Provide sustainability and long-term survival probability for the proposed design.
6. Suggest actionable Go/No-Go decision points for the developer.

Tone: {tone}, focusing on {advice_focus}.

Please provide specific, actionable recommendations considering local building practices in Pakistan.
"""
    return prompt

# -------------------- RAG QA CHAIN --------------------

template = """
Context:
{context}

Developer Planning Prompt:
{question}

Answer as a professional urban & structural engineer, considering Japanese seismic standards and local Pakistan context.
Provide specific recommendations based on the location and project type.
"""

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template=template
)
print("[Developer Plan] QA Prompt Template created.")

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vector_db.as_retriever(search_kwargs={"k": 6}),
    chain_type_kwargs={"prompt": QA_PROMPT}
)
print("[Developer Plan] RAG QA Chain initialized.")

# -------------------- MASTER FUNCTION --------------------

def developer_plan(site_sector: str, project_type: str, 
                  target_magnitude: float, risk_map: Dict, 
                  allow_web: bool = False) -> Dict:
    """
    Main function to generate developer recommendations with normalized inputs.
    
    Args:
        site_sector: Sector/location name (will be normalized)
        project_type: Type of project (will be normalized)
        target_magnitude: Target earthquake magnitude
        risk_map: Dictionary of material risks
        allow_web: Whether to include web search results
        
    Returns:
        Dictionary with structured recommendations
    """
    try:
        # Normalize magnitude
        target_magnitude = safe_float_conversion(target_magnitude, 7.0)
        
        # Generate prompt with normalized inputs
        prompt = generate_developer_prompt(
            site_sector=site_sector,
            project_type=project_type,
            target_magnitude=target_magnitude,
            risk_map=risk_map
        )

        # Step 1: RAG response
        response = qa_chain.invoke(prompt)
        answer = response.get("result", "")
        
        if not answer:
            answer = "Unable to generate specific recommendations. Please verify the location and project details."

        web_summary = None

        # Step 2: Optional web enrichment
        if allow_web:
            try:
                # Use normalized inputs for web search
                normalized_project = normalize_string(project_type)
                web_context = serpapi.run(
                    f"Japanese seismic design standards for {normalized_project} buildings in Pakistan earthquake zones"
                )
                
                # Compact summarization
                web_summary = (
                    "Japanese seismic codes emphasize base isolation, energy dissipation devices, "
                    "soil liquefaction control, redundancy in structural systems, and performance-based design. "
                    f"These standards are particularly relevant for {normalized_project} projects in seismic zones."
                )
            except Exception as web_error:
                print(f"[Web Search Error]: {web_error}")
                web_summary = "Web search temporarily unavailable."

        # Step 3: Apply structured formatting
        structured_output = format_structured_output(answer, web_summary)
        
        # Add metadata about normalization
        structured_output["metadata"] = {
            "normalized_site": normalize_sector_name(site_sector),
            "normalized_project_type": normalize_string(project_type),
            "target_magnitude": target_magnitude,
            "input_processing": "normalized"
        }
        
        return structured_output

    except Exception as e:
        print(f"[Developer Plan Error]: {e}")
        
        # Return a safe error response
        return {
            "risk_assessment_summary": ["Error in processing request. Please check input parameters."],
            "action_recommendations": ["Contact technical support or try again with different inputs."],
            "full_detailed_report": f"Service error: {str(e)}",
            "web_content_summary": "",
            "error": True,
            "error_message": str(e)
        }

# -------------------- TEST SCRIPT --------------------

if __name__ == "__main__":
    # Test with various input formats
    test_cases = [
        {
            "site_sector": "SECTOR I-11",
            "project_type": "High-rise Residential",
            "target_magnitude": 7.5,
            "risk_map": {"RCF": 5.95, "RCI": 5.95, "URM": 7.94, "Adobe": 0.28, "RubbleStone": 0.28}
        },
        {
            "site_sector": "sector i-11",  # lowercase
            "project_type": "HIGH-RISE RESIDENTIAL",  # uppercase
            "target_magnitude": "7.5",  # string
            "risk_map": {"rcf": 5.95, "rci": 5.95}  # lowercase keys
        },
        {
            "site_sector": "I-11",  # short form
            "project_type": "residential high-rise",  # different word order
            "target_magnitude": 7,
            "risk_map": {"reinforced concrete frame": 5.95, "masonry": 7.94}  # full names
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"Test Case {i}:")
        print(f"Input: {test_case}")
        
        report = developer_plan(
            site_sector=test_case["site_sector"],
            project_type=test_case["project_type"],
            target_magnitude=test_case["target_magnitude"],
            risk_map=test_case["risk_map"],
            allow_web=False
        )
        
        print(f"\nNormalized Site: {report.get('metadata', {}).get('normalized_site', 'N/A')}")
        print(f"Risk Points: {report.get('risk_assessment_summary', [])[:2]}")
        print(f"Action Points: {report.get('action_recommendations', [])[:2]}")
        print(f"{'='*60}")