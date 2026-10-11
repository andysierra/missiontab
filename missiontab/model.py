"""Escritorios virtuales y ventanas (libwnck), y las acciones de Mission Control sobre ellos."""
from dataclasses import dataclass, field

from gi.repository import Gio, GLib, Wnck

from missiontab import apps, log

KINDS = (Wnck.WindowType.NORMAL, Wnck.WindowType.DIALOG)


@dataclass
class Win:
    xid: int
    title: str
    app: str
    icon: object
    x: int
    y: int
    w: int
    h: int
    minimized: bool
    space: int            # índice del escritorio (-1 = en todos)
    wnck: object = field(default=None, repr=False)


@dataclass
class Space:
    index: int
    name: str
    windows: list         # [Win], de la más reciente (frente) a la más antigua


def screen():
    s = Wnck.Screen.get_default()
    s.force_update()
    return s


def snapshot(ignore=()):
    """(escritorios, índice del activo). Las ventanas "en todos los escritorios" aparecen en cada uno."""
    s = screen()
    active = s.get_active_workspace()
    cur = active.get_number() if active else 0
    spaces = [Space(ws.get_number(), ws.get_name(), []) for ws in s.get_workspaces()]
    for w in reversed(s.get_windows_stacked()):          # frente -> fondo
        if w.get_xid() in ignore or w.is_skip_tasklist() or w.get_window_type() not in KINDS:
            continue
        icon, app = apps.icon_and_name(w)
        x, y, ww, hh = w.get_client_window_geometry()
        ws = w.get_workspace()
        idx = ws.get_number() if ws is not None and not w.is_pinned() else -1
        win = Win(w.get_xid(), w.get_name() or app, app, icon, x, y, max(ww, 1), max(hh, 1),
                  w.is_minimized(), idx, w)
        for sp in spaces:
            if idx == -1 or sp.index == idx:
                sp.windows.append(win)
    return spaces, cur


# --- acciones ---------------------------------------------------------------------------------------

def activate(win, ts):
    """Ir a la ventana: cambia a su escritorio si hace falta, la restaura si está minimizada y la enfoca."""
    w = win.wnck
    ws = w.get_workspace()
    if ws is not None and ws != w.get_screen().get_active_workspace():
        ws.activate(ts)
    if w.is_minimized():
        w.unminimize(ts)
    w.activate(ts)


def switch(index, ts):
    ws = screen().get_workspace(index)
    if ws is not None:
        ws.activate(ts)


def move(win, index):
    ws = screen().get_workspace(index)
    if ws is not None and win.wnck is not None:
        win.wnck.move_to_workspace(ws)


def count():
    return screen().get_workspace_count()


def _set_count(n):
    # Marco guarda la cantidad en gsettings: así sobrevive al reinicio y lo ve el resto de MATE
    Gio.Settings.new("org.mate.Marco.general").set_int("num-workspaces", max(1, n))


def add_space(then=None):
    """Crea un escritorio al final. `then(índice_nuevo)` corre cuando Marco ya lo creó."""
    n = count()
    _set_count(n + 1)
    if then:
        GLib.timeout_add(200, lambda: (then(n), False)[1])
    return n


def remove_space(k, ts):
    """Borra el escritorio k: sus ventanas pasan al de la izquierda (o al siguiente si es el primero) y los de
    la derecha se corren uno. Después se reduce la cantidad (Marco borra el último, que quedó vacío)."""
    s = screen()
    n = s.get_workspace_count()
    if n <= 1 or not 0 <= k < n:
        return
    target = k - 1 if k > 0 else 1

    def final(i):
        j = target if i == k else i
        return j - 1 if j > k else j

    for w in s.get_windows():
        ws = w.get_workspace()
        if ws is None or w.is_pinned() or w.get_window_type() not in KINDS:
            continue
        i = ws.get_number()
        dst = final(i)
        if dst != i:
            w.move_to_workspace(s.get_workspace(dst))
    cur = s.get_active_workspace().get_number() if s.get_active_workspace() else 0
    new_cur = final(cur)
    log.write(f"remove_space {k}: ventanas movidas, activo {cur} -> {new_cur}")

    def shrink():
        switch(new_cur, ts) if new_cur != cur else None
        _set_count(n - 1)
        return False

    GLib.timeout_add(150, shrink)
