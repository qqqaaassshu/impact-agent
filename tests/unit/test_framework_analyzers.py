from impact_agent.adapters.framework.react import ReactAnalyzer
from impact_agent.adapters.framework.vue import VueAnalyzer


def test_vue_analyzer_extracts_template_and_script_field_usages() -> None:
    content = """
<template>
  <span>{{ order.amount }}</span>
  <input v-model="form.amount" />
</template>
<script>
export default {
  data() {
    return { amount: 0 };
  },
};
</script>
""".strip()

    usages = VueAnalyzer().extract_field_usages(content, "amount")

    assert [item["usage_type"] for item in usages] == [
        "template_interpolation",
        "template_binding",
        "object_field",
    ]
    assert all(item["framework"] == "vue" for item in usages)


def test_react_analyzer_extracts_jsx_and_config_field_usages() -> None:
    content = """
import React from 'react';

const columns = [{ key: 'amount', dataIndex: 'amount' }];
const View = ({ row }) => <span>{row.amount}</span>;
const Query = () => <TraderInput fieldName="amount" />;
""".strip()

    usages = ReactAnalyzer().extract_field_usages(content, "amount")

    assert [item["usage_type"] for item in usages] == [
        "config_field",
        "object_property",
        "config_field",
    ]
    assert all(item["framework"] == "react" for item in usages)
