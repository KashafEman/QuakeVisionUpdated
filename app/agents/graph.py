# Graph composition (The "Manager")
from datetime import datetime
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes import (
    process_inputs_node,
    retrieve_knowledge_node,
    generate_report_node,
    validate_report_node,
    extract_visualization_node,  # NEW
    fallback_node,
    chatbot_node
)

# ==========================================
# 1. ROUTER LOGIC (Pure functions - NO state modification)
# ==========================================

def entry_point(state: AgentState):
    """
    Route based on current progress:
    - If we have visualization_data → chatbot (fully processed)
    - If we have final_output → extract_visualization (report ready)
    - If we have normalized_inputs → retrieve_knowledge
    - Otherwise → process_inputs
    """
    # Fully processed with visualization → go to chatbot
    if state.get("visualization_data") is not None and state.get("is_validated"):
        print("✅ Report with visualization ready, going to chatbot")
        return "chatbot"
    
    # Report validated but visualization not extracted yet
    if state.get("final_output") is not None and state.get("is_validated") and state.get("visualization_data") is None:
        print("📊 Report validated, extracting visualization data...")
        return "extract_visualization"
    
    # Report exists but not validated yet
    if state.get("final_output") is not None and not state.get("is_validated"):
        print("🔍 Report generated, validating...")
        return "validate_report"
    
    # Knowledge retrieved but no report generated
    if state.get("retrieved_context") is not None and state.get("raw_report") is None:
        print("📝 Knowledge retrieved, generating report...")
        return "generate_report"
    
    # Inputs normalized but no knowledge retrieved
    if state.get("normalized_inputs") is not None and state.get("retrieved_context") is None:
        print("🔍 Inputs normalized, retrieving knowledge...")
        return "retrieve_knowledge"
    
    # Fresh start
    if state.get("raw_report") is None:
        print("🆕 Starting fresh - processing inputs")
        return "process_inputs"
    
    # Fallback
    print("⚠️ Unknown state, defaulting to process_inputs")
    return "process_inputs"


def route_after_generation(state: AgentState):
    """Route after report generation: fallback, validate, or end."""
    if state.get("raw_report") == "TRIGGER_FALLBACK":
        return "fallback"
    if state.get("raw_report") == "END_NOW":
        return END
    return "validate_report"


def route_after_validation(state: AgentState):
    """
    Routes based on validation score:
    - Score < 70: Regenerate (up to max attempts)
    - Score >= 70: Extract visualization then chatbot
    - Max retries exceeded: Force proceed
    """
    validation_score = state.get("validation_score", 0)
    validation_attempts = state.get("validation_attempts", 0)
    max_attempts = 3
    
    # Force proceed after max attempts
    if validation_attempts >= max_attempts:
        print(f"⚠️ Max validation attempts ({max_attempts}) reached. Forcing pass.")
        # Force visualization extraction even with weak report
        return "extract_visualization"
    
    # Score too low - regenerate with feedback
    if validation_score < 70.0:
        print(f"📝 Score {validation_score}/100 < 70. Regenerating with feedback...")
        return "generate_report"
    
    # Score good - extract visualization then chatbot
    print(f"✅ Score {validation_score}/100 accepted. Extracting visualization...")
    return "extract_visualization"


def route_after_visualization(state: AgentState):
    """After visualization extraction, go to chatbot."""
    if state.get("visualization_data") is not None:
        print("✅ Visualization extracted successfully")
    else:
        print("⚠️ Visualization extraction failed, proceeding without structured data")
    return "chatbot"

def route_after_chatbot(state: AgentState):
    chatbot_response = state.get("chatbot_response", "")
    if chatbot_response == "END_CONVERSATION":
        print("👋 User requested exit")
    return END  # Always END — chat loop is handled outside the graph


def route_after_fallback(state: AgentState):
    """After fallback, extract visualization then chatbot."""
    if state.get("fallback_status") == "END" or state.get("raw_report") == "END_NOW":
        return END
    # Even fallback reports get visualization extraction
    return "extract_visualization"


# ==========================================
# 2. GRAPH CONSTRUCTION
# ==========================================

def create_quakevision_graph():
    workflow = StateGraph(AgentState)
    
    # Add all nodes
    workflow.add_node("process_inputs", process_inputs_node)
    workflow.add_node("retrieve_knowledge", retrieve_knowledge_node)
    workflow.add_node("generate_report", generate_report_node)
    workflow.add_node("validate_report", validate_report_node)
    workflow.add_node("extract_visualization", extract_visualization_node)  # NEW
    workflow.add_node("fallback", fallback_node)
    workflow.add_node("chatbot", chatbot_node)
    
    # Set entry point
    workflow.set_conditional_entry_point(entry_point)
    
    # process_inputs → retrieve_knowledge
    workflow.add_edge("process_inputs", "retrieve_knowledge")
    
    # retrieve_knowledge → generate_report
    workflow.add_edge("retrieve_knowledge", "generate_report")
    
    # generate_report → validate or fallback or END
    workflow.add_conditional_edges(
        "generate_report",
        route_after_generation,
        {
            "fallback": "fallback",
            "validate_report": "validate_report",
            END: END
        }
    )
    
    # validate_report → generate_report (retry), extract_visualization (pass), or fallback
    workflow.add_conditional_edges(
        "validate_report",
        route_after_validation,
        {
            "generate_report": "generate_report",
            "extract_visualization": "extract_visualization",
            "fallback": "fallback"
        }
    )
    
    # extract_visualization → chatbot (always)
    workflow.add_conditional_edges(
        "extract_visualization",
        route_after_visualization,
        {
            "chatbot": "chatbot"
        }
    )
    
    # fallback → extract_visualization or END
    workflow.add_conditional_edges(
        "fallback",
        route_after_fallback,
        {
            "extract_visualization": "extract_visualization",
            END: END
        }
    )
    
    # chatbot → END, process_inputs (new report), or chatbot (continue)
    workflow.add_conditional_edges(
        "chatbot",
        route_after_chatbot,
        {
            END: END,
            "process_inputs": "process_inputs",
            "chatbot": "chatbot"
        }
    )
    
    return workflow.compile()


app = create_quakevision_graph()