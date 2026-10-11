"""Punto de entrada y flags."""
import sys

from gi.repository import Gtk

import missiontab

HELP = f"""MissionTab {missiontab.__version__} — Mission Control para Linux MATE (X11)

  missiontab                 mostrar / ocultar la vista (lo que llama el atajo)
  missiontab --daemon        arrancar el proceso residente sin mostrar nada (autoarranque)
  missiontab --quit          cerrar el proceso residente
  missiontab --list          imprimir escritorios y ventanas
  missiontab --render=X.png  dibujar la vista en un PNG sin mostrarla (pruebas)
"""


def pump(seconds):
    import time
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(HELP)
        return
    if "--version" in args:
        print(missiontab.__version__)
        return

    if "--list" in args:
        from missiontab import model
        spaces, cur = model.snapshot()
        for sp in spaces:
            print(f"{'*' if sp.index == cur else ' '} Escritorio {sp.index + 1}  ({len(sp.windows)} ventanas)")
            for w in sp.windows:
                print(f"    {w.app[:22]:22} {w.title[:50]}" + ("  [minimizada]" if w.minimized else "")
                      + ("  [en todos]" if w.space == -1 else ""))
        return

    render = next((a.split("=", 1)[1] for a in args if a.startswith("--render=")), None)
    if render:
        from gi.repository import Gdk
        from missiontab.overlay import View
        from missiontab.thumbs import Thumbs
        t = Thumbs()
        t.request(t.visible_xids())
        pump(2.5)                                    # dejar que capture las visibles
        v = View(t)
        geo = Gdk.Display.get_default().get_primary_monitor().get_geometry()
        v.W, v.H = geo.width, geo.height
        v.load()
        v.sel = 1 if len(v.cards) > 1 else 0
        v.hover = ("space", v.cur)
        v.render_png(render)
        print(render, f"{v.W}x{v.H}", f"{len(v.spaces)} escritorios", f"{len(v.cards)} ventanas")
        return

    from missiontab.app import App
    sys.exit(App().run(sys.argv))
