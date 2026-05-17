from impact_agent.services.context_review import apply_context_review_decisions, build_context, select_review_candidates


def test_select_review_candidates_limits_uncertain_dynamic_items() -> None:
    state = {
        "read_files": {"src/a.ts": "const fieldName = 'amount'\nreturn row[fieldName]\n"},
        "uncertain": [
            {
                "evidence_id": "e-1",
                "file_path": "src/a.ts",
                "line_no": 2,
                "reason": "dynamic_field_reference",
                "code": "return row[fieldName]",
            },
            {
                "evidence_id": "e-2",
                "file_path": "src/a.ts",
                "line_no": 1,
                "reason": "other_reason",
                "code": "noop",
            },
            {
                "evidence_id": "e-3",
                "file_path": "src/a.ts",
                "line_no": 2,
                "reason": "variable_propagation_reference",
                "code": "return row[fieldName]",
            },
        ],
    }

    candidates = select_review_candidates(state, limit=2)

    assert len(candidates) == 2
    assert candidates[0]["evidence_id"] == "e-1"
    assert candidates[1]["evidence_id"] == "e-3"
    assert "return row[fieldName]" in candidates[0]["context"]


def test_apply_context_review_decisions_only_updates_existing_evidence() -> None:
    state = {
        "confirmed_affected": [],
        "excluded": [],
        "uncertain": [
            {
                "evidence_id": "e-1",
                "status": "uncertain",
                "reason": "dynamic_field_reference",
                "confidence": "low",
            }
        ],
        "evidence_chain": {
            "items": [
                {
                    "evidence_id": "e-1",
                    "decision": "uncertain",
                    "reason": "dynamic_field_reference",
                    "confidence": "low",
                }
            ],
            "count": 1,
        },
    }

    updated = apply_context_review_decisions(
        state,
        {
            "e-1": {
                "evidence_id": "e-1",
                "status": "confirmed_affected",
                "reason": "变量 fieldName 由字段 amount 赋值并被用于动态访问",
                "confidence": "medium",
            },
            "new-evidence": {
                "evidence_id": "new-evidence",
                "status": "confirmed_affected",
                "reason": "should be ignored",
                "confidence": "high",
            },
        },
    )

    assert len(updated["confirmed_affected"]) == 1
    assert updated["confirmed_affected"][0]["evidence_id"] == "e-1"
    assert updated["uncertain"] == []
    assert updated["evidence_chain"]["items"][0]["decision"] == "confirmed_affected"
    assert updated["evidence_chain"]["count"] == 1


def test_build_context_uses_local_window() -> None:
    content = "\n".join(f"line {index}" for index in range(1, 20))

    context = build_context(content, line_no=10, radius=2)

    assert "8: line 8" in context
    assert "10: line 10" in context
    assert "12: line 12" in context
    assert "13: line 13" not in context
