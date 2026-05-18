from typing import TypedDict

from langchain_core.messages import BaseMessage

from impact_agent.models.impact import ImpactItem


class AgentState(TypedDict):
    request_id: str
    repo_root: str
    requirement: str
    messages: list[BaseMessage]
    entities: list[str]
    findings: list[ImpactItem]
    visited_queries: set[str]
    iteration: int
    max_iteration: int
