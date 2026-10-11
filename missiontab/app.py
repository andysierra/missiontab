"""Proceso residente (una sola instancia, vía Gtk.Application/D-Bus).

`missiontab --daemon` lo arranca sin mostrar nada (autoarranque): desde ahí va guardando miniaturas.
`missiontab` (el atajo) le avisa al proceso que ya corre que muestre u oculte la vista: así abre al instante,
con las miniaturas ya en caché.
"""
from gi.repository import Gio, GLib, Gtk

from missiontab import log
from missiontab.overlay import Overlay
from missiontab.thumbs import Thumbs

APP_ID = "dev.andysierra.MissionTab"


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.overlay = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()                       # residente aunque no haya ventanas abiertas
        self.thumbs = Thumbs()
        self.overlay = Overlay(self.thumbs)
        self.thumbs.start()
        log.write("startup")

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if "--quit" in args:
            self.quit()
        elif "--daemon" not in args:
            # dejar que el bucle procese primero lo pendiente (el arranque, si fue en frío)
            GLib.idle_add(lambda: (self.overlay.toggle(), False)[1])
        return 0
