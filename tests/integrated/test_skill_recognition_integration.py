# -*- coding: utf-8 -*-
"""Integration tests for skill recognition enhancement."""
# pylint: disable=protected-access, unused-variable

from pathlib import Path

import pytest

from src.swe.agents.skill_feature_extractor import (
    SkillFeatureExtractor,
    reset_skill_feature_extractor,
)
from src.swe.agents.skill_feature_inferencer import (
    SkillFeature,
    SkillFeatureInferencer,
    reset_skill_feature_inferencer,
)
from src.swe.agents.skill_invocation_detector import (
    SkillInvocationDetector,
    reset_skill_invocation_detector,
)
from src.swe.agents.skill_context_manager import (
    SkillContextManager,
    reset_skill_context_manager,
)


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset all global instances before and after each test."""
    reset_skill_feature_extractor()
    reset_skill_feature_inferencer()
    reset_skill_invocation_detector()
    reset_skill_context_manager()
    yield
    reset_skill_feature_extractor()
    reset_skill_feature_inferencer()
    reset_skill_invocation_detector()
    reset_skill_context_manager()


class TestSkillRecognitionIntegration:
    """Integration tests for the complete skill recognition flow."""

    @pytest.mark.asyncio
    async def test_gold_qa_skill_extraction_from_skill_md(self):
        """Test extracting features from the gold Q&A SKILL.md in project root."""
        skill_md_path = Path("SKILL.md")
        if not skill_md_path.exists():
            pytest.skip("SKILL.md not found in project root")

        extractor = SkillFeatureExtractor()
        content = skill_md_path.read_text(encoding="utf-8")
        features = extractor.extract_from_content(content, "gold_qa")

        # Should have trigger keywords extracted
        assert len(features.trigger_keywords) > 0
        # Should be marked as conversational
        assert features.is_conversational is True

    @pytest.mark.asyncio
    async def test_user_message_detection_with_chinese_keywords(self):
        """Test Layer 0 detection with Chinese trigger keywords."""
        # Create a skill with Chinese trigger keywords
        feature = SkillFeature(
            skill_name="gold_qa",
            trigger_keywords=["黄金", "金价", "金条"],
            is_conversational=True,
        )
        inferencer = SkillFeatureInferencer(
            builtin_features={"gold_qa": feature},
        )
        context_manager = SkillContextManager()

        detector = SkillInvocationDetector(
            inferencer=inferencer,
            context_manager=context_manager,
        )
        detector.set_enabled_skills(["gold_qa"])

        # Test matching messages
        skill1, conf1 = detector.detect_from_user_message("黄金定期利率多少")
        assert skill1 == "gold_qa"
        assert conf1 >= 0.7

        skill2, conf2 = detector.detect_from_user_message("最近金价怎么样")
        assert skill2 == "gold_qa"
        assert conf2 >= 0.7

        # Test non-matching message
        skill3, conf3 = detector.detect_from_user_message("今天天气怎么样")
        assert skill3 is None
        assert conf3 == 0.0

    @pytest.mark.asyncio
    async def test_file_extension_skill_detection(self):
        """Test file extension detection in tool calls."""
        context_manager = SkillContextManager()
        detector = SkillInvocationDetector(context_manager=context_manager)
        detector.set_enabled_skills(["xlsx", "pdf"])

        # Tool call with .xlsx extension
        skill, weights = await detector.on_tool_call(
            "execute_shell_command",
            {"command": "python process.py data.xlsx"},
        )

        assert skill == "xlsx"
        assert weights.get("xlsx", 0) >= 0.8

    @pytest.mark.asyncio
    async def test_mcp_server_skill_detection(self):
        """Test MCP server based skill detection."""
        # Create skill with MCP server
        feature = SkillFeature(
            skill_name="filesystem_skill",
            mcp_servers=["filesystem"],
        )
        inferencer = SkillFeatureInferencer(
            builtin_features={"filesystem_skill": feature},
        )
        context_manager = SkillContextManager()

        detector = SkillInvocationDetector(
            inferencer=inferencer,
            context_manager=context_manager,
        )
        detector.set_enabled_skills(["filesystem_skill"])

        # Tool call with MCP server
        skill, weights = await detector.on_tool_call(
            "mcp_read_file",
            {"path": "/some/file"},
            mcp_server="filesystem",
        )

        assert skill == "filesystem_skill"
        assert weights.get("filesystem_skill", 0) >= 0.85

    @pytest.mark.asyncio
    async def test_layer0_cache_integration(self):
        """Test that Layer 0 cache is used during tool calls."""
        # Create conversational skill with trigger keywords
        feature = SkillFeature(
            skill_name="chat_skill",
            trigger_keywords=["hello", "help"],
            is_conversational=True,
        )
        inferencer = SkillFeatureInferencer(
            builtin_features={"chat_skill": feature},
        )
        context_manager = SkillContextManager()

        detector = SkillInvocationDetector(
            inferencer=inferencer,
            context_manager=context_manager,
        )
        detector.set_enabled_skills(["chat_skill"])

        # Detect from user message first
        detector.detect_from_user_message("hello, I need help")

        # Cache should be set
        assert detector._message_detected_skill == "chat_skill"
        assert detector._message_detected_confidence >= 0.7

        # Tool call should use the cache
        skill, _ = await detector.on_tool_call(
            "unknown_tool",
            {"data": "something"},
        )

        assert skill == "chat_skill"

    @pytest.mark.asyncio
    async def test_full_detection_flow_with_real_skill_md(self):
        """Test complete flow with real SKILL.md if available."""
        skill_md_path = Path("SKILL.md")
        if not skill_md_path.exists():
            pytest.skip("SKILL.md not found in project root")

        # Extract features
        extractor = SkillFeatureExtractor()
        content = skill_md_path.read_text(encoding="utf-8")
        features = extractor.extract_from_content(content, "gold_qa")

        # Build and register feature
        inferencer = SkillFeatureInferencer()
        skill_feature = extractor.build_skill_feature("gold_qa", features)
        inferencer.register_feature(skill_feature)
        context_manager = SkillContextManager()

        # Setup detector
        detector = SkillInvocationDetector(
            inferencer=inferencer,
            context_manager=context_manager,
        )
        detector.set_enabled_skills(["gold_qa"])

        # Test user message detection
        skill, confidence = detector.detect_from_user_message("黄金投资怎么样")
        assert skill == "gold_qa"
        assert confidence >= 0.7

        # Reset and verify cache clears
        detector.reset()
        assert detector._message_detected_skill is None
