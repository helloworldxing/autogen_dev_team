"""Tests for engineer anti-single-file prompt and layered-architecture guard."""

from __future__ import annotations

from src.agents.engineer import create_engineer_agent
from src.app.architecture_guard import validate_layered_architecture


def _get_engineer_system_message() -> str:
    agent = create_engineer_agent()
    message = getattr(agent, "system_message", "")
    if isinstance(message, str) and message.strip():
        return message

    # Fallback for autogen internals: _oai_system_message may be a list of message dicts.
    oai_system = getattr(agent, "_oai_system_message", [])
    if isinstance(oai_system, list) and oai_system:
        first = oai_system[0]
        if isinstance(first, dict):
            return str(first.get("content", ""))
    return ""


def test_engineer_prompt_contains_multi_file_constraints():
    system_message = _get_engineer_system_message()

    assert "You are working inside a multi-file software project." in system_message
    assert "Follow existing architecture patterns." in system_message
    assert "Prefer separation of concerns." in system_message
    assert "Do not collapse logic into single file." in system_message
    assert "先判断任务类型并选择结构模板（必须）" in system_message
    assert "后端项目最小模板示例" in system_message
    assert "前端项目最小模板示例" in system_message
    assert "全栈项目最小模板示例" in system_message


def test_architecture_guard_rejects_single_file_delivery():
    files = ["main.py", "README.md"]
    result = validate_layered_architecture(files)

    assert result.is_valid is False
    assert result.code_file_count == 1
    assert any("单文件" in reason or "分层" in reason for reason in result.reasons)


def test_architecture_guard_accepts_python_layered_convention():
    files = [
        "backend/api/user_router.py",
        "backend/services/user_service.py",
        "backend/models/user_model.py",
        "backend/repositories/user_repository.py",
        "tests/test_user_service.py",
        "README.md",
    ]

    result = validate_layered_architecture(files)

    assert result.primary_language == "python"
    assert result.is_valid is True
    assert result.detected_layers["presentation"]
    assert result.detected_layers["application"]
    assert result.detected_layers["domain"]
    assert result.detected_layers["data"]
