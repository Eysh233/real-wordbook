"""词根聚合（F11）：从备注与 AI 拆解里抽取词根，按词根分组。"""
import re
from collections import defaultdict
from typing import Dict, List, Sequence

from ..models import Word

_ROOT_PATTERNS = [
    re.compile(r"词根[：: ]\s*([a-zA-Z\-]{2,20})"),
    re.compile(r"root[：: ]\s*([a-zA-Z\-]{2,20})", re.IGNORECASE),
    re.compile(r"^([a-zA-Z]{2,12})[（(]"),
]


def extract_root(word: Word) -> str:
    for source in (
        (word.ai or {}).get("breakdown", "") if isinstance(word.ai, dict) else "",
        word.note,
    ):
        if not source:
            continue
        for pattern in _ROOT_PATTERNS:
            match = pattern.search(str(source))
            if match:
                return match.group(1).lower().strip("-")
    return ""


def group_by_root(words: Sequence[Word]) -> Dict[str, List[Word]]:
    groups: Dict[str, List[Word]] = defaultdict(list)
    for word in words:
        root = extract_root(word)
        if root:
            groups[root].append(word)
    return dict(sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])))


def ungrouped(words: Sequence[Word]) -> List[Word]:
    return [w for w in words if not extract_root(w)]
