"""开发辅助：写入一批演示单词，方便检查排版与分页。

用法：python tests/seed_demo.py [--clear]
只写 data/words.json（已被 .gitignore 忽略），不影响 StudyBook 与记录。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.models import Word  # noqa: E402
from app.repositories import WordsRepo  # noqa: E402

DATA = [
    ("2026-10-26", [
        ("abandon", "v.", "放弃；抛弃", "", ""),
        ("brief", "adj.", "简短的；短暂的", "highlight", "CET4"),
        ("resilient", "adj.", "有韧性的；能恢复的", "", "CET6"),
        ("attain", "v.", "达到；获得", "", ""),
        ("deliberate", "adj.", "深思熟虑的；故意的", "", ""),
        ("fragile", "adj.", "易碎的；脆弱的", "strike", ""),
        ("genuine", "adj.", "真正的；真诚的", "", ""),
        ("hesitate", "v.", "犹豫；踌躇", "", ""),
        ("inevitable", "adj.", "不可避免的", "highlight", ""),
        ("justify", "v.", "证明…正当；为…辩护", "", ""),
        ("modest", "adj.", "谦虚的；适度的", "", ""),
        ("persuade", "v.", "说服；劝说", "", ""),
    ]),
    ("2026-10-27", [
        ("reluctant", "adj.", "不情愿的；勉强的", "", ""),
        ("sustain", "v.", "维持；支撑", "", "考研"),
        ("vivid", "adj.", "生动的；鲜明的", "", ""),
        ("wander", "v.", "漫游；走神", "", ""),
        ("yield", "v.", "屈服；产生（收益）", "", ""),
        ("zeal", "n.", "热情；热忱", "", ""),
        ("absorb", "v.", "吸收；使全神贯注", "", ""),
        ("bloom", "v.", "开花；繁荣", "", ""),
    ]),
    ("2026-10-28", [
        ("candid", "adj.", "坦率的；直言的", "", ""),
        ("dedicate", "v.", "奉献；致力于", "", ""),
        ("elaborate", "adj.", "精心制作的；详尽的", "", ""),
        ("feasible", "adj.", "可行的", "", ""),
        ("grasp", "v.", "抓住；领会", "strike", ""),
        ("humble", "adj.", "谦逊的；卑微的", "", ""),
        ("intricate", "adj.", "错综复杂的", "", ""),
        ("jeopardize", "v.", "危及；损害", "", ""),
        ("keen", "adj.", "热衷的；敏锐的", "", ""),
    ]),
]


def main() -> int:
    repo = WordsRepo()
    if "--clear" in sys.argv:
        repo.save([])
        print("已清空我的单词本")
        return 0
    existing = {w.word for w in repo.all()}
    added = 0
    for day, rows in DATA:
        for index, (word, pos, meaning, mark, tag) in enumerate(rows):
            if word in existing:
                continue
            weight = config.DEFAULT_WEIGHT
            if mark == "highlight":
                weight = config.HIGHLIGHT_WEIGHT
            elif mark == "strike":
                weight = config.STRIKE_WEIGHT
            repo.add(
                Word(
                    id="",
                    word=word,
                    meaning_cn=meaning,
                    pos=pos,
                    tags=[tag] if tag else [],
                    weight=weight,
                    highlight=(mark == "highlight"),
                    strike=(mark == "strike"),
                    date_added=day,
                    created_at="%sT09:%02d:00" % (day, 10 + index),
                ),
                save=False,
            )
            added += 1
    repo.save()
    print("已写入 %d 个演示单词，共 %d 词" % (added, len(repo.all())))

    from app.repositories import BooksRepo, RecordsRepo
    from app.services import book_parser

    books = BooksRepo()
    records = RecordsRepo()
    for path in sorted(config.STUDYBOOK_DIR.glob("*.md")):
        result = book_parser.parse_file(path)
        if not result.words:
            continue
        book = book_parser.build_book(path, result, "2026-10-28T09:00:00")
        book.book_id = path.stem
        books.save(book)
        records.ensure(book)
        for index, word in enumerate(book.words):
            if index < 4:
                records.mark_seen(book.book_id, word.no)
            if index < 2:
                records.mark_registered(book.book_id, word.no, "w_%06d" % (index + 1))
        print("已导入单词书《%s》· %d 词" % (book.title, len(book.words)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
