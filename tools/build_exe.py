"""把程序打包成 release/RealWordbook/ 下的可执行目录。

用法：python tools/build_exe.py
产物：release/RealWordbook/RealWordbook.exe（release/ 与 build/ 都不进仓库）

说明：
- 用 PyInstaller 的 onedir 模式：启动快、依赖放在同目录的 _internal/ 里，
  整个 release/RealWordbook/ 文件夹一起拷走即可运行。
  想要「一个文件」就把 --onedir 换成 --onefile，并补上
  `--runtime-tmpdir .`（onefile 默认解包到 %TEMP%，受限环境里会失败）。
- --windowed 表示不带黑框控制台；调试时改成 --console 可以看到报错，
  正式版也可以查 data/crash.log（main.py 里装了 excepthook）。
- 图标：assets/app.ico（tools/make_icon.py 生成）既作为 exe 图标，
  也通过 --add-data 打进包里，供窗口图标使用。
- exe 旁边的 data/、StudyBook/、StudyRecord/ 才是真正读写的位置
  （config.py 里对 frozen 状态做了判断）。
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "release"
BUILD = ROOT / "build" / "pyinstaller"
ASSETS = ROOT / "assets"

EXCLUDES = [
    "tkinter",
    "unittest",
    "pydoc_data",
    "PySide2",
    "wx",
    "PyQt5.QtWebEngine",
    "PyQt5.QtWebEngineWidgets",
    "PyQt5.QtWebEngineCore",
    "PyQt5.QtQml",
    "PyQt5.QtQuick",
    "PyQt5.QtQuickWidgets",
    "PyQt5.QtMultimedia",
    "PyQt5.QtMultimediaWidgets",
    "PyQt5.QtBluetooth",
    "PyQt5.QtPositioning",
    "PyQt5.QtSensors",
    "PyQt5.QtSerialPort",
    "PyQt5.QtTest",
    "PyQt5.QtDesigner",
    "PyQt5.QtHelp",
    "PyQt5.QtXml",
    "PyQt5.QtSql",
    "PyQt5.QtSvg",
    "PyQt5.QtNetwork",
    "numpy",
    "matplotlib",
    "pandas",
]


def main() -> int:
    RELEASE.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "RealWordbook",
        "--distpath",
        str(RELEASE),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(BUILD),
        "--icon",
        str(ASSETS / "app.ico"),
        "--add-data",
        "%s%s." % (ASSETS / "app.ico", os.pathsep),
    ]
    for name in EXCLUDES:
        cmd += ["--exclude-module", name]
    cmd.append(str(ROOT / "main.py"))

    print(" ".join(cmd))
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


if __name__ == "__main__":
    sys.exit(main())
