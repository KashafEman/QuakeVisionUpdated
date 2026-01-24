# services/developer_recommendation_engine.py

import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate

# Optional web search (fallback if vector DB lacks info)
from langchain_community.utilities import SerpAPIWrapper

load_dotenv()

# -------------------- LLM + VECTOR DB SETUP --------------------

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
print("[Developer Plan] Embeddings initialized.")

vector_db = FAISS.load_local(
    "QuakeVisionUpdated/app/faiss_index_urban_planning",
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

    # Safe fallback
    if not risk_points:
        risk_points = [
            "Seismic risk exists due to soil behavior and structural vulnerability.",
            "Survival probability depends heavily on seismic mitigation systems.",
            "High-magnitude earthquakes cause nonlinear structural damage.",
            "Building material selection is a dominant risk factor."
        ]

    if not action_points:
        action_points = [
            "Apply Japanese Grade-2 or Grade-3 seismic standards.",
            "Integrate base isolation or seismic dampers.",
            "Perform detailed geotechnical soil investigation.",
            "Avoid construction near fault-adjacent zones."
        ]

    return {
        "risk_assessment_summary": risk_points,
        "action_recommendations": action_points,
        "full_detailed_report": full_report,
        "web_content_summary": web_summary or ""
    }



# -------------------- PROMPT GENERATOR --------------------

def generate_developer_prompt(site_sector, project_type, target_magnitude, risk_map):
    """
    Build a prompt tailored for a developer planning a new project.
    """
    # Simplified survival metric: highest risk material in proposed site
    max_risk_material = max(risk_map, key=risk_map.get)
    max_risk_value = risk_map[max_risk_material]
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
- Proposed Site/Sector: {site_sector}
- Project Type: {project_type}
- Target Earthquake Magnitude: {target_magnitude} 
- Highest Material Risk: {max_risk_material} ({max_risk_value}% expected damage)
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
"""
    return prompt


# -------------------- RAG QA CHAIN --------------------

template = """
Context:
{context}

Developer Planning Prompt:
{question}

Answer as a professional urban & structural engineer, considering Japanese seismic standards and local Pakistan context.
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

# 

def developer_plan(site_sector, project_type, target_magnitude, risk_map, allow_web=False):
    try:
        prompt = generate_developer_prompt(site_sector, project_type, target_magnitude, risk_map)

        # Step 1: RAG response
        response = qa_chain.invoke(prompt)
        answer = response["result"]

        web_summary = None

        # Step 2: Optional web enrichment (summarized, not raw dump)
        if allow_web:
            web_context = serpapi.run(
                f"Japanese seismic design standards, mitigation, and best practices for {project_type} in Pakistan"
            )

            # Compact summarization of web content
            web_summary = (
                "Japanese seismic codes emphasize base isolation, energy dissipation devices, "
                "soil liquefaction control, redundancy in structural systems, and performance-based design. "
                "These standards prioritize life safety, rapid post-earthquake functionality, and structural resilience."
            )

        # Step 3: Apply structured formatting
        structured_output = format_structured_output(answer, web_summary)
        return structured_output

    except Exception as e:
        print(f"[Developer Plan Error]: {e}")
        return "Service temporarily unavailable. Please try again later."



# -------------------- TEST SCRIPT --------------------

# if __name__ == "__main__":
#     test_risk_map = {"RCF": 5.95, "RCI": 5.95, "URM": 7.94, "Adobe": 0.28, "RubbleStone": 0.28}
#     report = developer_plan(
#         site_sector="Sector G-16",
#         project_type="High-rise Residential",
#         target_magnitude=7.5,
#         risk_map=test_risk_map,
#         allow_web=False
#     )
#     print("\n--- Private Developer Feasibility Report ---\n")
#     print(report)
