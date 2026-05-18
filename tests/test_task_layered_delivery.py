"""Integration-style test for layered project delivery after task submission."""

from __future__ import annotations

from pathlib import Path

import src.app.main as app_main


class _DummyLogger:
    def close(self) -> None:
        return None


class _DummyKnowledgeManager:
    def initialize_default_knowledge(self) -> None:
        return None


def _patch_run_task_dependencies(monkeypatch, output_dir):
    monkeypatch.setattr(app_main, "patch_autogen_streaming_token_count", lambda: None)
    monkeypatch.setattr(app_main, "MongoConversationLogger", lambda: _DummyLogger())
    monkeypatch.setattr(
        app_main,
        "enable_streaming_with_mongo_logging",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        app_main, "RAGKnowledgeManager", lambda: _DummyKnowledgeManager()
    )
    monkeypatch.setattr(
        app_main,
        "build_rag_agents",
        lambda km: {role: object() for role in app_main.ROLE_ORDER},
    )
    monkeypatch.setattr(
        app_main,
        "create_delivery_workspace",
        lambda task, root: ("demo_project", output_dir),
    )
    monkeypatch.setattr(
        app_main, "print_delivery_artifacts", lambda *args, **kwargs: None
    )


def test_run_task_creates_layered_project_style_after_user_task(monkeypatch, tmp_path):
    output_dir = tmp_path / "delivery"
    output_dir.mkdir(parents=True, exist_ok=True)

    _patch_run_task_dependencies(monkeypatch, output_dir)

    dummy_groupchat = type("DummyGroupChat", (), {"messages": []})()

    class _DummyUserProxy:
        def initiate_chat(self, manager, message):
            dummy_groupchat.messages.append({"content": "mock-chat-content"})

    monkeypatch.setattr(
        app_main, "create_user_proxy", lambda out_dir: _DummyUserProxy()
    )
    monkeypatch.setattr(
        app_main,
        "build_group_chat",
        lambda agents, user_proxy: (dummy_groupchat, object()),
    )

    def _fake_materialize_code_files(messages, out_dir, project_tag, **kwargs):
        files = {
            "backend/api/user_router.py": "def route_user():\n    return {'ok': True}\n",
            "backend/services/user_service.py": "def create_user():\n    return 1\n",
            "backend/models/user_model.py": "class User:\n    pass\n",
            "backend/repositories/user_repository.py": "def save_user(user):\n    return True\n",
            "tests/test_user_service.py": "def test_create_user():\n    assert create_user() == 1\n",
            "README.md": "# Demo Project\n",
        }

        created = []
        for rel_path, content in files.items():
            file_path = out_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            created.append(rel_path)
        return created

    monkeypatch.setattr(
        app_main, "materialize_code_files", _fake_materialize_code_files
    )

    result = app_main.run_task("开发一个用户管理系统")

    assert Path(result["output_dir"]) == output_dir
    assert result["architecture_validation"]["is_valid"] is True
    assert result["architecture_validation"]["retry_count"] == 0

    detected_layers = result["architecture_validation"]["detected_layers"]
    assert detected_layers["presentation"]
    assert detected_layers["application"]
    assert detected_layers["domain"]
    assert detected_layers["data"]


def test_run_task_can_generate_layered_files_from_chat_messages(monkeypatch, tmp_path):
    output_dir = tmp_path / "delivery_from_chat"
    output_dir.mkdir(parents=True, exist_ok=True)

    _patch_run_task_dependencies(monkeypatch, output_dir)
    monkeypatch.setattr(app_main, "MAX_ARCHITECTURE_RETRY", 1)

    dummy_groupchat = type("DummyGroupChat", (), {"messages": []})()

    first_round_message = {
        "content": """filename: main.py
```python
def run():
    return 'single-file'
```
"""
    }

    layered_round_messages = [
        {
            "content": """filename: backend/api/user_router.py
```python
def route_user():
    return {"ok": True}
```
"""
        },
        {
            "content": """filename: backend/services/user_service.py
```python
def create_user(name: str):
    return {"name": name}
```
"""
        },
        {
            "content": """filename: backend/models/user_model.py
```python
class User:
    def __init__(self, name: str):
        self.name = name
```
"""
        },
        {
            "content": """filename: backend/repositories/user_repository.py
```python
def save_user(user):
    return True
```
"""
        },
        {
            "content": """filename: tests/test_user_service.py
```python
def test_create_user():
    assert create_user("a")["name"] == "a"
```
"""
        },
        {
            "content": """filename: README.md
```markdown
# Demo
```
"""
        },
    ]

    class _DummyUserProxy:
        def __init__(self):
            self.calls = 0

        def initiate_chat(self, manager, message):
            self.calls += 1
            if self.calls == 1:
                dummy_groupchat.messages.append(first_round_message)
            else:
                dummy_groupchat.messages.extend(layered_round_messages)

    monkeypatch.setattr(
        app_main, "create_user_proxy", lambda out_dir: _DummyUserProxy()
    )
    monkeypatch.setattr(
        app_main,
        "build_group_chat",
        lambda agents, user_proxy: (dummy_groupchat, object()),
    )

    result = app_main.run_task("开发一个用户管理系统")

    assert result["architecture_validation"]["is_valid"] is True
    assert result["architecture_validation"]["retry_count"] == 1
    assert (output_dir / "backend" / "api" / "user_router.py").is_file()
    assert (output_dir / "backend" / "services" / "user_service.py").is_file()
    assert (output_dir / "backend" / "models" / "user_model.py").is_file()
    assert (output_dir / "backend" / "repositories" / "user_repository.py").is_file()
