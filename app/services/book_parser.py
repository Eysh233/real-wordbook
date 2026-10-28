"""单词书 Markdown 解析器（RW-SPEC-002 v1）。

支持两种写法：
1) 固定列序表格：| 编号 | 单词 | 音标 | 词性 | 中文 | 例句 | 例句中文 | 标签 | 备注 |
2) 块格式：### 0001 word  +  - 音标: /əˈbændən/ ...
返回 ParseResult，错误不抛异常，交给 UI 呈现。
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..models import Book, BookWord

COLUMNS = ["编号", "单词", "音标", "词性", "中文", "例句", "例句中文", "标签", "备注"]
REQUIRED = ["编号", "单词", "词性", "中文"]
FILE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}\.md$")

_ALIASES = {
    "编号": ["编号", "no", "id", "index"],
    "单词": ["单词", "word", "英文"],
    "音标": ["音标", "phonetic", "ipa"],
    "词性": ["词性", "pos", "part of speech"],
    "中文": ["中文", "释义", "meaning", "meaning_cn", "中文含义"],
    "例句": ["例句", "example", "sentence"],
    "例句中文": ["例句中文", "例句翻译", "example_cn"],
    "标签": ["标签", "tag", "tags"],
    "备注": ["备注", "note", "notes"],
}


@dataclass
class ParseResult:
    meta: Dict[str, Any] = field(default_factory=dict)
    words: List[BookWord] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.words) and not [e for e in self.errors if e.get("fatal")]


def _strip_cell(text: str) -> str:
    text = text.strip()
    if text.startswith("`") and text.endswith("`") and len(text) > 1:
        text = text[1:-1]
    return text.strip()


def _split_row(line: str) -> List[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    sentinel = "\x00"
    body = body.replace("\\|", sentinel)
    cells = [cell.replace(sentinel, "|") for cell in body.split("|")]
    return [_strip_cell(cell) for cell in cells]


def _is_separator(cells: List[str]) -> bool:
    if not cells:
        return False
    for cell in cells:
        if not re.match(r"^:?-{2,}:?$", cell.replace(" ", "")):
            return False
    return True


def _parse_front_matter(lines: List[str]) -> Tuple[Dict[str, Any], int]:
    """解析文件头 `---` YAML 子集，返回 (meta, 正文起始行号)。"""
    meta: Dict[str, Any] = {}
    if not lines or lines[0].strip() != "---":
        return meta, 0
    end = -1
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            end = index
            break
    if end < 0:
        return meta, 0
    current_list = None
    for raw in lines[1:end]:
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.lstrip().startswith("- "):
            value = _strip_cell(line.lstrip()[2:])
            if current_list is not None:
                current_list.append(value)
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = _strip_cell(value)
            if not value:
                meta[key] = []
                current_list = meta[key]
            elif value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                meta[key] = [_strip_cell(v) for v in inner.split(",") if v.strip()]
                current_list = None
            else:
                meta[key] = value.strip("\"'")
                current_list = None
    return meta, end + 1


def _column_index(header: List[str]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    lowered = [h.lower() for h in header]
    for canonical, aliases in _ALIASES.items():
        for alias in aliases:
            if alias.lower() in lowered:
                mapping[canonical] = lowered.index(alias.lower())
                break
    return mapping


def _clean_no(raw: str, fallback: int) -> str:
    digits = re.sub(r"[^0-9]", "", raw or "")
    if not digits:
        return "%04d" % fallback
    return digits.zfill(4)[-6:]


def _split_examples(text: str) -> List[Dict[str, str]]:
    """`He left. 他走了。<br>...` → [{en, cn}]，用 <br> 或 `||` 分隔。"""
    if not text:
        return []
    items: List[Dict[str, str]] = []
    for piece in re.split(r"<br\s*/?>|\|\|", text):
        piece = piece.strip()
        if not piece:
            continue
        match = re.search(r"[\u4e00-\u9fff]", piece)
        if match and match.start() > 0:
            items.append({"en": piece[:match.start()].strip(), "cn": piece[match.start():].strip()})
        else:
            items.append({"en": piece, "cn": ""})
    return items


def _parse_table(lines: List[str], start: int, result: ParseResult) -> None:
    header_at = -1
    for index in range(start, len(lines)):
        if lines[index].lstrip().startswith("|"):
            header_at = index
            break
    if header_at < 0:
        result.errors.append({"line": start + 1, "msg": "未找到单词表格", "fatal": True})
        return
    header = _split_row(lines[header_at])
    index_map = _column_index(header)
    missing = [name for name in REQUIRED if name not in index_map]
    if missing:
        result.errors.append(
            {"line": header_at + 1, "msg": "表头缺少列：%s" % "、".join(missing), "fatal": True}
        )
        return
    seen = set()
    for offset, raw in enumerate(lines[header_at + 1:], start=header_at + 2):
        if not raw.strip():
            continue
        if raw.lstrip().startswith("#"):
            break
        if not raw.lstrip().startswith("|"):
            continue
        cells = _split_row(raw)
        if _is_separator(cells):
            continue
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))

        def cell(name: str) -> str:
            position = index_map.get(name)
            if position is None or position >= len(cells):
                return ""
            return cells[position]

        word = cell("单词")
        meaning = cell("中文")
        no = _clean_no(cell("编号"), len(result.words) + 1)
        if not word or not meaning:
            result.errors.append({"line": offset, "msg": "第 %d 行缺少单词或中文" % offset})
            continue
        if no in seen:
            result.errors.append({"line": offset, "msg": "编号重复：%s" % no})
            continue
        seen.add(no)
        tags = [t.strip() for t in re.split(r"[,;/、]", cell("标签")) if t.strip()]
        examples = _split_examples(cell("例句"))
        example_cn = _split_examples(cell("例句中文"))
        for i, cn in enumerate(example_cn):
            if i < len(examples) and cn.get("en"):
                examples[i]["cn"] = cn["en"]
            elif cn.get("en") and not cn.get("cn"):
                examples.append({"en": "", "cn": cn["en"]})
        result.words.append(
            BookWord(
                no=no,
                word=word,
                meaning_cn=meaning,
                phonetic=cell("音标"),
                pos=cell("词性"),
                tags=tags,
                note=cell("备注"),
                examples=examples,
            )
        )


def _parse_blocks(lines: List[str], start: int, result: ParseResult) -> None:
    seen = set()
    current: Optional[Dict[str, Any]] = None
    line_no = start

    def flush() -> None:
        if not current:
            return
        word = current.get("word", "").strip()
        meaning = current.get("中文", "").strip() or current.get("meaning", "").strip()
        no = _clean_no(current.get("no", ""), len(result.words) + 1)
        if not word or not meaning:
            result.errors.append({"line": current.get("_line", line_no), "msg": "块缺少单词或中文"})
            return
        if no in seen:
            result.errors.append({"line": current.get("_line", line_no), "msg": "编号重复：%s" % no})
            return
        seen.add(no)
        tags = [t.strip() for t in re.split(r"[,;/、]", current.get("标签", "")) if t.strip()]
        examples = _split_examples(current.get("例句", ""))
        result.words.append(
            BookWord(
                no=no,
                word=word,
                meaning_cn=meaning,
                phonetic=current.get("音标", ""),
                pos=current.get("词性", ""),
                tags=tags,
                note=current.get("备注", ""),
                examples=examples,
            )
        )

    for raw in lines[start:]:
        line = raw.rstrip()
        line_no += 1
        match = re.match(r"^#{2,4}\s*(\d{1,6})?[\s.、:-]*(.+?)\s*$", line)
        if match:
            flush()
            current = {"no": match.group(1) or "", "word": match.group(2).strip(), "_line": line_no}
            continue
        if current is None:
            continue
        item = re.match(r"^\s*[-*]\s*([^:：]+)[:：]\s*(.*)$", line)
        if item:
            key = item.group(1).strip().lower()
            value = _strip_cell(item.group(2))
            canonical = key
            for name, aliases in _ALIASES.items():
                if key == name.lower() or key in [a.lower() for a in aliases]:
                    canonical = name
                    break
            current[canonical] = value
            continue
        if line.strip().startswith("例句"):
            current.setdefault("例句", "")
    flush()


def parse_markdown(text: str, fallback_title: str = "未命名单词书") -> ParseResult:
    result = ParseResult()
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    meta, body_start = _parse_front_matter(lines)
    result.meta = meta
    if not meta.get("title"):
        meta["title"] = fallback_title
    if "book_id" not in meta:
        slug = re.sub(r"[^a-z0-9]+", "-", str(meta["title"]).lower()).strip("-")
        meta["book_id"] = (slug or "book")[:48]

    if any(line.lstrip().startswith("|") for line in lines[body_start:]):
        _parse_table(lines, body_start, result)
    else:
        _parse_blocks(lines, body_start, result)

    if not result.words:
        result.errors.append({"line": 1, "msg": "没有解析到任何单词", "fatal": True})
    word_count = meta.get("word_count")
    if word_count:
        try:
            declared = int(str(word_count))
            if declared != len(result.words):
                result.errors.append(
                    {"line": 1, "msg": "声明 %d 词，实际解析 %d 词" % (declared, len(result.words))}
                )
        except ValueError:
            pass
    return result


def parse_file(path: Path) -> ParseResult:
    path = Path(path)
    if not FILE_RE.match(path.name):
        return ParseResult(
            errors=[{"line": 1, "msg": "文件名需匹配 %s" % FILE_RE.pattern, "fatal": True}]
        )
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return ParseResult(errors=[{"line": 1, "msg": "读取失败：%s" % exc, "fatal": True}])
    result = parse_markdown(text, fallback_title=path.stem)
    if not result.meta.get("book_id"):
        result.meta["book_id"] = path.stem
    return result


def build_book(path: Path, result: ParseResult, imported_at: str) -> Book:
    meta = result.meta or {}
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,;/、]", tags) if t.strip()]
    return Book(
        book_id=str(meta.get("book_id") or Path(path).stem),
        title=str(meta.get("title") or Path(path).stem),
        file=Path(path).name,
        author=str(meta.get("author", "")),
        level=str(meta.get("level", "")),
        tags=[str(t) for t in tags],
        description=str(meta.get("description", "")),
        version=str(meta.get("version", "1")),
        imported_at=imported_at,
        words=result.words,
    )


def to_markdown(book: Book) -> str:
    """导出为规范表格（F6 反向能力，也方便用户二次编辑）。"""
    lines = [
        "---",
        "title: %s" % book.title,
        "book_id: %s" % book.book_id,
        "version: %s" % (book.version or "1"),
        "word_count: %d" % len(book.words),
        "author: %s" % book.author,
        "level: %s" % book.level,
        "tags: [%s]" % ", ".join(book.tags),
        "---",
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "| " + " | ".join(["---"] * len(COLUMNS)) + " |",
    ]
    for item in book.words:
        examples = "<br>".join(
            ("%s %s" % (e.get("en", ""), e.get("cn", ""))).strip() for e in item.examples
        )
        cells = [
            item.no,
            item.word,
            item.phonetic,
            item.pos,
            item.meaning_cn,
            examples,
            "",
            ",".join(item.tags),
            item.note,
        ]
        lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    return "\n".join(lines) + "\n"
