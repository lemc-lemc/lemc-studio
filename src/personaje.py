"""Capa de personaje con transparencia, trayectoria y animación de sprite."""

import math
from bisect import bisect_right
from pathlib import Path

from PIL import Image, ImageOps


def keyframes(text, duration):
    if not isinstance(text, str):
        raise ValueError('Escribe la trayectoria del personaje en una línea.')
    points = []
    for entry in text.split(';') if text.strip() else ():
        try:
            time, x, y, scale, angle = map(float, entry.split(','))
        except ValueError:
            raise ValueError('Cada marca del personaje usa segundo,x,y,tamaño,giro.') from None
        if (not all(math.isfinite(v) for v in (time, x, y, scale, angle))
                or not 0 <= time <= duration or (points and time <= points[-1][0])
                or not 0 <= x <= 1 or not 0 <= y <= 1 or not .02 <= scale <= 1.5 or not -360 <= angle <= 360):
            raise ValueError('Ordena los tiempos. Usa x e y de 0 a 1, tamaño de 0.02 a 1.5 y giro de -360 a 360.')
        points.append((time, x, y, scale, angle))
    return tuple(points)


class Character:
    def __init__(self, data):
        self.marks = keyframes(data['movimiento_personaje'], data['duracion']) or ((0, .5, .62, .38, 0),)
        self.times = tuple(mark[0] for mark in self.marks)
        self.sway = data['balanceo_personaje']
        self.sprites = []
        self.ends = []
        path = Path(data['archivo_personaje'])
        total = 0
        decoded_pixels = 0
        try:
            with Image.open(path) as source:
                count = getattr(source, 'n_frames', 1)
                first = int(count > 1 and bool(source.info.get('default_image', False)))
                for index in range(first, count):
                    source.seek(index)
                    sprite = ImageOps.exif_transpose(source).convert('RGBA')
                    sprite.thumbnail((1080, 1080), Image.Resampling.LANCZOS)
                    decoded_pixels += sprite.width * sprite.height
                    if decoded_pixels > 24_000_000:
                        raise ValueError('El sprite animado es demasiado grande. Reduce su resolución o sus fotogramas.')
                    total += max(.01, float(source.info.get('duration', 100)) / 1000)
                    self.ends.append(total)
                    self.sprites.append(sprite)
        except OSError as error:
            raise ValueError(f'No se pudo abrir el personaje «{path.name}».') from error
        if not self.sprites or all(sprite.getchannel('A').getextrema() == (255, 255) for sprite in self.sprites):
            raise ValueError('El personaje necesita un PNG, APNG o WebP con transparencia.')

    def composite(self, image, time):
        mark = bisect_right(self.times, time)
        first = self.marks[max(0, mark - 1)]
        last = self.marks[min(mark, len(self.marks) - 1)]
        progress = (time - first[0]) / (last[0] - first[0]) if last[0] > first[0] else 0
        eased = progress * progress * (3 - 2 * progress)
        x, y, size, angle = (a + (b - a) * eased for a, b in zip(first[1:], last[1:]))
        if self.sway:
            pulse = math.sin(math.tau * time / 2.4)
            y += .012 * pulse
            angle += 3.6 * math.sin(math.tau * time / 3.2)
        sprite = self.sprites[bisect_right(self.ends, time % self.ends[-1])]
        width = max(1, round(image.width * size))
        height = max(1, round(width * sprite.height / sprite.width))
        sprite = sprite.resize((width, height), Image.Resampling.LANCZOS)
        if angle:
            sprite = sprite.rotate(angle, Image.Resampling.BICUBIC, expand=True)
        mode = image.mode
        background = image.convert('RGBA')
        background.alpha_composite(sprite, (round(x * image.width - sprite.width / 2),
                                            round(y * image.height - sprite.height / 2)))
        return background if mode == 'RGBA' else background.convert(mode)
