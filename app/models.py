"""数据模型：Word / Book / BookWord / Settings。只依赖标准库。"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _s(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


@dataclass
class Word:
    """我的单词本里的一条登记记录。"""

    id: str
    word: str
    meaning_cn: str
    phonetic: str = ""
    pos: str = ""
    root: str = ""
    root_cn: str = ""
    meaning_en: str = ""
    note: str = ""
    tags: List[str] = field(default_factory=list)
    highlight: bool = False
    strike: bool = False
    weight: int = 3
    date_added: str = ""
    created_at: str = ""
    source: str = "manual"
    ai: Optional[Dict[str, Any]] = None

    # 记忆曲线（F1）
    due: str = ""
    interval: int = 0
    ease: float = 2.5
    seen_count: int = 0
    wrong_count: int = 0
    last_quiz_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "word": self.word,
            "meaning_cn": self.meaning_cn,
            "phonetic": self.phonetic,
            "pos": self.pos,
            "root": self.root,
            "root_cn": self.root_cn,
            "meaning_en": self.meaning_en,
            "note": self.note,
            "tags": list(self.tags),
            "highlight": self.highlight,
            "strike": self.strike,
            "weight": self.weight,
            "date_added": self.date_added,
            "created_at": self.created_at,
            "source": self.source,
            "ai": self.ai,
            "due": self.due,
            "interval": self.interval,
            "ease": self.ease,
            "seen_count": self.seen_count,
            "wrong_count": self.wrong_count,
            "last_quiz_at": self.last_quiz_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Word":
        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        try:
            weight = int(data.get("weight", 3))
        except (TypeError, ValueError):
            weight = 3
        try:
            interval = int(data.get("interval", 0) or 0)
        except (TypeError, ValueError):
            interval = 0
        try:
            ease = float(data.get("ease", 2.5) or 2.5)
        except (TypeError, ValueError):
            ease = 2.5
        ai = data.get("ai")
        return cls(
            id=_s(data.get("id")),
            word=_s(data.get("word")),
            meaning_cn=_s(data.get("meaning_cn")),
            phonetic=_s(data.get("phonetic")),
            pos=_s(data.get("pos")),
            root=_s(data.get("root")),
            root_cn=_s(data.get("root_cn")),
            meaning_en=_s(data.get("meaning_en")),
            note=_s(data.get("note")),
            tags=[str(t) for t in tags],
            highlight=bool(data.get("highlight")),
            strike=bool(data.get("strike")),
            weight=max(1, min(10, weight)),
            date_added=_s(data.get("date_added")),
            created_at=_s(data.get("created_at")),
            source=_s(data.get("source"), "manual"),
            ai=ai if isinstance(ai, dict) else None,
            due=_s(data.get("due")),
            interval=interval,
            ease=ease,
            seen_count=int(data.get("seen_count", 0) or 0),
            wrong_count=int(data.get("wrong_count", 0) or 0),
            last_quiz_at=_s(data.get("last_quiz_at")),
        )


@dataclass
class BookWord:
    """单词书中的一条词（只读缓存）。"""

    no: str
    word: str
    meaning_cn: str
    phonetic: str = ""
    pos: str = ""
    tags: List[str] = field(default_factory=list)
    note: str = ""
    examples: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "no": self.no,
            "word": self.word,
            "meaning_cn": self.meaning_cn,
            "phonetic": self.phonetic,
            "pos": self.pos,
            "tags": list(self.tags),
            "note": self.note,
            "examples": list(self.examples),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BookWord":
        examples = data.get("examples") or []
        if not isinstance(examples, list):
            examples = []
        clean = []
        for item in examples:
            if not isinstance(item, dict):
                continue
            clean.append({"en": _s(item.get("en")), "cn": _s(item.get("cn"))})
        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        return cls(
            no=str(data.get("no", "")),
            word=_s(data.get("word")),
            meaning_cn=_s(data.get("meaning_cn")),
            phonetic=_s(data.get("phonetic")),
            pos=_s(data.get("pos")),
            tags=[str(t) for t in tags],
            note=_s(data.get("note")),
            examples=clean,
        )


@dataclass
class Book:
    """一本已导入的单词书。"""

    book_id: str
    title: str
    file: str
    author: str = ""
    level: str = ""
    tags: List[str] = field(default_factory=list)
    description: str = ""
    version: str = ""
    imported_at: str = ""
    words: List[BookWord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "file": self.file,
            "author": self.author,
            "level": self.level,
            "tags": list(self.tags),
            "description": self.description,
            "version": self.version,
            "imported_at": self.imported_at,
            "words": [w.to_dict() for w in self.words],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Book":
        words = data.get("words") or []
        tags = data.get("tags") or []
        return cls(
            book_id=str(data.get("book_id", "")),
            title=_s(data.get("title")),
            file=_s(data.get("file")),
            author=_s(data.get("author")),
            level=_s(data.get("level")),
            tags=[str(t) for t in tags] if isinstance(tags, list) else [],
            description=_s(data.get("description")),
            version=_s(data.get("version")),
            imported_at=_s(data.get("imported_at")),
            words=[BookWord.from_dict(w) for w in words if isinstance(w, dict)],
        )


@dataclass
class Settings:
    """用户偏好（不含密钥）。"""

    display_mode: str = "both"
    theme: str = "paper"
    reduced_motion: bool = False
    font_scale: float = 1.0
    ai_model: str = "deepseek-flash"
    ai_effort: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "display_mode": self.display_mode,
            "theme": self.theme,
            "reduced_motion": self.reduced_motion,
            "font_scale": self.font_scale,
            "ai_model": self.ai_model,
            "ai_effort": self.ai_effort,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        try:
            scale = float(data.get("font_scale", 1.0) or 1.0)
        except (TypeError, ValueError):
            scale = 1.0
        return cls(
            display_mode=_s(data.get("display_mode"), "both"),
            theme=_s(data.get("theme"), "paper"),
            reduced_motion=bool(data.get("reduced_motion")),
            font_scale=max(0.85, min(1.4, scale)),
            ai_model=_s(data.get("ai_model"), "deepseek-flash"),
            ai_effort=_s(data.get("ai_effort"), "low"),
        )
