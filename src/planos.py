"""Encuadres y movimientos de cámara sobre una fuente continua."""

import math
from functools import lru_cache

from PIL import Image


@lru_cache(maxsize=32)
def parse(text, duration):
    if not isinstance(text, str):
        raise ValueError('Los planos de cámara deben estar escritos en una línea.')
    shots = []
    for entry in text.split(';') if text.strip() else ():
        try:
            interval, *fields = entry.split(',')
            start, end = map(float, interval.split('-'))
            z0, x0, y0, z1, x1, y1 = map(float, fields)
        except ValueError:
            raise ValueError('Escribe cada plano como inicio-fin,z0,x0,y0,z1,x1,y1.') from None
        if (not all(math.isfinite(v) for v in (start, end, z0, x0, y0, z1, x1, y1))
                or not 0 <= start < end <= duration
                or (shots and start < shots[-1][1])
                or not all(1 <= z <= 3 for z in (z0, z1))
                or not all(0 <= pos <= 1 for pos in (x0, y0, x1, y1))):
            raise ValueError('Ordena los planos sin superponerlos. Usa zoom de 1 a 3 y posiciones de 0 a 1.')
        shots.append((start, end, z0, x0, y0, z1, x1, y1))
    return tuple(shots)


def frame(image, time, shots):
    for start, end, z0, x0, y0, z1, x1, y1 in shots:
        if not start <= time < end:
            continue
        progress = (time - start) / (end - start)
        ease = progress * progress * (3 - 2 * progress)
        zoom = z0 + (z1 - z0) * ease
        if zoom == 1:
            return image
        x, y = x0 + (x1 - x0) * ease, y0 + (y1 - y0) * ease
        w, h = image.size
        crop_w, crop_h = w / zoom, h / zoom
        left = min(w - crop_w, max(0, w * x - crop_w / 2))
        top = min(h - crop_h, max(0, h * y - crop_h / 2))
        return image.resize((w, h), Image.Resampling.BICUBIC,
                            box=(left, top, left + crop_w, top + crop_h))
    return image
