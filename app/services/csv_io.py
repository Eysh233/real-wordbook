"""CSV 导入导出（F6）。导入只写「我的单词本」，不碰单词书。"""
import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..models import Word

IMPORT_HEADERS = ["word", "meaning_cn", "phonetic", "pos", "tags", "note"]
HEADER_ALIASES = {
    "word": ["word", "单词", "英文", "english"],
    "meaning_cn": ["meaning_cn", "中文", "释义", "meaning", "中文含义"],
    "phonetic": ["phonetic", "音标", "ipa"],
    "pos": ["pos", "词性"],
    "tags": ["tags", "标签"],
    "note": ["note", "备注"],
}


def _pick(row: Dict[str, str], key: str) -> str:
    for alias in HEADER_ALIASES[key]:
        for header, value in row.items():
            if header and header.strip().lower() == alias.lower():
                return (value or "").strip()
    return ""


def import_csv(path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """返回 (待登记行, 错误信息)。行字段与 Word 构造兼容。"""
    rows: List[Dict[str, Any]] = []
    errors: List[str] = []
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        return [], ["读取失败：%s" % exc]
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        return [], ["无法识别文件编码（建议 UTF-8）"]
    delimiter = ","
    if text.count("\t") > text.count(",") * 2:
        delimiter = "\t"
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        return [], ["文件没有表头"]
    for line_no, row in enumerate(reader, start=2):
        word = _pick(row, "word")
        meaning = _pick(row, "meaning_cn")
        if not word and not meaning:
            continue
        if not word or not meaning:
            errors.append("第 %d 行缺少单词或中文" % line_no)
            continue
        tags = [t.strip() for t in (_pick(row, "tags") or "").replace("，", ",").split(",") if t.strip()]
        rows.append(
            {
                "word": word,
                "meaning_cn": meaning,
                "phonetic": _pick(row, "phonetic"),
                "pos": _pick(row, "pos"),
                "tags": tags,
                "note": _pick(row, "note"),
            }
        )
    return rows, errors


def export_csv(words: List[Word], path: Path) -> int:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["word", "meaning_cn", "phonetic", "pos", "tags", "weight", "date_added", "note"])
    for word in words:
        writer.writerow(
            [
                word.word,
                word.meaning_cn,
                word.phonetic,
                word.pos,
                ",".join(word.tags),
                word.weight,
                word.date_added,
                word.note,
            ]
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")
    return len(words)
