"""分页：日期行 + 词行 → 页（行槽模型）。"""
from dataclasses import dataclass, field
from typing import List, Sequence

from .. import config
from ..models import Word


@dataclass
class Slot:
    kind: str  # "date" | "words"
    date: str = ""
    count: int = 0
    words: List[Word] = field(default_factory=list)
    continued: bool = False


@dataclass
class Page:
    index: int
    slots: List[Slot]


def group_by_date(words: Sequence[Word]):
    """按 date_added 分组，组内保持 created_at 顺序。"""
    ordered = sorted(words, key=lambda w: (w.date_added or "0000-00-00", w.created_at or ""))
    groups = []  # type: List[tuple]
    for word in ordered:
        key = word.date_added or "0000-00-00"
        if groups and groups[-1][0] == key:
            groups[-1][1].append(word)
        else:
            groups.append((key, [word]))
    return groups


def _chunks(items: Sequence[Word], size: int):
    for start in range(0, len(items), size):
        yield list(items[start:start + size])


def build_slots(words: Sequence[Word], per_row: int = config.WORDS_PER_ROW) -> List[Slot]:
    slots = []  # type: List[Slot]
    for date, items in group_by_date(words):
        slots.append(Slot(kind="date", date=date, count=len(items)))
        for chunk in _chunks(items, per_row):
            slots.append(Slot(kind="words", date=date, words=chunk))
    return slots


def paginate(slots: Sequence[Slot], rows: int = config.ROWS_PER_PAGE) -> List[Page]:
    """按行槽切页；若一页以词行开头（日期行在上一页），补一行「续」。"""
    pages = []  # type: List[Page]
    bucket = []  # type: List[Slot]
    for slot in slots:
        if len(bucket) >= rows:
            pages.append(Page(len(pages), bucket))
            bucket = []
        if not bucket and slot.kind == "words" and slot.date:
            bucket.append(Slot(kind="date", date=slot.date, count=0, continued=True))
        bucket.append(slot)
    if bucket:
        pages.append(Page(len(pages), bucket))
    return pages


def paginate_words(words: Sequence[Word]) -> List[Page]:
    return paginate(build_slots(words))


def page_label(date_text: str, count: int, continued: bool = False) -> str:
    """`2026-10-28 周三 · 今日登记 12 词`（非当天说「登记」）"""
    from datetime import date, datetime

    text = date_text
    is_today = False
    try:
        stamp = datetime.strptime(date_text, config.DATE_FMT)
        text = "%s %s" % (date_text, config.WEEKDAY_CN[stamp.weekday()])
        is_today = stamp.date() == date.today()
    except ValueError:
        pass
    if continued:
        return "%s ·（续）" % text
    if count:
        return "%s · %s登记 %d 词" % (text, "今日" if is_today else "", count)
    return text
