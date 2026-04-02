from typing import Annotated, List, Optional, Dict, Any, Union, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, field_validator
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.documents import Document  # For vector DB results

# ==========================================
# 0. NORMALIZED INPUT SCHEMAS (NEW)
# ==========================================

class NormalizedInputs(BaseModel):
    """
    Processed and validated inputs after passing through normalizers.
    This is what the report generation node should actually use.
    """
    # Common normalized fields
    magnitude: float = Field(..., description="Normalized magnitude value")
    budget_level: Literal["low", "moderate", "high"] = Field(..., description="Normalized budget level")
    timeline_months: int = Field(..., description="Timeline in months")
    project_size_sqft: int = Field(..., description="Normalized project size")
    
    # Home-specific
    material_normalized: Optional[str] = Field(None, description="Normalized material code (RCF, URM, etc.)")
    
    # Gov-specific  
    sector_normalized: Optional[str] = Field(None, description="Normalized sector code")
    
    # Dev-specific
    site_sector_normalized: Optional[str] = Field(None, description="Normalized site sector")
    building_type: Optional[str] = Field(None, description="Building type classification")
    total_sqft: Optional[int] = Field(None, description="Total square footage (floors * size)")
    building_class: Optional[str] = Field(None, description="Class A+, A, or B")
    
    # Timeline description for prompts
    timeline_description: Optional[str] = Field(None, description="Human-readable timeline description")

    # Gov-specific
    total_sqft: Optional[int] = Field(None, description="Total sqft across all buildings to retrofit")
    dominant_construction_type: Optional[str] = Field(None, description="Kacha / Semi-Pacca / Pacca")
    affected_population: Optional[int] = Field(None)
    kacha_percent: Optional[float] = Field(None)
    semi_pacca_percent: Optional[float] = Field(None)
    pacca_percent: Optional[float] = Field(None)

# ==========================================
# 1. INPUT SCHEMAS (The Requests) - UNCHANGED
# ==========================================

class BaseQuakeQuery(BaseModel):
    """Common fields for all modules."""
    magnitude: float = Field(..., description="Earthquake magnitude", ge=0, le=10)
    allow_web: bool = Field(default=False)
    
    budget_level: Literal["low", "moderate", "high"] = Field(
        default="moderate",
        description="Budget level for retrofit/reconstruction"
    )
    
    timeline_value: int = Field(default=12, description="Timeline duration value", ge=1)
    timeline_unit: Literal["months", "years"] = Field(default="months")
    
    project_size_sqft: int = Field(
        default=5000,
        description="Project size in square feet",
        ge=100,
        le=1000000
    )
    floors: int = Field(default=1, ge=1, le=50)
    
    @property
    def timeline_months(self) -> int:
        """Convert timeline to months for consistent processing."""
        if self.timeline_unit == "years":
            return self.timeline_value * 12
        return self.timeline_value
    
    @field_validator('project_size_sqft')
    @classmethod
    def validate_project_size(cls, v: int) -> int:
        if v < 100:
            raise ValueError("Project size must be at least 100 sq ft")
        if v > 1000000:
            raise ValueError("Project size cannot exceed 1,000,000 sq ft")
        return v

class HomeQuery(BaseQuakeQuery):
    """Homeowner Retrofit Module."""
    material: str
    risk_map: Dict[str, float]
    building_type: Literal["single_story", "multi_story", "apartment", "townhouse"] = Field(
        default="single_story",
        description="Type of residential structure"
    )
    
    @property
    def total_sqft(self) -> int:
        return self.project_size_sqft * self.floors
    

class GovQuery(BaseQuakeQuery):
    """Government Urban Planning Module."""
    sector_data: Dict[str, Any]
    retrofit_capacity: int = Field(default=100)
    priority_metric: str = Field(default="Save Maximum Lives")
    retrofit_style: str = Field(default="Hybrid")

    @property
    def affected_population(self) -> int:
        return self.sector_data.get('population', 0)

    @property
    def total_sqft(self) -> int:
        """Total sqft across all buildings to be retrofitted."""
        return self.retrofit_capacity * self.project_size_sqft * self.floors

    @property
    def dominant_construction_type(self) -> str:
        """Most prevalent construction type in the sector."""
        kacha = self.sector_data.get("kacha_percent", 0)
        semi  = self.sector_data.get("semi_pacca_percent", 0)
        pacca = self.sector_data.get("pacca_percent", 0)
        return max(
            [("Kacha", kacha), ("Semi-Pacca", semi), ("Pacca", pacca)],
            key=lambda x: x[1]
        )[0]

class DevQuery(BaseQuakeQuery):
    """Real Estate Developer Module."""
    site_sector: str
    project_type: str
    risk_map: Dict[str, float]
    project_name: Optional[str] = Field(default=None)
    building_type: Literal["residential", "commercial", "mixed-use", "industrial"] = Field(default="commercial")
    
    
    @property
    def total_sqft(self) -> int:
        return self.project_size_sqft * self.floors
    
    @property
    def building_class(self) -> str:
        if self.budget_level == "high" and self.total_sqft > 50000:
            return "Class A+"
        elif self.budget_level == "moderate" or self.total_sqft > 20000:
            return "Class A"
        else:
            return "Class B"

# ==========================================
# 2. OUTPUT SCHEMAS (The Results) - ENHANCED
# ==========================================

class RetrofitReport(BaseModel):
    """
    Structured response including metadata and sources.
    """
    risk_assessment_summary: List[str]
    action_recommendations: List[str]
    full_detailed_report: str
    
    # Metadata for normalized outputs
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Stores normalized_material, sector_name, budget_level, timeline, project_size, etc."
    )
    
    # NEW: Track what knowledge was used
    sources_used: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tracks vector_db_results and web_search_results used"
    )
    
    is_validated: bool = False
    validation_score: float = 0.0
    validation_feedback: Optional[str] = None

# ==========================================
# 3. THE GRAPH STATE (The Brain) - ENHANCED
# ==========================================

class AgentState(TypedDict):
    """
    Main state object with knowledge retrieval and normalization support.
    """
    # ===== CORE FIELDS =====
    messages: Annotated[list, add_messages]
    inputs: Union[HomeQuery, GovQuery, DevQuery]
    user_type: str  # "home", "gov", or "dev"
    loop_count: int
    
    # ===== NORMALIZED INPUTS (NEW) =====
    # These are populated by an input_processor node using normalizers
    normalized_inputs: Optional[NormalizedInputs]
    
    # ===== KNOWLEDGE RETRIEVAL FIELDS (NEW) =====
    # Retrieved context from vector DB
    retrieved_context: Optional[List[Document]]
    # Whether retrieval was successful
    retrieval_success: Optional[bool]
    
    # Web search results (when allow_web=True or retrieval insufficient)
    web_search_results: Optional[str]
    # Whether web search was performed
    web_search_performed: Optional[bool]
    
    # Combined context for LLM (retrieved + web search formatted)
    combined_context: Optional[str]
    
    # ===== REPORT GENERATION FIELDS =====
    raw_report: Optional[str]
    critique: Optional[str]
    final_output: Optional[RetrofitReport]
    visualization_data: Optional[Dict]
    
    # ===== VALIDATION FIELDS =====
    validation_score: Optional[float]
    validation_feedback: Optional[str]
    is_validated: Optional[bool]
    validation_attempts: Optional[int]
    last_validation_feedback: Optional[str]
    
    # ===== CHATBOT FIELDS =====
    in_chat_mode: Optional[bool]
    chatbot_response: Optional[str]
    regenerated_report: Optional[RetrofitReport]
    regenerated_visualization_data: Optional[Dict]   # New viz data
    active_report: Literal["original", "regenerated"] # Which one to use for dashboard
    previous_report: Optional[RetrofitReport]  # Archive for comparison after swap
    
    # ===== FALLBACK FIELDS =====
    fallback_status: Optional[str]
    fallback_reason: Optional[str]
    validation_forced: Optional[bool]
    missing_elements: Optional[List[str]]
    extracted_costs: Optional[Dict[str, Any]]  # NEW

    

# ==========================================
# 4. DEFAULT STATE FACTORY - UPDATED
# ==========================================

def create_initial_state(
    inputs: Union[HomeQuery, GovQuery, DevQuery],
    user_type: str,
    messages: Optional[List[Union[HumanMessage, AIMessage]]] = None
) -> AgentState:
    """Factory function with all new fields initialized."""
    formatted_messages = []
    if messages:
        for msg in messages:
            if isinstance(msg, tuple):
                role, content = msg
                if role == "user":
                    formatted_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    formatted_messages.append(AIMessage(content=content))
            else:
                formatted_messages.append(msg)
    
    return {
        # Core
        "messages": formatted_messages or [],
        "inputs": inputs,
        "user_type": user_type,
        "loop_count": 0,
        
        # Normalized inputs (populated by processor node)
        "normalized_inputs": None,
        
        # Knowledge retrieval (populated by retrieval node)
        "retrieved_context": None,
        "retrieval_success": False,
        "web_search_results": None,
        "web_search_performed": False,
        "combined_context": None,
        
        # Report generation
        "raw_report": None,
        "critique": None,
        "final_output": None,
        
        # Validation
        "validation_score": None,
        "validation_feedback": None,
        "is_validated": False,
        "validation_attempts": 0,
        "last_validation_feedback": None,
        
        # Chatbot
        "in_chat_mode": False,
        "chatbot_response": None,
        
        # Fallback
        "fallback_status": None,
        "fallback_reason": None,
        "validation_forced": False,
        "missing_elements": None
    }

# ==========================================
# 5. TYPE ALIASES & HELPERS - UNCHANGED
# ==========================================

MIN_VALIDATION_SCORE = 70.0
MAX_VALIDATION_ATTEMPTS = 3

class BudgetLevel:
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    
    MULTIPLIERS = {
        LOW: 0.6,
        MODERATE: 1.0,
        HIGH: 1.5
    }
    
    DESCRIPTIONS = {
        LOW: "budget-conscious, minimal essential upgrades only, focus on cost-effective solutions",
        MODERATE: "standard approach with balanced cost-effectiveness, typical market solutions",
        HIGH: "premium, comprehensive upgrades with advanced technologies, best-in-class solutions"
    }

class TimelineUnit:
    MONTHS = "months"
    YEARS = "years"

def get_budget_description(budget_level: str) -> str:
    return BudgetLevel.DESCRIPTIONS.get(budget_level, BudgetLevel.DESCRIPTIONS[BudgetLevel.MODERATE])

def get_budget_multiplier(budget_level: str) -> float:
    return BudgetLevel.MULTIPLIERS.get(budget_level, 1.0)

def get_building_type_multiplier(building_type: str) -> float:
    multipliers = {
        "residential": 1.0,
        "commercial": 1.2,
        "mixed-use": 1.3,
        "industrial": 0.9
    }
    return multipliers.get(building_type, 1.0)