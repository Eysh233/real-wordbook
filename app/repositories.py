"""仓储层：唯一允许触碰磁盘数据的模块（UI 不得直接 open 文件）。"""
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config, storage
from .models import Book, BookWord, Settings, Word


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _today() -> str:
    return date.today().strftime(config.DATE_FMT)


class WordsRepo:
    """我的单词本。内存持有 + 显式 save()。"""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path or config.WORDS_FILE)
        self._words: List[Word] = []
        self.loaded_ok = True
        self.load()

    # ---------------------------------------------------------------- 读写
    def load(self) -> None:
        raw = storage.read_json(self.path, default=None)
        if raw is None:
            self._words = []
            return
        items = raw.get("words", []) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            self._words = []
            self.loaded_ok = False
            return
        self._words = [Word.from_dict(item) for item in items if isinstance(item, dict)]

    def save(self) -> None:
        storage.write_json_atomic(
            self.path,
            {"schema": 1, "updated_at": _now_iso(), "words": [w.to_dict() for w in self._words]},
        )

    def clear(self) -> int:
        """清空我的单词本，返回被删除的词数。"""
        removed = len(self._words)
        self._words = []
        self.save()
        return removed

    # ---------------------------------------------------------------- 查询
    def all(self) -> List[Word]:
        return list(self._words)

    def get(self, word_id: str) -> Optional[Word]:
        for word in self._words:
            if word.id == word_id:
                return word
        return None

    def find(self, text: str) -> Optional[Word]:
        key = (text or "").strip().lower()
        if not key:
            return None
        for word in self._words:
            if word.word.strip().lower() == key:
                return word
        return None

    def sorted_words(self) -> List[Word]:
        def key(item: Word):
            return (item.date_added or "0000-00-00", item.created_at or "")

        return sorted(self._words, key=key)

    def tags(self) -> List[str]:
        found = set()
        for word in self._words:
            for tag in word.tags:
                if tag:
                    found.add(tag)
        return sorted(found)

    def counts(self) -> Dict[str, int]:
        return {
            "total": len(self._words),
            "highlight": sum(1 for w in self._words if w.highlight),
            "strike": sum(1 for w in self._words if w.strike),
        }

    # ---------------------------------------------------------------- 变更
    def next_id(self) -> str:
        biggest = 0
        for word in self._words:
            m = re.match(r"w_(\d+)$", word.id or "")
            if m:
                biggest = max(biggest, int(m.group(1)))
        return "w_%06d" % (biggest + 1)

    def add(self, word: Word, save: bool = True) -> Word:
        if not word.id:
            word.id = self.next_id()
        if not word.date_added:
            word.date_added = _today()
        if not word.created_at:
            word.created_at = _now_iso()
        if not word.due:
            word.due = word.date_added
        self._words.append(word)
        if save:
            self.save()
        return word

    def update(self, word: Word, save: bool = True) -> None:
        for index, existing in enumerate(self._words):
            if existing.id == word.id:
                self._words[index] = word
                break
        if save:
            self.save()

    def delete(self, word_id: str, save: bool = True) -> bool:
        before = len(self._words)
        self._words = [w for w in self._words if w.id != word_id]
        changed = len(self._words) != before
        if changed and save:
            self.save()
        return changed


class SettingsRepo:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path or config.SETTINGS_FILE)
        self.settings = Settings.from_dict(storage.read_json(self.path, default={}) or {})

    def save(self) -> None:
        storage.write_json_atomic(self.path, self.settings.to_dict())


class SecretRepo:
    """API Key：用户目录，永不入库。环境变量优先。"""

    ENV_KEY = "DEEPSEEK_API_KEY"

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path or config.SECRET_FILE)
        self._data: Dict[str, Any] = storage.read_json(self.path, default={}) or {}
        if not isinstance(self._data, dict):
            self._data = {}

    @property
    def api_key(self) -> str:
        env = os.environ.get(self.ENV_KEY, "").strip()
        if env:
            return env
        return str(self._data.get("api_key", "") or "").strip()

    @property
    def from_env(self) -> bool:
        return bool(os.environ.get(self.ENV_KEY, "").strip())

    def save_key(self, key: str) -> None:
        self._data["api_key"] = (key or "").strip()
        self._data["updated_at"] = _now_iso()
        storage.write_json_atomic(self.path, self._data)

    @staticmethod
    def mask(key: str) -> str:
        if not key:
            return "未配置"
        if len(key) <= 8:
            return "sk-****"
        return "sk-****" + key[-4:]


class BooksRepo:
    """单词书缓存（data/books/*.json）。"""

    def __init__(self, cache_dir: Optional[Path] = None, book_dir: Optional[Path] = None) -> None:
        self.cache_dir = Path(cache_dir or config.BOOKS_CACHE_DIR)
        self.book_dir = Path(book_dir or config.STUDYBOOK_DIR)

    def cache_path(self, book_id: str) -> Path:
        return self.cache_dir / ("%s.json" % book_id)

    def list_books(self) -> List[Book]:
        books: List[Book] = []
        if not self.cache_dir.exists():
            return books
        for path in sorted(self.cache_dir.glob("*.json")):
            data = storage.read_json(path, default=None)
            if isinstance(data, dict) and data.get("book_id"):
                try:
                    books.append(Book.from_dict(data))
                except (TypeError, ValueError):
                    continue
        books.sort(key=lambda b: b.imported_at or "")
        return books

    def get(self, book_id: str) -> Optional[Book]:
        data = storage.read_json(self.cache_path(book_id), default=None)
        if isinstance(data, dict) and data.get("book_id"):
            return Book.from_dict(data)
        return None

    def save(self, book: Book) -> None:
        storage.write_json_atomic(self.cache_path(book.book_id), book.to_dict())

    def delete(self, book_id: str) -> None:
        path = self.cache_path(book_id)
        for candidate in (path, Path(str(path) + ".bak")):
            if candidate.exists():
                try:
                    candidate.unlink()
                except OSError:
                    pass


class RecordsRepo:
    """单词书记忆进度（StudyRecord/{book_id}.json）。"""

    def __init__(self, folder: Optional[Path] = None) -> None:
        self.folder = Path(folder or config.RECORD_DIR)

    def path(self, book_id: str) -> Path:
        return self.folder / ("%s.json" % book_id)

    def load(self, book_id: str) -> Dict[str, Any]:
        data = storage.read_json(self.path(book_id), default=None)
        if not isinstance(data, dict):
            data = {}
        data.setdefault("book_id", book_id)
        data.setdefault("words", {})
        data.setdefault("session", {"mode": "sequential", "last_index": 0})
        if not isinstance(data["words"], dict):
            data["words"] = {}
        return data

    def ensure(self, book: Book) -> Dict[str, Any]:
        data = self.load(book.book_id)
        data["title"] = book.title
        data["file"] = book.file
        data.setdefault("imported_at", book.imported_at or _now_iso())
        for item in book.words:
            data["words"].setdefault(
                item.no,
                {
                    "seen": False,
                    "seen_count": 0,
                    "first_seen": "",
                    "last_seen": "",
                    "registered": False,
                    "registered_at": "",
                    "word_id": "",
                },
            )
        self.save(book.book_id, data)
        return data

    def save(self, book_id: str, data: Dict[str, Any]) -> None:
        storage.write_json_atomic(self.path(book_id), data)

    def mark_seen(self, book_id: str, no: str) -> None:
        data = self.load(book_id)
        entry = data["words"].setdefault(
            no,
            {"seen": False, "seen_count": 0, "first_seen": "", "last_seen": "",
             "registered": False, "registered_at": "", "word_id": ""},
        )
        entry["seen"] = True
        entry["seen_count"] = int(entry.get("seen_count", 0)) + 1
        if not entry.get("first_seen"):
            entry["first_seen"] = _now_iso()
        entry["last_seen"] = _now_iso()
        self.save(book_id, data)

    def mark_registered(self, book_id: str, no: str, word_id: str) -> None:
        data = self.load(book_id)
        entry = data["words"].setdefault(
            no,
            {"seen": True, "seen_count": 1, "first_seen": _now_iso(), "last_seen": _now_iso(),
             "registered": False, "registered_at": "", "word_id": ""},
        )
        entry["registered"] = True
        entry["registered_at"] = entry.get("registered_at") or _now_iso()
        entry["word_id"] = word_id
        self.save(book_id, data)

    def save_session(self, book_id: str, mode: str, last_index: int) -> None:
        data = self.load(book_id)
        data["session"] = {"mode": mode, "last_index": int(last_index), "updated_at": _now_iso()}
        self.save(book_id, data)

    def progress(self, book: Book) -> Dict[str, int]:
        data = self.load(book.book_id)
        seen = registered = 0
        for item in book.words:
            entry = data["words"].get(item.no) or {}
            if entry.get("seen"):
                seen += 1
            if entry.get("registered"):
                registered += 1
        return {"total": len(book.words), "seen": seen, "registered": registered}

    def delete(self, book_id: str) -> None:
        path = self.path(book_id)
        for candidate in (path, Path(str(path) + ".bak")):
            if candidate.exists():
                try:
                    candidate.unlink()
                except OSError:
                    pass


class StatsRepo:
    """抽背统计（正确率 / 每日量）。"""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path or config.STATS_FILE)
        raw = storage.read_json(self.path, default={}) or {}
        self.data: Dict[str, Any] = raw if isinstance(raw, dict) else {}
        self.data.setdefault("quiz", {"total": 0, "correct": 0})
        self.data.setdefault("daily", {})

    def record_quiz(self, correct: bool) -> None:
        quiz = self.data["quiz"]
        quiz["total"] = int(quiz.get("total", 0)) + 1
        if correct:
            quiz["correct"] = int(quiz.get("correct", 0)) + 1
        key = _today()
        day = self.data["daily"].setdefault(key, {"quiz": 0, "correct": 0})
        day["quiz"] = int(day.get("quiz", 0)) + 1
        if correct:
            day["correct"] = int(day.get("correct", 0)) + 1
        self.save()

    def reset(self) -> None:
        """清空抽背统计（正确率与每日量）。"""
        self.data["quiz"] = {"total": 0, "correct": 0}
        self.data["daily"] = {}
        self.save()

    def save(self) -> None:
        storage.write_json_atomic(self.path, self.data)

    def heatmap(self, weeks: int = 12) -> List[Dict[str, Any]]:
        """返回最后 N 周的每日词汇量（登记 + 抽背），供热力图绘制。"""
        today = date.today()
        start = today - timedelta(days=weeks * 7 - 1)
        daily = self.data.get("daily", {})
        bucket: Dict[str, int] = {}
        for offset in range((today - start).days + 1):
            key = (start + timedelta(days=offset)).strftime(config.DATE_FMT)
            bucket[key] = int(daily.get(key, {}).get("quiz", 0))
        return [{"date": k, "count": v} for k, v in bucket.items()]

    def accuracy(self) -> float:
        quiz = self.data.get("quiz", {})
        total = int(quiz.get("total", 0))
        if total <= 0:
            return 0.0
        return int(quiz.get("correct", 0)) / float(total)
