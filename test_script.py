import src.app.artifacts as art
from pathlib import Path

msg = {"content": "```python\nprint(1)\n```"}
print(art.materialize_code_files([msg], Path("test_out_script"), "test"))
