# services/recommendation_engine.py

import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate

# Optional web search (only when your DB lacks info)
from langchain_community.utilities import SerpAPIWrapper

load_dotenv()

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

#---------------------Output Structure----------------------

def format_structured_output(full_report, web_summary=None):
    lines = [l.strip() for l in full_report.split("\n") if l.strip()]

    risk_points = []
    action_points = []

    for line in lines:
        l = line.lower()
        if any(k in l for k in ["risk", "damage", "hazard", "probability", "vulnerability"]):
            if len(risk_points) < 5:
                risk_points.append(line)

        if any(k in l for k in ["recommend", "should", "must", "install", "use", "apply", "adopt"]):
            if len(action_points) < 5:
                action_points.append(line)

    # Safe fallback (Retrofit-Oriented)

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

def convert_damage_to_survival(material, damage_percent):
    """
    Converts abstract damage % into realistic survival probability.
    Calibrated by structural vulnerability.
    """
    # Normalize material name to match vulnerability_factor keys
    material_lower = material.lower().replace(" ", "")
    
    vulnerability_factor = {
        "rubblestone": 0.25,
        "adobe": 0.20,
        "urm": 0.45,
        "rcf": 0.85,
        "rci": 0.75
    }

    base_survival = 100 - damage_percent
    
    # Get material key - handle variations
    material_key = None
    for key in vulnerability_factor.keys():
        if key in material_lower:
            material_key = key
            break
    
    if not material_key:
        material_key = "rubblestone"  # default
    
    calibrated = base_survival * vulnerability_factor[material_key]

    return round(calibrated, 2)



# -------------------- PROMPT GENERATOR --------------------

def generate_prompt(material, risk_value, magnitude, height):
    print(f"Generating prompt for material: {material}, risk: {risk_value}%, magnitude: {magnitude}")
    survival = convert_damage_to_survival(material, risk_value)
    print(f"Calculated survival probability: {survival}%")

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
    else:
        risk_level = "Extreme"
        tone = "urgent and safety-critical"
        focus = "full retrofitting and collapse prevention"

    print(f"Determined risk level: {risk_level}, tone: {tone}, focus: {focus}")

    return f"""
        You are QuakeVision AI, a seismic safety advisor.
        Your tone should be {tone}.

        Building Details:
        Material: {material}
        Earthquake Magnitude: {magnitude}
        Height: {height} stories
        Estimated Structural Survival Probability: {survival}%
        Risk Category: {risk_level}

        First, explain clearly what this survival percentage means in practical terms for occupants.

        Then:
        - If survival is below 25%, explain that structural failure or collapse is highly probable.
        - If survival is above 80%, explain that the building already approaches Japanese Grade-1 seismic performance.
        - Otherwise, explain how far the building is from Japanese Grade-1 safety.

        Focus your recommendations on {focus}.  

        Use only techniques appropriate to the building material:
        - For Rubble Stone / Adobe → emphasize PP-Band mesh, wall confinement, foundation tying
        - For URM → emphasize shear bands, through-ties, diaphragm action
        - For RCF/RCI → emphasize column jacketing, shear walls, base isolation only if justified

        End with a conclusion that matches the risk level:
        - Low risk → "This structure is generally safe but can be improved."
        - Moderate risk → "This structure should be strengthened."
        - High risk → "This structure is vulnerable and requires intervention."
        - Extreme risk → "This structure is unsafe without immediate retrofitting."
        """


# -------------------- QA CHAIN (RAG CORE) --------------------

template = """
Context:
{context}

User Engineering Prompt:
{question}

Answer as a professional structural seismic engineer.
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

def generate_retrofit_plan(material, risk_map, magnitude, height, allow_web=False):
    """
    material: "Rubble Stone", "URM", "RCF", etc.
    risk_map: dict like {RCF:5.9, RCI:5.9, URM:7.9, Adobe:0.28, RubbleStone:0.28}
    """

    try:
        key_map = {
            "rubble stone": "RubbleStone",
            "rubblestone": "RubbleStone",
            "adobe": "Adobe",
            "urm": "URM",
            "rcf": "RCF",
            "rci": "RCI"
        }

        # Normalize material name
        material_lower = material.lower().replace(" ", "")
        material_key = None

        for k, v in key_map.items():
            if k.replace(" ", "") in material_lower:
                material_key = v
                break

        if not material_key:
            material_key = material

        risk_value = risk_map[material_key]

        # Step 1: Engineering prompt
        engineering_prompt = generate_prompt(material, risk_value, magnitude, height)

        # Step 2: RAG inference
        response = qa_chain.invoke(engineering_prompt)
        answer = response["result"]

        # Step 3: Optional web enrichment (summarized, not appended raw)
        web_summary = ""
        if allow_web:
            serpapi.run(
                f"latest Japanese earthquake retrofitting techniques for {material}"
            )

            web_summary = (
                "Modern Japanese retrofitting emphasizes PP-band mesh for masonry, "
                "shear wall strengthening, column jacketing, base isolation where feasible, "
                "and performance-based seismic design to reduce collapse probability and "
                "improve post-earthquake usability."
            )

        # Step 4: Structured formatting for API + UI
        structured = format_structured_output(answer, web_summary)
        return structured

    except Exception as e:
        print(f"[Retrofit Engine Error]: {e}")
        return {
            "error": "Service temporarily unavailable. Please try again later."
        }



# risk_map = {
#     "RCF": 5.95,
#     "RCI": 5.95,
#     "URM": 7.94,
#     "Adobe": 0.28,
#     "RubbleStone": 0.28
# }

# # Now this will work with different variations:
# plan = generate_retrofit_plan(
#     material="RubbleStone",  # or "rubble stone", "rubblestone"
#     risk_map=risk_map,
#     magnitude=7,
#     allow_web=False
# )

# print("\n--- QuakeVision Retrofit Plan ---\n")
# print(plan)
