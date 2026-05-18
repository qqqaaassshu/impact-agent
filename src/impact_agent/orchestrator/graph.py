from impact_agent.orchestrator.state import AgentState


def should_continue(state: AgentState) -> str:
    if state["iteration"] >= state["max_iteration"]:
        return "done"
    if not state["messages"]:
        return "done"

    last = state["messages"][-1]
    if not getattr(last, "tool_calls", None):
        return "done"
    return "continue"
