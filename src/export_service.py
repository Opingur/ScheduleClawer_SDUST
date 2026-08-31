from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from src.export_xlsx import export_schedule


SOURCE_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", SOURCE_ROOT))
USER_ROOT = (
    SOURCE_ROOT
    if not getattr(sys, "frozen", False)
    else Path(os.environ.get("LOCALAPPDATA", SOURCE_ROOT)) / "课表导出器"
)
EXPORT_DIR = USER_ROOT / "exports"
PROFILE_DIR = USER_ROOT / "browser_profile"


def run_exporter(payload: dict, output: Path) -> None:
    """使用随 Python 打包的 Excel 引擎，终端用户无需安装 Node.js。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    export_schedule(payload, output)


def load_demo_payload() -> dict:
    return json.loads(
        (BUNDLE_ROOT / "src" / "demo_schedule.json").read_text(encoding="utf-8")
    )