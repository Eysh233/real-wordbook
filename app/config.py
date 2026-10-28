"""全局配置：路径、常量、AI 参数、枚举。

原则：所有路径与魔法数字集中在此，其它模块禁止散落字符串。
"""
from pathlib import Path

# ---------------------------------------------------------------- 应用信息
APP_NAME = "Real Wordbook"
APP_TITLE = "真实单词本"
APP_VERSION = "0.1.0"

# ---------------------------------------------------------------- 目录
APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
BOOKS_CACHE_DIR = DATA_DIR / "books"
STUDYBOOK_DIR = APP_DIR / "StudyBook"
RECORD_DIR = APP_DIR / "StudyRecord"
BACKUP_DIR = DATA_DIR / "backup"

# 用户目录（密钥只存这里，永不入库）
USER_DIR = Path.home() / ".real_wordbook"

WORDS_FILE = DATA_DIR / "words.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
AI_CACHE_FILE = DATA_DIR / "ai_cache.json"
STATS_FILE = DATA_DIR / "stats.json"
SECRET_FILE = USER_DIR / "config.json"

# ---------------------------------------------------------------- 版面
ROWS_PER_PAGE = 9
WORDS_PER_ROW = 5

# ---------------------------------------------------------------- 权重
DEFAULT_WEIGHT = 3
HIGHLIGHT_WEIGHT = 6
STRIKE_WEIGHT = 1
MIN_WEIGHT = 1
MAX_WEIGHT = 10

# ---------------------------------------------------------------- AI
AI_BASE_URL = "https://api.deepseek.com/chat/completions"
AI_MODEL = "deepseek-flash"
AI_EFFORT = "low"
AI_PROMPT_VERSION = 1
AI_TIMEOUT = 30
AI_MAX_TOKENS = 900

# ---------------------------------------------------------------- 记忆曲线（F1）
SRS_INTERVALS = [1, 3, 7, 15, 30, 60]

# ---------------------------------------------------------------- 显示
DATE_FMT = "%Y-%m-%d"
WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

DISPLAY_BOTH = "both"
DISPLAY_EN = "en"
DISPLAY_CN = "cn"
DISPLAY_MODES = (DISPLAY_BOTH, DISPLAY_EN, DISPLAY_CN)
DISPLAY_LABELS = {DISPLAY_BOTH: "中英", DISPLAY_EN: "英", DISPLAY_CN: "中"}

THEME_PAPER = "paper"
THEME_GREEN = "green"
THEME_DARK = "dark"
THEMES = (THEME_PAPER, THEME_GREEN, THEME_DARK)
THEME_LABELS = {THEME_PAPER: "米白纸", THEME_GREEN: "护眼绿", THEME_DARK: "深色"}

POS_OPTIONS = ["n.", "v.", "adj.", "adv.", "prep.", "conj.", "pron.", "num.", "phr."]


def ensure_dirs() -> None:
    """创建全部运行期目录（幂等）。"""
    for path in (DATA_DIR, BOOKS_CACHE_DIR, STUDYBOOK_DIR, RECORD_DIR, USER_DIR, BACKUP_DIR):
        path.mkdir(parents=True, exist_ok=True)
