"""Log de depuración opcional: solo escribe si existe ~/.missiontab-debug  ->  ~/.cache/missiontab.log"""
import os
from datetime import datetime

FLAG = os.path.expanduser("~/.missiontab-debug")
PATH = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "missiontab.log")


def write(msg):
    """msg puede ser un str o una función que lo devuelve (para no armar el texto si no hay log)."""
    if not os.path.exists(FLAG):
        return
    text = msg() if callable(msg) else msg
    with open(PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {text}\n")
