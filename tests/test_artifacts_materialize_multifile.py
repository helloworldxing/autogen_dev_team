from pathlib import Path

from src.app.artifacts import materialize_code_files
from src.app.stack_policy import infer_stack_policy


def test_materialize_code_files_keeps_distinct_filenames_per_code_block(tmp_path: Path):
    output_dir = tmp_path / "delivery"
    output_dir.mkdir(parents=True, exist_ok=True)

    message = {
        "content": """filename: backend/controllers/student_controller.py
```python
def list_students():
    return []
```

filename: backend/services/student_service.py
```python
def create_student(name: str):
    return {"name": name}
```
"""
    }

    created = materialize_code_files([message], output_dir, "student_mgmt")

    assert "backend/controllers/student_controller.py" in created
    assert "backend/services/student_service.py" in created
    assert (
        output_dir / "backend" / "controllers" / "student_controller.py"
    ).read_text(encoding="utf-8").strip().startswith("def list_students")
    assert (
        output_dir / "backend" / "services" / "student_service.py"
    ).read_text(encoding="utf-8").strip().startswith("def create_student")


def test_materialize_uses_java_default_extension_when_task_is_java_backend(
    tmp_path: Path,
):
    output_dir = tmp_path / "java_delivery"
    output_dir.mkdir(parents=True, exist_ok=True)

    policy = infer_stack_policy("使用 Java Spring Boot 开发学生管理系统后端")
    message = {"content": "```java\npublic class StudentService {}\n```"}

    created = materialize_code_files(
        [message],
        output_dir,
        "student_java",
        default_code_extension=policy.default_code_extension,
        allowed_extensions=policy.allowed_extensions,
    )

    assert any(path.endswith(".java") for path in created)


def test_materialize_allows_xml_in_fullstack_policy(tmp_path: Path):
    output_dir = tmp_path / "fullstack_delivery"
    output_dir.mkdir(parents=True, exist_ok=True)

    policy = infer_stack_policy("做一个全栈学生管理系统，后端 Java，前端 Vue")
    message = {
        "content": """filename: backend/resources/mapper/StudentMapper.xml
```xml
<mapper namespace="StudentMapper"></mapper>
```
"""
    }

    created = materialize_code_files(
        [message],
        output_dir,
        "student_fullstack",
        default_code_extension=policy.default_code_extension,
        allowed_extensions=policy.allowed_extensions,
    )

    assert "backend/resources/mapper/StudentMapper.xml" in created
