"""把程序打包成单文件 exe。

用法：python tools/build_exe.py
产物：release/RealWordbook.exe（release/ 与 build/ 都不进仓库）

说明：
- 用 PyInstaller 的 onefile 模式，PyQt5 的运行时会被塞进同一个 exe，
  首次启动会解包到 %TEMP%\\_MEIxxxx，因此启动比直接跑 .py 慢一两秒。
- --windowed 表示不带黑框控制台；调试时改成 --console 可以看到报错。
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
        "--onefile",
        "--windowed",
        "--name",
        "RealWordbook",
        "--distpath",
        str(RELEASE),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(BUILD),
        # onefile 默认解包到 %TEMP%\_MEIxxx；本机受限环境里 bootloader 建不了临时目录，
        # 改成解包到 exe 自己所在的目录（运行期会看到一个 _MEIxxxx 文件夹，退出即删）。
        "--runtime-tmpdir",
        ".",
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
