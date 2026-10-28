"""抽背算法：加权无放回排序（Efraimidis–Spirakis）+ 间隔重复（SRS）。"""
import random
from datetime import date, datetime, timedelta
from typing import List, Optional, Sequence

from .. import config
from ..models import Word


def weighted_order(words: Sequence[Word], rng: Optional[random.Random] = None) -> List[Word]:
    """一次生成整轮加权随机顺序，同轮不重复；权重越大越靠前。"""
    rng = rng or random.Random()
    keyed = []
    for index, word in enumerate(words):
        weight = max(config.MIN_WEIGHT, min(config.MAX_WEIGHT, int(word.weight or 3)))
        u = rng.random()
        if u <= 0.0:
            u = 1e-12
        score = u ** (1.0 / weight)
        keyed.append((score, index, word))
    keyed.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in keyed]


def due_words(words: Sequence[Word], today: Optional[str] = None) -> List[Word]:
    today = today or date.today().strftime(config.DATE_FMT)
    return [w for w in words if (w.due or "") <= today]


def build_queue(words: Sequence[Word], rng: Optional[random.Random] = None) -> List[Word]:
    """到期词优先（SRS），其余按权重随机；两段内部均不重复。"""
    rng = rng or random.Random()
    today = date.today().strftime(config.DATE_FMT)
    due = due_words(words, today)
    rest = [w for w in words if w not in due]
    return weighted_order(due, rng) + weighted_order(rest, rng)


def apply_review(word: Word, known: bool, today: Optional[date] = None) -> None:
    """认识 → 间隔阶梯前进；不认识 → 间隔归零、明天再来。"""
    today = today or date.today()
    word.seen_count = int(word.seen_count or 0) + 1
    word.last_quiz_at = datetime.now().replace(microsecond=0).isoformat()
    if known:
        index = 0
        for i, interval in enumerate(config.SRS_INTERVALS):
            if interval >= int(word.interval or 0):
                index = i
                break
        word.interval = config.SRS_INTERVALS[min(index + 1, len(config.SRS_INTERVALS) - 1)]
    else:
        word.interval = 0
        word.wrong_count = int(word.wrong_count or 0) + 1
    word.due = (today + timedelta(days=max(int(word.interval or 0), 1))).strftime(config.DATE_FMT)


def difficulty_marks(word: Word) -> str:
    """UI 用的小标记：到期显示 ●，超期显示 ▲。"""
    due = word.due or ""
    if not due:
        return ""
    today = date.today().strftime(config.DATE_FMT)
    if due < today:
        return "▲"
    if due == today:
        return "●"
    return ""
