"""文件读写：JSON 原子写、.bak 回退、损坏保护。"""
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from . import config


def read_json(path: Path, default: Any = None) -> Any:
    """读取 JSON；失败时尝试 .bak，再失败返回 default（不静默清空磁盘）。"""
    for candidate in (Path(path), Path(str(path) + ".bak")):
        if not candidate.exists():
            continue
        try:
            with candidate.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (ValueError, OSError):
            continue
    return default


def write_json_atomic(path: Path, data: Any) -> None:
    """tmp → fsync → os.replace；覆盖前保留一份 .bak。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            shutil.copy2(str(path), str(path) + ".bak")
        except OSError:
            pass
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def read_text(path: Path) -> Optional[str]:
    try:
        with Path(path).open("r", encoding="utf-8-sig") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
