from typing import Dict, Any

# Home prompts
from app.utils.prompts.home_prompts import (
    get_home_generation_prompt,
    get_home_regeneration_prompt
)

# Gov prompts
from app.utils.prompts.gov_prompts import (
    get_gov_generation_prompt,
    get_gov_regeneration_prompt
)

# Developer prompts
from app.utils.prompts.developer_prompts import (
    get_developer_generation_prompt,
    get_developer_regeneration_prompt
)


# ==========================================
# CORE PROMPT BUILDER - FIXED SIGNATURE
# ==========================================

def build_prompt(
    user_type: str,
    inputs: Any,
    is_regeneration: bool,
    previous_report: str,
    feedback: str,
    missing_elements: list,
    metadata: Dict[str, Any] = None,
    combined_context: str = "",
    extracted_costs: Dict[str, Any] = None  # NEW
) -> str:
    """
    Centralized prompt builder with explicit parameters.
    
    Parameters:
    - user_type: "home", "gov", or "dev" (NOTE: "dev" not "developer")
    - inputs: The query object (HomeQuery, GovQuery, or DevQuery)
    - is_regeneration: Whether this is a regeneration attempt
    - previous_report: Previous report content for regeneration
    - feedback: Validation feedback for regeneration
    - missing_elements: List of missing elements from validation
    - metadata: Pre-computed metadata (optional)
    """
    
    # Ensure metadata exists
    if metadata is None:
        metadata = {}
    
    # Debug log
    print(f"[PromptBuilder] user_type={user_type}, regeneration={is_regeneration}")
    
    # Safety fallback
    if not inputs:
        return "ERROR: Missing inputs for prompt generation."

    # ==========================================
    # HOME
    # ==========================================
    if user_type == "home":
        if is_regeneration:
            return get_home_regeneration_prompt(
                inputs=inputs,
                metadata=metadata,
                previous_report=previous_report,
                feedback=feedback,
                missing_elements=missing_elements
            )
        return get_home_generation_prompt(
            inputs=inputs,
            metadata=metadata
        )

    # ==========================================
    # GOVERNMENT
    # ==========================================
    elif user_type == "gov":
        if is_regeneration:
            return get_gov_regeneration_prompt(
                inputs=inputs,
                metadata=metadata,
                previous_report=previous_report,
                feedback=feedback,
                missing_elements=missing_elements
            )
        return get_gov_generation_prompt(
            inputs=inputs,
            metadata=metadata
        )

    # ==========================================
    # DEVELOPER (mapped from "dev")
    # ==========================================
    elif user_type == "dev" or user_type == "developer":  # Accept both for safety
        if is_regeneration:
            return get_developer_regeneration_prompt(
                inputs=inputs,
                metadata=metadata,
                previous_report=previous_report,
                feedback=feedback,
                missing_elements=missing_elements
            )
        return get_developer_generation_prompt(
            inputs=inputs,
            metadata=metadata
        )

    # ==========================================
    # FALLBACK
    # ==========================================
    else:
        return f"""
Invalid user_type: {user_type}

Expected one of:
- home
- gov
- dev (or developer)

Cannot build prompt.
"""  # Fixed: exactly 3 quotes