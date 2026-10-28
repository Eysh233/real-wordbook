"""学习统计（F4）：总量、今日、连续天数、正确率、热力图数据。"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Sequence

from .. import config
from ..models import Word


def _as_date(text: str):
    try:
        return datetime.strptime(text, config.DATE_FMT).date()
    except (ValueError, TypeError):
        return None


def streak(words: Sequence[Word]) -> int:
    days = {w.date_added for w in words if w.date_added}
    if not days:
        return 0
    cursor = date.today()
    if cursor.strftime(config.DATE_FMT) not in days:
        cursor = cursor - timedelta(days=1)
    count = 0
    while cursor.strftime(config.DATE_FMT) in days:
        count += 1
        cursor = cursor - timedelta(days=1)
    return count


def heatmap_weeks(words: Sequence[Word], stats_repo, weeks: int = 12) -> List[List[Dict[str, Any]]]:
    """按周（周一→周日）返回方块，供热力图绘制。"""
    quiz_map = {item["date"]: item["count"] for item in stats_repo.heatmap(weeks)}
    add_map: Dict[str, int] = {}
    for word in words:
        if word.date_added:
            add_map[word.date_added] = add_map.get(word.date_added, 0) + 1

    today = date.today()
    end = today + timedelta(days=(6 - today.weekday()))
    start = end - timedelta(days=weeks * 7 - 1)
    grid: List[List[Dict[str, Any]]] = []
    for week in range(weeks):
        column = []
        for weekday in range(7):
            current = start + timedelta(days=week * 7 + weekday)
            key = current.strftime(config.DATE_FMT)
            column.append(
                {
                    "date": key,
                    "added": add_map.get(key, 0),
                    "quiz": quiz_map.get(key, 0),
                    "future": current > today,
                }
            )
        grid.append(column)
    return grid


def summary(words: Sequence[Word], stats_repo) -> Dict[str, Any]:
    today = date.today().strftime(config.DATE_FMT)
    total = len(words)
    today_added = sum(1 for w in words if w.date_added == today)
    due = sum(1 for w in words if (w.due or "") <= today)
    quiz = stats_repo.data.get("quiz", {})
    total_quiz = int(quiz.get("total", 0))
    correct = int(quiz.get("correct", 0))
    return {
        "total": total,
        "today_added": today_added,
        "due": due,
        "streak": streak(words),
        "quiz_total": total_quiz,
        "accuracy": (correct / total_quiz) if total_quiz else 0.0,
        "highlight": sum(1 for w in words if w.highlight),
        "strike": sum(1 for w in words if w.strike),
    }
