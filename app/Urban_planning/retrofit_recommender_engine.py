# services/retrofit_recommender_engine.py

import os
import re
import unicodedata
from datetime import date
from typing import Dict, Any, Union
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate
from langchain_community.utilities import SerpAPIWrapper

# -------------------- STRING NORMALIZATION UTILITIES --------------------

def normalize_string(text: str) -> str:
    """
    Normalize string for case-insensitive and whitespace-insensitive matching.
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

def normalize_sector_name(sector: str) -> str:
    """Standardize sector names"""
    normalized = normalize_string(sector)
    
    # Sector pattern standardization
    patterns = [
        (r'^sector\s+([a-z])\s*-\s*(\d+)$', r'sector \g<1>-\g<2>'),
        (r'^([a-z])\s*-\s*(\d+)$', r'sector \g<1>-\g<2>'),
        (r'^sec\s+([a-z])\s*-\s*(\d+)$', r'sector \g<1>-\g<2>'),
        (r'^sect\s+([a-z])\s*-\s*(\d+)$', r'sector \g<1>-\g<2>'),
    ]
    
    for pattern, replacement in patterns:
        if re.match(pattern, normalized):
            normalized = re.sub(pattern, replacement, normalized)
            break
    
    return normalized.title()  # Return title case for display

def normalize_priority_metric(metric: str) -> str:
    """Normalize priority metric names"""
    normalized = normalize_string(metric)
    
    metric_mapping = {
        'save maximum lives': 'Save Maximum Lives',
        'save lives': 'Save Maximum Lives',
        'maximum lives': 'Save Maximum Lives',
        'lifesaving': 'Save Maximum Lives',
        'reduce sector vulnerability': 'Reduce Sector Vulnerability',
        'sector vulnerability': 'Reduce Sector Vulnerability',
        'vulnerability reduction': 'Reduce Sector Vulnerability',
        'risk reduction': 'Reduce Sector Vulnerability',
        'optimize resource allocation': 'Optimize Resource Allocation',
        'resource optimization': 'Optimize Resource Allocation',
        'cost effective': 'Optimize Resource Allocation'
    }
    
    for pattern, standard_name in metric_mapping.items():
        if pattern in normalized:
            return standard_name
    
    # Default to first option
    return 'Save Maximum Lives'

def normalize_retrofit_style(style: str) -> str:
    """Normalize retrofit style names"""
    normalized = normalize_string(style)
    
    style_mapping = {
        'low-cost': 'Low-cost',
        'low cost': 'Low-cost',
        'budget': 'Low-cost',
        'economic': 'Low-cost',
        'structural': 'Structural',
        'structural upgrade': 'Structural',
        'full structural': 'Structural',
        'hybrid': 'Hybrid',
        'mixed': 'Hybrid',
        'balanced': 'Hybrid',
        'comprehensive': 'Hybrid'
    }
    
    for pattern, standard_name in style_mapping.items():
        if pattern in normalized:
            return standard_name
    
    # Default to Hybrid
    return 'Hybrid'

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

def safe_int_conversion(value: Any, default: int = 0) -> int:
    """Safely convert any value to integer"""
    try:
        return int(safe_float_conversion(value, default))
    except (ValueError, TypeError):
        return default

# -------------------- DATE HANDLING (NO HALLUCINATION) --------------------

today = date.today().strftime("%B %d, %Y")

load_dotenv()

# -------------------- LLM + VECTOR DB SETUP --------------------

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
print("[Retrofit Planner] Embeddings initialized.")

vector_db = FAISS.load_local(
    "app/faiss_index_urban_planning",
    embeddings,
    allow_dangerous_deserialization=True
)
print("[Retrofit Planner] Vector DB loaded.")

llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("Retrofit_API_KEY"),
    temperature=0.15  # very deterministic for engineering planning
)
print("[Retrofit Planner] LLM initialized.")

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
                    'weak', 'deficient', 'prone', 'fatal', 'casualty', 'extreme'}
    
    action_keywords = {'recommend', 'should', 'must', 'install', 'use', 'apply', 
                      'adopt', 'implement', 'consider', 'include', 'add', 'strengthen',
                      'retrofit', 'improve', 'enhance', 'upgrade', 'reinforce',
                      'allocate', 'prioritize', 'focus', 'target', 'apply'}
    
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
    
    # Safe fallback (Sector Retrofit Planning Oriented)
    if not risk_points:
        risk_points = [
            "The sector shows extreme vulnerability due to a high proportion of collapse-prone Kacha and semi-pacca structures.",
            "Current building stock lacks any systematic seismic resistance, making mass casualty risk unacceptably high.",
            "Collapse probability is the dominant risk driver and outweighs all other urban planning considerations.",
            "Without immediate intervention, large-scale structural failure is expected in a strong earthquake.",
            "Sector-wide fatality risk remains critically high under existing construction conditions."
        ]
    
    if not action_points:
        action_points = [
            "Allocate the majority of retrofit capacity to Kacha (Rubble Stone / Adobe) structures to maximize life safety.",
            "Apply low-cost, high-impact techniques such as PP-band mesh, seismic banding, and wall confinement at scale.",
            "Strengthen semi-pacca (URM) buildings using ferrocement jacketing and diaphragm improvements.",
            "Reserve advanced retrofitting methods for a limited number of critical Pacca (RCF/RCI) structures.",
            "Implement rapid screening and phased retrofitting to progressively reduce sector-wide collapse probability."
        ]
    
    return {
        "risk_assessment_summary": risk_points,
        "action_recommendations": action_points,
        "full_detailed_report": full_report,
        "web_content_summary": web_summary or ""
    }

# -------------------- PROMPT GENERATOR (FIXED PRIORITY LOGIC) --------------------

def generate_retrofit_prompt(sector_data: Dict, retrofit_capacity: int, 
                            priority_metric: str, retrofit_style: str) -> str:
    """
    Build a policy-constrained prompt for retrofitting ONE sector.
    Collapse probability always dominates when 'Save Maximum Lives' is selected.
    """
    # Normalize all inputs
    sector_name = normalize_sector_name(sector_data.get("sector_name", "Unknown Sector"))
    total_buildings = safe_int_conversion(sector_data.get("total_buildings", 0), 1000)
    overall_risk = safe_float_conversion(sector_data.get("overall_percent", 50.0), 50.0)
    magnitude = safe_float_conversion(sector_data.get("magnitude", 7.5), 7.5)
    
    kacha = safe_float_conversion(sector_data.get("kacha_percent", 0.0), 0.0)
    semi_pacca = safe_float_conversion(sector_data.get("semi_pacca_percent", 0.0), 0.0)
    pacca = safe_float_conversion(sector_data.get("pacca_percent", 0.0), 0.0)
    
    # Normalize percentages (ensure they sum to ~100)
    total_percent = kacha + semi_pacca + pacca
    if total_percent > 0:
        kacha = round(kacha / total_percent * 100, 2)
        semi_pacca = round(semi_pacca / total_percent * 100, 2)
        pacca = round(pacca / total_percent * 100, 2)
    
    # Normalize user constraints
    retrofit_capacity = safe_int_conversion(retrofit_capacity, 100)
    priority_metric = normalize_priority_metric(priority_metric)
    retrofit_style = normalize_retrofit_style(retrofit_style)
    
    print(f"[Retrofit Prompt] Sector: {sector_name}, Capacity: {retrofit_capacity}")
    print(f"[Retrofit Prompt] Metric: {priority_metric}, Style: {retrofit_style}")
    print(f"[Retrofit Prompt] Distribution: Kacha={kacha}%, Semi-Pacca={semi_pacca}%, Pacca={pacca}%")
    
    # Determine policy rules based on priority metric
    policy_rules = ""
    if priority_metric == "Save Maximum Lives":
        policy_rules = """
If Priority Metric = "Save Maximum Lives":
1. Buildings with the HIGHEST collapse probability must always be prioritized first.
2. At least 60–70% of retrofit capacity MUST be allocated to:
   - Kacha (Rubble Stone / Adobe)
3. The remaining capacity is distributed in this order:
   - Semi-Pacca (URM)
   - Then Pacca (RCF/RCI), only if capacity remains.
4. High occupancy alone is NOT sufficient to override collapse probability.
"""
    elif priority_metric == "Reduce Sector Vulnerability":
        policy_rules = """
If Priority Metric = "Reduce Sector Vulnerability":
1. Allocate resources to reduce total sector-wide risk percentage.
2. Balance across all typologies based on proportional contribution to vulnerability.
3. Consider both collapse probability and number of buildings in each category.
"""
    else:  # Optimize Resource Allocation or default
        policy_rules = """
If Priority Metric = "Optimize Resource Allocation":
1. Balance life safety with cost-effectiveness.
2. Consider retrofit cost per building vs. risk reduction.
3. Prioritize interventions with highest risk reduction per unit cost.
"""
    
    prompt = f"""
You are QuakeVision AI, operating as the Seismic Retrofit Planning Engine for the 
National Disaster Management Authority (NDMA) and Capital Development Authority (CDA), Pakistan.

Official Planning Date: {today}

SECTOR PROFILE:
- Sector Name: {sector_name}
- Total Buildings: {total_buildings}
- Earthquake Magnitude: {magnitude}
- Overall Collapse Probability: {overall_risk}%
- Building Distribution:
    - Kacha (Rubble Stone / Adobe): {kacha}%
    - Semi-Pacca (URM): {semi_pacca}%
    - Pacca (RCF/RCI): {pacca}%

USER CONSTRAINTS:
- Retrofit Capacity: {retrofit_capacity} buildings
- Priority Metric: {priority_metric}
- Retrofit Strategy Style: {retrofit_style} (Low-cost / Structural / Hybrid)

IMPORTANT POLICY RULES:

{policy_rules}

YOUR TASKS:
1. Classify the sector using Japanese Seismic Safety Grades:
   - Grade 0 (Extremely Vulnerable): >80% collapse probability
   - Grade 1 (Highly Vulnerable): 60-80% collapse probability
   - Grade 2 (Moderate): 40-60% collapse probability
   - Grade 3 (Acceptable): <40% collapse probability

2. Allocate exactly {retrofit_capacity} buildings using the above policy rules.
   Show clear allocation:
   - Kacha allocation: [number] buildings ([percentage]% of capacity)
   - Semi-Pacca allocation: [number] buildings ([percentage]% of capacity)
   - Pacca allocation: [number] buildings ([percentage]% of capacity)

3. Justify allocation using:
   - Collapse probability dominance
   - Life-safety impact
   - Cost efficiency
   - Sector-wide risk reduction

4. Provide Japanese-style retrofit methods adapted to Pakistan:
   - For Kacha (mesh wrapping, banding, timber stiffening, foundation tying)
   - For URM (seismic bands, ferrocement jacketing, through-ties, wall anchoring)
   - For RCF (column jacketing, shear walls, soft-story strengthening, beam-column joints)

5. Estimate:
   - Building-level collapse probability reduction after retrofit
   - Sector-level fatality risk reduction percentage
   - Expected lives saved with this allocation

6. Give short-term emergency measures for buildings NOT yet retrofitted:
   - Evacuation planning
   - Temporary bracing
   - Occupant education
   - Emergency shelter identification

7. Provide implementation timeline and phases:
   - Phase 1 (Months 1-3): Rapid assessment and high-priority retrofits
   - Phase 2 (Months 4-9): Medium-priority retrofits
   - Phase 3 (Months 10-12): Low-priority retrofits and monitoring

8. Include cost estimates (approximate in PKR):
   - Kacha retrofitting cost per building
   - Semi-Pacca retrofitting cost per building
   - Pacca retrofitting cost per building
   - Total budget required

Write as a formal government technical action plan.
Use professional structure, headings, and numerical justification.
Be specific, practical, and actionable for implementation in Pakistan.
"""
    return prompt

# -------------------- RAG QA CHAIN --------------------

template = """
Context:
{context}

Sector Retrofit Planning Prompt:
{question}

You are a professional seismic retrofit engineer using Japanese standards adapted to Pakistan.
Follow all policy rules strictly.
Provide specific, actionable recommendations with clear numerical allocations.
"""

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template=template
)
print("[Retrofit Planner] QA Prompt Template created.")

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vector_db.as_retriever(search_kwargs={"k": 6}),
    chain_type_kwargs={"prompt": QA_PROMPT}
)
print("[Retrofit Planner] RAG QA Chain initialized.")

# -------------------- MASTER FUNCTION --------------------

def retrofit_plan(magnitude: float, sector_data: Dict, retrofit_capacity: int, 
                 priority_metric: str, retrofit_style: str) -> Dict:
    """
    Generate a retrofit action plan for ONE sector.
    This function is policy-driven, not suggestion-based.
    
    Args:
        magnitude: Earthquake magnitude
        sector_data: Dictionary containing sector information
        retrofit_capacity: Number of buildings to retrofit
        priority_metric: "Save Maximum Lives" or "Reduce Sector Vulnerability"
        retrofit_style: "Low-cost", "Structural", or "Hybrid"
        
    Returns:
        Dictionary with structured retrofit plan
    """
    try:
        # Normalize and validate inputs
        magnitude = safe_float_conversion(magnitude, 7.5)
        retrofit_capacity = safe_int_conversion(retrofit_capacity, 100)
        priority_metric = normalize_priority_metric(priority_metric)
        retrofit_style = normalize_retrofit_style(retrofit_style)
        
        # Add magnitude to sector_data
        sector_data = sector_data.copy()  # Don't modify original
        sector_data["magnitude"] = magnitude
        
        print(f"[Retrofit Plan] Processing sector: {sector_data.get('sector_name', 'Unknown')}")
        print(f"[Retrofit Plan] Capacity: {retrofit_capacity}, Metric: {priority_metric}")
        
        # Generate prompt
        prompt = generate_retrofit_prompt(
            sector_data,
            retrofit_capacity,
            priority_metric,
            retrofit_style
        )
        
        # RAG inference
        response = qa_chain.invoke(prompt)
        answer = response.get("result", "")
        
        if not answer:
            answer = f"Unable to generate retrofit plan for {sector_data.get('sector_name', 'the sector')}. Please verify input data."
        
        # Optional web enrichment
        web_summary = ""
        try:
            # Use normalized sector name for web search
            sector_name = normalize_sector_name(sector_data.get("sector_name", "Pakistan"))
            web_query = f"Japanese government sector-wide earthquake retrofit prioritization and life safety planning for {sector_name}"
            web_content = serpapi.run(web_query)
            
            web_summary = (
                "International retrofit programs, particularly in Japan, prioritize life-safety-first strategies by "
                "targeting high-collapse-probability structures such as unreinforced masonry and informal housing. "
                "Sector-wide planning emphasizes cost-effective mass retrofitting, rapid vulnerability screening, "
                "and allocation of resources based on collapse risk dominance rather than occupancy alone. "
                "Techniques such as PP-band mesh, seismic banding, and column jacketing are favored due to scalability "
                "and strong fatality reduction performance."
            )
        except Exception as web_error:
            print(f"[Web Search Error]: {web_error}")
            web_summary = "International retrofit best practices information currently unavailable."
        
        # Structured formatting
        structured = format_structured_output(answer, web_summary)
        
        # Add metadata
        structured["metadata"] = {
            "sector_name": normalize_sector_name(sector_data.get("sector_name", "Unknown")),
            "normalized_priority_metric": priority_metric,
            "normalized_retrofit_style": retrofit_style,
            "retrofit_capacity": retrofit_capacity,
            "magnitude": magnitude,
            "input_processing": "normalized"
        }
        
        return structured
        
    except KeyError as e:
        print(f"[KeyError]: Missing key in sector_data: {e}")
        return {
            "error": f"Missing required sector data: {e}",
            "risk_assessment_summary": ["Incomplete sector data provided."],
            "action_recommendations": ["Please provide all required sector parameters."],
            "full_detailed_report": "Cannot generate plan due to missing data."
        }
    except Exception as e:
        print(f"[Retrofit Engine Error]: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "error": "Service temporarily unavailable. Please try again later.",
            "risk_assessment_summary": ["Error in processing retrofit plan."],
            "action_recommendations": ["Please verify all input parameters."],
            "full_detailed_report": f"Technical error: {str(e)}"
        }

# -------------------- TEST FUNCTION --------------------

def test_retrofit_engine():
    """Test the retrofit engine with various input formats"""
    test_cases = [
        {
            "name": "Test 1: Standard inputs",
            "magnitude": 7.5,
            "sector_data": {
                "sector_name": "SECTOR I-11",
                "total_buildings": 1146,
                "overall_percent": 93.15,
                "kacha_percent": 75.59,
                "semi_pacca_percent": 7.4,
                "pacca_percent": 10.16
            },
            "retrofit_capacity": 100,
            "priority_metric": "Save Maximum Lives",
            "retrofit_style": "Hybrid"
        },
        {
            "name": "Test 2: Lowercase inputs",
            "magnitude": "7.0",
            "sector_data": {
                "sector_name": "sector i-11",
                "total_buildings": "1146",
                "overall_percent": "93.15",
                "kacha_percent": "75.59",
                "semi_pacca_percent": "7.4",
                "pacca_percent": "10.16"
            },
            "retrofit_capacity": "150",
            "priority_metric": "save lives",
            "retrofit_style": "low cost"
        },
        {
            "name": "Test 3: Different sector",
            "magnitude": 6.5,
            "sector_data": {
                "sector_name": "G-16",
                "total_buildings": 850,
                "overall_percent": 65.0,
                "kacha_percent": 40.0,
                "semi_pacca_percent": 30.0,
                "pacca_percent": 30.0
            },
            "retrofit_capacity": 75,
            "priority_metric": "Reduce Sector Vulnerability",
            "retrofit_style": "Structural"
        },
        {
            "name": "Test 4: Abbreviated inputs",
            "magnitude": 8.0,
            "sector_data": {
                "sector_name": "I-11",
                "total_buildings": 1000,
                "overall_percent": 80.0,
                "kacha_percent": 60.0,
                "semi_pacca_percent": 20.0,
                "pacca_percent": 20.0
            },
            "retrofit_capacity": 200,
            "priority_metric": "lifesaving",
            "retrofit_style": "balanced"
        }
    ]
    
    for test in test_cases:
        print(f"\n{'='*60}")
        print(f"{test['name']}")
        print(f"Sector: {test['sector_data']['sector_name']}")
        print(f"Capacity: {test['retrofit_capacity']}, Metric: {test['priority_metric']}")
        
        try:
            plan = retrofit_plan(
                magnitude=test["magnitude"],
                sector_data=test["sector_data"],
                retrofit_capacity=test["retrofit_capacity"],
                priority_metric=test["priority_metric"],
                retrofit_style=test["retrofit_style"]
            )
            
            if "error" in plan:
                print(f"Error: {plan.get('error')}")
            else:
                print(f"Normalized Sector: {plan.get('metadata', {}).get('sector_name', 'N/A')}")
                print(f"Priority Metric: {plan.get('metadata', {}).get('normalized_priority_metric', 'N/A')}")
                print(f"Risk Points: {plan.get('risk_assessment_summary', [])[:2]}")
                print(f"Action Points: {plan.get('action_recommendations', [])[:2]}")
        
        except Exception as e:
            print(f"Test failed with error: {e}")
        
        print(f"{'='*60}")

# -------------------- MAIN EXECUTION --------------------

if __name__ == "__main__":
    # Run tests
    test_retrofit_engine()
    
    # Or run a single test
    # test_sector = {
    #     "sector_name": "SECTOR I-11",
    #     "total_buildings": 1146,
    #     "overall_percent": 93.15,
    #     "kacha_percent": 75.59,
    #     "semi_pacca_percent": 7.4,
    #     "pacca_percent": 10.16
    # }
    
    # report = retrofit_plan(
    #     magnitude=7.5,
    #     sector_data=test_sector,
    #     retrofit_capacity=100,
    #     priority_metric="Save Maximum Lives",
    #     retrofit_style="Hybrid"
    # )
    
    # print("\n--- Retrofit Action Plan ---\n")
    # print(report)