"""An animated ASCII seascape built from character cells."""
from functools import lru_cache
import os
from math import sin, tau

import numpy as np
from PIL import Image, ImageDraw

NAME = 'El caballero del faro'
SIZE = (540, 960)
COLS, ROWS = 90, 80
CELL_W, CELL_H = 6, 12
IGNITION = 20
GLYPHS = " .,:;~=-_*+x/|\\()[]<>oO@#%WM^v"
KNIGHT = (
    "       /^\\",
    "      /###\\",
    "      [===]",
    "       |#|",
    "     /[###]\\",
    "    /@|###|@\\",
    "    @ |###| [<>]",
    "    @ [###] [<>]",
    "      /===\\  []",
    "     /#/ \\#\\",
    "     []   []",
)
SHIP = ("       |", "      /|", "     /%|", "    /%%|\\", "   /%%%|%\\", "   ========", "    \\____/")


def ease(value):
    value = min(1, max(0, value))
    return value * value * (3 - 2 * value)


class Scene:
    def __init__(self, font, atlas):
        self.mono = font('consola.ttf', 11)
        self.heading = font('consola.ttf', 16)
        self.caption = font('consola.ttf', 12)
        self.signature = font('seguisym.ttf' if os.name == 'nt' else 'georgia.ttf', 15)
        self.atlas = atlas(self.mono, GLYPHS, CELL_W, CELL_H)
        rng = np.random.default_rng(61)
        self.pattern = rng.random((ROWS, COLS))
        self.waves = rng.uniform(0, 1, (145, 4))
        self.rain = rng.uniform(0, 1, (75, 3))
        self.background = self.build_background()
        self.excerpt = (
            'ignition = IGNITION * duration / 35',
            'light = ease((time - ignition) / 1.2)',
            'sweep = sin((time - ignition) * 1.65)',
        )

    def build_background(self):
        image = Image.new('RGB', SIZE, (6, 12, 23))
        draw = ImageDraw.Draw(image)
        for y in range(SIZE[1]):
            glow = max(0, 1 - abs(y - 470) / 440)
            draw.line((0, y, 540, y), (6 + int(5*glow), 12 + int(12*glow), 23 + int(16*glow)))

        for y in range(5, 78):
            for x in range(COLS):
                seed = self.pattern[y, x]
                if y > 42 and seed > .62:
                    self.cell(image, x, y, '~=._'[int(seed*90) % 4], (29, 63, 85))
                elif seed > .89:
                    self.cell(image, x, y, '.,'[int(seed*90) % 2], (25, 44, 64))

        for y in range(9, 24):
            for x in range(10, 38):
                outer = ((x-23)/12)**2 + ((y-16)/6.6)**2
                inner = ((x-27)/11)**2 + ((y-14)/6.4)**2
                if outer < 1 and inner > 1:
                    self.cell(image, x, y, 'o' if outer > .77 else '+', (69, 106, 137))

        self.shape(image, [(0, 42), (13, 33), (23, 38), (35, 29), (57, 44), (89, 45), (89, 49), (0, 48)],
                   ' .:/^', (49, 75, 95))
        self.shape(image, [(52, 58), (61, 44), (69, 41), (81, 43), (89, 51), (89, 63), (64, 63)],
                   '.:/#%', (83, 92, 112))
        self.shape(image, [(0, 57), (9, 54), (18, 58), (23, 63), (13, 73), (0, 74)],
                   ':/#%', (80, 94, 113))
        self.shape(image, [(62, 47), (65, 16), (76, 16), (79, 47)],
                   ':/#%', (111, 123, 139))
        self.shape(image, [(64, 17), (64, 11), (67, 11), (67, 14), (70, 14), (70, 10),
                           (73, 10), (73, 14), (76, 14), (76, 11), (78, 11), (78, 17)],
                   ':#%', (129, 140, 153))
        self.shape(image, [(0, 53), (21, 51), (42, 46), (62, 43), (65, 48), (39, 54), (0, 61)],
                   ':o#%', (108, 111, 134))
        for x in range(0, 64):
            y = round(54 - x*.17)
            self.cell(image, x, y, '=' if x % 5 else '+', (140, 155, 178))
            if x % 5 == 0:
                self.cell(image, x, y-1, '|', (123, 144, 168))
        for y in range(23, 44):
            x = round(77 - .6*(y-23))
            self.cell(image, x, y, '=', (150, 162, 176))
            self.cell(image, x+1, y-1, '|', (90, 124, 149))
        return image

    @lru_cache(maxsize=1024)
    def tile(self, glyph, color):
        mask = Image.fromarray(self.atlas[GLYPHS.index(glyph)])
        tile = Image.new('RGB', mask.size, color)
        return tile, mask

    def cell(self, image, x, y, glyph, color):
        tile, mask = self.tile(glyph, color)
        image.paste(tile, (round(x * CELL_W), round(y * CELL_H)), mask)

    def shape(self, image, points, symbols, color):
        mask = Image.new('1', (COLS, ROWS))
        ImageDraw.Draw(mask).polygon(points, fill=1)
        for y, x in np.argwhere(np.asarray(mask)):
            seed = self.pattern[y, x]
            tint = tuple(round(ch * (.47 + .53*seed)) for ch in color)
            self.cell(image, x, y, symbols[min(len(symbols)-1, int(seed*len(symbols)))], tint)

    def sprite(self, image, sprite, x, y, color, stride=0):
        for row, line in enumerate(sprite):
            sway = stride if row >= len(sprite)-2 else 0
            for col, glyph in enumerate(line):
                if glyph != ' ':
                    self.cell(image, x+col+sway, y+row, glyph, color)

    def frame(self, time, data):
        duration = data['duracion']
        position = time * 35 / duration
        image = self.background.copy()
        ignition = IGNITION * duration / 35
        light = ease((time - ignition) / 1.2)
        sweep = sin((time - ignition) * 1.65)
        lightning = max(0, 1 - abs(position - 14.25) / .26)
        if lightning:
            image = Image.blend(image, Image.new('RGB', SIZE, (165, 193, 221)), .24 * lightning)
        ship_x = 6 + 26*ease((position-19)/16)
        ship_y = 59 + .32*sin(time*2.2)
        self.sprite(image, SHIP, ship_x, ship_y, (127, 151, 169) if position < 20 else (195, 160, 119))

        for a, b, c, d in self.waves:
            x = (a * 92 + time*(1.3 + d*3)) % 92 - 1
            y = 62 + b * 17 + .33*sin(time*2+c*20)
            reflection = light * max(0, 1-abs(x-(68+sweep*15))/21)
            color = (int(60+110*reflection), int(111+31*reflection), int(141-55*reflection))
            self.cell(image, x, y, '~' if c < .7 else '=', color)

        if light:
            glow = Image.new('RGBA', (90, 160))
            draw = ImageDraw.Draw(glow)
            tip = 34 + sweep * 10
            draw.polygon([(72, 27), (0, tip-5), (0, tip+10)], fill=(200, 130, 49, int(26*light)))
            draw.polygon([(72, 27), (0, tip), (0, tip+3)], fill=(245, 173, 69, int(34*light)))
            glow = glow.resize(SIZE, Image.Resampling.BILINEAR)
            image.paste(glow, (0, 0), glow)
            for a, b, c, _ in self.waves:
                x = 72 - a * (76 - sweep * 18)
                y = 14 + a * (7 + sweep * 7) + (b-.5) * (1+a*12)
                power = light * (1-a*.65)
                self.cell(image, x, y, '.' if c < .7 else '-', (int(240*power), int(175*power), int(85*power)))
            for row in range(11, 15):
                for col in range(68, 75):
                    self.cell(image, col, row, '*+o#'[int(time*9+row+col) % 4], (255, 206, 113))
        for a, b, c in self.rain if data['particulas'] else ():
            if b > .6 or position < 20:
                self.cell(image, (a*90-time*4) % 90, (b*80+time*12) % 80,
                          '/' if c > .5 else '.', (44, 72, 100))

        crossing = ease(position / 12)
        climbing = ease((position - 12) / 8)
        x = 1 + 52*crossing + 3*climbing
        y = 42 - 9*crossing - 20*climbing
        walking = sin(time*10) if .4 < position < 19.8 else 0
        for i in range(7):
            self.cell(image, x+5-i*.69, y+4+i*.58+.5*sin(time*5-i),
                      '<' if i%2 else '/', (173, 67, 92))
        self.sprite(image, KNIGHT, x, y + abs(walking)*.23, (201, 212, 219), round(walking))

        if data['codigo']:
            self.panel(image, data, light, time)
        return image

    def panel(self, image, data, light, time):
        overlay = Image.new('RGBA', (488, 103))
        draw = ImageDraw.Draw(overlay)
        if not data['panel_reactivo']:
            light = 0
        edge = (int(94+126*light), int(166+16*light), int(201-94*light))
        fill = (int(12+45*light), int(26+8*light), int(46-25*light))
        opacity = round(data['opacidad_panel'] * 2.55)
        draw.rounded_rectangle((0, 0, 487, 102), radius=8,
                               fill=(*fill, opacity), outline=(*edge, 210))
        draw.text((13, 10), data['archivo_panel'], font=self.heading, fill=(*edge, 255))
        draw.text((411, 12), f'{time:05.2f}s', font=self.caption, fill=(217, 226, 234, 255))
        for i, line in enumerate(self.excerpt):
            draw.text((15, 36 + 16*i), line, font=self.caption, fill=(228, 232, 238, 255))
        if data['firma_ascii']:
            draw.text((420, 76), data['firma_ascii'], font=self.signature, fill=(*edge, 235))
        image.paste(overlay, (19, 826), overlay)


def soundtrack(duration, rate):
    """Original synth score with surf and a downbeat at the beacon cue."""
    t = np.arange(round(duration*rate))/rate
    rng = np.random.default_rng(130)
    tide = rng.normal(0, 1, t.size)
    surf = np.interp(t, t[::45], tide[::45]) * (.021+.013*np.sin(t*1.6))
    music = np.zeros_like(t)
    for start, root in ((0, 55), (5, 46.25), (10, 43.65), (15, 49), (20, 55), (25, 65.41), (30, 58.27)):
        elapsed = np.maximum(0, t-start)
        envelope = np.minimum(1, elapsed/1.1)*np.clip((6.3-elapsed)/1.5, 0, 1)
        for ratio, volume in ((1, .085), (1.5, .034), (2.38, .023)):
            music += envelope*volume*np.sin(tau*root*ratio*t+.3*np.sin(t*2.1))
    for start in (2, 6, 10, 14, 18, 20, 21.5, 23, 25, 27, 29, 31, 33):
        dt = np.maximum(0, t-start)
        music += (t >= start)*np.exp(-dt*5)*(.19 if start == 20 else .09)*np.sin(tau*(46*dt+1.6*(1-np.exp(-dt*20))))
    for i, note in enumerate((440, 523.25, 659.25, 587.33, 523.25, 392)):
        dt = np.maximum(0, t-(20+i*1.5))
        music += .055*np.minimum(1, dt*65)*np.exp(-dt*2)*np.sin(tau*note*dt)
    fade = np.clip(t/.4, 0, 1)*np.clip((duration-t)/1.65, 0, 1)
    return (music + surf)*fade
