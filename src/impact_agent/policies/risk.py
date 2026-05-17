class RiskPolicy:
    def evaluate(self, state) -> dict:
        confirmed_count = len(state.confirmed_affected)
        uncertain_count = len(state.uncertain)
        searched_count = len(state.searched_clues)

        if uncertain_count >= 3 or confirmed_count + uncertain_count >= 8:
            level = "high"
        elif uncertain_count >= 1 or confirmed_count >= 3 or searched_count >= 3:
            level = "medium"
        else:
            level = "low"

        return {
            "risk_level": level,
            "reason": f"确定影响 {confirmed_count} 项，不确定 {uncertain_count} 项，已检索线索 {searched_count} 个",
        }
