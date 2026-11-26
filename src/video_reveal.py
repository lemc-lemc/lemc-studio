"""Reveal the original video while keeping the ASCII composition editable."""

import math
from colorsys import hsv_to_rgb
from dataclasses import replace

import numpy as np
from PIL import Image, ImageDraw

import ascii_art


SIZE = (ascii_art.WIDTH, ascii_art.HEIGHT)
HUE_ANGLES = np.arange(256) * (math.tau / 256)
HUE_VECTORS = np.exp(1j * HUE_ANGLES)


def enabled(data):
    return data['fuente'] == 'Video' and (bool(data.get('tramos_original', '').strip()) or data['fin_ascii'] is not None)


class VideoReveal:
    def __init__(self, data, font):
        self.data = data
        self.ranges = ascii_art.original_ranges(data['tramos_original'], data['duracion'])
        self.ascii = ascii_art.prepare(data | {'solo_video': True, 'codigo': False}, font)
        self.panel = None
        if data['codigo'] and not data['solo_video']:
            self.panel = ascii_art.prepare(data | {'lienzo_original': True, 'solo_video': False}, font)
        self.overlay_key = None
        self.layers = ()
        self.scene_hue = None

    def amount(self, time):
        duration = self.data['fundido_video']
        if self.ranges:
            for start, end in self.ranges:
                if not start <= time < end:
                    continue
                if not duration:
                    return 1
                toward_original = (time - start) / duration if start else 1
                toward_ascii = (end - time) / duration if end < self.data['duracion'] else 1
                return min(1, toward_original, toward_ascii)
            return 0
        start = self.data['fin_ascii']
        if time < start:
            return 0
        return min(1, (time - start) / duration) if duration else 1

    def frame(self, time, original):
        amount = self.amount(time)
        original = original if original.mode == 'RGB' else original.convert('RGB')
        if amount < 1:
            source = original.resize(SIZE, Image.Resampling.LANCZOS).convert('RGBA')
            image = ascii_art.scene_frame(time, self.ascii, source)
            image = image.resize(original.size, Image.Resampling.LANCZOS)
            if amount > 0:
                luma = original.resize((180, 320), Image.Resampling.BILINEAR).convert('L')
                level = [round(255 * min(1, max(0, amount * 1.45 - .45 * (1 - value / 255))) ** .92)
                         for value in range(256)]
                mask = luma.point(level).resize(original.size, Image.Resampling.BILINEAR)
                image = Image.composite(original, image, mask)
        else:
            image = original
        if self.panel is not None and (amount < 1 or self.data['mantener_codigo']):
            image = image.copy() if image is original else image
            for position, layer in self.overlay(time, original):
                image.paste(layer, position, layer)
        return image

    def panel_for_frame(self, original, tick):
        if not self.data.get('panel_reactivo'):
            return self.panel
        hues, saturation, brightness = np.asarray(
            original.resize((42, 74), Image.Resampling.BOX).convert('HSV')
        ).reshape(-1, 3).T
        weights = (saturation / 255.) ** 1.6 * (brightness / 255.) ** 2.4
        if self.overlay_key is None or not 0 <= tick - self.overlay_key[0] <= 5:
            self.scene_hue = None
        if weights.sum() > 4:
            spectrum = np.bincount(hues, weights=weights, minlength=256)
            candidates = spectrum.reshape(16, 16).sum(axis=1)
            window = candidates + .7 * (np.roll(candidates, 1) + np.roll(candidates, -1))
            center = int(window.argmax()) * 16 + 8
            nearby = np.abs((np.arange(256) - center + 128) % 256 - 128) <= 32
            accent = np.dot(spectrum[nearby], HUE_VECTORS[nearby])
            if abs(accent):
                accent /= abs(accent)
                self.scene_hue = accent if self.scene_hue is None else .80 * self.scene_hue + .20 * accent
        if self.scene_hue is None:
            return self.panel
        hue = np.angle(self.scene_hue) / math.tau % 1

        def tint(saturation, brightness):
            return '#{:02x}{:02x}{:02x}'.format(
                *(round(channel * 255) for channel in hsv_to_rgb(hue, saturation, brightness))
            )

        theme = replace(self.panel['theme'], panel=tint(.64, .18), border=tint(.67, .67),
                        keyword=tint(.43, .99), active=tint(.63, .34))
        return self.panel | {'theme': theme}

    def overlay(self, time, original):
        # Updating at video-source cadence avoids drawing the same characters twice at 60 fps.
        size = original.size
        key = int(time * 30 + 1e-7), size
        if key == self.overlay_key:
            return self.layers
        panel = self.panel_for_frame(original, key[0])
        time = key[0] / 30
        dark = Image.new('RGB', SIZE, 'black')
        light = Image.new('RGB', SIZE, 'white')
        safe = self.data['margen_tiktok']
        header_y = 170 if safe else 51
        for base in (dark, light):
            draw = ImageDraw.Draw(base)
            sign = self.data['firma_ascii']
            draw.text((42, header_y), sign or 'VIDEO / ASCII',
                      font=self.panel['signature'] if sign else self.panel['label'],
                      fill=self.panel['gold'], anchor='lm')
            draw.text((596 if safe else 680, header_y - 3), f'{time:05.2f} s',
                      font=self.panel['mono'], fill=self.panel['gold'], anchor='ra')
            if not safe:
                draw.line((42, 80, 678, 80), fill='#3c5670')
            ascii_art.code_panel(base, panel, min(1, time / self.data['duracion']))
        boxes = ((23, header_y - 26, 696, header_y + 39), (23, 998, 696, 1248))
        layers = []
        for box in boxes:
            # Recover the opacity of the native panel from its rendering over two matte colors.
            low = np.asarray(dark.crop(box), dtype=np.float32)
            high = np.asarray(light.crop(box), dtype=np.float32)
            alpha = np.clip(255 - np.rint((high - low).mean(axis=2)), 0, 255)
            rgb = np.clip(np.rint(low * 255 / np.maximum(alpha[:, :, None], 1)), 0, 255)
            layer = Image.fromarray(np.dstack((rgb, alpha)).astype(np.uint8))
            left, top, right, bottom = (
                round(value * size[axis % 2] / SIZE[axis % 2]) for axis, value in enumerate(box)
            )
            layers.append(((left, top), layer.resize((right - left, bottom - top), Image.Resampling.LANCZOS)))
        self.overlay_key, self.layers = key, tuple(layers)
        return self.layers
