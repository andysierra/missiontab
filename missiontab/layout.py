"""Mosaico estilo Exposé: acomoda N ventanas (respetando su proporción) en un área, lo más grandes posible."""
import math


def grid(aspects, x, y, width, height, gap=28, max_h=None):
    """aspects: [ancho/alto]. Devuelve [(x, y, w, h)] en el mismo orden. Prueba todas las cantidades de filas
    (orden de aparición, filas contiguas) y se queda con la que más área total ocupa."""
    n = len(aspects)
    if n == 0:
        return []
    best, best_area = None, -1
    for rows in range(1, n + 1):
        per = math.ceil(n / rows)
        chunks = [list(range(i, min(i + per, n))) for i in range(0, n, per)]
        row_h = (height - gap * (len(chunks) - 1)) / len(chunks)
        if max_h:
            row_h = min(row_h, max_h)
        if row_h <= 20:
            break
        placed, area = [], 0
        for chunk in chunks:
            total = sum(aspects[i] for i in chunk) * row_h + gap * (len(chunk) - 1)
            h = row_h * min(1.0, width / total)
            placed.append((chunk, h))
            area += sum(aspects[i] * h * h for i in chunk)
        if area > best_area:
            best, best_area = placed, area
    # centrar: filas en vertical, tarjetas de cada fila en horizontal
    total_h = sum(h for _, h in best) + gap * (len(best) - 1)
    cy = y + (height - total_h) / 2
    rects = [None] * n
    for chunk, h in best:
        row_w = sum(aspects[i] * h for i in chunk) + gap * (len(chunk) - 1)
        cx = x + (width - row_w) / 2
        for i in chunk:
            w = aspects[i] * h
            rects[i] = (cx, cy, w, h)
            cx += w + gap
        cy += h + gap
    return rects
