"""程序入口：python main.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app import config  # noqa: E402
from app.ui import motion, theme  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def main() -> int:
    config.ensure_dirs()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_TITLE)
    app.setApplicationDisplayName(config.APP_TITLE)
    app.setStyleSheet(theme.qss())
    # 全局按下反馈：所有按钮按下时缩到 0.97，松开弹回（含对话框里的按钮）
    motion.install_press_feedback(app)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
