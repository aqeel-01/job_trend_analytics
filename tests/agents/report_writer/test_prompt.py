"""Tests for prompt construction."""

from pipeline.agents.report_writer.prompt import SYSTEM_PROMPT, build_report_prompt


class TestBuildReportPrompt:
    def test_includes_skill_data(self, valid_analyst_report):
        prompt = build_report_prompt(valid_analyst_report)
        assert "Python" in prompt
        assert "Java" in prompt
        assert "80" in prompt  # current_mentions

    def test_includes_model_version(self, valid_analyst_report):
        prompt = build_report_prompt(valid_analyst_report)
        assert "v1.0" in prompt

    def test_includes_stable_skills(self, valid_analyst_report):
        prompt = build_report_prompt(valid_analyst_report)
        assert "Go" in prompt

    def test_includes_data_quality_notes(self, valid_analyst_report):
        prompt = build_report_prompt(valid_analyst_report)
        assert "z-score" in prompt

    def test_system_prompt_has_grounding_rules(self):
        assert "Never invent" in SYSTEM_PROMPT
        assert "fabricate" in SYSTEM_PROMPT
        assert "limitations" in SYSTEM_PROMPT
