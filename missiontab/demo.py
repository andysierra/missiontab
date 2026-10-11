"""Modo demo (`--render=X.png --demo`): escritorios y ventanas ficticias, con "contenido" dibujado por código,
para las capturas del README sin mostrar nada del escritorio real."""
import random

import cairo
from gi.repository import Gdk

from missiontab.apps import themed_icon
from missiontab.model import Space, Win

# (íconos candidatos, app, título, estilo, x, y, w, h) por escritorio — geometría sobre una pantalla 1920x1080
SPACES = [
    [
        (["brave-browser", "web-browser"], "Brave", "Hacker News", "browser", 80, 60, 1100, 760),
        (["zed", "dev.zed.Zed", "text-editor"], "Zed", "missiontab — overlay.py", "editor", 760, 160, 1080, 820),
        (["org.wezfurlong.wezterm", "utilities-terminal"], "WezTerm", "yazi: Escritorio", "terminal", 300, 420, 900, 560),
        (["com.visualstudio.code", "code", "text-editor"], "Visual Studio Code", "App.tsx — 03-gifs-app", "editor-light", 980, 40, 900, 620),
        (["sublime-text", "accessories-text-editor"], "Sublime Text", "notas.md", "notes", 120, 640, 640, 400),
    ],
    [
        (["brave-browser", "web-browser"], "Brave", "YouTube", "video", 120, 80, 1400, 880),
        (["org.wezfurlong.wezterm", "utilities-terminal"], "WezTerm", "htop", "terminal", 1100, 520, 760, 500),
    ],
    [
        (["utilities-system-monitor", "utilities-terminal"], "Monitor del sistema", "Procesos", "monitor", 360, 140, 1200, 780),
    ],
]

STYLES = {
    "browser":      ((0.13, 0.14, 0.17), (0.98, 0.98, 0.99), (0.98, 0.42, 0.13)),
    "video":        ((0.06, 0.06, 0.06), (0.09, 0.09, 0.09), (0.93, 0.18, 0.18)),
    "editor":       ((0.10, 0.11, 0.15), (0.12, 0.13, 0.18), (0.48, 0.64, 0.97)),
    "editor-light": ((0.12, 0.12, 0.13), (0.12, 0.12, 0.13), (0.22, 0.60, 0.95)),
    "terminal":     ((0.10, 0.11, 0.15), (0.10, 0.11, 0.15), (0.62, 0.81, 0.42)),
    "notes":        ((0.16, 0.16, 0.16), (0.16, 0.16, 0.16), (0.98, 0.75, 0.30)),
    "monitor":      ((0.18, 0.19, 0.22), (0.20, 0.21, 0.25), (0.40, 0.80, 0.55)),
}


def _thumb(style, w, h, seed):
    """Una "captura" verosímil: barra de título, y contenido según el tipo de app."""
    rnd = random.Random(seed)
    bar, body, accent = STYLES[style]
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    cr = cairo.Context(s)
    cr.set_source_rgb(*body)
    cr.paint()
    cr.set_source_rgb(*bar)
    cr.rectangle(0, 0, w, 34)
    cr.fill()
    for k, c in enumerate(((0.95, 0.35, 0.33), (0.98, 0.75, 0.25), (0.35, 0.80, 0.40))):
        cr.arc(w - 22 - k * 20, 17, 6, 0, 6.3)
        cr.set_source_rgb(*c)
        cr.fill()
    if style in ("browser", "video"):
        cr.set_source_rgb(0.85, 0.86, 0.88) if style == "browser" else cr.set_source_rgb(0.15, 0.15, 0.15)
        cr.rectangle(20, 44, w - 40, 26)
        cr.fill()
        if style == "video":
            cr.set_source_rgb(0.05, 0.05, 0.05)
            cr.rectangle(30, 90, w * 0.66, (w * 0.66) * 9 / 16)
            cr.fill()
            cr.set_source_rgb(*accent)
            cr.rectangle(30, 90 + (w * 0.66) * 9 / 16 - 6, w * 0.66 * 0.4, 6)
            cr.fill()
            for i in range(5):
                cr.set_source_rgb(0.18, 0.18, 0.18)
                cr.rectangle(w * 0.70, 90 + i * 110, w * 0.27, 96)
                cr.fill()
        else:
            for i in range(9):
                cr.set_source_rgb(*accent) if i == 0 else cr.set_source_rgb(0.30, 0.32, 0.38)
                cr.rectangle(40, 100 + i * 70, rnd.uniform(0.3, 0.8) * (w - 80), 14)
                cr.fill()
                cr.set_source_rgb(0.62, 0.64, 0.68)
                cr.rectangle(40, 122 + i * 70, rnd.uniform(0.2, 0.5) * (w - 80), 9)
                cr.fill()
    elif style == "monitor":
        cr.set_source_rgb(*accent)
        cr.set_line_width(3)
        cr.move_to(40, h * 0.45)
        for x in range(40, w - 40, 20):
            cr.line_to(x, h * 0.45 - rnd.uniform(0, h * 0.3))
        cr.stroke()
        for i in range(8):
            cr.set_source_rgb(0.35, 0.37, 0.42)
            cr.rectangle(40, h * 0.55 + i * 34, w - 80, 20)
            cr.fill()
    else:   # editores, terminal, notas: líneas de "código"
        colors = [accent, (0.73, 0.60, 0.97), (0.88, 0.69, 0.41), (0.75, 0.78, 0.86)]
        y = 56
        while y < h - 20:
            x = 30 + (rnd.randint(0, 3) * 26 if style != "terminal" else 0)
            for _ in range(rnd.randint(1, 4)):
                seg = rnd.uniform(40, 220)
                if x + seg > w - 30:
                    break
                cr.set_source_rgb(*rnd.choice(colors))
                cr.rectangle(x, y, seg, 11)
                cr.fill()
                x += seg + 14
            y += 24
    return Gdk.pixbuf_get_from_surface(s, 0, 0, w, h)


class DemoThumbs:
    def __init__(self):
        self.cache = {}

    def get(self, xid):
        return self.cache.get(xid)


def load(view):
    """Llena una View con los escritorios ficticios (en vez de model.snapshot)."""
    thumbs = DemoThumbs()
    view.thumbs = thumbs
    sx, sy = view.W / 1920, view.H / 1080
    spaces, xid = [], 1
    for i, wins in enumerate(SPACES):
        sp = Space(i, f"Escritorio {i + 1}", [])
        for names, app, title, style, x, y, w, h in wins:
            icon = next((p for p in (themed_icon(n) for n in names) if p is not None), None)
            sp.windows.append(Win(xid, title, app, icon, int(x * sx), int(y * sy), int(w * sx), int(h * sy),
                                  False, i, None))
            thumbs.cache[xid] = _thumb(style, w // 2, h // 2, xid)
            xid += 1
        spaces.append(sp)
    view.spaces, view.cur = spaces, 0
    view.compute()
