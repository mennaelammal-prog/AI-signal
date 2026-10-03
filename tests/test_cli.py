
from pathlib import Path

from signalforge.cli import _load_json


def test_load_json_accepts_utf8_bom(tmp_path: Path):
    path = tmp_path / "powershell.json"
    path.write_text('[{"ok": true}]', encoding="utf-8-sig")
    assert _load_json(path) == [{"ok": True}]
