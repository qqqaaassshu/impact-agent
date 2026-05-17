class ConfidencePolicy:
    def evaluate(self, state) -> dict:
        uncertain_count = len(state.uncertain)
        excluded_count = len(state.excluded)
        read_failures = sum(1 for item in state.uncertain if item.get("reason") == "file_read_failed")

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
            "reason": f"不确定项 {uncertain_count} 个，读取失败 {read_failures} 个",
        }
