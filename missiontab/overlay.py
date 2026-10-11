"""La vista de Mission Control: pantalla completa con la barra de escritorios arriba y las ventanas del
escritorio actual en mosaico. Todo se dibuja con cairo (como ListTab) para controlar el aspecto.

  clic en ventana            ir a esa ventana
  arrastrar ventana          soltarla sobre un escritorio = moverla ahí · sobre "+" = escritorio nuevo con ella
  clic en escritorio         ir a ese escritorio          · "×" (al pasar el mouse) = borrarlo
  "+"                        crear escritorio
  Esc / atajo / clic fondo   salir
  flechas + Enter            elegir ventana · 1–9 = ir al escritorio N · Ctrl+←/→ = cambiar de escritorio en vivo
"""
import math
import os

import cairo
from gi.repository import Gdk, GdkPixbuf, GdkX11, Gio, GLib, Gtk, Pango, PangoCairo

from missiontab import layout, log, model

ACCENT = (10 / 255, 132 / 255, 255 / 255)       # azul de selección de macOS
DIM = 0.42                                       # oscurecido del fondo de escritorio
DRAG_THRESHOLD = 8


def _rounded(cr, x, y, w, h, r):
    r = max(0, min(r, w / 2, h / 2))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _inside(px, py, rect):
    x, y, w, h = rect
    return x <= px <= x + w and y <= py <= y + h


def _wallpaper_path():
    try:
        p = Gio.Settings.new("org.mate.background").get_string("picture-filename")
        return p if p and os.path.exists(p) else None
    except Exception:
        return None


class View:
    """Estado + geometría + dibujo. No depende de una ventana: se puede renderizar a un PNG."""

    def __init__(self, thumbs):
        self.thumbs = thumbs
        self.W, self.H = 1920, 1080
        self.spaces, self.cur = [], 0
        self.cards = []            # [(Win, rect)]
        self.space_rects = []      # [rect]
        self.plus_rect = (0, 0, 0, 0)
        self.hover = None          # ("card", i) | ("space", i) | ("close", i) | ("plus",)
        self.sel = None            # índice de tarjeta elegida con el teclado
        self.drag = None           # {"card": i, "x": , "y": }
        self.drop = None           # destino bajo el mouse durante un arrastre
        self._wall = None          # (W, H, pixbuf)
        self.family = Pango.FontDescription.from_string(
            Gtk.Settings.get_default().props.gtk_font_name or "Sans 10").get_family() or "Sans"

    # --- datos y geometría ---------------------------------------------------------------------------

    def load(self, ignore=()):
        self.spaces, self.cur = model.snapshot(ignore)
        self.cur = min(self.cur, len(self.spaces) - 1) if self.spaces else 0
        self.compute()

    def compute(self):
        W, H, n = self.W, self.H, max(len(self.spaces), 1)
        self.bar_h = int(H * 0.2)
        th = int(self.bar_h * 0.6)                     # alto de la miniatura de escritorio
        tw = int(th * W / H)
        gap = int(W * 0.02)
        p = int(th * 0.5)                              # botón "+"
        total = n * tw + (n - 1) * gap + gap + p
        x = (W - total) / 2
        top = int(self.bar_h * 0.13)
        self.space_rects = []
        for _ in range(n):
            self.space_rects.append((x, top, tw, th))
            x += tw + gap
        self.plus_rect = (x, top + (th - p) / 2, p, p)

        wins = self.spaces[self.cur].windows if self.spaces else []
        wins = [w for w in wins if not w.minimized] + [w for w in wins if w.minimized]
        aspects = []
        for w in wins:
            pb = self.thumbs.get(w.xid)
            aspects.append(pb.get_width() / pb.get_height() if pb else w.w / w.h)
        mx, top_y = int(W * 0.05), self.bar_h + int(H * 0.05)
        rects = layout.grid(aspects, mx, top_y, W - 2 * mx, H - top_y - int(H * 0.07),
                            gap=int(W * 0.025), max_h=H * 0.6)
        self.cards = list(zip(wins, rects))
        if self.sel is not None and self.sel >= len(self.cards):
            self.sel = len(self.cards) - 1 if self.cards else None

    def close_rect(self, i):
        x, y, _, _ = self.space_rects[i]
        return (x - 9, y - 9, 22, 22)

    def hit(self, px, py):
        for i, rect in enumerate(self.space_rects):
            if self.hover in (("space", i), ("close", i)) and len(self.space_rects) > 1 and _inside(px, py, self.close_rect(i)):
                return ("close", i)
            if _inside(px, py, rect):
                return ("space", i)
        if _inside(px, py, self.plus_rect):
            return ("plus",)
        for i, (_, rect) in enumerate(self.cards):
            if _inside(px, py, rect):
                return ("card", i)
        return None

    # --- dibujo --------------------------------------------------------------------------------------

    def _font(self, cr, text, size, bold=False, max_w=None):
        lay = PangoCairo.create_layout(cr)
        d = Pango.FontDescription.from_string(self.family)
        d.set_absolute_size(size * Pango.SCALE)
        d.set_weight(Pango.Weight.MEDIUM if bold else Pango.Weight.NORMAL)
        lay.set_font_description(d)
        lay.set_text(text, -1)
        if max_w:
            lay.set_width(int(max_w * Pango.SCALE))
            lay.set_ellipsize(Pango.EllipsizeMode.END)
        return lay

    def _wallpaper(self):
        if self._wall and self._wall[:2] == (self.W, self.H):
            return self._wall[2]
        pb, path = None, _wallpaper_path()
        if path:
            try:
                src = GdkPixbuf.Pixbuf.new_from_file(path)
                s = max(self.W / src.get_width(), self.H / src.get_height())   # cubrir, recortando
                sw, sh = math.ceil(src.get_width() * s), math.ceil(src.get_height() * s)
                big = src.scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)
                pb = big.new_subpixbuf((sw - self.W) // 2, (sh - self.H) // 2, self.W, self.H).copy()
            except Exception as e:
                log.write(f"fondo: {e}")
        self._wall = (self.W, self.H, pb)
        return pb

    def _paint_background(self, cr, x, y, w, h):
        pb = self._wallpaper()
        cr.save()
        cr.translate(x, y)
        cr.scale(w / self.W, h / self.H)
        if pb is not None:
            Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
        else:
            g = cairo.LinearGradient(0, self.H, self.W, 0)
            g.add_color_stop_rgb(0, 26 / 255, 27 / 255, 38 / 255)
            g.add_color_stop_rgb(1, 36 / 255, 40 / 255, 59 / 255)
            cr.set_source(g)
        cr.rectangle(0, 0, self.W, self.H)
        cr.fill()
        cr.restore()

    def _paint_image(self, cr, pb, x, y, w, h, radius, alpha=1.0):
        cr.save()
        _rounded(cr, x, y, w, h, radius)
        cr.clip()
        cr.translate(x, y)
        cr.scale(w / pb.get_width(), h / pb.get_height())
        Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_GOOD)
        cr.paint_with_alpha(alpha)
        cr.restore()

    def _paint_icon(self, cr, pb, cx, cy, size, alpha=1.0):
        if pb is None:
            return
        cr.save()
        cr.translate(cx - size / 2, cy - size / 2)
        cr.scale(size / pb.get_width(), size / pb.get_height())
        Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
        cr.paint_with_alpha(alpha)
        cr.restore()

    def draw(self, cr):
        W, H = self.W, self.H
        self._paint_background(cr, 0, 0, W, H)
        cr.set_source_rgba(0, 0, 0, DIM)
        cr.paint()
        cr.set_source_rgba(0, 0, 0, 0.22)               # franja de la barra de escritorios
        cr.rectangle(0, 0, W, self.bar_h)
        cr.fill()

        for i, sp in enumerate(self.spaces):
            self._draw_space(cr, i, sp)
        self._draw_plus(cr)

        if not self.cards:
            lay = self._font(cr, "No hay ventanas en este escritorio", 18)
            tw, th = lay.get_pixel_size()
            cr.move_to((W - tw) / 2, self.bar_h + (H - self.bar_h - th) / 2)
            cr.set_source_rgba(1, 1, 1, 0.55)
            PangoCairo.show_layout(cr, lay)
        for i, (win, rect) in enumerate(self.cards):
            if self.drag and self.drag["card"] == i and self.drag.get("moving"):
                continue
            self._draw_card(cr, i, win, rect)
        if self.drag and self.drag.get("moving"):
            win, (x, y, w, h) = self.cards[self.drag["card"]]
            s = 0.55
            gw, gh = w * s, h * s
            self._draw_card(cr, self.drag["card"], win, (self.drag["x"] - gw / 2, self.drag["y"] - gh / 2, gw, gh),
                            ghost=True)

    def _draw_space(self, cr, i, sp):
        x, y, w, h = self.space_rects[i]
        sx, sy = w / self.W, h / self.H
        cr.save()
        _rounded(cr, x, y, w, h, 8)
        cr.clip()
        self._paint_background(cr, x, y, w, h)
        for win in reversed(sp.windows):                 # del fondo al frente
            if win.minimized:
                continue
            rx, ry, rw, rh = x + win.x * sx, y + win.y * sy, win.w * sx, win.h * sy
            pb = self.thumbs.get(win.xid)
            if pb is not None:
                self._paint_image(cr, pb, rx, ry, rw, rh, 3)
            else:
                _rounded(cr, rx, ry, rw, rh, 3)
                cr.set_source_rgba(0.16, 0.17, 0.24, 0.95)
                cr.fill()
                self._paint_icon(cr, win.icon, rx + rw / 2, ry + rh / 2, min(rw, rh) * 0.45)
        cr.restore()

        target = self.drop == ("space", i)
        if i == self.cur or target or self.hover in (("space", i), ("close", i)):
            _rounded(cr, x - 1.5, y - 1.5, w + 3, h + 3, 9)
            cr.set_line_width(3 if (i == self.cur or target) else 2)
            cr.set_source_rgba(*(ACCENT if target else (1, 1, 1)), 1 if (i == self.cur or target) else 0.6)
            cr.stroke()

        lay = self._font(cr, f"Escritorio {i + 1}", max(11, self.H * 0.012), bold=i == self.cur)
        tw, _ = lay.get_pixel_size()
        cr.move_to(x + (w - tw) / 2, y + h + 6)
        cr.set_source_rgba(1, 1, 1, 0.95 if i == self.cur else 0.7)
        PangoCairo.show_layout(cr, lay)

        if len(self.spaces) > 1 and self.hover in (("space", i), ("close", i)) and not self.drag:
            cx, cy, cs, _ = self.close_rect(i)
            cr.arc(cx + cs / 2, cy + cs / 2, cs / 2, 0, 2 * math.pi)
            cr.set_source_rgba(0.95, 0.27, 0.23, 1) if self.hover == ("close", i) else cr.set_source_rgba(0.25, 0.25, 0.3, 0.95)
            cr.fill()
            arm = cs * 0.2
            cr.set_line_width(2)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.move_to(cx + cs / 2 - arm, cy + cs / 2 - arm)
            cr.line_to(cx + cs / 2 + arm, cy + cs / 2 + arm)
            cr.move_to(cx + cs / 2 + arm, cy + cs / 2 - arm)
            cr.line_to(cx + cs / 2 - arm, cy + cs / 2 + arm)
            cr.set_source_rgb(1, 1, 1)
            cr.stroke()

    def _draw_plus(self, cr):
        x, y, w, h = self.plus_rect
        active = self.hover == ("plus",) or self.drop == ("plus",)
        _rounded(cr, x, y, w, h, 10)
        cr.set_source_rgba(1, 1, 1, 0.28 if active else 0.14)
        cr.fill_preserve()
        cr.set_line_width(2)
        cr.set_source_rgba(*(ACCENT if self.drop == ("plus",) else (1, 1, 1)), 0.8 if active else 0.35)
        cr.stroke()
        arm = w * 0.22
        cr.set_line_width(max(2, w * 0.06))
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(x + w / 2 - arm, y + h / 2)
        cr.line_to(x + w / 2 + arm, y + h / 2)
        cr.move_to(x + w / 2, y + h / 2 - arm)
        cr.line_to(x + w / 2, y + h / 2 + arm)
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.stroke()

    def _draw_card(self, cr, i, win, rect, ghost=False):
        x, y, w, h = rect
        alpha = 0.85 if ghost else (0.55 if win.minimized else 1.0)
        for k in range(1, 12, 2):                        # sombra
            _rounded(cr, x - k, y - k + 5, w + 2 * k, h + 2 * k, 10 + k)
            cr.set_source_rgba(0, 0, 0, 0.035 * (1 - k / 12) * alpha)
            cr.fill()
        pb = self.thumbs.get(win.xid)
        if pb is not None:
            self._paint_image(cr, pb, x, y, w, h, 8, alpha)
        else:
            _rounded(cr, x, y, w, h, 8)
            cr.set_source_rgba(0.16, 0.17, 0.24, 0.92 * alpha)
            cr.fill()
            self._paint_icon(cr, win.icon, x + w / 2, y + h / 2, min(w, h) * 0.35, alpha)
        highlighted = not ghost and (self.hover == ("card", i) or self.sel == i)
        if highlighted:
            _rounded(cr, x - 2, y - 2, w + 4, h + 4, 10)
            cr.set_line_width(4)
            cr.set_source_rgb(*ACCENT)
            cr.stroke()
        # ícono de la app, montado sobre el borde inferior
        isz = max(28, min(52, h * 0.22))
        self._paint_icon(cr, win.icon, x + w / 2, y + h, isz, alpha)
        if highlighted:
            title = win.title + ("  · minimizada" if win.minimized else "")
            lay = self._font(cr, title, max(12, self.H * 0.013), bold=True, max_w=max(w, 260))
            tw, th = lay.get_pixel_size()
            bx, by = x + (w - tw) / 2 - 10, y + h + isz / 2 + 6
            _rounded(cr, bx, by, tw + 20, th + 8, (th + 8) / 2)
            cr.set_source_rgba(0, 0, 0, 0.6)
            cr.fill()
            cr.move_to(bx + 10, by + 4)
            cr.set_source_rgb(1, 1, 1)
            PangoCairo.show_layout(cr, lay)

    def render_png(self, path):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.W, self.H)
        self.draw(cairo.Context(surf))
        surf.write_to_png(path)


class Overlay:
    """La ventana a pantalla completa que muestra la View y maneja mouse y teclado."""

    def __init__(self, thumbs):
        self.view = View(thumbs)
        self.thumbs = thumbs
        thumbs.on_update = self._thumb_updated
        self.visible = False
        self._press = None

        self.win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.win.set_title("MissionTab")
        self.win.set_decorated(False)
        self.win.set_skip_taskbar_hint(True)
        self.win.set_skip_pager_hint(True)
        self.win.set_keep_above(True)
        self.win.set_app_paintable(True)
        self.area = Gtk.DrawingArea()
        self.area.set_can_focus(True)
        self.area.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_PRESS_MASK
                             | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
                             | Gdk.EventMask.KEY_PRESS_MASK)
        self.area.connect("draw", self._safe(lambda _w, cr: (self.view.draw(cr), True)[1]))
        self.area.connect("motion-notify-event", self._safe(self._motion))
        self.area.connect("button-press-event", self._safe(self._press_cb))
        self.area.connect("button-release-event", self._safe(self._release))
        self.win.connect("key-press-event", self._safe(self._key))
        self.win.connect("delete-event", lambda *_: (self.hide(), True)[1])
        self.win.add(self.area)
        self.win.realize()
        self.xid = self.win.get_window().get_xid()
        thumbs.ignore.add(self.xid)

    def _safe(self, fn):
        """Un error en un evento nunca debe dejar la pantalla tapada: se registra y se cierra la vista."""
        def wrapper(*a):
            try:
                return fn(*a)
            except Exception as e:
                import traceback
                log.write("ERROR: " + traceback.format_exc())
                print("missiontab:", e, flush=True)
                self.hide()
                return True
        return wrapper

    def _now(self):
        return GdkX11.x11_get_server_time(self.win.get_window())

    # --- mostrar / ocultar -----------------------------------------------------------------------------

    def toggle(self):
        self.hide() if self.visible else self.show()

    def show(self):
        display = Gdk.Display.get_default()
        _, px, py = display.get_default_seat().get_pointer().get_position()
        monitor = display.get_monitor_at_point(px, py) or display.get_primary_monitor()
        geo = monitor.get_geometry()
        v = self.view
        v.W, v.H = geo.width, geo.height
        v.hover = v.drag = v.drop = None
        v.sel = 0
        v.load(ignore={self.xid})
        v.sel = 1 if len(v.cards) > 1 else (0 if v.cards else None)   # como Alt+Tab: la anterior
        self.thumbs.request(self.thumbs.visible_xids({self.xid}))      # refrescar las visibles
        self.win.move(geo.x, geo.y)
        self.win.resize(geo.width, geo.height)
        self.visible = True
        self.win.show_all()
        self.win.fullscreen()
        self.win.present_with_time(self._now())
        self.area.grab_focus()
        log.write(f"show: {len(v.spaces)} escritorios, {len(v.cards)} ventanas en el {v.cur + 1}")

    def hide(self):
        import traceback
        log.write("hide desde: " + " < ".join(f"{f.name}:{f.lineno}" for f in traceback.extract_stack()[-4:-1]))
        self.visible = False
        self.view.drag = self.view.drop = None
        self._press = None
        self.win.hide()

    def reload(self, delay=250):
        def go():
            if self.visible:
                self.view.load(ignore={self.xid})
                self.area.queue_draw()
            return False
        GLib.timeout_add(delay, go)

    def _thumb_updated(self, _xid):
        if self.visible and not self.view.drag:
            self.view.compute()
            self.area.queue_draw()

    # --- acciones ------------------------------------------------------------------------------------

    def _go_window(self, i, ts):
        win = self.view.cards[i][0]
        self.hide()
        model.activate(win, ts or self._now())

    def _go_space(self, i, ts):
        self.hide()
        model.switch(i, ts or self._now())

    def _switch_live(self, delta):
        v = self.view
        i = v.cur + delta
        if 0 <= i < len(v.spaces):
            model.switch(i, self._now())
            v.cur = i
            v.sel = 0
            v.compute()
            self.area.queue_draw()
            self.thumbs.refresh_visible(350)   # las de ese escritorio ya están mapeadas (detrás de la vista)
            self.reload(300)

    # --- mouse ---------------------------------------------------------------------------------------

    def _motion(self, _w, ev):
        v = self.view
        if self._press and self._press[0] and self._press[0][0] == "card":
            if not v.drag and math.hypot(ev.x - self._press[1], ev.y - self._press[2]) > DRAG_THRESHOLD:
                v.drag = {"card": self._press[0][1], "moving": True}
            if v.drag:
                v.drag["x"], v.drag["y"] = ev.x, ev.y
                h = v.hit(ev.x, ev.y)
                v.drop = h if h and h[0] in ("space", "plus") else None
                self.area.queue_draw()
                return True
        h = v.hit(ev.x, ev.y)
        if h != v.hover:
            v.hover = h
            self.area.queue_draw()
        return True

    def _press_cb(self, _w, ev):
        if ev.button == 1:
            self._press = (self.view.hit(ev.x, ev.y), ev.x, ev.y)
        return True

    def _release(self, _w, ev):
        v = self.view
        if ev.button != 1 or self._press is None:
            return True
        target = self._press[0]
        self._press = None
        if v.drag:                                     # soltar un arrastre
            win = v.cards[v.drag["card"]][0]
            drop = v.drop
            v.drag = v.drop = None
            if drop and drop[0] == "space" and drop[1] != win.space:
                model.move(win, drop[1])
                log.write(f"mover {win.xid:#x} al escritorio {drop[1] + 1}")
                self.reload()
            elif drop and drop[0] == "plus":
                model.add_space(then=lambda idx: (model.move(win, idx), self.reload(150)))
            self.area.queue_draw()
            return True
        if target is None:
            self.hide()                                # clic en el fondo: salir
        elif target[0] == "card":
            self._go_window(target[1], ev.time)
        elif target[0] == "space":
            self._go_space(target[1], ev.time)
        elif target[0] == "close":
            model.remove_space(target[1], ev.time)
            v.hover = None
            self.reload(400)
        elif target[0] == "plus":
            model.add_space(then=lambda _i: self.reload(50))
        return True

    # --- teclado -------------------------------------------------------------------------------------

    def _key(self, _w, ev):
        v = self.view
        key = Gdk.keyval_name(ev.keyval) or ""
        ctrl = bool(ev.state & Gdk.ModifierType.CONTROL_MASK)
        n = len(v.cards)
        if key == "Escape":
            self.hide()
        elif key in ("Return", "KP_Enter", "space") and v.sel is not None and n:
            self._go_window(v.sel, ev.time)
        elif ctrl and key in ("Left", "Right"):
            self._switch_live(-1 if key == "Left" else 1)
        elif key in ("Left", "Right", "Tab", "ISO_Left_Tab") and n:
            back = key in ("Left", "ISO_Left_Tab")
            v.sel = ((v.sel or 0) + (-1 if back else 1)) % n
        elif key in ("Up", "Down") and n:
            v.sel = self._vertical(v.sel or 0, -1 if key == "Up" else 1)
        elif key.isdigit() and key != "0" and int(key) <= len(v.spaces):
            self._go_space(int(key) - 1, ev.time)
        self.area.queue_draw()
        return True

    def _vertical(self, i, direction):
        """La tarjeta más cercana en la fila de arriba/abajo."""
        cards = self.view.cards
        x, y, w, h = cards[i][1]
        cx, cy = x + w / 2, y + h / 2
        best, best_d = i, None
        for j, (_, (x2, y2, w2, h2)) in enumerate(cards):
            dy = (y2 + h2 / 2 - cy) * direction
            if dy <= 1:
                continue
            d = dy * 3 + abs(x2 + w2 / 2 - cx)
            if best_d is None or d < best_d:
                best, best_d = j, d
        return best
