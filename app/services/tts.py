"""朗读（F3）：Windows SAPI，通过 PowerShell 调用，后台线程不阻塞 UI。"""
import platform
import subprocess
import threading
from typing import Callable, Optional

_SCRIPT = (
    "Add-Type -AssemblyName System.Speech;"
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "$s.Rate = 0;"
    "$s.Volume = 100;"
    "$s.Speak([Console]::In.ReadToEnd());"
    "$s.Dispose();"
)


def available() -> bool:
    return platform.system() == "Windows"


def _speak_blocking(text: str, timeout: int = 15) -> None:
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],
            input=text,
            text=True,
            timeout=timeout,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        pass


def speak(text: str, on_error: Optional[Callable[[str], None]] = None) -> None:
    """异步朗读；空文本直接忽略。"""
    text = (text or "").strip()
    if not text:
        return
    if not available():
        if on_error:
            on_error("当前系统不支持 SAPI 朗读")
        return
    thread = threading.Thread(target=_speak_blocking, args=(text,), daemon=True)
    thread.start()
