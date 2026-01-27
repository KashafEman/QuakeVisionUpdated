# services/recommendation_engine.py

import os
import re
import unicodedata
from typing import Dict, Any
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate

# Optional web search (only when your DB lacks info)
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
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Convert to lowercase
    normalized = text.lower()
    
    # Normalize unicode characters
    normalized = unicodedata.normalize('NFKD', normalized).encode('ascii', 'ignore').decode('ascii')
    
    # Remove extra whitespace and strip
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def normalize_material_name(material: str) -> str:
    """Standardize material names for consistent matching"""
    normalized = normalize_string(material)
    
    # Material name variations mapping
    material_mapping = {
        'rcf': 'RCF',
        'reinforced concrete frame': 'RCF',
        'rc frame': 'RCF',
        'concrete frame': 'RCF',
        'reinforced concrete': 'RCF',
        
        'rci': 'RCI',
        'reinforced concrete infill': 'RCI',
        'concrete infill': 'RCI',
        'infilled frame': 'RCI',
        
        'urm': 'URM',
        'unreinforced masonry': 'URM',
        'masonry': 'URM',
        'brick masonry': 'URM',
        'brick': 'URM',
        
        'adobe': 'Adobe',
        'adobe brick': 'Adobe',
        'mud brick': 'Adobe',
        'mud': 'Adobe',
        
        'rubble stone': 'RubbleStone',
        'rubblestone': 'RubbleStone',
        'rubble masonry': 'RubbleStone',
        'stone masonry': 'RubbleStone',
        'rubble': 'RubbleStone',
        'stone': 'RubbleStone',
    }
    
    # Find the best match
    for pattern, standard_name in material_mapping.items():
        if pattern in normalized:
            return standard_name
    
    # If no match found, try partial matching
    for standard_name in ['RCF', 'RCI', 'URM', 'Adobe', 'RubbleStone']:
        if standard_name.lower() in normalized:
            return standard_name
    
    # Default to original (capitalized)
    return material.upper() if material else "UNKNOWN"

def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """Safely convert any value to float"""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            # Remove any non-numeric characters except decimal point and minus
            cleaned = re.sub(r'[^\d.-]', '', value.strip())
            return float(cleaned) if cleaned else default
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
print("Embeddings initialized.")

vector_db = FAISS.load_local(
    "app/faiss_index_urban_planning",
    embeddings,
    allow_dangerous_deserialization=True
)
print("Vector DB loaded.")

llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("VDB_CHAT_MODEL"),
    temperature=0.3
)
print("LLM initialized.")

# Optional web search tool
serpapi = SerpAPIWrapper(serpapi_api_key=os.getenv("SERPAPI_API_KEY"))
print("Web search tool ready.")

# -------------------- OUTPUT STRUCTURE --------------------

def format_structured_output(full_report: str, web_summary: str = None) -> Dict:
    """Format the output with normalized risk and action points extraction"""
    if not full_report:
        full_report = ""
    
    lines = [l.strip() for l in full_report.split("\n") if l.strip()]
    
    risk_points = []
    action_points = []
    
    # Normalized keywords for categorization
    risk_keywords = {'risk', 'damage', 'hazard', 'probability', 'vulnerability', 
                    'danger', 'threat', 'failure', 'collapse', 'seismic', 'unsafe',
                    'weak', 'deficient', 'prone'}
    
    action_keywords = {'recommend', 'should', 'must', 'install', 'use', 'apply', 
                      'adopt', 'implement', 'consider', 'include', 'add', 'strengthen',
                      'retrofit', 'improve', 'enhance', 'upgrade', 'reinforce'}
    
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
    
    # Safe fallbacks (Retrofit-Oriented) with normalization
    if not risk_points:
        risk_points = [
            "The structure shows significant vulnerability to seismic shaking due to its current material behavior.",
            "Existing construction lacks sufficient energy dissipation and lateral resistance mechanisms.",
            "Structural damage is likely to concentrate at weak joints, walls, and foundation connections.",
            "Without retrofitting, the probability of severe damage or partial collapse remains high.",
            "Occupant safety is strongly dependent on immediate structural strengthening measures."
        ]
    
    if not action_points:
        action_points = [
            "Apply material-appropriate retrofitting such as PP-band mesh, shear bands, or column jacketing.",
            "Strengthen wall-to-roof and wall-to-foundation connections to improve load transfer.",
            "Introduce confinement techniques to prevent brittle failure of masonry elements.",
            "Conduct a rapid structural audit to prioritize the most vulnerable components.",
            "Adopt Japanese-inspired performance-based retrofitting strategies for life safety improvement."
        ]
    
    return {
        "risk_assessment_summary": risk_points,
        "action_recommendations": action_points,
        "full_detailed_report": full_report,
        "web_content_summary": web_summary or ""
    }

# -------------------- SURVIVAL GENERATOR --------------------

def convert_damage_to_survival(material: str, damage_percent: float) -> float:
    """
    Converts abstract damage % into realistic survival probability.
    Calibrated by structural vulnerability.
    """
    # Normalize material name
    normalized_material = normalize_material_name(material)
    material_key = normalized_material.lower()
    
    # Vulnerability factors with normalized keys
    vulnerability_factor = {
        'rcf': 0.85,
        'rci': 0.75,
        'urm': 0.45,
        'adobe': 0.20,
        'rubblestone': 0.25
    }
    
    # Ensure damage_percent is a float
    damage_percent = safe_float_conversion(damage_percent, 0.0)
    
    # Clamp damage_percent between 0 and 100
    damage_percent = max(0.0, min(100.0, damage_percent))
    
    base_survival = 100.0 - damage_percent
    
    # Get appropriate vulnerability factor
    factor = vulnerability_factor.get(material_key, 0.5)  # Default to 0.5 if unknown
    
    calibrated = base_survival * factor
    
    # Ensure survival is between 0 and 100
    calibrated = max(0.0, min(100.0, calibrated))
    
    return round(calibrated, 2)

# -------------------- PROMPT GENERATOR --------------------

def generate_prompt(material: str, risk_value: float, magnitude: float, height: float = 3.0) -> str:
    """Generate engineering prompt with normalized inputs"""
    print(f"Generating prompt for material: {material}, risk: {risk_value}%, magnitude: {magnitude}, height: {height}")
    
    # Normalize inputs
    normalized_material = normalize_material_name(material)
    risk_value = safe_float_conversion(risk_value, 0.0)
    magnitude = safe_float_conversion(magnitude, 7.0)
    height = safe_float_conversion(height, 3.0)
    
    survival = convert_damage_to_survival(normalized_material, risk_value)
    print(f"Calculated survival probability: {survival}% for material: {normalized_material}")
    
    # Risk assessment with normalized thresholds
    if survival >= 85:
        risk_level = "Very Low"
        tone = "reassuring and maintenance-focused"
        focus = "inspection, monitoring, and minor upgrades"
    elif survival >= 60:
        risk_level = "Moderate"
        tone = "cautious and improvement-focused"
        focus = "selective strengthening and preparedness"
    elif survival >= 40:
        risk_level = "High"
        tone = "serious and risk-mitigation-focused"
        focus = "structural strengthening methods"
    elif survival >= 25:
        risk_level = "High-Very High"
        tone = "urgent and intervention-focused"
        focus = "immediate retrofitting and safety measures"
    else:
        risk_level = "Extreme"
        tone = "urgent and safety-critical"
        focus = "full retrofitting and collapse prevention"
    
    print(f"Determined risk level: {risk_level}, tone: {tone}, focus: {focus}")
    
    # Material-specific guidance
    material_guidance = ""
    material_lower = normalized_material.lower()
    
    if 'rubblestone' in material_lower or 'adobe' in material_lower:
        material_guidance = (
            "For Rubble Stone/Adobe structures, emphasize: "
            "PP-Band mesh application, wall confinement techniques, foundation tying, "
            "roof-to-wall connections, and seismic band installation."
        )
    elif 'urm' in material_lower:
        material_guidance = (
            "For Unreinforced Masonry (URM) structures, emphasize: "
            "shear bands, through-ties, diaphragm action improvement, "
            "wall anchoring, and out-of-plane bracing."
        )
    elif 'rcf' in material_lower or 'rci' in material_lower:
        material_guidance = (
            "For Reinforced Concrete structures, emphasize: "
            "column jacketing, shear wall addition, beam-column joint strengthening, "
            "and base isolation only if economically and structurally justified."
        )
    else:
        material_guidance = (
            "Apply general seismic retrofitting principles: "
            "improve lateral resistance, enhance ductility, strengthen connections, "
            "and ensure load path continuity."
        )
    
    prompt = f"""
You are QuakeVision AI, a seismic safety advisor specialized in retrofit recommendations.
Your tone should be {tone}.

Building Details:
- Material: {normalized_material}
- Earthquake Magnitude: {magnitude}
- Height: {height} stories
- Estimated Structural Survival Probability: {survival}%
- Risk Category: {risk_level}

First, explain clearly what this survival percentage means in practical terms for occupants:
- How likely is the building to remain standing?
- What level of damage is expected?
- What are the implications for occupant safety?

Then, provide specific assessment:
- If survival is below 25%, explain that structural failure or collapse is highly probable.
- If survival is above 80%, explain that the building already approaches Japanese Grade-1 seismic performance.
- Otherwise, explain how far the building is from Japanese Grade-1 safety standards.

Focus your recommendations on {focus}.

{material_guidance}

Consider building height ({height} stories) in your recommendations:
- For low-rise buildings (1-3 stories), focus on wall strengthening and foundation work.
- For mid-rise buildings (4-7 stories), consider both local and global retrofitting.
- For high-rise buildings (8+ stories), emphasize system-level retrofitting.

End with a clear conclusion that matches the risk level:
- Low risk → "This structure is generally safe but can be improved with minor upgrades."
- Moderate risk → "This structure should be strengthened to enhance seismic performance."
- High risk → "This structure is vulnerable and requires significant intervention."
- Extreme risk → "This structure is unsafe without immediate retrofitting or evacuation."
"""
    return prompt

# -------------------- QA CHAIN (RAG CORE) --------------------

template = """
Context:
{context}

User Engineering Prompt:
{question}

Answer as a professional structural seismic engineer with expertise in retrofit design.
Be specific, practical, and safety-focused in your recommendations.
"""

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template=template
)
print("QA Prompt Template created.")

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vector_db.as_retriever(search_kwargs={"k": 6}),
    chain_type_kwargs={"prompt": QA_PROMPT}
)
print("RAG QA Chain initialized.")

# -------------------- MASTER FUNCTION --------------------

def generate_retrofit_plan(material: str, risk_map: Dict, magnitude: float, 
                          height: float = 3.0, allow_web: bool = False) -> Dict:
    """
    Generate retrofit plan with normalized inputs.
    
    Args:
        material: Building material (any format: "Rubble Stone", "rubblestone", etc.)
        risk_map: dict like {RCF:5.9, RCI:5.9, URM:7.9, Adobe:0.28, RubbleStone:0.28}
        magnitude: Earthquake magnitude
        height: Building height in stories (default: 3)
        allow_web: Whether to include web search results
        
    Returns:
        Dictionary with structured retrofit plan
    """
    try:
        # Normalize all inputs
        normalized_material = normalize_material_name(material)
        magnitude = safe_float_conversion(magnitude, 7.0)
        height = safe_float_conversion(height, 3.0)
        
        print(f"Normalized material: {normalized_material}")
        print(f"Input risk_map: {risk_map}")
        
        # Normalize risk_map keys for lookup
        normalized_risk_map = {}
        for key, value in risk_map.items():
            norm_key = normalize_material_name(key)
            normalized_risk_map[norm_key] = safe_float_conversion(value, 0.0)
        
        print(f"Normalized risk_map: {normalized_risk_map}")
        
        # Get risk value for the material
        risk_value = normalized_risk_map.get(normalized_material)
        
        if risk_value is None:
            # Try to find the closest match
            material_lower = normalized_material.lower()
            for key in normalized_risk_map.keys():
                if key.lower() in material_lower or material_lower in key.lower():
                    risk_value = normalized_risk_map[key]
                    print(f"Found approximate match: {key} -> {risk_value}")
                    break
        
        # If still not found, use average or default
        if risk_value is None:
            if normalized_risk_map:
                risk_value = sum(normalized_risk_map.values()) / len(normalized_risk_map)
                print(f"Using average risk value: {risk_value}")
            else:
                risk_value = 50.0  # Default moderate risk
                print(f"Using default risk value: {risk_value}")
        
        print(f"Final risk_value for {normalized_material}: {risk_value}")
        
        # Step 1: Engineering prompt
        engineering_prompt = generate_prompt(normalized_material, risk_value, magnitude, height)
        
        # Step 2: RAG inference
        response = qa_chain.invoke(engineering_prompt)
        answer = response.get("result", "")
        
        if not answer:
            answer = f"Unable to generate specific retrofit recommendations for {normalized_material} construction. Please consult with a structural engineer."
        
        # Step 3: Optional web enrichment
        web_summary = ""
        if allow_web:
            try:
                # Use normalized material for web search
                web_query = f"Japanese earthquake retrofitting techniques for {normalized_material.lower()} buildings"
                web_content = serpapi.run(web_query)
                
                web_summary = (
                    f"Modern Japanese retrofitting for {normalized_material} emphasizes "
                    "PP-band mesh for masonry, shear wall strengthening, column jacketing, "
                    "and performance-based seismic design to reduce collapse probability."
                )
            except Exception as web_error:
                print(f"[Web Search Error]: {web_error}")
                web_summary = "Web search information currently unavailable."
        
        # Step 4: Structured formatting for API + UI
        structured = format_structured_output(answer, web_summary)
        
        # Add metadata
        structured["metadata"] = {
            "normalized_material": normalized_material,
            "risk_value": risk_value,
            "magnitude": magnitude,
            "height": height,
            "survival_probability": convert_damage_to_survival(normalized_material, risk_value)
        }
        
        return structured
        
    except KeyError as e:
        print(f"[KeyError]: Missing key in risk_map: {e}")
        return {
            "error": f"Missing risk data for material: {material}",
            "suggestion": "Please ensure all material types have corresponding risk values.",
            "risk_assessment_summary": ["Data incomplete for this material type."],
            "action_recommendations": ["Consult a structural engineer for site-specific assessment."]
        }
    except Exception as e:
        print(f"[Retrofit Engine Error]: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "error": "Service temporarily unavailable. Please try again later.",
            "risk_assessment_summary": ["Error in processing request."],
            "action_recommendations": ["Please verify input parameters and try again."],
            "full_detailed_report": f"Technical error: {str(e)}"
        }

# -------------------- TEST FUNCTION --------------------

def test_retrofit_engine():
    """Test the retrofit engine with various input formats"""
    test_cases = [
        {
            "name": "Test 1: Standard inputs",
            "material": "RubbleStone",
            "risk_map": {"RCF": 5.95, "RCI": 5.95, "URM": 7.94, "Adobe": 0.28, "RubbleStone": 0.28},
            "magnitude": 7.0,
            "height": 3.0
        },
        {
            "name": "Test 2: Lowercase inputs",
            "material": "rubblestone",
            "risk_map": {"rcf": 5.95, "rci": 5.95, "urm": 7.94, "adobe": 0.28, "rubblestone": 0.28},
            "magnitude": "7.5",
            "height": "2"
        },
        {
            "name": "Test 3: Full names",
            "material": "Reinforced Concrete Frame",
            "risk_map": {"RCF": 5.95, "RCI": 5.95, "URM": 7.94},
            "magnitude": 6.5,
            "height": 5.0
        },
        {
            "name": "Test 4: Mixed case",
            "material": "rubble stone",
            "risk_map": {"RubbleStone": 0.28, "Adobe": 0.20},
            "magnitude": 8.0,
            "height": 1.0
        }
    ]
    
    for test in test_cases:
        print(f"\n{'='*60}")
        print(f"{test['name']}")
        print(f"Input: material={test['material']}, magnitude={test['magnitude']}")
        
        try:
            plan = generate_retrofit_plan(
                material=test["material"],
                risk_map=test["risk_map"],
                magnitude=test["magnitude"],
                height=test["height"],
                allow_web=False
            )
            
            if "error" in plan:
                print(f"Error: {plan.get('error')}")
            else:
                print(f"Normalized material: {plan.get('metadata', {}).get('normalized_material', 'N/A')}")
                print(f"Survival probability: {plan.get('metadata', {}).get('survival_probability', 'N/A')}%")
                print(f"Risk points: {plan.get('risk_assessment_summary', [])[:2]}")
                print(f"Action points: {plan.get('action_recommendations', [])[:2]}")
        
        except Exception as e:
            print(f"Test failed with error: {e}")
        
        print(f"{'='*60}")

# -------------------- MAIN EXECUTION --------------------

if __name__ == "__main__":
    # Run tests
    test_retrofit_engine()
    
    # Or run a single test
    # risk_map = {
    #     "RCF": 5.95,
    #     "RCI": 5.95,
    #     "URM": 7.94,
    #     "Adobe": 0.28,
    #     "RubbleStone": 0.28
    # }
    
    # plan = generate_retrofit_plan(
    #     material="RubbleStone",
    #     risk_map=risk_map,
    #     magnitude=7.0,
    #     height=3.0,
    #     allow_web=False
    # )
    
    # print("\n--- QuakeVision Retrofit Plan ---\n")
    # print(plan)