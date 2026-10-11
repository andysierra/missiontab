"""Miniaturas de ventanas, con caché.

Con el compositor de Marco activo, el contenido de cada ventana visible se puede leer aunque esté TAPADA por
otra (~50-90 ms por ventana). Las de otros escritorios y las minimizadas están desmapeadas: leerlas da una
imagen vacía. Por eso, igual que Mission Control, se guarda la última captura buena de cada ventana y se
refresca cuando cambia el foco o el escritorio. Las capturas se hacen de a una por iteración del bucle (idle)
para no congelar nada.
"""
from gi.repository import Gdk, GdkPixbuf, GdkX11, GLib, Wnck

from missiontab import log

MAX_W = 520          # ancho máximo guardado (las tarjetas nunca son más grandes)


def _blank(pb):
    """True si la captura es de un solo color (ventana desmapeada: sale blanca/negra)."""
    px = pb.get_pixels()
    step = max(len(px) // 400, 4) & ~3 or 4
    first = px[0:3]
    return all(px[i:i + 3] == first for i in range(0, len(px) - 3, step))


class Thumbs:
    def __init__(self):
        self.cache = {}          # xid -> pixbuf escalado
        self.ignore = set()      # xids propios
        self.on_update = None    # callback(xid)
        self._queue = []
        self._idle = None
        self._debounce = None
        self._display = GdkX11.X11Display.get_default()

    def get(self, xid):
        return self.cache.get(xid)

    def capture(self, xid):
        d = self._display
        d.error_trap_push()      # la ventana pudo cerrarse entre medio: nunca romper por un BadWindow
        try:
            gw = GdkX11.X11Window.foreign_new_for_display(d, xid)
            if gw is None:
                return
            w, h = gw.get_width(), gw.get_height()
            if w < 8 or h < 8:
                return
            pb = Gdk.pixbuf_get_from_window(gw, 0, 0, w, h)
        finally:
            d.error_trap_pop_ignored()
        if pb is None or _blank(pb):
            return
        if w > MAX_W:
            pb = pb.scale_simple(MAX_W, max(1, round(h * MAX_W / w)), GdkPixbuf.InterpType.BILINEAR)
        self.cache[xid] = pb
        if self.on_update:
            self.on_update(xid)

    def request(self, xids):
        for x in xids:
            if x not in self._queue and x not in self.ignore:
                self._queue.append(x)
        if self._queue and self._idle is None:
            self._idle = GLib.idle_add(self._work, priority=GLib.PRIORITY_LOW)

    def _work(self):
        if not self._queue:
            self._idle = None
            return False
        xid = self._queue.pop(0)
        try:
            self.capture(xid)
        except Exception as e:
            log.write(f"capture {xid:#x}: {e}")
        return True

    @staticmethod
    def visible_xids(ignore=()):
        s = Wnck.Screen.get_default()
        s.force_update()
        ws = s.get_active_workspace()
        return [w.get_xid() for w in s.get_windows_stacked()
                if not w.is_minimized() and w.get_xid() not in ignore and not w.is_skip_tasklist()
                and (ws is None or w.is_on_workspace(ws))
                and w.get_window_type() in (Wnck.WindowType.NORMAL, Wnck.WindowType.DIALOG)]

    def refresh_visible(self, delay_ms=0):
        if self._debounce:
            GLib.source_remove(self._debounce)

        def go():
            self._debounce = None
            self.request(self.visible_xids(self.ignore))
            return False

        self._debounce = GLib.timeout_add(delay_ms, go)

    def start(self):
        s = Wnck.Screen.get_default()
        s.force_update()
        s.connect("active-window-changed", lambda *_: self.refresh_visible(1200))
        s.connect("active-workspace-changed", lambda *_: self.refresh_visible(500))
        s.connect("window-closed", lambda _s, w: self.cache.pop(w.get_xid(), None))
        self.refresh_visible(300)
        GLib.timeout_add_seconds(30, lambda: (self.refresh_visible(0), True)[1])   # por si algo cambió sin foco
