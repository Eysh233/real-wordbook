"""DeepSeek 客户端（标准库 urllib，无第三方依赖）。

- 模型 deepseek-flash，推理等级 low（reasoning_effort）
- 强制 JSON 输出并做 schema 校验
- 失败抛 AIError，UI 显示可读原因
"""
import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .. import config, storage

SYSTEM_PROMPT = (
    "你是资深英语词汇教练。请用简体中文解释单词，输出严格 JSON，不要任何多余文字。"
)

USER_TEMPLATE = """请为一单词生成学习卡片，JSON 字段：
{{
  "word": "原词",
  "phonetic": "国际音标，带斜杠",
  "pos": "主要词性，如 n. / v. / adj.",
  "translation_cn": "简明中文释义，不超过 20 字",
  "meaning_en": "一句英文释义",
  "breakdown": "构词/词根拆解，中文说明，60 字内",
  "collocations": ["高频搭配1", "搭配2", "搭配3"],
  "confusables": ["易混词1", "易混词2"],
  "examples": [{{"en": "英文例句", "cn": "中文翻译"}}, {{"en": "...", "cn": "..."}}],
  "memory_tip": "记忆法，中文，50 字内"
}}
要求：例句必须体现该词典型用法，共 2 条。

单词：{word}
已知中文：{meaning}
已知词性：{pos}
"""


class AIError(Exception):
    def __init__(self, message: str, code: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def build_payload(word: str, meaning: str, pos: str, model: str, effort: str) -> Dict[str, Any]:
    effort = effort if effort in ("low", "high", "max") else "low"
    return {
        "model": model or config.AI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_TEMPLATE.format(word=word, meaning=meaning or "（未填）", pos=pos or "（未填）"),
            },
        ],
        "reasoning_effort": effort,
        "thinking": {"type": "enabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": config.AI_MAX_TOKENS,
        "stream": False,
    }


def _post(payload: Dict[str, Any], api_key: str, timeout: int = config.AI_TIMEOUT) -> Dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        config.AI_BASE_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer %s" % api_key,
            "User-Agent": "RealWordbook/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:  # noqa: BLE001 - 读取错误体失败不影响主流程
            detail = ""
        mapping = {
            400: "请求格式有误",
            401: "API Key 无效或已过期",
            402: "账户余额不足",
            422: "参数不被接受",
            429: "请求过于频繁，请稍后重试",
            500: "服务端错误，请稍后重试",
            503: "服务繁忙，请稍后重试",
        }
        raise AIError("%s（HTTP %d）%s" % (mapping.get(exc.code, "请求失败"), exc.code, detail), exc.code)
    except urllib.error.URLError as exc:
        raise AIError("网络不可达：%s（如需代理请在系统层配置）" % getattr(exc, "reason", exc))
    except TimeoutError:
        raise AIError("请求超时（%d 秒）" % timeout)
    try:
        return json.loads(raw)
    except ValueError:
        raise AIError("响应不是合法 JSON")


def _normalize(data: Dict[str, Any], fallback_word: str) -> Dict[str, Any]:
    def as_text(key: str, default: str = "") -> str:
        value = data.get(key, default)
        if isinstance(value, (int, float)):
            return str(value)
        return value.strip() if isinstance(value, str) else default

    def as_list(key: str) -> list:
        value = data.get(key)
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    examples = []
    raw_examples = data.get("examples")
    if isinstance(raw_examples, list):
        for item in raw_examples:
            if isinstance(item, dict):
                examples.append({"en": str(item.get("en", "")).strip(), "cn": str(item.get("cn", "")).strip()})
            elif isinstance(item, str) and item.strip():
                examples.append({"en": item.strip(), "cn": ""})

    return {
        "word": as_text("word", fallback_word),
        "phonetic": as_text("phonetic"),
        "pos": as_text("pos"),
        "translation_cn": as_text("translation_cn"),
        "meaning_en": as_text("meaning_en"),
        "breakdown": as_text("breakdown"),
        "collocations": as_list("collocations"),
        "confusables": as_list("confusables"),
        "examples": examples[:3],
        "memory_tip": as_text("memory_tip"),
    }


def explain(
    word: str,
    meaning: str = "",
    pos: str = "",
    api_key: str = "",
    model: str = config.AI_MODEL,
    effort: str = config.AI_EFFORT,
    timeout: int = config.AI_TIMEOUT,
) -> Dict[str, Any]:
    if not api_key:
        raise AIError("未配置 API Key，请在「设置」中填写")
    if not word.strip():
        raise AIError("单词为空")
    payload = build_payload(word.strip(), meaning, pos, model, effort)
    data = _post(payload, api_key, timeout)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AIError("响应结构异常（缺少 choices）")
    if isinstance(content, dict):
        parsed = content
    else:
        text = str(content or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        try:
            parsed = json.loads(text)
        except ValueError:
            raise AIError("模型未返回合法 JSON")
    if not isinstance(parsed, dict):
        raise AIError("模型返回的 JSON 不是对象")
    return _normalize(parsed, word.strip())


class AICache:
    """ai_cache.json：key = 小写单词 + 模型 + 提示词版本。"""

    def __init__(self, path=None) -> None:
        from .. import config as cfg

        self.path = path or cfg.AI_CACHE_FILE
        raw = storage.read_json(self.path, default={}) or {}
        self.data: Dict[str, Any] = raw if isinstance(raw, dict) else {}

    @staticmethod
    def key(word: str, model: str) -> str:
        return "%s|%s|v%d" % (word.strip().lower(), model, config.AI_PROMPT_VERSION)

    def get(self, word: str, model: str) -> Optional[Dict[str, Any]]:
        value = self.data.get(self.key(word, model))
        return value if isinstance(value, dict) else None

    def put(self, word: str, model: str, value: Dict[str, Any]) -> None:
        self.data[self.key(word, model)] = value
        storage.write_json_atomic(self.path, self.data)
