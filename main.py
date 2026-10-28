"""程序入口：python main.py"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtGui import QIcon  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import config  # noqa: E402
from app.ui import motion, theme  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def _install_crash_log() -> None:
    """把未捕获异常写进 data/crash.log。

    打包成 --windowed 之后没有控制台，stderr 是 None，异常信息会直接消失
    （设置对话框签名对不上那次就是这么静默退出的）。这里落盘一份，方便事后查。
    """

    def hook(exc_type, exc_value, exc_tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with (config.DATA_DIR / "crash.log").open("a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except Exception:  # 日志失败也不能影响程序
            pass
        if sys.stderr is not None:
            sys.stderr.write(text)

    sys.excepthook = hook


def main() -> int:
    _install_crash_log()
    config.ensure_dirs()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_TITLE)
    app.setApplicationDisplayName(config.APP_TITLE)
    icon_path = config.resource_path("app.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyleSheet(theme.qss())
    # 全局按下反馈：所有按钮按下时缩到 0.97，松开弹回（含对话框里的按钮）
    motion.install_press_feedback(app)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
