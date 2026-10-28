"""后台线程：调用 DeepSeek，避免阻塞界面。"""
from PyQt5.QtCore import QThread, pyqtSignal

from ..models import Word
from ..services import ai_client


class AIWorker(QThread):
    done = pyqtSignal(str, dict)
    failed = pyqtSignal(str, str)

    def __init__(self, word: Word, api_key: str, model: str, effort: str, parent=None) -> None:
        super().__init__(parent)
        self._word = word
        self._api_key = api_key
        self._model = model
        self._effort = effort

    def run(self) -> None:  # noqa: D401 - QThread 入口
        try:
            data = ai_client.explain(
                self._word.word,
                meaning=self._word.meaning_cn,
                pos=self._word.pos,
                api_key=self._api_key,
                model=self._model,
                effort=self._effort,
            )
        except ai_client.AIError as exc:
            self.failed.emit(self._word.id, exc.message)
            return
        except Exception as exc:  # noqa: BLE001 - 线程里任何异常都要回传
            self.failed.emit(self._word.id, str(exc))
            return
        self.done.emit(self._word.id, data)
