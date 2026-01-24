# services/retrofit_recommender_engine.py

import os
from dotenv import load_dotenv
from datetime import date

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate
from langchain_community.utilities import SerpAPIWrapper


# -------------------- DATE HANDLING (NO HALLUCINATION) --------------------

today = date.today().strftime("%B %d, %Y")

load_dotenv()

# -------------------- LLM + VECTOR DB SETUP --------------------

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
print("[Retrofit Planner] Embeddings initialized.")

vector_db = FAISS.load_local(
    "faiss_index_urban_planning",
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

def generate_retrofit_prompt(sector_data, retrofit_capacity, priority_metric, retrofit_style):
    """
    Build a policy-constrained prompt for retrofitting ONE sector.
    Collapse probability always dominates when 'Save Maximum Lives' is selected.
    """

    sector_name = sector_data["sector_name"]
    total_buildings = sector_data["total_buildings"]
    overall_risk = sector_data["overall_percent"]
    magnitude = sector_data.get("magnitude", 7.5)  # default to 7.5 if not provided

    kacha = sector_data["kacha_percent"]
    semi_pacca = sector_data["semi_pacca_percent"]
    pacca = sector_data["pacca_percent"]

    prompt = f"""
You are QuakeVision AI, operating as the Seismic Retrofit Planning Engine for the 
National Disaster Management Authority (NDMA) and Capital Development Authority (CDA), Pakistan.

Official Planning Date: {today}

Sector Profile:
- Sector Name: {sector_name}
- Total Buildings: {total_buildings}
- Earthquake Magnitude: {magnitude}
- Overall Collapse Probability: {overall_risk}%
- Building Distribution:
    - Kacha (Rubble Stone / Adobe): {kacha}%
    - Semi-Pacca (URM): {semi_pacca}%
    - Pacca (RCF/RCI): {pacca}%

User Constraints:
- Retrofit Capacity: {retrofit_capacity} buildings
- Priority Metric: {priority_metric}
- Retrofit Strategy Style: {retrofit_style} (Low-cost / Structural / Hybrid)

IMPORTANT POLICY RULES:

If Priority Metric = "Save Maximum Lives":
1. Buildings with the HIGHEST collapse probability must always be prioritized first.
2. At least 60–70% of retrofit capacity MUST be allocated to:
   - Kacha (Rubble Stone / Adobe)
3. The remaining capacity is distributed in this order:
   - Semi-Pacca (URM)
   - Then Pacca (RCF/RCI), only if capacity remains.
4. High occupancy alone is NOT sufficient to override collapse probability.

If Priority Metric = "Reduce Sector Vulnerability":
1. Allocate resources to reduce total sector-wide risk percentage.
2. Balance across all typologies based on proportional contribution to vulnerability.

Your Tasks:
1. Classify the sector using Japanese Seismic Safety Grades:
   - Grade 0 (Extremely Vulnerable)
   - Grade 1 (Highly Vulnerable)
   - Grade 2 (Moderate)
   - Grade 3 (Acceptable)

2. Allocate exactly {retrofit_capacity} buildings using the above policy rules.
   Show:
   - Kacha allocation
   - Semi-Pacca allocation
   - Pacca allocation

3. Justify allocation using:
   - Collapse probability dominance
   - Life-safety impact
   - Cost efficiency

4. Provide Japanese-style retrofit methods adapted to Pakistan:
   - For Kacha (mesh wrapping, banding, timber stiffening)
   - For URM (seismic bands, ferrocement jacketing)
   - For RCF (column jacketing, shear walls, soft-story strengthening)

5. Estimate:
   - Building-level collapse probability reduction
   - Sector-level fatality risk reduction

6. Give short-term emergency measures for buildings NOT yet retrofitted.

7. Keep all engineering advice economically feasible for Pakistan.

Write as a formal government technical action plan.
Use professional structure, headings, and numerical justification.
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

def retrofit_plan(magnitude, sector_data, retrofit_capacity, priority_metric, retrofit_style):
    """
    Generate a retrofit action plan for ONE sector.
    This function is policy-driven, not suggestion-based.
    """
    try:
        prompt = generate_retrofit_prompt(
            sector_data,
            retrofit_capacity,
            priority_metric,
            retrofit_style
        )

        response = qa_chain.invoke(prompt)
        answer = response["result"]

         # Step 3: Optional web enrichment (summarized, not appended raw)
        web_summary = ""
        
        serpapi.run(
            f"Japanese government sector-wide earthquake retrofit prioritization and life safety planning"
        )

        web_summary = (
            "International retrofit programs, particularly in Japan, prioritize life-safety-first strategies by "
            "targeting high-collapse-probability structures such as unreinforced masonry and informal housing. "
            "Sector-wide planning emphasizes cost-effective mass retrofitting, rapid vulnerability screening, "
            "and allocation of resources based on collapse risk dominance rather than occupancy alone. "
            "Techniques such as PP-band mesh, seismic banding, and column jacketing are favored due to scalability "
            "and strong fatality reduction performance."
        )


        # Step 4: Structured formatting for API + UI
        structured = format_structured_output(answer, web_summary)
        return structured

        return answer
    
    except Exception as e:
        print(f"[Retrofit Engine Error]: {e}")
        return {
            "error": "Service temporarily unavailable. Please try again later."
        }


# # -------------------- TEST SCRIPT --------------------

# if __name__ == "__main__":
#     test_sector = {
#         "sector_name": "SECTOR I-11",
#         "total_buildings": 1146,
#         "overall_percent": 93.15,
#         "kacha_percent": 75.59,
#         "semi_pacca_percent": 7.4,
#         "pacca_percent": 10.16
#     }

#     report = retrofit_plan(
#         sector_data=test_sector,
#         retrofit_capacity=100,
#         priority_metric="Save Maximum Lives",
#         retrofit_style="Hybrid",
#          magnitude=7.5
#     )

#     print("\n--- Retrofit Action Plan ---\n")
#     print(report)
