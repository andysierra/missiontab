"""Nombre e ícono de la app de cada ventana, a partir de su .desktop (misma lógica que ListTab).

La INSTANCIA de WM_CLASS va primero: las PWA de Brave/Chrome comparten la clase ("Brave-browser") pero cada
una tiene su instancia ("crx_<id>") y su propio .desktop con StartupWMClass=crx_<id>, nombre e ícono.
"""
import os

from gi.repository import Gio, Gtk

ICON_SIZE = 96

_wm = None        # StartupWMClass (minúsculas) -> Gio.DesktopAppInfo
_ids = None       # id del .desktop / ejecutable (minúsculas) -> Gio.DesktopAppInfo
_icons = {}       # clave de app -> pixbuf


def _index():
    global _wm, _ids
    if _wm is None:
        _wm, _ids = {}, {}
        for info in Gio.AppInfo.get_all():
            if not isinstance(info, Gio.DesktopAppInfo):
                continue
            wm = info.get_startup_wm_class()
            if wm:
                _wm.setdefault(wm.lower(), info)
            app_id = (info.get_id() or "").removesuffix(".desktop").lower()
            if app_id:
                _ids.setdefault(app_id, info)
            exe = os.path.basename(info.get_executable() or "").lower()
            if exe:
                _ids.setdefault(exe, info)
    return _wm, _ids


def app_info(w):
    wm, ids = _index()
    keys = [k.lower() for k in (w.get_class_instance_name(), w.get_class_group_name()) if k]
    for table in (wm, ids):
        for k in keys:
            if k in table:
                return table[k]
    return None


def themed_icon(name_or_gicon, size=ICON_SIZE):
    theme = Gtk.IconTheme.get_default()
    try:
        if isinstance(name_or_gicon, str):
            info = theme.lookup_icon(name_or_gicon, size, Gtk.IconLookupFlags.FORCE_SIZE)
        else:
            info = theme.lookup_by_gicon(name_or_gicon, size, Gtk.IconLookupFlags.FORCE_SIZE)
        return info.load_icon() if info else None
    except Exception:
        return None


def icon_and_name(w):
    info = app_info(w)
    key = info.get_id() if info else (w.get_class_instance_name() or w.get_class_group_name() or str(w.get_xid()))
    app = w.get_application()
    name = info.get_name() if info else (w.get_class_group_name() or (app.get_name() if app else "") or "?")
    if key not in _icons:
        pix = themed_icon(info.get_icon()) if info and info.get_icon() else None
        _icons[key] = pix if pix is not None else w.get_icon()   # sin .desktop: _NET_WM_ICON de la ventana
    return _icons[key], name
