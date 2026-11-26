"""Escenas originales de LEMC Studio. Todas las capas nacen de geometría y color."""

from functools import lru_cache
from math import cos, pi, sin, tau
from random import Random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


SIZE = (1080, 1440)
WIDTH, HEIGHT = 360, 480
SILICIO = ('Terminal de medianoche', 'Corazón de silicio', 'La ciudad de las señales',
           'El jardín de los circuitos', 'La quietud del futuro')
NAMES = ('Turno de noche', 'Observatorio de Ío', 'La última cara B',
         'Taller de autómatas', 'El umbral', 'El último andén',
         'Faro de niebla', 'Medusas de medianoche', 'Mar de dunas', 'Escarabajo de cobre', *SILICIO)
Y, X = np.mgrid[:HEIGHT, :WIDTH]
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 - .5
DITHER = np.tile(BAYER, (HEIGHT // 4, WIDTH // 4))


class Scene:
    def __init__(self, seed, ground, *lights):
        self.rng = Random(seed)
        color = np.full((HEIGHT, WIDTH, 3), ground, dtype=np.float32)
        for x, y, w, h, tint in lights:
            falloff = np.exp(-((X - x) / w) ** 2 - ((Y - y) / h) ** 2)
            color += falloff[:, :, None] * tint
        self.image = Image.fromarray(np.clip(color, 0, 255).astype('uint8'))
        self.draw = ImageDraw.Draw(self.image)

    def poly(self, points, color, edge=None):
        self.draw.polygon(points, fill=color, outline=edge)

    def line(self, points, color, width=1):
        self.draw.line(points, fill=color, width=width, joint='curve')

    def ellipse(self, x, y, rx, ry, color, edge=None, width=1):
        self.draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=color, outline=edge, width=width)

    def box(self, bounds, color, edge=None):
        self.draw.rectangle(bounds, fill=color, outline=edge)

    def label(self, xy, text, color, font, size=8):
        self.draw.text(xy, text, fill=color, font=font('consola.ttf', size), anchor='la')

    def dust(self, bounds, n, colors):
        l, t, r, b = bounds
        for _ in range(n):
            x, y = self.rng.randrange(l, r), self.rng.randrange(t, b)
            ink = self.rng.choice(colors)
            if self.rng.random() < .16:
                self.line((x, y, x + self.rng.randrange(1, 5), y), ink)
            else:
                self.draw.point((x, y), fill=ink)

    def glaze(self, x, y, w, h, tint, amount=.35):
        a = np.exp(-((X - x) / w) ** 2 - ((Y - y) / h) ** 2) * amount
        mask = Image.fromarray((255 * a).astype('uint8'))
        self.image.paste(tint, (0, 0, WIDTH, HEIGHT), mask)


def bezier(points, steps=36):
    a, b, c, d = np.asarray(points)
    return [tuple((1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t*t*c + t**3*d)
            for t in np.linspace(0, 1, steps)]


def wire(scene, points, dark, bright, width=4):
    path = bezier(points)
    scene.line(path, dark, width)
    scene.line([(x, y - 1) for x, y in path], bright)


def plane(corners):
    """Map a unit square onto a planar quadrilateral with foreshortening."""
    unit = [(0, 0), (1, 0), (1, 1), (0, 1)]
    system, targets = [], []
    for (u, v), (x, y) in zip(unit, corners):
        system.extend(((u, v, 1, 0, 0, 0, -u*x, -v*x), (0, 0, 0, u, v, 1, -u*y, -v*y)))
        targets.extend((x, y))
    a, b, c, d, e, f, g, h = np.linalg.solve(system, targets)

    def at(u, v):
        z = g*u + h*v + 1
        return ((a*u + b*v + c) / z, (d*u + e*v + f) / z)

    return at


def panel(scene, corners, palette, tiles):
    at = plane(corners)
    scene.poly(corners, palette[0], palette[1])
    for u, v, w, h, color in tiles:
        scene.poly([at(u, v), at(u+w, v), at(u+w, v+h), at(u, v+h)], color)
    return at


def coder(font):
    s = Scene(54321, (9, 13, 28), (225, 211, 106, 100, (23, 59, 63)),
              (38, 117, 92, 146, (37, 20, 34)), (307, 356, 130, 91, (49, 24, 25)))
    # Rain at the window, shelves and the back wall.
    s.box((20, 58, 137, 220), '#352938', '#513545')
    s.box((26, 65, 131, 216), '#142338', '#7a4c55')
    for x in range(29, 130, 7):
        y = s.rng.randrange(166, 211)
        s.box((x, y, x+5, 215), s.rng.choice(('#242945', '#2e304b', '#333751')))
        for yy in range(y+3, 214, 6):
            if s.rng.random() < .35:
                s.line((x+1, yy, x+2, yy), '#8a6666')
    for _ in range(280):
        x, y = s.rng.randrange(27, 130), s.rng.randrange(67, 215)
        s.line((x, y, x-1, y+s.rng.randrange(1, 8)), s.rng.choice(('#21384b', '#324354', '#3b4658')))
    s.box((78, 64, 83, 216), '#462f3d')
    s.box((26, 137, 132, 141), '#45323f')
    s.poly([(16, 215), (138, 215), (145, 222), (13, 224)], '#573a46')
    s.line((8, 36, 346, 37, 343, 260), '#2d2b3c', 2)
    for y in (85, 122):
        s.poly([(259, y), (359, y-6), (359, y+4), (259, y+8)], '#362b3f')
        s.line((259, y, 359, y-6), '#59414d')
    for i in range(15):
        x = 267 + i * 5
        h = s.rng.randrange(14, 30)
        s.box((x, 82-h, x+3, 82), s.rng.choice(('#744e55', '#495268', '#554453', '#705d65')))
        s.line((x, 77, x+3, 77), '#99756c')
    s.dust((148, 48, 359, 238), 1300, ('#292738', '#26323d', '#343041'))
    # Desk and CRT casing, aligned along the same diagonal.
    s.poly([(0, 294), (238, 239), (359, 283), (359, 429), (0, 448)], '#3b2934')
    s.poly([(0, 298), (237, 240), (359, 284), (359, 347), (107, 437), (0, 400)], '#6f4147')
    s.poly([(0, 316), (242, 260), (358, 289), (341, 333), (115, 406), (0, 369)], '#81554e')
    for _ in range(1040):
        x, y = s.rng.randrange(360), s.rng.randrange(263, 422)
        if 307 - .24*x < y < 415 - .19*x:
            s.line((x, y, x+4, y-1), s.rng.choice(('#6f4848', '#98665a', '#765151', '#5f4050')))
    s.line((103, 438, 359, 348), '#ae705b', 3)
    s.ellipse(229, 294, 82, 16, '#543c41')
    s.poly([(176, 267), (232, 250), (284, 270), (275, 289), (212, 307), (174, 291)], '#34383f', '#272e37')
    s.poly([(174, 275), (239, 257), (283, 270), (212, 294)], '#717269', '#8f8e73')
    s.poly([(145, 149), (196, 130), (296, 147), (318, 163), (311, 253), (285, 275), (189, 262)], '#49454c', '#222a38')
    s.poly([(145, 149), (197, 130), (296, 147), (307, 160), (218, 149), (183, 165)], '#a08374', '#bf9f81')
    s.poly([(285, 162), (318, 164), (311, 251), (285, 275)], '#5b4b52', '#363542')
    for i in range(10):
        y = 173+i*5
        s.line((290, y+5, 311, y), '#33323e', 2)
        s.line((291, y+7, 310, y+2), '#80636a')
    face = [(149, 151), (287, 161), (285, 274), (145, 250)]
    panel(s, face, ('#79786c', '#9fa38a'), [
        (.025, .03, .948, .91, '#a1a58a'), (.04, .059, .92, .813, '#6c776c'),
        (.068, .087, .87, .755, '#303e41'), (.085, .104, .84, .72, '#1b3038'),
        (.11, .13, .79, .67, '#1c5351'), (.955, .889, .025, .037, '#d7f2b5')])
    glass = plane([(162, 168), (274, 177), (272, 248), (159, 229)])
    for i in range(43):
        v = i / 43
        s.line((glass(0, v), glass(1, v)), ('#215953', '#286961', '#1f514f')[i % 3])
    # Reflections and a boot prompt drawn on the curved glass plane.
    for i in range(14):
        v = .09 + i*.059
        for j in range(40):
            if s.rng.random() < .7 - i*.022:
                u = .07 + j*.0205
                s.line((glass(u, v), glass(u+.013, v)), s.rng.choice(('#388479', '#61a694', '#b6dfae')))
    s.label(glass(.10, .12), '> READY', '#d0f9bf', font, 9)
    s.line((glass(.02, .06), glass(.76, .06)), '#3b8377')
    s.line((glass(.015, .12), glass(.015, .78)), '#408476', 2)
    s.line((glass(.10, .95), glass(.80, .95)), '#163e43', 2)
    s.label((251, 251), 'LEMC', '#354344', font, 7)
    s.glaze(210, 205, 116, 98, '#66c9ad', .16)
    # Keycaps, desk accessories, sleeves and the back of the head.
    keys = [(145, 299), (238, 278), (288, 307), (173, 338)]
    blocks = []
    for row in range(5):
        for col in range(14):
            blocks.append((.027+col*.067, .09+row*.174, .054, .135,
                           s.rng.choice(('#a09f87', '#809382', '#b6b49a', '#737d74'))))
    at = panel(s, keys, ('#404b4c', '#9a9c85'), blocks)
    s.line((at(.04, .98), at(.96, .98)), '#232f39', 3)
    wire(s, [(264, 285), (330, 276), (332, 318), (358, 327)], '#282834', '#886764', 3)
    s.ellipse(314, 335, 14, 7, '#533747')
    s.box((303, 299, 322, 329), '#ae734e')
    s.ellipse(312, 329, 9, 4, '#ac7557')
    s.ellipse(312, 300, 10, 4, '#e2a578', '#f1c08c')
    s.ellipse(313, 300, 7, 2, '#553949')
    s.ellipse(323, 315, 5, 7, None, '#c58965', 2)
    s.poly([(50, 323), (99, 298), (131, 309), (146, 340), (153, 408),
            (128, 479), (0, 479), (0, 379), (18, 345)], '#353044', '#151c30')
    s.poly([(18, 344), (54, 321), (109, 313), (141, 337), (128, 351), (92, 340),
            (71, 354), (32, 367), (9, 404), (0, 408), (0, 379)], '#51445a')
    s.poly([(107, 328), (138, 342), (169, 325), (177, 338), (145, 367),
            (118, 360), (98, 350)], '#575366', '#262a42')
    s.poly([(160, 325), (168, 320), (177, 306), (183, 307), (181, 315), (194, 310),
            (196, 313), (187, 321), (180, 334), (173, 337)], '#b58370', '#82665e')
    s.poly([(101, 286), (130, 288), (126, 317), (114, 329), (89, 313)], '#875f60')
    s.poly([(68, 248), (83, 222), (111, 216), (138, 226), (150, 248), (148, 270),
            (140, 277), (133, 307), (117, 318), (90, 311), (75, 293), (67, 269)], '#252639', '#161c31')
    s.poly([(78, 246), (91, 227), (114, 221), (135, 229), (148, 248), (145, 273),
            (138, 279), (132, 301), (126, 307), (129, 281), (123, 269),
            (115, 257), (96, 250)], '#535260')
    s.poly([(136, 265), (144, 259), (149, 264), (142, 278), (137, 282), (132, 277)], '#c08070')
    s.line([(85, 234), (109, 219), (131, 225), (145, 238), (149, 254)], '#74847b', 2)
    for _ in range(460):
        x, y = s.rng.randrange(72, 146), s.rng.randrange(224, 309)
        if ((x-108)/37)**2 + ((y-266)/44)**2 < .9:
            s.line((x, y, x-2, y+3), s.rng.choice(('#343249', '#423e50', '#5e5965')))
    for points in ([(16, 377), (34, 346), (74, 344), (87, 359)],
                   [(1, 437), (25, 408), (89, 415), (108, 449)],
                   [(48, 479), (42, 451), (77, 414), (112, 423)],
                   [(97, 330), (104, 346), (134, 347), (151, 337)]):
        wire(s, points, '#272739', '#5b4d64', 5)
    s.line([(0, 469), (16, 449), (64, 439), (115, 450), (116, 479)], '#222237', 10)
    s.glaze(196, 254, 63, 88, '#7cb798', .13)
    s.glaze(337, 339, 52, 104, '#e09466', .14)
    return s


def stars(s, n, limit):
    for _ in range(n):
        x, y = s.rng.randrange(WIDTH), s.rng.randrange(limit)
        ink = s.rng.choice(('#625473', '#82729a', '#a58ba8', '#cb9e9d', '#e6c3ac'))
        s.draw.point((x, y), fill=ink)
        if s.rng.random() < .035:
            s.line((x-2, y, x+2, y), '#9b7899')
            s.line((x, y-2, x, y+2), '#d1aeb1')
            s.draw.point((x, y), '#fbe1c7')


def ridges(s, x0, y0, ink):
    points = [(x, y0 + s.rng.randrange(-7, 8) - 16*sin(x/36 + x0) - 9*sin(x/11)) for x in range(-8, 369, 8)]
    s.poly(points + [(360, 480), (0, 480)], ink)
    return points


def astronomy(font):
    s = Scene(5132, (15, 12, 36), (170, 278, 156, 161, (76, 26, 52)),
              (310, 106, 140, 190, (24, 29, 65)), (72, 312, 94, 61, (83, 31, 13)))
    stars(s, 1070, 353)
    for _ in range(1600):
        x = s.rng.randrange(360)
        y = round(.63*x + s.rng.gauss(55, 22))
        if 10 < y < 270:
            s.draw.point((x, y), s.rng.choice(('#59426a', '#674c7a', '#97769f')))
    cx, cy, p = 197, 180, 94
    px, py = (X-cx)/p, (Y-cy)/p
    radial = px*px+py*py
    depth = np.sqrt(np.maximum(0, 1-radial))
    texture = np.sin(py*37 + 2*depth + 1.2*np.sin(px*6+py*9))
    texture += .28*np.sin(py*133 + np.sin(px*15+py*21))
    light = (.78 * depth - .70*px - .28*py).clip(0, 1)
    low = np.array((73, 40, 76))
    high = np.array((253, 182, 123))
    planet = low + (high-low) * (light*.83 + texture*.077 + .06)[..., None]
    planet += ((1-depth)**6 * (.58-.37*px))[..., None] * (39, 33, 39)
    outer = np.exp(-((np.sqrt(radial)-1.005)/.032)**2) * (.62-.34*px)
    s.image.paste('#c599bd', (0, 0, WIDTH, HEIGHT), Image.fromarray((outer.clip(0,1)*255).astype('uint8')))
    angle = -.32

    def ring(a, radius):
        u, v = radius*cos(a), radius*.265*sin(a)
        return cx + u*cos(angle)-v*sin(angle), cy + u*sin(angle)+v*cos(angle)

    def rings(start):
        colors = ('#b9817f', '#f1c29b', '#81618e', '#d68d83', '#e0ac91', '#a17595')
        for i in range(44):
            radius = 111 + i*1.48
            if i not in (3, 4, 13, 14, 15, 26, 38):
                path = [ring(a, radius) for a in np.linspace(start, start+pi, 166)]
                s.line(path, colors[(i*11+i//7) % len(colors)])

    rings(pi)
    s.image.paste(Image.fromarray(np.clip(planet, 0, 255).astype('uint8')), (0, 0),
                  Image.fromarray((radial <= 1).astype('uint8')*255))
    rings(0)
    s.ellipse(76, 110, 12, 12, '#a2809d')
    s.ellipse(80, 108, 12, 12, '#392842')
    s.ellipse(82, 107, 10, 10, '#2a2342')
    for index, ink in enumerate(('#433052', '#312943', '#242237', '#1c1c30', '#161828')):
        points = ridges(s, index*2.33, 322+index*23, ink)
        s.line(points, ('#796079', '#59506a', '#51435a', '#3a384f', '#363246')[index])
    # The dome and open slit sit on the near ridge.
    s.ellipse(104, 407, 51, 45, '#28283a', '#837789', 2)
    s.ellipse(99, 403, 44, 38, '#4a465b')
    s.ellipse(93, 400, 31, 32, '#655365')
    s.poly([(76, 382), (94, 367), (112, 366), (91, 407), (72, 407)], '#262333')
    s.poly([(81, 403), (107, 350), (117, 349), (124, 355), (101, 404)], '#8c6871', '#241f36')
    s.line((87, 398, 111, 351, 117, 352), '#c98e81', 2)
    s.box((52, 408, 155, 437), '#4c3d53', '#282337')
    for x in range(53, 155, 6):
        s.line((x, 412, x, 433), '#6a5163')
    s.box((97, 415, 116, 436), '#292537', '#8d6470')
    s.box((121, 416, 140, 425), '#9d615c', '#bd7e6b')
    s.label((123, 417), 'LEMC', '#f3b381', font, 7)
    s.poly([(0, 457), (71, 430), (130, 435), (167, 426), (215, 439), (355, 423), (359, 479), (0, 479)], '#1a1729')
    s.dust((4, 446, 357, 479), 420, ('#3a2c40', '#54364a', '#685064'))
    s.line([(206, 460), (247, 418), (282, 412), (300, 380), (300, 346)], '#242033', 3)
    s.line((287, 356, 315, 356), '#4a3b55')
    s.glaze(79, 329, 101, 36, '#e09881', .13)
    return s


def music(font):
    s = Scene(426, (13, 24, 44), (92, 129, 110, 157, (102, 35, 43)),
              (284, 225, 110, 178, (42, 82, 75)), (170, 368, 135, 72, (73, 32, 37)))
    # An after-hours record shop. The shelves lead diagonally into the deck.
    for shelf in (146, 201, 250):
        s.poly([(0, shelf-29), (360, shelf), (360, shelf+7), (0, shelf-22)], '#493443')
        s.line([(0, shelf-29), (360, shelf)], '#a55b57')
        for x in range(5, 360, 5):
            y = round(shelf-29+x*.08)
            h = s.rng.randrange(17, 41)
            s.line((x, y-2, x+2, y-h), s.rng.choice(('#6a4156', '#71535b', '#576c6c', '#40384c', '#4b4f66')), 3)
            if x % 4:
                s.line((x+1, y-h+6, x+2, y-h+11), '#a36b6f')
    s.dust((0, 15, 360, 250), 1200, ('#47384f', '#574556', '#525666'))
    s.box((29, 49, 110, 116), '#322b41', '#ae6869')
    s.box((34, 54, 105, 111), '#714b59', '#413348')
    for i in range(11):
        s.ellipse(69, 82, 23-i*2, 23-i*2, None, ('#c67b76', '#db9d85')[i%2])
    s.line((43, 101, 93, 60), '#f3b69b', 2)
    s.poly([(0, 303), (229, 232), (359, 264), (359, 479), (0, 479)], '#57414e')
    s.poly([(0, 330), (239, 247), (359, 277), (359, 437), (248, 479), (0, 479)], '#784953')
    for _ in range(760):
        x, y = s.rng.randrange(360), s.rng.randrange(268, 480)
        if y > 330-.22*x:
            s.line((x, y, x+s.rng.randrange(2, 11), y-2), s.rng.choice(('#6a4352', '#946064', '#a26260', '#543b51')))
    cover = [(20, 253), (123, 219), (146, 289), (39, 332)]
    p = panel(s, cover, ('#a36762', '#d59b80'), [(.07,.08,.86,.78,'#4b3a5d'), (.10,.10,.80,.27,'#e3947b')])
    for i in range(18):
        u = i*.043+.13
        s.line((p(u, .37), p(u+.08, .79)), ('#71617e','#956d81','#ba7c83')[i%3])
    s.label(p(.14, .11), 'CARA B', '#4a304a', font, 10)
    s.poly([(23, 341), (240, 273), (342, 302), (339, 369), (135, 458), (15, 411)], '#292638', '#201e30')
    s.poly([(17, 352), (240, 286), (341, 306), (336, 351), (135, 432), (16, 393)], '#c19680', '#534259')
    at = panel(s, [(16, 348), (239, 275), (340, 304), (135, 410)], ('#6a646f', '#e6b394'),
               [(.035,.06,.93,.88,'#8f7777'), (.07,.08,.84,.78,'#837681')])
    for v in np.linspace(.12, .88, 26):
        s.line((at(.09, v), at(.91, v)), '#786977')
    # Groove geometry shares the perspective of the turntable.
    def groove(radius, start=0, end=tau):
        return [at(.48 + .42*radius*cos(a), .49 + .43*radius*sin(a)) for a in np.linspace(start, end, 156)]

    s.poly(groove(1), '#232638', '#ddd0bd')
    s.poly(groove(.965), '#262539', '#121b31')
    for i, radius in enumerate(np.linspace(.31, .95, 35)):
        s.line(groove(radius), ('#39374d', '#4e455e', '#574c62', '#68576c')[i % 4])
        for a in (1.85, 4.78):
            s.line(groove(radius, a, a+.7), ('#998087', '#b58a88', '#56737b', '#726a81')[i % 4])
    s.poly(groove(.31), '#bd7b73', '#e6bc9f')
    s.line(groove(.23), '#f0b097')
    s.line(groove(.12), '#7d4c67')
    x, y = at(.48, .49)
    s.ellipse(x, y, 3, 2, '#f9d6b2')
    ax, ay = at(.87, .21)
    s.ellipse(ax, ay, 14, 8, '#3e344c', '#d9a48f')
    s.ellipse(ax, ay-2, 9, 5, '#d09580', '#f3c2a1')
    wire(s, [(ax, ay-5), (ax-16, ay-40), (213, 289), (198, 327)], '#3e344c', '#e5b49c', 5)
    s.poly([(192, 322), (203, 323), (203, 332), (191, 334)], '#623f56', '#e08c82')
    for i in range(6):
        x, y = at(.13 + i*.035, .9)
        s.ellipse(x, y, 2, 1, '#f5bea0')
    s.label((153, 411), 'LEMC', '#553a4d', font, 8)
    wire(s, [(285, 374), (357, 358), (342, 441), (274, 479)], '#32283e', '#9c676c', 6)
    s.glaze(32, 188, 76, 114, '#ed8270', .20)
    s.glaze(260, 298, 116, 106, '#79a99a', .12)
    return s


def mechanism(s, x, y, radius):
    s.ellipse(x, y, radius, radius, '#14282e', '#9a946d', 2)
    s.ellipse(x, y, radius*.78, radius*.78, '#4a5b50', '#d3b580')
    for i in range(12):
        a = tau*i/12
        s.line((x+cos(a)*radius*.56, y+sin(a)*radius*.56,
                x+cos(a)*radius*.75, y+sin(a)*radius*.75), '#a5a175', 2)
    s.ellipse(x, y, radius*.43, radius*.43, '#274443', '#759986')
    s.ellipse(x, y, radius*.19, radius*.19, '#d6d2a1')


def robotics(font):
    s = Scene(871, (12, 26, 29), (262, 171, 135, 194, (34, 69, 57)),
              (46, 254, 92, 167, (52, 47, 19)), (166, 352, 150, 111, (58, 70, 32)))
    # Workshop pegboard and silhouettes behind the inspection bench.
    s.poly([(13, 50), (347, 39), (344, 261), (10, 285)], '#283c38', '#4c5748')
    for y in range(58, 264, 8):
        for x in range(19, 346, 8):
            s.ellipse(x, y-x*.033, 1, 1, '#213436', '#3c5146')
    for i in range(5):
        x = 30 + i*13
        s.line((x, 94+i*4, x+5, 151+i*7), '#111e26', 5)
        s.line((x, 94+i*4, x+5, 151+i*7), '#848967', 2)
        s.ellipse(x, 93+i*4, 4, 5, '#283c38', '#838e70', 2)
    s.poly([(34, 72), (79, 67), (81, 79), (36, 84)], '#aa9463')
    for i in range(3):
        x = 283 + i*16
        wire(s, [(x, 98), (x+27, 115), (x+23, 164), (x+1, 147)], '#1d2d32', '#96946b')
    s.poly([(0, 327), (216, 259), (359, 294), (359, 480), (0, 480)], '#514c38')
    s.poly([(0, 355), (216, 285), (359, 311), (359, 399), (94, 480), (0, 480)], '#6b6548')
    for _ in range(1060):
        x, y = s.rng.randrange(360), s.rng.randrange(300, 480)
        if y > 355-x*.2:
            s.line((x, y, x+s.rng.randrange(2, 6), y-1), s.rng.choice(('#57553e', '#8b8053', '#a08a5d', '#766744')))
    s.ellipse(189, 395, 129, 28, '#3e473c')
    wire(s, [(86, 278), (18, 288), (39, 421), (346, 408)], '#232b2a', '#af7c4d', 7)
    wire(s, [(254, 298), (322, 263), (351, 330), (299, 352)], '#202e2e', '#8d8a55', 5)
    # Upper chassis and articulated arms built from facing surfaces and collars.
    s.poly([(113, 257), (155, 233), (216, 230), (267, 271), (260, 369), (234, 393),
            (143, 392), (95, 356)], '#4e6657', '#192e33')
    s.poly([(143, 263), (207, 244), (259, 271), (235, 361), (127, 364)], '#94a27a', '#b4b182')
    s.poly([(235, 361), (259, 271), (266, 289), (259, 361), (235, 386), (141, 391), (127, 364)],
           '#3e584e', '#263d3c')
    s.poly([(144, 276), (203, 258), (242, 279), (222, 343), (143, 346)], '#243a3a', '#f1c183')
    for i in range(9):
        y = 282+i*6
        s.line((149, y+5, 222-i*.55, y), '#55634d')
    for i in range(20):
        x, y = 154 + i%5*13, 304+i//5*8
        s.ellipse(x, y, 2, 1, ('#a5ab74', '#ebaa6c', '#3e6c5f')[i%3])
    s.label((171, 353), 'LEMC', '#293e3d', font, 9)
    s.poly([(96, 272), (119, 281), (105, 327), (76, 356), (58, 345), (67, 323)], '#738467', '#333f37')
    s.poly([(58, 345), (76, 356), (75, 379), (43, 387), (36, 375), (54, 366)], '#536b57', '#b4a170')
    s.poly([(253, 270), (275, 289), (300, 327), (280, 346), (257, 331), (242, 302)], '#6b856e', '#373f36')
    mechanism(s, 102, 281, 24)
    mechanism(s, 267, 295, 21)
    mechanism(s, 284, 341, 13)
    s.box((154, 217, 205, 246), '#2b4341', '#8f956d')
    for y in range(222, 246, 5):
        s.line((155, y, 202, y), '#65735b')
    # Faceplate, side housing, eyes and hand-cut vents.
    s.poly([(101, 143), (138, 116), (223, 119), (261, 149), (255, 215), (226, 240),
            (135, 238), (96, 215)], '#879674', '#202e31')
    s.poly([(101, 143), (138, 116), (223, 119), (246, 138), (153, 138), (117, 157)], '#c0bc8f', '#ddd1a7')
    s.poly([(224, 145), (260, 149), (255, 215), (226, 240), (227, 211)], '#49685e', '#263e3d')
    s.poly([(95, 156), (116, 146), (225, 148), (227, 209), (206, 222), (111, 222),
            (94, 204)], '#304d49', '#c7c795')
    s.poly([(107, 161), (215, 159), (218, 192), (207, 205), (112, 205), (104, 195)], '#193136', '#64837a')
    for x in (132, 186):
        s.ellipse(x, 180, 17, 14, '#365a53', '#688875')
        s.ellipse(x, 180, 12, 10, '#76b193', '#c8d7a2')
        s.ellipse(x, 180, 6, 7, '#20383a')
        s.ellipse(x-2, 177, 2, 2, '#e4e7b2')
    for i in range(13):
        x = 117+i*7
        s.line((x, 211, x+2, 217), '#90a684', 2)
    for y in range(163, 211, 6):
        s.line((236, y+4, 253, y), '#2b4746', 2)
    s.line((154, 122, 149, 86, 138, 72), '#394945', 4)
    s.line((155, 121, 150, 86, 139, 72), '#aaa273')
    s.ellipse(138, 72, 4, 4, '#e39f54', '#efc380')
    s.glaze(162, 175, 94, 51, '#7ab79b', .19)
    for x, y, radius in ((49, 423, 13), (296, 406, 11), (317, 415, 6), (247, 445, 10)):
        mechanism(s, x, y, radius)
    s.poly([(105, 422), (174, 407), (226, 434), (151, 460)], '#a29772', '#d4c28b')
    for i in range(7):
        s.line((121+i*4, 425+i*3, 166+i*4, 415+i*3), '#696d59')
    s.poly([(157, 434), (172, 429), (191, 438), (174, 444)], '#53685b', '#746f5a')
    s.glaze(117, 142, 94, 90, '#e4ce8d', .18)
    s.glaze(256, 256, 76, 114, '#74ac90', .15)
    return s


def arch(x, y, radius, floor):
    lintel = [(x+radius*cos(a), y+radius*sin(a)) for a in np.linspace(pi, tau, 70)]
    return [(x-radius, floor), *lintel, (x+radius, floor)]


def philosophy(font):
    s = Scene(18, (16, 25, 38), (189, 207, 112, 195, (41, 74, 74)),
              (182, 371, 134, 133, (67, 51, 30)), (61, 151, 108, 149, (28, 21, 45)))
    # A vaulted reading room opens onto an apparently unreachable horizon.
    stars(s, 450, 321)
    s.ellipse(186, 186, 29, 29, '#c1b08d')
    s.ellipse(195, 178, 29, 29, '#36545b')
    s.ellipse(198, 173, 26, 25, '#38545e')
    for i, ink in enumerate(('#63746b', '#4c655e', '#3c5956')):
        ridge = [(x, 230+i*11 + 13*sin(x/29+i) + 4*sin(x/9)) for x in range(360)]
        s.poly(ridge+[(360, 330), (0, 330)], ink)
    s.poly([(0, 0), (359, 0), (359, 330), (286, 331), *reversed(arch(179, 162, 91, 324)),
            (74, 330), (0, 330)], '#2a2d42')
    s.poly([(0, 0), (359, 0), (359, 42), (260, 58), (181, 48), (90, 58), (0, 51)], '#1c2339')
    for i in range(15):
        radius = 92 + i*3.7
        s.line(arch(179, 162, radius, 352), ('#635951', '#72634f', '#53534d', '#43434b', '#323b46')[i%5],
               2 if i%3 else 3)
    for a in np.linspace(pi+.08, tau-.08, 22):
        s.line((179+94*cos(a), 162+94*sin(a), 179+151*cos(a), 162+151*sin(a)), '#313946', 2)
    for left in (0, 278):
        s.box((left+12, 174, left+71, 329), '#2a293b', '#53504f')
        for shelf in (225, 271, 317):
            s.line((left+14, shelf, left+70, shelf), '#897559', 3)
            for i in range(11):
                x = left+15+i*5
                h = s.rng.randrange(17, 39)
                s.box((x, shelf-h, x+3, shelf-3), s.rng.choice(('#4a5156', '#705448', '#5c6260', '#926952', '#343d51')))
                s.line((x, shelf-h+4, x+2, shelf-h+4), '#9c8b68')
        for x in (left+5, left+75):
            s.box((x, 153, x+7, 336), '#5d574f', '#827056')
            s.line((x+4, 160, x+4, 322), '#3b3f48', 2)
    s.line([(91, 163), (91, 322), (175, 318)], '#bd9e71', 2)
    s.line([(268, 162), (268, 321), (199, 318)], '#ad956b', 2)
    s.poly([(0, 345), (160, 274), (204, 272), (359, 351), (359, 479), (0, 479)], '#3e4649')
    for i in range(12):
        y = 280+i*3+i*i*.76
        l, r = 172-i*12, 197+i*13
        s.poly([(l, y), (r, y), (r+4, y+4+i*.5), (l-4, y+4+i*.5)], '#816e59')
        s.line((l, y, r, y), ('#cfaa79', '#9f8868', '#bca179')[i%3])
        s.line((l-3, y+4+i*.5, r+4, y+4+i*.5), '#333b43', 2)
    for x in range(-310, 700, 61):
        s.line((186+(x-186)*.038, 274, x, 479), '#5f584f')
    for _ in range(650):
        x, y = s.rng.randrange(360), s.rng.randrange(302, 480)
        if abs(x - 184) < (y - 272)*.83:
            s.draw.point((x, y), fill=s.rng.choice(('#655a4f', '#57554f', '#a08665', '#4a4d4c')))
    s.glaze(185, 315, 101, 120, '#b39c70', .20)
    # A reader at the threshold casts a long shadow down the stairs.
    s.poly([(170, 330), (197, 334), (167, 388), (129, 429), (98, 430), (128, 388)], '#343542')
    s.poly([(174, 268), (191, 268), (201, 297), (197, 336), (171, 334), (169, 309),
            (163, 292)], '#29323e', '#172531')
    s.poly([(175, 272), (189, 271), (196, 292), (194, 319), (184, 322), (177, 304)], '#5b5d55')
    s.poly([(165, 290), (172, 285), (183, 300), (199, 291), (204, 297), (186, 311), (174, 309)],
           '#444b50', '#222b38')
    s.ellipse(182, 259, 10, 13, '#41494d', '#c0a17c')
    s.ellipse(180, 257, 8, 10, '#292e3d')
    s.poly([(192, 291), (203, 286), (207, 290), (198, 297)], '#c9ad86')
    # Open book in the foreground, illuminated by the view through the arch.
    s.poly([(0, 427), (56, 404), (115, 422), (155, 412), (225, 440), (233, 479), (0, 479)], '#302e3c')
    s.poly([(13, 433), (58, 416), (112, 432), (151, 422), (204, 445), (181, 471),
            (111, 455), (75, 471), (14, 452)], '#958467', '#c0a27b')
    s.poly([(17, 431), (58, 414), (112, 429), (151, 420), (204, 442), (180, 466),
            (111, 451), (75, 465), (17, 449)], '#c2a785', '#d7ba8b')
    s.line((112, 430, 111, 451), '#776755', 2)
    for i in range(5):
        s.line((29-i, 432+i*3, 72-i, 421+i*4, 101, 432+i*3), '#927b60')
        s.line((120, 433+i*3, 151, 426+i*4, 185-i, 441+i*3), '#927b60')
    s.label((158, 444), 'LEMC', '#725f4e', font, 7)
    s.dust((25, 17, 345, 57), 340, ('#353447', '#464153', '#514854'))
    s.glaze(187, 252, 64, 89, '#d0b67f', .12)
    return s


def night_train(font):
    s = Scene(334, (8, 19, 27), (181, 241, 122, 107, (41, 65, 55)),
              (318, 164, 109, 148, (76, 41, 28)))
    horizon = (175, 254)
    s.poly([(0, 5), (360, 3), (360, 105), horizon, (0, 91)], '#1b3541')
    for i in np.linspace(0, 1, 14) ** 2:
        left, right = (175 - 202*i, 254 - 254*i), (175+202*i, 254-254*i)
        s.line([left, (175, 223-224*i), right], '#4b6c72', max(1, round(5*i)))
        s.line([left, (175, 226-224*i), right], '#243d46', max(1, round(7*i)))
    for x in range(0, 361, 54):
        s.line([horizon, (x, 0)], '#33535d', 2)
    s.poly([(0, 91), horizon, (360, 105), (360, 480), (0, 480)], '#152a31')
    s.poly([(0, 180), horizon, (63, 480), (0, 480)], '#36504d')
    s.poly([(360, 149), horizon, (279, 480), (360, 480)], '#584a3b')
    for x in (21, 54, 91, 264, 303, 345):
        s.line([horizon, (x, 480)], '#688076' if x < 175 else '#857455', 2)
    for t in np.linspace(.03, 1, 38) ** 2:
        y = 254 + 226*t
        s.line((175-132*t, y, 175+112*t, y), '#344b49', max(1, round(t*4)))
    for x in (108, 142, 215, 248):
        s.line([horizon, (x, 480)], '#a1a392', 2)
    for x in (22, 41, 59, 295, 321, 347):
        width = 7 + abs(x-175)*.035
        y = 108 + (165-abs(x-175))*.69
        s.line((x, y, x, 353-abs(x-175)*.16), '#263d3e', round(width))
        s.line((x+2, y, x+2, 353-abs(x-175)*.16), '#8b8060', 2)
        s.ellipse(x, y+17, width, 3, '#f5bd7e')
        s.glaze(x, y+20, 19, 31, '#e7ad73', .23)
    for _ in range(670):
        x, y = s.rng.randrange(360), s.rng.randrange(274, 480)
        s.line((x, y, x+s.rng.randrange(2, 12), y), s.rng.choice(('#223b42','#466266','#526e6c','#655d48')))
    side = [(111, 204), (164, 181), (191, 210), (182, 286), (112, 341)]
    at = panel(s, side, ('#123037', '#58827c'), [
        (.05,.13,.89,.36,'#355d5e'), (.08,.55,.84,.29,'#293b39'), (.04,.82,.90,.09,'#715e43')])
    for i in range(7):
        u = .063+.128*i
        s.poly([at(u,.20),at(u+.092,.20),at(u+.092,.48),at(u,.48)], '#d19a64' if i%3 else '#62817f')
    s.poly([(110, 204), (129, 183), (217, 180), (242, 203), (247, 322),
            (232, 350), (122, 353), (108, 333)], '#254a50', '#779c91')
    s.poly([(112, 207), (129, 185), (217, 182), (241, 201), (126, 202)], '#52837d')
    s.poly([(119, 214), (234, 210), (236, 270), (222, 279), (129, 281), (118, 267)], '#101d27', '#6f8e83')
    for p in ((123,219,174,270), (181,216,229,268)):
        s.box(p, '#31565c', '#4a7271')
        a,b,c,d = p
        s.line((a+4,d-2,c-4,b+5), '#668c83', 2)
    s.box((155, 192, 199, 202), '#213337', '#8c9171')
    s.line((111, 296, 241, 290), '#b1865f', 6)
    s.line((111, 299, 241, 293), '#725b49', 2)
    for x in (132, 224):
        s.ellipse(x, 310, 10, 10, '#5c634f', '#c5a570', 2)
        s.ellipse(x, 310, 6, 6, '#ffe5ae')
        s.glaze(x, 319, 27, 32, '#ffd598', .38)
        s.poly([(x-4, 346), (x+9, 345), (x+16, 422), (x-19, 405)], '#6e725c')
        s.glaze(x-2, 385, 19, 45, '#e6b67c', .26)
        for i in range(39):
            y = s.rng.randrange(353, 464)
            xx = x + s.rng.gauss(0, 2 + (y-353)*.12)
            span = s.rng.randrange(2, 12)
            s.line((xx-span, y, xx+span, y), ('#968265', '#b19770', '#cfb783')[i%3])
    s.line((123, 344, 232, 341), '#151f28', 7)
    s.line([(121, 283), (154, 286), (197, 281), (232, 280)], '#6f9588', 2)
    s.line([(126, 323), (147, 325), (213, 321), (233, 319)], '#3a6567', 2)
    for x in (156, 164, 174, 183, 191, 201):
        s.line((x, 333, x+4, 333), '#77948b')
    for i in range(180):
        x = s.rng.randrange(360)
        y = s.rng.randrange(91, 458)
        s.line((x, y, x-3, y+8), s.rng.choice(('#587479','#698d8d','#85938a')))
    return s


def lighthouse(font):
    s = Scene(88, (11, 17, 38), (103, 143, 162, 95, (48, 47, 83)),
              (273, 286, 146, 85, (29, 56, 76)))
    cloud = np.sin(X*.044 + Y*.07) + .54*np.sin(X*.10 - Y*.08) + .29*np.cos(X*.19+Y*.15)
    a = np.clip((cloud-.02)*.14, 0,.27) * np.exp(-((Y-145)/89)**2)
    s.image.paste('#8a81ad', (0,0,WIDTH,HEIGHT), Image.fromarray((a*255).astype('uint8')))
    for level in range(26):
        y = 249 + level*9
        line = [(x, y + (2+level*.27)*sin(x*.033 + level*.62) + 4*sin(x*.074 + level*.21))
                for x in range(-12, 373, 3)]
        s.poly([*line, (373,480),(-12,480)], ('#1b344f','#24435a','#29526a','#18304d')[level%4])
        s.line(line, ('#60849b','#446e82','#548497','#9bb4b9')[level%4], 2 if level%3 else 3)
    for i in range(460):
        x, y = s.rng.randrange(360), s.rng.randrange(264, 480)
        s.line((x,y,x+s.rng.randrange(1,12),y+s.rng.choice((-1,0,1))),
               s.rng.choice(('#365d77','#508198','#769aab','#9dafb3')))
    cliff = [(0,317),(50,293),(104,301),(137,277),(163,284),(199,322),(164,335),
             (127,377),(86,410),(79,449),(0,480)]
    s.poly(cliff, '#22283d', '#48556c')
    for _ in range(240):
        x,y=s.rng.randrange(190),s.rng.randrange(283,476)
        if 317-.20*x < y < 458-.73*x:
            s.line((x,y,x+10,y+s.rng.randrange(-5,3)),s.rng.choice(('#41465d','#51536a','#39465c')))
    s.poly([(70,300),(86,155),(130,155),(147,290),(128,308),(87,310)], '#697687', '#aab4b9')
    s.poly([(111,154),(131,155),(146,291),(125,307)], '#414b66')
    for y in (183,217,252):
        extra=(y-153)*.10
        s.poly([(86-extra,y),(132+extra,y-3),(134+extra,y+13),(84-extra,y+16)], '#794d67')
    s.poly([(84,158),(81,136),(137,136),(132,160)], '#27334c', '#a4a0aa')
    s.poly([(86,136),(88,110),(130,110),(134,136)], '#67818a', '#c8c5b4')
    for x in (92,103,115,126):
        s.line((x,111,x,136), '#35465c', 2)
    s.poly([(83,111),(108,87),(137,109)], '#775670', '#b68f98')
    s.line((108,94,108,77), '#9197a7', 2)
    beam = (X >= 105) * np.exp(-((Y - (122-(X-105)*.24))/(8+(X-105)*.068)) ** 2) * .68
    s.image.paste('#f4dfaa', (0,0,WIDTH,HEIGHT), Image.fromarray((beam*255).astype('uint8')))
    s.glaze(109,123,33,27,'#ffeab8',.56)
    s.ellipse(109,123,6,4,'#fff1c5')
    s.poly([(92,285),(94,270),(108,270),(109,287)], '#343b50')
    for i in range(5):
        surf = [(x, 345 + i * 8 + 9 * sin(x / 17 + i * .43) + .09 * (x - 172))
                for x in range(168 + i*8, 321 - i*9)]
        s.line(surf, ('#8caeb1', '#597e98', '#b9c7bb')[i%3])
    for i in range(36):
        x = s.rng.randrange(139, 223)
        y = round(330 - (x-174)*.52 + s.rng.gauss(0, 9))
        s.draw.point((x,y), s.rng.choice(('#bfd3ce', '#749bac', '#88a1b1')))
    return s


def jellyfish(font):
    s = Scene(619, (10, 13, 39), (173, 111, 142, 116, (35, 27, 91)),
              (300, 283, 130, 167, (19, 35, 78)))
    for i in range(5):
        a = np.exp(-((X-34-i*36 + Y*.27)/(10+i*2))**2) * np.exp(-Y/147) * .25
        s.image.paste('#4a78b6', (0,0,WIDTH,HEIGHT), Image.fromarray((a*255).astype('uint8')))
    for _ in range(790):
        x,y=s.rng.randrange(360),s.rng.randrange(480)
        s.ellipse(x,y,1 if s.rng.random()<.24 else 0,1,s.rng.choice(('#364a77','#556395','#696ba8','#46558f')))
    for cx,cy,r,palette in ((65,293,32,('#345f89','#6c9bc8','#bac9ee')),
                            (296,247,47,('#544780','#8574af','#ce92c4')),
                            (164,144,87,('#4e3e8f','#a26cc1','#fad0e6'))):
        shadow, mid, glow = palette
        for i in range(14):
            x = cx-r*.77+i*r*.114
            height = r*(.9+s.rng.random()*1.8)
            path = bezier([(x, cy+r*.11), (x+26*sin(i*2),cy+r*.66),
                           (x-35*cos(i),cy+height*.68), (x+25*sin(i),cy+height)], 60)
            s.line(path, shadow, max(2,round(r/19)))
            s.line(path, mid, max(1,round(r/55)))
            s.line(path[::5], glow if i%4==0 else mid)
            for px,py in path[3::7]:
                s.ellipse(px,py,1,1,glow)
        bell = ((X-cx)/r)**2 + ((Y-cy)/(r*.68))**2
        lower = cy + r*.12 + r*.09*np.sin((X-cx)/r*8)
        shell = (bell<1)&(Y<lower)
        depth = np.sqrt(np.maximum(0,1-bell))
        striation = np.sin(np.arctan2((Y-cy)/.68,X-cx)*46 + .95*np.sin(Y*.17))
        base = (np.maximum(0,1-depth)*.72 + .10*striation + .22) * shell
        s.image.paste(mid, (0,0,WIDTH,HEIGHT), Image.fromarray((base.clip(0,1)*255).astype('uint8')))
        lip = shell * np.exp(-((Y-lower)/2.8)**2) * .93
        rim = shell * np.exp(-((bell-.94)/.14)**2)*.8
        s.image.paste(glow,(0,0,WIDTH,HEIGHT),Image.fromarray((np.maximum(lip,rim)*255).astype('uint8')))
        for i in range(5):
            u = r * (.15 + .14*i)
            rib = [(cx+u*cos(t), cy - .63*r*sin(t)*(1-u/r*.52)) for t in np.linspace(.25, pi-.25, 61)]
            s.line(rib, mid if i%2 else glow)
        core = ((X-cx)/(r*.21))**2 + ((Y-cy+r*.13)/(r*.30))**2
        light = np.exp(-core) * shell * .31
        s.image.paste(glow, (0,0,WIDTH,HEIGHT), Image.fromarray((light*255).astype('uint8')))
        s.glaze(cx-r*.18,cy-r*.29,r*.46,r*.60,glow,.22)
    s.poly([(0,479),(0,456),(37,451),(63,466),(94,455),(123,464),(152,470),
            (189,457),(224,473),(280,462),(326,471),(359,456),(359,479)], '#182541')
    for x,y,h in ((25,470,52),(41,473,38),(315,473,71),(338,477,45)):
        wire(s,[(x,y),(x-19,y-h*.22),(x+27,y-h*.85),(x+4,y-h)],'#243954','#3f5b78',5)
    return s


def dunes(font):
    s = Scene(3905, (38, 27, 60), (184, 197, 149, 146, (121, 54, 32)),
              (281, 310, 171, 102, (107, 79, 35)))
    s.glaze(183,161,94,105,'#f99f6e',.47)
    s.ellipse(183,151,49,49,'#ffd797','#ffe1ad',2)
    for y in range(118, 196, 8):
        width = np.sqrt(49**2-(y-151)**2)
        s.line((183-width,y,183+width,y),'#dda37c')
    for i in range(11):
        y = 112 + i*9
        x = 19 + (i*29)%114
        s.line([(x,y),(x+32,y+2),(x+69,y),(x+88,y-4)], '#ad6a71')
    for _ in range(265):
        x,y=s.rng.randrange(360),s.rng.randrange(180)
        if (x-183)**2+(y-151)**2>57**2:
            s.draw.point((x,y),s.rng.choice(('#7c576e','#a56975','#bd7776','#e68f77')))
    for i, (level, rise, slope, color, crest) in enumerate((
        (216,21,-.13,'#8d5361','#d48b82'), (249,31,.18,'#945958','#d99079'),
        (278,36,-.36,'#a26759','#e1a17e'), (321,41, .45,'#855358','#d28e6e'),
        (356,44,-.37,'#ae6c59','#f4bd88'), (402,32,.34,'#6e4752','#e8a674'))):
        profile = [level + rise*sin(x/69+i*1.82) + slope*(x-180) + 8*sin(x/27+i)
                   for x in range(WIDTH)]
        s.poly([*enumerate(profile), (359,479),(0,479)],color)
        s.line(list(enumerate(profile)),crest,3)
        for j in range(18):
            y = 3+j*4+j*j*.19
            curve = [(x, profile[x]+y+.9*j*sin(x/57-i)) for x in range(0,360,3)]
            s.line(curve,(crest if j%7==0 else ('#8a595c' if i%2 else '#bc8268')))
    # A lone field walker, cloth streaming into the wind.
    s.poly([(211,286),(221,285),(250,316),(245,320),(218,309),(207,295)],'#654557')
    s.line([(209,274),(208,290),(204,303),(203,312)],'#2a2b42',3)
    s.line([(214,277),(215,293),(220,306)],'#29273f',3)
    s.poly([(208,256),(217,255),(224,269),(222,291),(210,288),(205,275)],'#354351','#574b57')
    s.poly([(211,256),(219,260),(221,280),(215,281),(211,274)],'#688083')
    s.ellipse(213,250,5,6,'#e4b481','#413648')
    s.line([(204,247),(223,248),(226,250),(205,251)],'#635163',3)
    wire(s,[(216,256),(230,247),(233,257),(248,247)],'#784355','#e39b71',4)
    s.line([(223,268),(231,277),(233,305)],'#52404d',2)
    for _ in range(475):
        x,y=s.rng.randrange(360),s.rng.randrange(336,480)
        s.draw.point((x,y),s.rng.choice(('#97665d','#d19a76','#6a5166','#e5b184')))
    for i in range(9):
        x, y = 203-i*4, 314+i*5
        s.line((x-2, y, x+2, y+1), '#514351')
    s.poly([(294,421),(308,408),(329,411),(343,427),(332,437),(295,436)],'#574458','#88616b')
    return s


def beetle(font):
    s = Scene(614, (9,22,28), (157,210,134,146,(19,65,56)),
              (283,82,131,103,(42,60,32)), (82,402,112,111,(37,62,35)))
    for cx,cy,rx,ry in ((41,112,27,13),(276,61,24,27),(319,281,28,36),(128,410,31,11),
                        (342,112,13,17),(58,344,19,26),(213,424,32,21)):
        s.glaze(cx,cy,rx,ry,'#6d9d79',.37)
    for i in range(9):
        y=290+i*16
        start=(0,y+69)
        end=(345,y-110-i*3)
        edge=bezier([start,(74,y-66),(255,y-119),end])
        underside=bezier([end,(232,y+22),(89,y+62),start])
        s.poly(edge+underside,('#204a49','#2f6860','#397665','#22564e')[i%4])
        s.line(edge,('#477d6a','#548d75','#376e63')[i%3],2)
        for j in range(5,32,3):
            x, yy=edge[j]
            s.line((x,yy+2,x+13,yy+18),'#4c8071')
    for _ in range(880):
        x,y=s.rng.randrange(360),s.rng.randrange(480)
        s.draw.point((x,y),s.rng.choice(('#265b58','#387669','#3f7164','#294b45')))
    s.ellipse(184,288,94,107,'#234a46')
    for direction in (-1,1):
        for i in range(3):
            x=178+direction*(38+i*9)
            y=224+i*35
            points=[(x,y),(x+direction*38,y-22+i*10),
                    (x+direction*(52+i*4),y+20+i*7),(x+direction*(63+i*4),y+29+i*6)]
            s.line(points,'#15272f',8)
            s.line([(px,py-2) for px,py in points],'#9c8560',2)
            s.ellipse(*points[1],4,4,'#745e51','#d1a071')
        wire(s,[(178+direction*20,158),(178+direction*36,121),
                (178+direction*52,106),(178+direction*72,111)],'#202e37','#bd996b',4)
        s.ellipse(178+direction*72,111,4,3,'#d4b185')
    s.ellipse(178,166,31,31,'#4d5352','#b49a77',2)
    for x in (157,199):
        s.ellipse(x,164,8,10,'#232c36','#a99570')
        s.ellipse(x-1,161,2,3,'#e2bd94')
    s.ellipse(178,203,47,37,'#675c57','#cbac82',2)
    for x in range(146,214,4):
        s.line((x,191,x-2,210),'#9c836b')
    ellipse=((X-178)/67)**2+((Y-270)/84)**2
    bump=np.sqrt(np.maximum(0,1-ellipse))
    specular=(.62*bump-.65*(X-178)/67-.24*(Y-270)/84).clip(0,1)
    grain=np.sin((X-178)*.66 + 13*bump + .39*np.sin(Y*.27))*.09
    color=np.array((84,51,57))+(specular*.7+grain+.13)[...,None]*(150,105,64)
    color+=np.exp(-((X-223)/17)**2-((Y-239)/54)**2)[...,None]*(10,20,28)
    sheen = np.exp(-((X-140-(Y-242)*.14)/9)**2-((Y-242)/48)**2)
    color += sheen[..., None] * (39, 35, 20)
    s.image.paste(Image.fromarray(color.clip(0,255).astype('uint8')),(0,0),
                  Image.fromarray((ellipse<1).astype('uint8')*255))
    contour=[(178+67*cos(a),270+84*sin(a)) for a in np.linspace(0,tau,161)]
    s.line(contour,'#b9866a',2)
    wire(s,[(177,188),(168,233),(164,293),(178,352)],'#472f3d','#e1a878',3)
    for _ in range(410):
        x,y=s.rng.randrange(116,242),s.rng.randrange(190,350)
        if ellipse[y,x]<.94:
            s.draw.point((x,y),s.rng.choice(('#d5906a','#976468','#926256','#bc795f')))
    for x,y,r in ((71,324,12),(257,352,9),(284,301,5),(83,388,5),(285,384,15)):
        s.ellipse(x,y,r,r*.64,'#35645e','#589386')
        s.line((x-r*.5,y-r*.4,x-r*.13,y-r*.57),'#bfd1ad',2)
        s.line((x+r*.05,y+r*.47,x+r*.48,y+r*.36),'#639e9a')
    return s


def bloom(scene, radius=8, strength=.55):
    pixels = np.asarray(scene.image, dtype=np.float32)
    bright = np.maximum(0, pixels.max(axis=-1) - 155) / 100
    emitters = Image.fromarray((pixels * bright[..., None]).clip(0, 255).astype('uint8'))
    halo = np.asarray(emitters.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
    scene.image.paste(Image.fromarray((pixels + halo * strength).clip(0, 255).astype('uint8')))


def skyline(s, x0, x1, base, min_height, max_height, colors):
    """Facade lights, parapets and antennas at a common depth."""
    x = x0
    while x < x1:
        width = s.rng.randint(7, 17)
        top = base - s.rng.randint(min_height, max_height)
        wall, windows, trim = colors[s.rng.randrange(len(colors))]
        s.box((x, top, min(x + width, x1), base), wall)
        s.line((x, top, min(x + width, x1), top), trim)
        if width > 9:
            s.line((x+width*.6, top, x+width*.6, top-9), trim)
        for yy in range(top+4, base-1, 5):
            for xx in range(x+2, min(x+width-1, x1), 4):
                if s.rng.random() < .57:
                    s.line((xx, yy, xx+1, yy), s.rng.choice(windows))
        x += width + s.rng.randint(1, 3)


def relay_cabin(font):
    s = Scene(2861, (3, 7, 17), (169, 183, 175, 103, (6, 18, 35)),
              (287, 303, 87, 112, (24, 12, 13)))
    teal, amber = '#4ae6f0', '#ffc382'
    # Wide observation glass set into the sloped shell of the cabin.
    outer = [(14, 112), (39, 52), (289, 74), (322, 102), (313, 209), (18, 219)]
    window = [(23, 115), (45, 62), (285, 84), (309, 107), (303, 197), (28, 208)]
    s.poly(outer, '#0b213c', '#3070a5')
    s.poly(window, '#0b1934', '#259aba')
    s.line(outer[:4], '#48bdd4', 3)
    s.line([(29, 206), (303, 197), (311, 176)], '#30709b', 2)
    sky = Image.new('L', (WIDTH, HEIGHT))
    ImageDraw.Draw(sky).polygon(window, fill=255)
    s.image.paste('#164875', (0, 0, WIDTH, HEIGHT), Image.fromarray(
        (np.asarray(sky) * np.exp(-((Y-167)/33)**2 - ((X-181)/112)**2) * .61).astype('uint8')))
    for i in range(5):
        x0, y0 = 44 + i*20, 122 + i*15
        coast = [(x, y0 + 5*sin(x/18+i) + 3*sin(x/7+i)) for x in range(x0, 300)]
        s.line(coast, ('#1b4b79', '#2b77a0', '#2d6291', '#18608b', '#2488a6')[i])
    for _ in range(195):
        x, y = s.rng.randrange(27, 305), s.rng.randrange(65, 203)
        if sky.getpixel((x, y)) and sky.getpixel((x-6, min(479, y+12))):
            length = s.rng.randrange(3, 13)
            s.line((x, y, x-5, y+length), s.rng.choice(('#174771', '#246aa0', '#2d9bc5', '#235687')))
    # The relay dish and its lattice rise from the rain behind the glass.
    s.poly([(110,200), (121,143), (128,137), (135,146), (145,198)], '#102544', '#3b96bc')
    for y in range(148, 197, 9):
        d = (y-143)*.18
        s.line((122-d, y, 133+d, y+6), '#3f92be')
        s.line((133+d, y, 122-d, y+6), '#194b80')
    dish = bezier([(85,106), (93,141), (127,146), (154,127)])
    s.poly(dish + [(142,119), (112,109), (85,106)], '#15385f', '#3183ad')
    s.line(dish, teal, 2)
    s.line([(86,106),(113,112),(154,127)], '#5ac7e1', 2)
    for x, y in dish[6:-1:4]:
        s.line((x,y,115,115), '#26638f')
    s.line([(118,119),(127,96),(133,100)], '#519ac1', 2)
    s.ellipse(131, 98, 2, 2, amber)
    s.glaze(131, 98, 12, 10, '#f79c73', .16)
    for x, y in ((54,177),(77,159),(173,190),(211,184),(266,175),(287,168)):
        s.ellipse(x, y, 1.5, 1.5, '#ffb776')
    s.line([(186,76),(184,200)], '#111f3a', 5)
    s.line([(187,77),(185,199)], '#2b80a9', 2)
    s.line([(24,220),(312,211),(331,85)], '#85506a', 3)
    # Industrial ceiling and a rack of illuminated switches.
    s.line([(0,35),(34,18),(273,38),(359,84)], '#294b76', 3)
    s.line([(0,26),(35,8),(274,29),(359,75)], '#163555', 4)
    for i in range(9):
        x, y = 155+i*14, 49+i
        s.line((x, y, x+7, y+1), '#b97965' if i%3 else '#ffb278', 2)
    for i in range(3):
        wire(s, [(326+i*8, 62),(306+i*9,126),(360,147+i*11),(358,232+i*3)],
             '#182241', ('#357fa9','#575887','#a16d72')[i], 3)
    s.poly([(0,315),(217,291),(359,328),(359,479),(0,479)], '#181c38', '#a16870')
    s.poly([(0,324),(213,302),(359,338),(282,370),(0,385)], '#413751', '#ba816b')
    s.line([(0,384),(282,369),(359,339)], '#e6a373', 3)
    for _ in range(460):
        x,y = s.rng.randrange(1,284),s.rng.randrange(304,381)
        if 324-x*.10 < y < 386-x*.060:
            s.line((x,y,x+s.rng.randrange(2,9),y-1), s.rng.choice(('#7c5865','#574866','#3e637c','#a27271')))
    # The CRT is turned toward the operator. Its screen is in perspective.
    s.poly([(57,240),(25,254),(43,330),(67,341),(166,320),(162,248)], '#101f3b', '#3975a8')
    s.poly([(25,254),(57,239),(163,242),(166,251),(64,257)], '#3c6391', '#4dadd2')
    s.poly([(25,254),(64,257),(72,335),(43,330)], '#162d55','#2e6d9f')
    for i in range(7):
        y = 265+7*i
        s.line((35+(y-265)*.24, y, 58+(y-265)*.24, y+6), '#347da8', 2)
    corners = [(58,248),(160,238),(169,320),(68,333)]
    screen = panel(s,corners,('#285984','#60dfee'),[
        (.035,.045,.93,.89,'#358db2'),(.073,.089,.855,.764,'#0b284d'),
        (.103,.131,.796,.675,'#081d3b')])
    s.line(corners[:2],teal,3)
    s.line((screen(.065,.88),screen(.930,.88)), '#3ad8e8', 2)
    for i in range(16):
        v=.172+i*.038
        s.line((screen(.116,v),screen(.89,v)), '#134670')
    for i, line in enumerate(('relé costero', '> abrir_escucha()', '> señal estable')):
        for j, char in enumerate(line):
            if char != ' ':
                s.label(screen(.139+j*.042,.221+i*.122),char,'#7feeea' if i==1 else '#2da8cb',font,6)
    for i in range(20):
        u=.13+i*.036
        top=.697-.10*abs(sin(i*.56)+.42*sin(i*1.22))
        s.line((screen(u,.779),screen(u,top)), '#28a6cf' if i%3 else '#71e8e6', 2)
    s.ellipse(*screen(.94,.94),2,1.5,amber)
    s.poly([(82,338),(128,330),(158,338),(148,349),(101,355)], '#1a4066', '#459fc4')
    keys = [(106,353),(175,335),(221,348),(149,370)]
    panel(s,keys,('#162749','#769bb5'),[
        (.045+i*.082,.10+j*.28,.065,.177,('#d39c78','#5aa9bc','#a5c6c3')[(i+j)%3])
        for i in range(11) for j in range(3)])
    mixer = panel(s,[(8,351),(66,340),(95,354),(38,368)],('#343749','#b08d87'),[
        (.07+i*.14,.15,.085,.57,('#eda36c','#5fadc6','#b7d9cc')[i%3]) for i in range(6)])
    s.line((mixer(.04,.83),mixer(.94,.83)), '#fde2aa')
    # The operator faces left in profile, with a warm collar and a headset.
    coat = [(246,255),(276,244),(312,255),(335,276),(352,315),(359,360),
            (359,479),(222,479),(221,419),(228,366),(218,323),(225,284)]
    s.poly(coat,'#132340','#39648f')
    s.poly([(249,260),(278,245),(313,260),(324,282),(301,296),(268,284),(247,295)],
           '#1b3358','#4c91b2')
    s.line([(249,260),(278,246),(310,260),(325,281)], '#589ec6', 3)
    s.poly([(252,280),(273,285),(290,301),(273,338),(245,376),(231,365),(242,328)], '#213b64')
    s.line([(261,289),(280,303),(272,332),(246,369)], '#366794', 3)
    s.poly([(226,299),(242,290),(254,307),(241,333),(214,351),(190,352),(185,341),
            (205,332)], '#1b2c50','#4d8fba')
    s.line([(225,302),(214,333),(195,340)], '#469fc2', 3)
    s.poly([(180,345),(188,336),(197,338),(199,344),(192,349),(179,353),
            (168,352),(168,349)], '#b47d6d', '#f0ba86')
    s.poly([(248,225),(270,230),(280,254),(273,265),(249,252),(242,238)], '#8c5961', '#d89975')
    head = [(225,182),(235,172),(259,166),(283,173),(299,190),(298,213),(285,229),
            (263,237),(244,228),(235,220),(225,215),(226,208),(216,206),(220,199)]
    s.poly(head,'#754b59','#cf907e')
    s.line([(225,182),(222,195),(216,206),(225,207),(225,215),(236,222),(245,229)], '#71d1df', 2)
    s.poly([(227,184),(237,172),(256,165),(280,169),(295,180),(303,196),(300,211),
            (293,222),(281,229),(268,225),(263,207),(248,201),(244,190)],'#0b1d3a','#3776a6')
    for i in range(8):
        x = 236+i*7
        s.line(bezier([(x,183),(x+6,169),(x+21,180),(x+25,200)]), '#255b8d')
    s.line([(257,174),(273,171),(288,178),(298,189),(301,203)],'#e4a17b',3)
    s.ellipse(265,207,13,16,'#142c4f','#92baca',2)
    s.ellipse(265,207,8,11,'#243f63','#4a8bb1',2)
    s.line([(257,213),(246,219),(234,216)],'#85dce3',2)
    s.ellipse(233,216,2,1,'#edb47f')
    s.line([(250,247),(269,256),(283,253)], '#de9e7c', 3)
    for i in range(9):
        y=386+i*9
        s.line([(242,y),(268,y+10),(311,y+20),(359,y+17)],('#234b75','#1a3b66','#284268')[i%3])
    # Bolted lower console, a visible cable loop and a small nameplate.
    s.poly([(0,404),(120,395),(156,415),(132,445),(0,449)], '#102944', '#327caf')
    s.line([(0,408),(120,398),(152,417)], teal, 2)
    for i in range(7):
        x = 14+i*16
        s.line((x,420,x+4,439), '#285d8d', 3)
        s.ellipse(x,419,2,1,'#f9bb82' if i%3==0 else '#4896b5')
    s.poly([(14,455),(84,448),(110,460),(39,469),(14,467)], '#1b2d4e', '#b57868')
    wire(s,[(129,440),(201,399),(207,483),(171,478)],'#141f3e','#316b97',6)
    wire(s,[(130,446),(185,427),(189,481),(147,479)],'#141f3e','#6e5b8b',5)
    return s


def silicon(font):
    s = Scene(6131,(14,21,33),(181,237,148,198,(25,52,54)),
              (286,93,147,87,(74,29,50)),(92,327,126,119,(43,24,42)))
    at = plane([(-201,155),(227,49),(565,206),(108,583)])
    for ix in range(55):
        u = ix/55
        s.line((at(u,0),at(u,1)),('#294653','#415b60')[ix%2])
    for iy in range(58):
        v = iy/58
        s.line((at(0,v),at(1,v)),('#233945','#3a4d55')[iy%2])
    for _ in range(700):
        u,v=s.rng.random(),s.rng.random()
        x,y=at(u,v)
        s.ellipse(x,y,1,1,s.rng.choice(('#658078','#58706f','#ad8375','#468c84')))
    metal = ('#86677b','#587b7d','#9a806d','#654e72','#578e84')
    lumens = ('#68d5c3','#ffd593','#ee91b5','#80d0e5')
    for side in range(4):
        for pin in range(19):
            q=.31+pin*.020
            sign = -1 if side%2==0 else 1
            edge = .29 if sign<0 else .71
            bends = [(q,edge),(q,edge+sign*.063),
                     (q+(pin-9)*.005,edge+sign*(.111+.012*(pin%5))),
                     (q+(pin-9)*.005,edge+sign*.29)]
            coords = [at(u,v) if side<2 else at(v,u) for u,v in bends]
            s.line(coords,metal[(pin+side)%5],3)
            s.line(coords,lumens[side] if pin%4==0 else '#708782')
            s.ellipse(*coords[-1],3,3,'#334b54',lumens[side])
    cap = [at(.285,.30),at(.718,.30),at(.718,.707),at(.285,.707)]
    sideface = [(x,y+22) for x,y in cap]
    s.poly([*cap,*reversed(sideface)],'#1d3037')
    s.poly([cap[1],cap[2],sideface[2],sideface[1]],'#2a3d50','#728c89')
    s.poly([cap[2],cap[3],sideface[3],sideface[2]],'#1d303d','#78948b')
    board = panel(s,cap,('#284751','#8eae9b'),[
        (.03,.04,.94,.91,'#315762'),(.05,.07,.89,.84,'#192c3e'),
        (.15,.15,.70,.70,'#5a827d'),(.17,.17,.66,.66,'#263849'),
        (.23,.23,.54,.54,'#507f7c'),(.25,.25,.50,.50,'#254955')])
    for i in range(21):
        q=.09+i*.039
        for v in (.075,.91):
            s.ellipse(*board(q,v),2,1,('#99c3aa','#d2ab87','#73b8b3')[i%3])
        for u in (.10,.89):
            s.ellipse(*board(u,q),2,1,'#759c99')
    for i in range(13):
        q=.275+i*.036
        s.line((board(q,.275),board(q,.725)),('#396b70','#4b8f87','#39617a')[i%3])
        s.line((board(.275,q),board(.725,q)),('#396b70','#4b8f87','#39617a')[i%3])
    for i in range(115):
        u,v=(.27+s.rng.random()*.46 for _ in range(2))
        s.ellipse(*board(u,v),1,1,s.rng.choice(('#91d1b6','#afccc0','#e6b88d','#bb89ba')))
    inner=[board(.39,.37),board(.63,.37),board(.63,.62),board(.39,.62)]
    die=panel(s,inner,('#4b9c93','#d6f8c5'),[(.08,.09,.84,.82,'#72bfa6'),(.27,.20,.46,.57,'#538e92')])
    for row in range(8):
        for col in range(9):
            u,v=.145+col*.079,.15+row*.087
            s.line((die(u,v),die(u+.042,v)),('#f3dfac','#a6ebc5','#59a69c')[(row+col)%3])
    s.poly([die(.40,.35),die(.65,.35),die(.65,.63),die(.40,.63)],'#aee3bb','#fdffc8')
    center=board(.5,.5)
    for a in np.linspace(0,tau,20,endpoint=False):
        dx,dy=cos(a),sin(a)
        s.line((center[0]+dx*18,center[1]+dy*11,center[0]+dx*33,center[1]+dy*21),
               ('#75c9af' if dx<.2 else '#e4c095'))
    s.glaze(*center,35,32,'#a4ffd6',.14)
    for u,v in ((.11,.47),(.23,.14),(.76,.23),(.39,.84),(.79,.69),(.19,.77),(.84,.42)):
        x,y=at(u,v)
        s.ellipse(x,y+2,9,5,'#172631','#54757c')
        s.ellipse(x,y-2,7,4,'#768f8c','#a8b9a8')
        s.ellipse(x,y-2,3,2,'#334851')
    for u,v in ((.22,.80),(.25,.84),(.29,.88),(.64,.14),(.68,.14),(.72,.14),(.82,.55),(.84,.60)):
        corners = [at(u,v),at(u+.036,v),at(u+.036,v+.035),at(u,v+.035)]
        corners = [(x,y-5) for x,y in corners]
        chip = panel(s,corners,('#35425a','#7c9c99'),[(.12,.13,.73,.62,'#414c69')])
        for j in range(3):
            q=.17+j*.28
            s.line((chip(q,.84),chip(q,1.26)), '#aab4a4')
            s.line((chip(q,-.21),chip(q,.15)), '#9d8da1')
        s.ellipse(*chip(.19,.28),.7,.7,'#b6dcbd')
    bloom(s,5,.48)
    return s
def signal_city(font):
    s = Scene(791,(18,19,43),(183,149,134,147,(61,26,91)),
              (285,193,154,121,(35,53,89)),(165,405,95,95,(24,34,53)))
    stars(s,470,187)
    s.ellipse(180,115,59,59,'#8f629a','#c88aae')
    for y in range(92,172,5):
        width=np.sqrt(59**2-(y-115)**2)
        s.line((180-width,y,180+width,y),'#845b97')
    s.glaze(180,113,86,73,'#e183ac',.27)
    skyline(s,0,359,260,49,127,(
        ('#2a3659',('#8c72a4','#65a3ba','#6e638d'),'#526286'),
        ('#384065',('#b17c9d','#829ab5','#756d95'),'#615f8b')))
    skyline(s,0,359,321,63,165,(
        ('#1e304b',('#659ca9','#75b9cc','#66688b'),'#55728e'),
        ('#2f3157',('#bf8caa','#ca92a9','#8770a8'),'#62628a')))
    s.poly([(157,263),(204,259),(343,480),(30,480)],'#242541','#25374e')
    for i in np.linspace(0,1,25)**1.7:
        y=263+217*i
        s.line((154-122*i,y,203+140*i,y),'#3e4162')
    for x in (32,64,104,138,163,195,225,278,318,343):
        s.line((180+(x-180)*.08,265,x,480),'#5f5a83' if x%2 else '#405571')

    def tower(x, y, w, d, height, palette):
        face, side, cap, light, line = palette
        f = [(x,y-height),(x+w,y-height+8),(x+w,y+8),(x,y)]
        roof = [(x+d,y-height-17),(x+w+d,y-height-9)]
        q=panel(s,f,(face,line),[])
        s.poly([f[1],roof[1],(x+w+d,y-9),f[2]],side,line)
        s.poly([f[0],roof[0],roof[1],f[1]],cap,line)
        rows=max(3,height//9)
        cols=max(2,w//8)
        for row in range(rows):
            v=.05+row*.90/rows
            for col in range(cols):
                u=.055+col*.91/cols
                if s.rng.random() < .69:
                    px,py=q(u,v)
                    xx,yy=q(u+.4/cols,v)
                    s.line((px,py,xx,yy),s.rng.choice(light),1 if height<175 else 2)
            if row%5==0:
                s.line((q(.03,v+.023),q(.97,v+.023)),line)
        s.line((f[0],f[3]),light[0],2)
        s.line([(x+w*.53+d*.4,y-height-7),(x+w*.53+d*.4,y-height-31)],line)
        s.ellipse(x+w*.53+d*.4,y-height-32,2,2,light[1])

    magenta=('#343251','#292743','#5c4e71',('#bc7fb3','#f7b5cc','#75668b'),'#62527e')
    turquoise=('#254158','#21304a','#456c83',('#7cc5ce','#b1e3dc','#557d9f'),'#4c6888')
    for position in ((49,311,46,22,133,magenta),(237,313,43,14,150,turquoise),
                     (-17,392,67,19,204,turquoise),(281,408,65,29,253,magenta),
                     (67,361,44,16,93,turquoise),(228,378,43,19,120,magenta)):
        tower(*position)
    way=bezier([(183,272),(204,336),(84,400),(129,480)],78)
    s.line(way,'#282c4f',16)
    s.line([(x+5,y) for x,y in way],'#835da5',3)
    s.line([(x-4,y) for x,y in way],'#68b8c7',2)
    for i in (27,39,56,68):
        x,y=way[i]
        s.line((x-3,y,x+3,y+2),'#f7d4b8',2)
        s.glaze(x,y,17,7,'#d49ccc',.29)
    for x,y,width in ((15,249,33),(313,305,33),(83,310,22),(247,312,17)):
        s.box((x,y,x+width,y+13),'#28314b','#8b6d91')
        s.line((x+3,y+4,x+width-3,y+4),'#bf81b4',2)
        for j in range(2,width-2,5):
            s.line((x+j,y+8,x+j+2,y+9),'#8fc3d2')
    for start, end in (((32,289),(80,332)),((287,299),(340,250))):
        wire(s,[start,(start[0]+14,start[1]+12),(end[0]-12,end[1]+9),end],
             '#28324c','#79708e',2)
    for x,y in ((17,262),(325,317),(94,326),(243,324)):
        s.glaze(x,y,32,22,'#e798d3',.15)
    for t in (31,50,71):
        x,y=way[t]
        s.poly([(x-3,y+4),(x+1,y-4),(x+9,y-5),(x+10,y+1)],'#2d3757','#79c5d0')
        s.line((x+6,y-3,x+9,y-3),'#dbf8de')
    for x,y in ((82,180),(219,103),(268,133)):
        s.line((x,y,x+16,y+1),'#6c81b0')
        s.ellipse(x+11,y,2,1,'#f9b7cc')
    s.box((288,246,317,259),'#292b49','#a56da4')
    bloom(s,5,.49)
    return s


def circuit_garden(font):
    s=Scene(4321,(14,27,32),(174,204,118,140,(34,73,53)),
            (268,87,122,102,(23,58,56)),(142,393,138,103,(54,51,33)))
    for i in range(13):
        r=91+i*7
        color=('#4d756c','#243f4b','#44665f','#30555a')[i%4]
        s.line(arch(180,223,r,438),color,2)
    for a in np.linspace(pi+.05,tau-.05,34):
        s.line((180+103*cos(a),223+103*sin(a),180+182*cos(a),223+182*sin(a)),'#37545c')
    for x in (16,50,302,340):
        s.line((x,87,x,389),'#395960',3)
        for y in range(122,345,20):
            s.line((x-3,y,x+4,y),'#749185')
    s.poly([(0,344),(131,280),(233,281),(359,341),(359,479),(0,479)],'#243e42')
    for x in range(-130,552,29):
        s.line((180+(x-180)*.06,281,x,479),'#4b6461')
    for i in range(26):
        y=286+i*i*.33
        s.line((0,y,359,y),'#3c5754')
    for rx,ry,ink in ((125,50,'#30565a'),(106,41,'#376e67'),(89,35,'#4b8777'),(68,27,'#2c504e')):
        s.ellipse(179,378,rx,ry,'#1f444b',ink,2)
    s.ellipse(179,359,72,24,'#334b47','#7a977e',2)
    s.ellipse(179,353,63,20,'#44574b','#a0a486')
    s.ellipse(179,348,59,17,'#263e38')
    for i in range(86):
        a=s.rng.uniform(0,tau)
        r=s.rng.random()
        x,y=179+57*r*cos(a),349+15*r*sin(a)
        s.ellipse(x,y,1.4,.7,s.rng.choice(('#60785b','#8a8870','#496b61','#7f9b77')))

    def branch(x,y,angle,length,width,depth):
        bend=angle+s.rng.uniform(-.29,.29)
        tip=(x+sin(bend)*length,y-cos(bend)*length)
        mid=(x+sin(angle)*length*.61,y-cos(angle)*length*.61)
        s.line([(x,y),mid,tip],('#565743','#9c8661','#b3a678','#718b65')[min(3,4-depth)],
               max(1,round(width)))
        if width>3:
            s.line([(x-1,y), (mid[0]-1,mid[1]),(tip[0]-1,tip[1])],'#c0a97f',2)
        if depth>0:
            for next_angle in (bend-.52,bend+.48):
                branch(*tip,next_angle,length*s.rng.uniform(.62,.77),width*.52,depth-1)
        else:
            for _ in range(67):
                theta,r=s.rng.uniform(0,tau),s.rng.random()**.65*s.rng.uniform(12,28)
                px,py=tip[0]+cos(theta)*r,tip[1]+sin(theta)*r*.68
                ink=s.rng.choice(('#457f62','#68986c','#8eae7d','#b5c18b','#d1dca0','#619e84'))
                s.line((px,py,px+s.rng.randint(1,4),py-1),ink)

    branch(178,350,-.11,72,13,4)
    branch(173,299,-.79,53,6,3)
    branch(179,282,.74,56,6,3)
    s.glaze(181,199,91,111,'#99c48a',.18)
    for x,y,r in ((94,233,12),(131,189,18),(173,174,17),(216,182,13),(261,231,14)):
        for _ in range(56):
            a=s.rng.uniform(0,tau)
            d=r*s.rng.random()**.52
            px,py=x+cos(a)*d,y+sin(a)*d*.76
            s.line((px,py,px+2,py-1),s.rng.choice(('#adbd86','#86a879','#7ea78a','#cad39a')))
    for i in range(125):
        x,y=s.rng.randrange(64,302),s.rng.randrange(114,365)
        if s.rng.random()<.16:
            s.line((x-2,y,x+2,y),'#a2b28a')
        s.draw.point((x,y),s.rng.choice(('#567d6c','#72896c','#c6bf93','#a8c196')))
    for side in (-1,1):
        for i in range(6):
            x=180+side*(77+i*10)
            s.ellipse(x,378+i*5,1.5,1,'#b8d3a4')
    for i in range(3):
        radius=84+i*17
        angle=np.linspace(.12,pi-.12,85)
        s.line([(180+radius*cos(t),397+(22+i*4)*sin(t)) for t in angle],
               ('#89ad83','#578c80','#446b71')[i])
    for x,y in ((113,369),(246,369),(145,398),(207,398)):
        s.glaze(x,y,21,11,'#efce8c',.13)
        s.ellipse(x,y,2,1,'#f2d89a')
    s.poly([(151,372),(208,372),(205,386),(158,386)],'#344b4b','#91aa88')
    bloom(s,8,.39)
    return s


def future_quiet(font):
    s=Scene(1342,(22,26,52),(177,219,138,161,(91,61,48)),
            (253,101,122,94,(53,23,39)),(177,387,108,63,(56,46,51)))
    stars(s,438,237)
    s.ellipse(178,205,70,70,'#dca078','#ffd3a0',2)
    disc = ((X-178)/70)**2 + ((Y-205)/70)**2
    dawn = (disc < .98) * np.clip(.30 + .24 * (Y-205)/70 + .11 * np.sin(Y*.38 + X*.022), 0, 1)
    s.image.paste('#fce0a9',(0,0,WIDTH,HEIGHT),Image.fromarray((dawn*255).astype('uint8')))
    for y in range(182,268,5):
        width=np.sqrt(70**2-(y-205)**2)
        s.line((178-width,y,178+width,y),('#d19480','#bd847d')[y%2])
    s.glaze(179,224,112,87,'#fbc090',.24)
    for i, color in enumerate(('#6c5e77','#595470','#46495f','#353c55')):
        y=271+i*8
        p=[(x,y+11*sin(x/47+i)+6*cos(x/18+i)-18*abs((x-180)/180)**1.6) for x in range(361)]
        s.poly([*p,(360,479),(0,479)],color)
        s.line(p,('#a48694','#8a788b','#6a647c','#657383')[i])
    s.poly([(0,307),(176,290),(359,303),(359,479),(0,479)],'#253948')
    for i in range(185):
        x,y=s.rng.randrange(360),s.rng.randrange(307,480)
        r=abs(x-180)/180
        ink=('#6c6580','#4a6876','#7f747f','#a48981')[i%4] if r<.35 else ('#3a4f65','#436076')[i%2]
        s.line((x,y,x+s.rng.randint(1,15),y),ink)
    # Portal masonry separated into the inner face, front rim and deep side.
    for offset, ink, width in ((12,'#262b45',29),(7,'#554862',25),(0,'#867184',19),
                               (-3,'#b79a96',9),(-5,'#dbc5a9',2)):
        coords=[(180+offset+127*cos(a),206+144*sin(a)) for a in np.linspace(.10,tau-.1,290)]
        s.line(coords,ink,width)
    for start,end,ink in ((.24,1.11,'#e4aa89'),(1.86,2.53,'#ffc99c'),(3.22,4.04,'#b2bada'),
                           (4.36,5.16,'#fff0ba'),(5.57,6.08,'#d9a5a5')):
        s.line([(176+123*cos(a),206+140*sin(a)) for a in np.linspace(start,end,57)],ink,3)
    for start,end in ((.37,1.18),(2.02,2.65),(3.52,4.3),(4.9,5.84)):
        s.line([(190+137*cos(a),206+152*sin(a)) for a in np.linspace(start,end,49)],'#696b89',2)
    for i,a in enumerate(np.linspace(.13,tau-.13,90)):
        x,y=180+127*cos(a),206+144*sin(a)
        s.line((x-6*cos(a),y-6*sin(a),x+7*cos(a),y+7*sin(a)),'#6f607b')
        if i%5==0:
            s.ellipse(x-8*cos(a),y-8*sin(a),1.5,1.5,'#ffe4b2')
    reflection_y = (348 - (Y-348)*1.29 + 3*np.sin(Y*.64)).clip(0,348).astype('intp')
    reflection_x = (X + (2+(Y-348)*.11)*np.sin(Y*.37)).clip(0,359).astype('intp')
    reflection = np.asarray(s.image)[reflection_y,reflection_x]
    ripple = .76 + .18*np.sin(Y*1.20) + .06*np.cos(X*.24+Y*.17)
    alpha = ((Y>348) * np.exp(-np.maximum(Y-349,0)/102) * ripple * 139).astype('uint8')
    s.image.paste(Image.fromarray(reflection),(0,0),Image.fromarray(alpha))
    for left, right in ((35,94),(276,338)):
        s.poly([(left,301),(right,303),(right+13,322),(left-9,326)],'#33374f','#806e83')
        s.line((left-8,324,right+13,320),'#c99291',2)
    for i in range(9):
        y=355+i*5
        half=15+12*sin(i*.31)
        center=180+14*sin(i*.66)
        s.line((center-half,y,center+half,y),('#6e6c7b','#9a858b','#b4998d')[i%3])
    for i in range(7):
        y=390+i*9
        x=185+i*9
        s.line((x-14-i*2,y,x+11+i*2,y),'#a98b87' if i%2 else '#647a83')
    s.poly([(165,364),(192,364),(222,383),(183,402),(151,395),(145,378)],'#33374b','#82758a')
    s.poly([(153,387),(191,393),(217,382),(209,396),(179,407),(151,397)],'#263447')
    # The seated figure faces the quiet horizon.
    s.ellipse(179,326,9,10,'#303344','#e1bb94',2)
    s.poly([(171,336),(184,336),(192,347),(189,362),(201,376),(180,379),(161,375),
            (170,360),(165,350)],'#3a3c4c','#a79b94')
    s.line([(174,338),(172,349),(175,364),(170,373)],'#727b83',2)
    s.line([(191,347),(189,360),(200,376)],'#c1a393',2)
    s.line([(170,338),(167,349),(171,356)],'#f4caa0')
    s.line([(163,377),(176,382),(188,379),(202,379)],'#67657a')
    s.glaze(178,285,150,88,'#d8b391',.12)
    bloom(s,7,.44)
    return s


BUILDERS = dict(zip(NAMES, (coder, astronomy, music, robotics, philosophy,
                           night_train, lighthouse, jellyfish, dunes, beetle,
                           relay_cabin, silicon, signal_city, circuit_garden, future_quiet), strict=True))
ASCII_SIGNATURES = {
    'El último andén': ((164, 192), '#eccc91'),
    'Faro de niebla': ((104, 283), '#ddd6c9'),
    'Medusas de medianoche': ((277, 452), '#91a2c2'),
    'Mar de dunas': ((307, 418), '#dca68b'),
    'Escarabajo de cobre': ((277, 400), '#9cbba1'),
    'Terminal de medianoche': ((44, 452), '#ffc287'),
    'Corazón de silicio': ((147, 277), '#bddbcc'),
    'La ciudad de las señales': ((289, 248), '#f4bed6'),
    'El jardín de los circuitos': ((169, 374), '#e2e1b4'),
    'La quietud del futuro': ((291, 305), '#e5bda5'),
}


def luminous_characters(source, characters, detail, font, glyph_atlas):
    """An unlit terminal surface with colored glyphs in place of filled shapes."""
    cell_w, cell_h = 3, 4
    cols, rows = WIDTH // cell_w, HEIGHT // cell_h
    cells = source.reshape(rows, cell_h, cols, cell_w, 3)
    rgb = cells.mean(axis=(1, 3))
    value = rgb.max(axis=-1)
    peak = cells.max(axis=(1, 3, 4))
    chroma = value - rgb.min(axis=-1)
    luminance = value * .66 + peak * .34
    edge = ((peak - value) / 105).clip(0, 1)
    signal = ((luminance - 19) / 179).clip(0, 1)
    rng = np.random.default_rng(541)
    grain = rng.uniform(-.085, .085, signal.shape)
    weight = (signal ** .82 + grain + (edge * .21 if detail else 0)).clip(0, 1)

    # Sufficient gutter between glyphs keeps a black gap even in bright areas.
    glyphs = ''.join(dict.fromkeys(' .:+x*oX#@' + characters))
    face = font('consolab.ttf', 14)
    atlas = glyph_atlas(face, glyphs, cell_w * 3, cell_h * 3)
    coverage = atlas.mean(axis=(1, 2))
    target = weight * coverage.max()
    index = np.abs(coverage - target[..., None]).argmin(axis=-1)
    index[(luminance < 24) | ((signal < .14) & (grain < -.06))] = 0
    masks = atlas[index]
    if detail:
        dy, dx = np.gradient(value, cell_h, cell_w)
        borders = (np.hypot(dx, dy) > 13) & (edge > .23) & (signal > .25)
        angle = np.where(np.abs(dx) > np.abs(dy)*2, 0,
                         np.where(np.abs(dy) > np.abs(dx)*2, 1, np.where(dx*dy>0,2,3)))
        contours = glyph_atlas(face, '|-/\\', cell_w * 3, cell_h * 3)
        masks[borders] = contours[angle[borders]]
    # A phosphor-like shoulder around bright strokes gives rims enough weight
    # for a small preview while preserving the black gutters in the grid.
    dots = np.pad(masks, ((0,0),(0,0),(1,1),(1,1)))
    softened = np.maximum.reduce((dots[:,:,1:-1,1:-1], dots[:,:,1:-1,:-2],
                                 dots[:,:,1:-1,2:], dots[:,:,:-2,1:-1],
                                 dots[:,:,2:,1:-1]))
    gain = ((signal + edge*.25 - .37)*1.01).clip(0,.68)
    masks = np.maximum(masks, (softened * gain[...,None,None]).astype('uint8'))

    # Normalize chroma before adding luminance so dark blue never washes to gray.
    r,g,b = (rgb[..., i] for i in range(3))
    aqua = ((g / np.maximum(b, 1) - .42) / .51).clip(0,1)
    warm = ((r - b*.87 - 7) / 42).clip(0,1)
    blue = np.array((21,91,222)) + aqua[..., None] * (8,129,20)
    amber = np.array((254,118,56)) + (g / np.maximum(r, 1))[..., None] * (0,64,26)
    hue = blue*(1-warm[...,None]) + amber*warm[...,None]
    white = ((signal-.66)*2.8).clip(0, .80) * (1 - (chroma / 360).clip(0, .55))
    paper = np.array((206,249,255)) + warm[...,None]*(49,-10,-61)
    ink = (hue*(1-white[...,None]) + paper*white[...,None])
    ink *= (.33 + .67 * (signal ** .48 + edge*.35).clip(0,1))[...,None]
    ink = Image.fromarray(ink.clip(0,255).astype('uint8')).resize(SIZE, Image.Resampling.NEAREST)
    stencil = Image.fromarray(masks.transpose(0,2,1,3).reshape(SIZE[1], SIZE[0]))
    image = Image.new('RGB', SIZE, (2,3,8))
    image.paste(ink,(0,0),stencil)
    return image


def colored_characters(source, characters, detail, font, glyph_atlas):
    """Use glyph density for tone and align edge glyphs with the local contour."""
    cell_w, cell_h = 3, 6
    cols, rows = WIDTH // cell_w, HEIGHT // cell_h
    cells = source.reshape(rows, cell_h, cols, cell_w, 3)
    rgb = cells.mean(axis=(1, 3))
    light = rgb @ np.array((.2126, .7152, .0722))
    # Keep the saturation of distant shadows and roll off light sources smoothly.
    tone = np.clip((light - 12) / 214, 0, 1)
    matte_gain = .58 + .34 * tone ** .65
    matte = (rgb * matte_gain[..., None]).astype('uint8')
    ink = (rgb * 1.13 + (12 + tone ** .64 * 48)[..., None]).clip(0, 255).astype('uint8')

    glyphs = ''.join(dict.fromkeys(' .,:;^+=oxX%#@' + characters))
    face = font('consola.ttf', 16)
    atlas = glyph_atlas(face, glyphs, cell_w * 3, cell_h * 3)
    coverage = atlas.mean(axis=(1, 2))
    order = np.argsort(coverage, kind='stable')
    atlas, coverage = atlas[order], coverage[order]
    noise = np.random.default_rng(143).random(light.shape) - .5
    weight = np.clip(tone ** .83 + noise * (.13 - .06 * tone), 0, 1)
    if detail:
        variance = cells.std(axis=(1, 3)).mean(axis=-1)
        weight = np.clip(weight + variance * .002, 0, 1)
    desired = weight * coverage[-1]
    index = np.abs(coverage - desired[..., None]).argmin(axis=-1)
    masks = atlas[index]
    if detail:
        dy, dx = np.gradient(light, cell_h, cell_w)
        magnitude = np.hypot(dx, dy)
        edges = (magnitude > 6.8) & (light > 37) & (light < 195)
        ax, ay = np.abs(dx), np.abs(dy)
        direction = np.where(ay > ax * 2.25, 0,
                             np.where(ax > ay * 2.25, 1, np.where(dx * dy > 0, 2, 3)))
        contours = glyph_atlas(face, '-|/\\', cell_w * 3, cell_h * 3)
        masks[edges] = contours[direction[edges]]

    pixels = Image.fromarray(matte).resize(SIZE, Image.Resampling.BILINEAR)
    field = Image.fromarray(ink).resize(SIZE, Image.Resampling.NEAREST)
    stencil = masks.transpose(0, 2, 1, 3).reshape(SIZE[1], SIZE[0])
    pixels.paste(field, (0,0), Image.fromarray(stencil))
    return pixels


@lru_cache(maxsize=16)
def prepare(name, style, characters, detail, signature, font, glyph_atlas):
    """Return the immutable background at the pixel-art working resolution."""
    scene = BUILDERS[name](font)
    pixels = np.asarray(scene.image, dtype=np.float32)
    if name in ASCII_SIGNATURES:
        if style == 'ASCII':
            render_characters = luminous_characters if name in SILICIO else colored_characters
            image = render_characters(pixels, characters, detail, font, glyph_atlas)
        else:
            pixels = (np.round(pixels / 4 + DITHER[..., None]) * 4).clip(0, 255).astype('uint8')
            image = Image.fromarray(pixels).resize(SIZE, Image.Resampling.NEAREST)
        (x, y), ink = ASCII_SIGNATURES[name]
        ImageDraw.Draw(image).text((x*3, y*3), signature or 'LEMC',
                                   font=font('consola.ttf', 23), fill=ink, anchor='la')
        return image
    # Preserve dark material colors while giving midtones a four-pixel dither.
    pixels = (np.round(pixels / 4 + DITHER[..., None]) * 4).clip(0, 255).astype('uint8')
    image = Image.fromarray(pixels)
    if style == 'ASCII':
        cell_w, cell_h = 5, 8
        cols, rows = WIDTH // cell_w, HEIGHT // cell_h
        means = pixels.reshape(rows, cell_h, cols, cell_w, 3).mean(axis=(1, 3))
        light = means @ np.array((.2126, .7152, .0722))
        glyphs = ' .,:;+-=x*o%#@' + ''.join(dict.fromkeys(characters))
        atlas = glyph_atlas(font('consola.ttf', 8), glyphs, cell_w, cell_h)
        atlas = atlas[np.argsort(atlas.sum(axis=(1, 2)))]
        if detail:
            contrast = pixels.reshape(rows, cell_h, cols, cell_w, 3).std(axis=(1, 3)).mean(axis=-1)
        else:
            contrast = 0
        index = (light*.058 + contrast*.12).clip(0, len(atlas)-1).astype('intp')
        mask = atlas[index].transpose(0, 2, 1, 3).reshape(HEIGHT, WIDTH) * .48
        field = np.clip(means*1.12 + 63, 0, 255).astype('uint8')
        image.paste(Image.fromarray(field.repeat(cell_h, 0).repeat(cell_w, 1)), (0, 0),
                    Image.fromarray(mask.astype('uint8')))
    if signature and signature != 'LEMC':
        ImageDraw.Draw(image).text((345, 467), signature, '#a49886',
                                   font=font('consola.ttf', 8), anchor='rs')
    return image


def frame(background, name, time, duration, animate):
    image = background.copy()
    if name in ASCII_SIGNATURES:
        return image
    if animate:
        phase = tau*time/duration
        draw = ImageDraw.Draw(image)
        if name == NAMES[0]:
            draw.rectangle((184, 197, 188, 199), fill=('#b7eca6' if sin(phase*4) > 0 else '#54877a'))
            y = round(175+48*(.5+.5*sin(phase)))
            draw.line((168, y, 268, y+9), '#6baca0')
        elif name == NAMES[1]:
            for i, (x, y) in enumerate(((58, 84), (247, 64), (308, 98), (62, 235), (277, 247))):
                if sin(phase*3+i*1.5) > .4:
                    draw.line((x-2, y, x+2, y), '#b88eaa')
                    draw.point((x, y), '#ffe0b1')
        elif name == NAMES[2]:
            for i in range(3):
                a = phase*4 + tau*i/3
                draw.point((143+9*cos(a), 338+5*sin(a)), '#ffa88e')
        elif name == NAMES[3]:
            for i in range(5):
                draw.rectangle((152+i*13, 303, 154+i*13, 304),
                               fill='#ffcc7e' if sin(phase*4+i) > .4 else '#638a73')
        else:
            for i in range(8):
                x = 111+i*18 + 4*sin(phase+i)
                y = 196+i*11 + 5*cos(phase+i*.7)
                draw.point((round(x), round(y)), '#c1af8a')
    return image.resize(SIZE, Image.Resampling.NEAREST)
