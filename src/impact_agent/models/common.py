from typing import Literal

ChangeType = Literal["field_rename", "feature_change"]
ConfidenceLevel = Literal["high", "medium", "low"]
DecisionStatus = Literal["confirmed_affected", "excluded", "uncertain"]
RiskLevel = Literal["low", "medium", "high", "unknown"]
SourceType = Literal["local", "gitlab"]
