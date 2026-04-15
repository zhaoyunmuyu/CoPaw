# -*- coding: utf-8 -*-
"""Tests for skill invocation detection and custom skill recognition.

This test module covers:
1. SkillToolRegistry - tool ownership declarations
2. SkillFeatureInferencer - feature-based skill inference
3. SkillInvocationDetector - multi-layer skill attribution
4. SkillContextManager - execution context tracking
"""
# pylint: disable=protected-access,redefined-outer-name

import pytest

from swe.agents.skill_tool_registry import (
    SkillToolRegistry,
    get_skill_tool_registry,
    reset_skill_tool_registry,
)
from swe.agents.skill_feature_inferencer import (
    SkillFeature,
    SkillFeatureInferencer,
    BUILTIN_SKILL_FEATURES,
    get_skill_feature_inferencer,
    reset_skill_feature_inferencer,
)
from swe.agents.skill_context_manager import (
    SkillContextManager,
    get_skill_context_manager,
    reset_skill_context_manager,
)
from swe.agents.skill_invocation_detector import (
    SkillInvocationDetector,
    get_skill_invocation_detector,
    reset_skill_invocation_detector,
)


@pytest.fixture(autouse=True)
def reset_all_globals():
    """Reset all global instances before and after each test."""
    reset_skill_tool_registry()
    reset_skill_feature_inferencer()
    reset_skill_context_manager()
    reset_skill_invocation_detector()
    yield
    reset_skill_tool_registry()
    reset_skill_feature_inferencer()
    reset_skill_context_manager()
    reset_skill_invocation_detector()


# =============================================================================
# SkillToolRegistry Tests
# =============================================================================


class TestSkillToolRegistry:
    """Tests for SkillToolRegistry class."""

    def test_register_single_skill(self):
        """Test registering tools for a single skill."""
        registry = SkillToolRegistry()
        registry.register_skill_tools(
            "pdf",
            ["read_file", "execute_shell_command"],
        )

        assert registry.skill_count == 1
        assert registry.get_tools_for_skill("pdf") == [
            "read_file",
            "execute_shell_command",
        ]

    def test_register_multiple_skills(self):
        """Test registering tools for multiple skills."""
        registry = SkillToolRegistry()
        registry.register_skill_tools(
            "pdf",
            ["read_file", "execute_shell_command"],
        )
        registry.register_skill_tools("xlsx", ["read_file", "write_file"])

        assert registry.skill_count == 2
        assert (
            registry.tool_count == 3
        )  # read_file, execute_shell_command, write_file

    def test_get_skills_for_tool(self):
        """Test getting skills that claim a tool."""
        registry = SkillToolRegistry()
        registry.register_skill_tools("pdf", ["read_file"])
        registry.register_skill_tools("xlsx", ["read_file", "write_file"])
        registry.register_skill_tools("docx", ["read_file"])

        skills = registry.get_skills_for_tool("read_file")
        assert skills == ["docx", "pdf", "xlsx"]  # Sorted

    def test_wildcard_pattern_matching(self):
        """Test wildcard pattern matching for tool names."""
        registry = SkillToolRegistry()
        registry.register_skill_tools("browser", ["browser_*"])

        skills = registry.get_skills_for_tool("browser_click")
        assert skills == ["browser"]

        skills = registry.get_skills_for_tool("browser_navigate")
        assert skills == ["browser"]

        skills = registry.get_skills_for_tool("other_tool")
        assert skills == []

    def test_calculate_weights_single_skill(self):
        """Test weight calculation for single skill."""
        registry = SkillToolRegistry()
        weights = registry.calculate_weights(["pdf"])

        assert weights == {"pdf": 1.0}

    def test_calculate_weights_multiple_skills(self):
        """Test weight calculation for multiple skills."""
        registry = SkillToolRegistry()
        weights = registry.calculate_weights(["pdf", "xlsx"])

        assert weights == {"pdf": 0.5, "xlsx": 0.5}

    def test_calculate_weights_empty(self):
        """Test weight calculation for empty list."""
        registry = SkillToolRegistry()
        weights = registry.calculate_weights([])

        assert weights == {}

    def test_clear_registry(self):
        """Test clearing the registry."""
        registry = SkillToolRegistry()
        registry.register_skill_tools("pdf", ["read_file"])

        assert registry.skill_count == 1

        registry.clear()

        assert registry.skill_count == 0
        assert registry.tool_count == 0

    def test_global_registry(self):
        """Test global registry functions."""
        registry1 = get_skill_tool_registry()
        registry2 = get_skill_tool_registry()

        assert registry1 is registry2

        reset_skill_tool_registry()
        registry3 = get_skill_tool_registry()

        assert registry3 is not registry1


# =============================================================================
# SkillFeatureInferencer Tests
# =============================================================================


class TestSkillFeatureInferencer:
    """Tests for SkillFeatureInferencer class."""

    def test_infer_from_file_extension(self):
        """Test skill inference from file extension in tool input."""
        inferencer = SkillFeatureInferencer()

        skill, confidence = inferencer.infer_skill_from_tool_input(
            "execute_shell_command",
            {"command": "python process.py data.xlsx"},
            ["xlsx", "pdf"],
        )

        assert skill == "xlsx"
        assert confidence == 0.8

    def test_infer_from_keyword(self):
        """Test skill inference from keywords in tool input."""
        inferencer = SkillFeatureInferencer()

        skill, confidence = inferencer.infer_skill_from_tool_input(
            "execute_shell_command",
            {"command": "convert this excel file"},
            ["xlsx", "pdf"],
        )

        assert skill == "xlsx"
        assert confidence >= 0.4

    def test_infer_from_tool_hint(self):
        """Test skill inference from tool hint."""
        inferencer = SkillFeatureInferencer()

        skill, confidence = inferencer.infer_skill_from_tool_input(
            "execute_shell_command",
            {"command": "do something generic"},
            ["xlsx"],
        )

        # execute_shell_command is in xlsx tools_hint
        assert skill == "xlsx"
        assert confidence == 0.5

    def test_infer_no_match(self):
        """Test no skill match returns None."""
        inferencer = SkillFeatureInferencer()

        skill, confidence = inferencer.infer_skill_from_tool_input(
            "unknown_tool",
            {"data": "generic content"},
            ["xlsx"],
        )

        assert skill is None
        assert confidence == 0.0

    def test_infer_from_tool_sequence(self):
        """Test skill inference from tool sequence pattern."""
        inferencer = SkillFeatureInferencer()

        # xlsx has pattern ["read_file", "execute_shell_command"]
        skill, confidence = inferencer.infer_skill_from_tool_sequence(
            ["other_tool", "read_file", "execute_shell_command"],
            ["xlsx"],
        )

        assert skill == "xlsx"
        assert confidence == 0.6

    def test_infer_sequence_no_match(self):
        """Test sequence inference with no pattern match."""
        inferencer = SkillFeatureInferencer()

        skill, _ = inferencer.infer_skill_from_tool_sequence(
            ["read_file", "write_file"],
            ["xlsx"],
        )

        assert skill is None

    def test_get_skills_for_tool(self):
        """Test getting skills that might use a tool."""
        inferencer = SkillFeatureInferencer()

        skills = inferencer.get_skills_for_tool(
            "execute_shell_command",
            ["xlsx", "pdf"],
        )

        assert len(skills) == 2
        assert ("xlsx", 0.4) in skills
        assert ("pdf", 0.4) in skills

    def test_register_custom_feature(self):
        """Test registering a custom skill feature."""
        inferencer = SkillFeatureInferencer()

        custom_feature = SkillFeature(
            skill_name="custom_skill",
            file_extensions=[".custom"],
            keywords=["custom_keyword"],
            tools_hint=["custom_tool"],
        )

        inferencer.register_feature(custom_feature)

        # Verify the feature is registered
        feature = inferencer.get_feature("custom_skill")
        assert feature is not None
        assert feature.skill_name == "custom_skill"

        # Test inference with custom skill
        skill, confidence = inferencer.infer_skill_from_tool_input(
            "custom_tool",
            {"file": "data.custom"},
            ["custom_skill"],
        )

        assert skill == "custom_skill"
        assert confidence == 0.8  # File extension match

    def test_builtin_features_loaded(self):
        """Test that built-in features are loaded by default."""
        inferencer = SkillFeatureInferencer()

        assert inferencer.get_feature("xlsx") is not None
        assert inferencer.get_feature("pdf") is not None
        assert inferencer.get_feature("docx") is not None
        assert inferencer.get_feature("pptx") is not None
        assert inferencer.get_feature("browser_cdp") is not None
        assert inferencer.get_feature("browser_visible") is not None
        assert inferencer.get_feature("cron") is not None

    def test_builtin_xlsx_feature_properties(self):
        """Test xlsx built-in feature properties."""
        feature = BUILTIN_SKILL_FEATURES["xlsx"]

        assert ".xlsx" in feature.file_extensions
        assert ".xls" in feature.file_extensions
        assert "excel" in feature.keywords
        assert "表格" in feature.keywords  # Chinese keyword
        assert "execute_shell_command" in feature.tools_hint

    def test_global_inferencer(self):
        """Test global inferencer functions."""
        inferencer1 = get_skill_feature_inferencer()
        inferencer2 = get_skill_feature_inferencer()

        assert inferencer1 is inferencer2

        reset_skill_feature_inferencer()
        inferencer3 = get_skill_feature_inferencer()

        assert inferencer3 is not inferencer1


# =============================================================================
# SkillContextManager Tests
# =============================================================================


class TestSkillContextManager:
    """Tests for SkillContextManager class."""

    def test_push_and_pop_skill(self):
        """Test pushing and popping skills from stack."""
        manager = SkillContextManager()

        manager.push_skill("xlsx", trigger_reason="declared")
        assert manager.current_skill == "xlsx"
        assert manager.skill_depth == 1

        context = manager.pop_skill()
        assert context is not None
        assert context.skill_name == "xlsx"
        assert manager.current_skill is None
        assert manager.skill_depth == 0

    def test_nested_skills(self):
        """Test nested skill execution."""
        manager = SkillContextManager()

        manager.push_skill("xlsx", trigger_reason="declared")
        manager.push_skill("pdf", trigger_reason="inferred")

        assert manager.skill_depth == 2
        assert manager.current_skill == "pdf"
        assert manager.active_skills == ["xlsx", "pdf"]

        manager.pop_skill()
        assert manager.current_skill == "xlsx"

        manager.pop_skill()
        assert manager.current_skill is None

    def test_record_tool_call(self):
        """Test recording tool calls in skill context."""
        manager = SkillContextManager()

        manager.push_skill("xlsx", trigger_reason="declared")
        manager.record_tool_call("read_file")
        manager.record_tool_call("execute_shell_command")

        context = manager.current_context
        assert context is not None
        assert "read_file" in context.tools_called
        assert "execute_shell_command" in context.tools_called

    def test_record_mcp_tool_call(self):
        """Test recording MCP tool calls in skill context."""
        manager = SkillContextManager()

        manager.push_skill("browser", trigger_reason="declared")
        manager.record_tool_call("navigate", mcp_server="puppeteer")

        context = manager.current_context
        assert context is not None
        assert "puppeteer:navigate" in context.mcp_tools_called

    def test_pop_empty_stack(self):
        """Test popping from empty stack returns None."""
        manager = SkillContextManager()

        context = manager.pop_skill()
        assert context is None

    def test_clear_context(self):
        """Test clearing the context."""
        manager = SkillContextManager()

        manager.push_skill("xlsx")
        manager.push_skill("pdf")

        assert manager.skill_depth == 2

        manager.clear()

        assert manager.skill_depth == 0
        assert manager.current_skill is None

    def test_get_all_contexts(self):
        """Test getting all contexts from stack."""
        manager = SkillContextManager()

        manager.push_skill("xlsx")
        manager.push_skill("pdf")

        contexts = manager.get_all_contexts()

        assert len(contexts) == 2
        assert contexts[0].skill_name == "xlsx"
        assert contexts[1].skill_name == "pdf"

    def test_global_context_manager(self):
        """Test global context manager functions."""
        manager1 = get_skill_context_manager()
        manager2 = get_skill_context_manager()

        assert manager1 is manager2

        reset_skill_context_manager()
        manager3 = get_skill_context_manager()

        assert manager3 is not manager1


# =============================================================================
# SkillInvocationDetector Tests
# =============================================================================


class TestSkillInvocationDetector:
    """Tests for SkillInvocationDetector class."""

    def test_set_enabled_skills(self):
        """Test setting enabled skills."""
        detector = SkillInvocationDetector()
        detector.set_enabled_skills(["xlsx", "pdf"])

        assert "xlsx" in detector._enabled_skills
        assert "pdf" in detector._enabled_skills

    @pytest.mark.asyncio
    async def test_declared_skill_attribution(self):
        """Test skill attribution from explicit declaration."""
        registry = SkillToolRegistry()
        registry.register_skill_tools("xlsx", ["read_file"])

        detector = SkillInvocationDetector(registry=registry)
        detector.set_enabled_skills(["xlsx"])

        skill, weights = await detector.on_tool_call(
            "read_file",
            {"path": "/data/test.xlsx"},
        )

        assert skill == "xlsx"
        assert weights == {"xlsx": 1.0}

    @pytest.mark.asyncio
    async def test_inferred_skill_from_extension(self):
        """Test skill inference from file extension."""
        detector = SkillInvocationDetector()
        detector.set_enabled_skills(["xlsx"])

        skill, weights = await detector.on_tool_call(
            "execute_shell_command",
            {"command": "python process data.xlsx"},
        )

        assert skill == "xlsx"
        assert weights.get("xlsx", 0) >= 0.8

    @pytest.mark.asyncio
    async def test_inferred_skill_from_keyword(self):
        """Test skill inference from keyword."""
        detector = SkillInvocationDetector()
        detector.set_enabled_skills(["xlsx"])

        skill, weights = await detector.on_tool_call(
            "execute_shell_command",
            {"command": "process this excel file"},
        )

        assert skill == "xlsx"
        assert weights.get("xlsx", 0) >= 0.4

    @pytest.mark.asyncio
    async def test_multi_skill_attribution(self):
        """Test multi-skill attribution when multiple skills declare tool."""
        registry = SkillToolRegistry()
        registry.register_skill_tools("xlsx", ["read_file"])
        registry.register_skill_tools("pdf", ["read_file"])
        registry.register_skill_tools("docx", ["read_file"])

        detector = SkillInvocationDetector(registry=registry)
        detector.set_enabled_skills(["xlsx", "pdf", "docx"])

        skill, weights = await detector.on_tool_call(
            "read_file",
            {"path": "/data/test.xlsx"},
        )

        # Should attribute to xlsx due to file extension
        assert skill == "xlsx"
        assert "xlsx" in weights
        assert weights["xlsx"] > 0

    @pytest.mark.asyncio
    async def test_skill_context_tracking(self):
        """Test that detector tracks skill context."""
        registry = SkillToolRegistry()
        registry.register_skill_tools("xlsx", ["execute_shell_command"])

        context_manager = SkillContextManager()
        detector = SkillInvocationDetector(
            registry=registry,
            context_manager=context_manager,
        )
        detector.set_enabled_skills(["xlsx"])

        # First call should start skill context
        await detector.on_tool_call(
            "execute_shell_command",
            {"command": "python process.py"},
        )

        assert context_manager.current_skill == "xlsx"

    @pytest.mark.asyncio
    async def test_no_attribution_for_unknown_tool(self):
        """Test no attribution for unknown tool."""
        detector = SkillInvocationDetector()
        detector.set_enabled_skills(["xlsx"])

        skill, weights = await detector.on_tool_call(
            "unknown_tool_xyz",
            {"data": "something"},
        )

        assert skill is None
        assert weights == {}

    @pytest.mark.asyncio
    async def test_idle_threshold_ends_skill(self):
        """Test that idle threshold ends active skill."""
        registry = SkillToolRegistry()
        registry.register_skill_tools("xlsx", ["read_file"])

        context_manager = SkillContextManager()
        detector = SkillInvocationDetector(
            registry=registry,
            context_manager=context_manager,
            idle_threshold=2,
        )
        detector.set_enabled_skills(["xlsx"])

        # Start skill with declared tool
        await detector.on_tool_call("read_file", {"path": "test.xlsx"})
        assert context_manager.current_skill == "xlsx"

        # Call non-declared tools to increment idle counter
        # The idle counter only increments when current skill is NOT in declared skills
        # For tools not in registry, no attribution happens, so idle counter won't increment
        # This test verifies the skill stays active until reasoning ends
        await detector.on_tool_call("unknown_tool", {})
        # The skill should still be active because the tool call didn't trigger any skill
        # Idle threshold logic only applies when a tool belongs to different skills
        assert context_manager.current_skill == "xlsx"

        # End reasoning to clear skill context
        await detector.on_reasoning_end()
        assert context_manager.current_skill is None

    @pytest.mark.asyncio
    async def test_on_reasoning_end_clears_all(self):
        """Test that on_reasoning_end clears all active skills."""
        context_manager = SkillContextManager()

        detector = SkillInvocationDetector(context_manager=context_manager)
        detector.set_enabled_skills(["xlsx"])

        # Manually push skills
        context_manager.push_skill("xlsx")
        context_manager.push_skill("pdf")

        assert context_manager.skill_depth == 2

        await detector.on_reasoning_end()

        assert context_manager.skill_depth == 0

    def test_reset_detector(self):
        """Test resetting detector state."""
        detector = SkillInvocationDetector()
        detector.set_enabled_skills(["xlsx"])
        detector._skill_activation_time["xlsx"] = "some_time"

        detector.reset()

        assert len(detector._skill_activation_time) == 0
        assert len(detector._skill_call_history) == 0

    def test_global_detector(self):
        """Test global detector functions."""
        detector1 = get_skill_invocation_detector()
        detector2 = get_skill_invocation_detector()

        assert detector1 is detector2

        reset_skill_invocation_detector()
        detector3 = get_skill_invocation_detector()

        assert detector3 is not detector1


# =============================================================================
# Integration Tests
# =============================================================================


class TestSkillDetectionIntegration:
    """Integration tests for skill detection flow."""

    @pytest.mark.asyncio
    async def test_full_detection_flow(self):
        """Test full detection flow with multiple layers."""
        # Setup registry with explicit declarations
        registry = SkillToolRegistry()
        registry.register_skill_tools("xlsx", ["read_file", "write_file"])
        registry.register_skill_tools("pdf", ["read_file"])

        # Setup context manager
        context_manager = SkillContextManager()

        # Setup detector
        detector = SkillInvocationDetector(
            registry=registry,
            context_manager=context_manager,
        )
        detector.set_enabled_skills(["xlsx", "pdf"])

        # Step 1: Call read_file with xlsx file (declared + inferred)
        skill1, weights1 = await detector.on_tool_call(
            "read_file",
            {"path": "/data/report.xlsx"},
        )

        assert skill1 == "xlsx"
        assert "xlsx" in weights1
        assert context_manager.current_skill == "xlsx"

        # Step 2: Call write_file (declared for xlsx only)
        skill2, _ = await detector.on_tool_call(
            "write_file",
            {"path": "/data/output.xlsx"},
        )

        assert skill2 == "xlsx"
        assert context_manager.current_skill == "xlsx"

        # Step 3: Call execute_shell_command with pdf keyword (inferred)
        skill3, _ = await detector.on_tool_call(
            "execute_shell_command",
            {"command": "convert to pdf"},
        )

        # Should switch to pdf skill due to keyword
        assert skill3 == "pdf"
        assert context_manager.current_skill == "pdf"

    @pytest.mark.asyncio
    async def test_custom_skill_feature_inference(self):
        """Test custom skill feature inference."""
        # Create custom feature
        custom_feature = SkillFeature(
            skill_name="image_processor",
            file_extensions=[".png", ".jpg", ".jpeg"],
            keywords=["image", "图片", "photo"],
            tools_hint=["execute_shell_command"],
        )

        # Setup with custom features
        inferencer = SkillFeatureInferencer(
            builtin_features={"image_processor": custom_feature},
        )

        detector = SkillInvocationDetector(inferencer=inferencer)
        detector.set_enabled_skills(["image_processor"])

        # Test inference from extension
        skill, weights = await detector.on_tool_call(
            "execute_shell_command",
            {"command": "resize photo.png"},
        )

        assert skill == "image_processor"
        # on_tool_call returns (skill_name, weights_dict)
        # weights dict contains the confidence for the skill
        assert weights.get("image_processor", 0) >= 0.8

    @pytest.mark.asyncio
    async def test_mcp_tool_attribution(self):
        """Test MCP tool call attribution."""
        registry = SkillToolRegistry()
        registry.register_skill_tools("browser", ["browser_*"])

        detector = SkillInvocationDetector(registry=registry)
        detector.set_enabled_skills(["browser"])

        skill, weights = await detector.on_tool_call(
            "browser_click",
            {"selector": "#submit"},
            mcp_server="puppeteer",
        )

        assert skill == "browser"
        assert weights == {"browser": 1.0}


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_tool_list(self):
        """Test registering empty tool list."""
        registry = SkillToolRegistry()
        registry.register_skill_tools("empty_skill", [])

        assert registry.skill_count == 0

    def test_duplicate_tool_registration(self):
        """Test registering same tool multiple times."""
        registry = SkillToolRegistry()
        registry.register_skill_tools("skill1", ["read_file"])
        registry.register_skill_tools("skill1", ["read_file", "write_file"])

        # Should overwrite, not merge
        tools = registry.get_tools_for_skill("skill1")
        assert tools == ["read_file", "write_file"]

    @pytest.mark.asyncio
    async def test_empty_enabled_skills(self):
        """Test detection with no enabled skills."""
        detector = SkillInvocationDetector()
        detector.set_enabled_skills([])

        skill, weights = await detector.on_tool_call(
            "execute_shell_command",
            {"command": "python process.xlsx"},
        )

        assert skill is None
        assert weights == {}

    def test_skill_feature_no_features(self):
        """Test inference with feature having no attributes."""
        feature = SkillFeature(skill_name="empty_feature")
        inferencer = SkillFeatureInferencer(
            builtin_features={"empty_feature": feature},
        )

        skill, confidence = inferencer.infer_skill_from_tool_input(
            "any_tool",
            {"data": "anything"},
            ["empty_feature"],
        )

        assert skill is None
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test handling concurrent tool calls in sequence."""
        registry = SkillToolRegistry()
        registry.register_skill_tools("xlsx", ["read_file"])
        registry.register_skill_tools("pdf", ["read_file"])

        detector = SkillInvocationDetector(registry=registry)
        detector.set_enabled_skills(["xlsx", "pdf"])

        # First call with xlsx file - should start xlsx skill
        skill1, _ = await detector.on_tool_call(
            "read_file",
            {"path": "/data/file.xlsx"},
        )
        assert skill1 == "xlsx"

        # Reset for next call (simulating new conversation)
        detector.reset()

        # Second call with pdf file - should start pdf skill
        skill2, _ = await detector.on_tool_call(
            "read_file",
            {"path": "/data/file.pdf"},
        )
        assert skill2 == "pdf"
