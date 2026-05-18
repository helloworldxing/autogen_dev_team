import json
from pathlib import Path

from src.app.stack_policy import infer_stack_policy


def test_infer_stack_policy_detects_java_fullstack_and_xml_support():
    policy = infer_stack_policy("开发一个全栈学生管理系统，后端使用 Java Spring Boot，前端 Vue")

    assert policy.stack_type == "fullstack"
    assert policy.backend_language == "java"
    assert ".java" in policy.allowed_extensions
    assert ".xml" in policy.allowed_extensions


def test_infer_stack_policy_defaults_to_python_backend():
    policy = infer_stack_policy("开发一个学生管理系统，包含增删改查和权限管理")

    assert policy.stack_type == "backend"
    assert policy.backend_language == "python"
    assert policy.default_code_extension == ".py"


def test_infer_stack_policy_uses_user_specified_backend_language_java():
    policy = infer_stack_policy("帮我做个学生管理系统，后端语言用java")

    assert policy.stack_type == "backend"
    assert policy.backend_language == "java"
    assert policy.default_code_extension == ".java"
    assert ".java" in policy.allowed_extensions
    assert ".py" not in policy.allowed_extensions


def test_infer_stack_policy_matches_java_spring_maven_profile():
    policy = infer_stack_policy("使用 Java Spring Boot + Maven 开发学生管理系统后端")

    assert policy.stack_type == "backend"
    assert policy.backend_language == "java"
    assert policy.default_code_extension == ".java"
    assert ".xml" in policy.allowed_extensions


def test_infer_stack_policy_supports_custom_rules_file(tmp_path: Path, monkeypatch):
    custom_rules = {
        "common_extensions": [".md"],
        "backend_extensions": {"python": [".py"], "go": [".go"]},
        "frontend_extensions": [".tsx"],
        "language_aliases": {"go": ["go", "golang"]},
        "profiles": [
            {
                "id": "go_backend",
                "priority": 300,
                "stack_type": "backend",
                "backend_language": "go",
                "frontend_language": "javascript",
                "default_code_extension": ".go",
                "keywords_any": ["go", "golang"],
                "guidance": "后端项目（Go 模板）。",
            }
        ],
    }
    rules_file = tmp_path / "stack_rules.json"
    rules_file.write_text(json.dumps(custom_rules, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("STACK_POLICY_RULES_PATH", str(rules_file))

    policy = infer_stack_policy("使用 Golang 开发后端")

    assert policy.backend_language == "go"
    assert policy.default_code_extension == ".go"
    assert policy.allowed_extensions == {".md", ".go"}
