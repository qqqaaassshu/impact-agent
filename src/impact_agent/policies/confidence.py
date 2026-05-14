class ConfidencePolicy:
    def evaluate(self, state) -> dict:
        uncertain_count = len(state.uncertain_matches)
        excluded_count = len(state.excluded_matches)
        read_failures = sum(1 for item in state.uncertain_matches if item.get("reason") == "file_read_failed")

        if read_failures > 0 or uncertain_count >= 3:
            level = "low"
        elif uncertain_count >= 1:
            level = "medium"
        elif excluded_count >= 0:
            level = "high"
        else:
            level = "medium"

        return {
            "overall_confidence": level,
            "reason": f"uncertain={uncertain_count}, read_failures={read_failures}",
        }
