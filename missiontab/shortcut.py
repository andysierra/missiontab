"""Atajo global: un paquete no puede crear atajos en la sesión del usuario, así que al arrancar MissionTab
crea el suyo (Ctrl+Super+↑, como Ctrl+↑ en macOS) como atajo propio de MATE, si no existe uno que ya lo llame
y si esa combinación está libre. Nunca pisa un atajo existente.
"""
import shutil

from gi.repository import Gio

from missiontab import log

SCHEMA = "org.mate.control-center.keybinding"
BASE = "/org/mate/desktop/keybindings/"
BINDING = "<Primary><Mod4>Up"


def _slot(i):
    return Gio.Settings.new_with_path(SCHEMA, f"{BASE}custom{i}/")


def ensure(command=None):
    command = command or shutil.which("missiontab") or "missiontab"
    used = []
    for i in range(100):
        s = _slot(i)
        action, binding = s.get_string("action"), s.get_string("binding")
        if action or binding:
            if "missiontab" in action:
                return f"custom{i}"            # ya hay un atajo que llama a MissionTab: no tocar
            used.append(binding)
        elif "free" not in locals():
            free = i
    if BINDING in used:
        log.write(f"atajo {BINDING} ocupado por otro atajo propio: no se crea")
        return None
    s = _slot(free)
    s.set_string("name", "Mission Control (MissionTab)")
    s.set_string("action", command)
    s.set_string("binding", BINDING)
    Gio.Settings.sync()
    log.write(f"atajo creado: custom{free} {BINDING} -> {command}")
    return f"custom{free}"
