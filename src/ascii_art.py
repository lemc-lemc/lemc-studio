import ast
import math
import os
import re
import textwrap
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageOps

from audio_mix import normalize as normalize_mix
from designs import CODE_THEMES, DESIGNS, PALETTES, silhouette
from media import FITS, VIDEO_ROTATIONS
import arte_procedural
import caballero_del_faro
import faro_tormenta
import mundos_ascii
import planos
import personaje


WIDTH, HEIGHT = 720, 1280
STAGE_HEIGHT = 764
CELL_W, CELL_H = 8, 10
COLUMNS, ROWS = WIDTH // CELL_W, STAGE_HEIGHT // CELL_H
ASCII_WORLDS = {caballero_del_faro.NAME: caballero_del_faro.Scene, faro_tormenta.NAME: faro_tormenta.prepare,
                **dict.fromkeys(mundos_ascii.NAMES, mundos_ascii.prepare)}
FIGURES = (*DESIGNS, *arte_procedural.NAMES, *ASCII_WORLDS)
SOURCES = ('Figura 3D', 'Imagen', 'Video')
MEDIA_STYLES = ('ASCII', 'Pixel art')
HYBRID_MODES = ('Escena completa', 'Entorno en ASCII', 'Protagonista en ASCII')
IMAGE_MOVEMENTS = ('Fijo', 'Balanceo', 'Dúo', 'Paralaje suave')
MEDIA_ANIMATIONS = ('Sin animación', 'Ascenso', 'Acercamiento', 'Recorrido lateral')
MEDIA_COLORS = ('Original', 'Paleta', 'Monocromo')
SOUNDS = ('Ambiente', 'Silencio', 'Archivo de audio', 'Audio del video')
GLYPHS = ' ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:+*#@·▲◆■'
GLYPH_ID = {glyph: i for i, glyph in enumerate(GLYPHS)}
LEAF, FROST, TRUNK, LIGHT, RED, GOLD, STAR, GIFT, RIBBON, SHADE, EMBLEM = range(11)
DEFAULTS = {
    'mundo_luz': mundos_ascii.LIGHTING[0], 'mundo_clima': mundos_ascii.WEATHER[0],
    'animacion_fuente': MEDIA_ANIMATIONS[0], 'intensidad_movimiento': 65, 'estela_ascenso': False,
    'puntos_escape': '',
    'giro_video': 'Según archivo', 'fin_ascii': None, 'tramos_original': '', 'fundido_video': .35,
    'planos_camara': '',
    'archivo_personaje': '', 'movimiento_personaje': '', 'balanceo_personaje': False,
    'mantener_codigo': True, 'panel_reactivo': False, 'repetir_audio': False, 'prueba_reescalada': False,
    'figura': 'Árbol', 'paleta': 'Invierno', 'caracteres': 'INVIERNO2026', 'mensaje': 'LUCES DE INVIERNO',
    'duracion': 20.0, 'vueltas': 0.75, 'particulas': True, 'detalles': True, 'codigo': True,
    'fuente': 'Figura 3D', 'archivo': '', 'ajuste': 'Encajar', 'modo_color': 'Original',
    'columnas': 78, 'contraste': 1.25, 'brillo': 0.0, 'invertir': False,
    'modo_hibrido': HYBRID_MODES[0], 'color_protagonista': '#ed8aae', 'tolerancia_color': 22,
    'rampa': ' .:-=+*#%@', 'bucle': True,
    'sonido': 'Ambiente', 'pista': '', 'inicio': 0.0, 'fin': None, 'navidad_nocturna': False,
    'tema_codigo': 'Terminal',
    'mensaje_desde': 70, 'mensaje_completo': 85, 'mensaje_hasta': 96.5, 'mensaje_fundido': False, 'tamano_mensaje': 0, 'movimiento_imagen': 'Fijo', 'estilo_media': 'ASCII', 'realzar_bordes': False,
    'detalle_sombras': False, 'panel_compacto': False, 'opacidad_panel': 100, 'polvo_dorado': False, 'suavizar_bordes': False, 'nieve_ascii': False, 'led_navidad': False, 'estrella_destellos': False, 'regalos_extra': False, 'nevada_intensa': False, 'cierre_invernal': False, 'margen_tiktok': False, 'lienzo_original': False, 'fondo_estadio': False, 'acentos_baile': '', 'zooms_video': '', 'zoom_progresivo': False, 'movimiento_orbital': False, 'flujo_orbital': False, 'flujo_exterior': False, 'escena_amplia': False, 'escena_maxima': False, 'solo_video': False, 'realce_estela': False, 'ritmo_flujo_orbital': 10.0, 'archivo_panel': 'ascii_art.py', 'firma_ascii': '', 'velocidad_video': 1.0,
}
KEYWORD = re.compile(r'#[^\n]*|"[^"\n]*"|\x27[^\x27\n]*\x27|\b\d+(?:\.\d+)?\b|\b\w+\b|[^\w]')


def dance_cues(value, duration):
    if not isinstance(value, str) or len(value) > 250:
        raise ValueError('Usa marcas de baile con tiempo y posición.')
    cues = []
    try:
        for field in value.split(';') if value.strip() else ():
            time, x, y = map(float, field.split(','))
            if not (0 <= time <= duration and 0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError
            cues.append((time, x, y))
    except ValueError:
        raise ValueError('Cada marca usa tiempo,x,y. Las posiciones van de 0 a 1.') from None
    return cues


def exhaust_points(value):
    if not isinstance(value, str) or len(value) > 100:
        raise ValueError('Escribe hasta cuatro salidas del escape.')
    if not value.strip():
        return ()
    try:
        points = [tuple(map(float, entry.split(','))) for entry in value.split(';')]
        if len(points) > 4 or any(len(point) != 2 or not all(0 <= v <= 100 for v in point) for point in points):
            raise ValueError
    except ValueError:
        raise ValueError('Usa hasta cuatro puntos x,y de 0 a 100, separados por punto y coma.') from None
    return tuple((x / 100, y / 100) for x, y in points)


def original_ranges(text, total):
    if not isinstance(text, str):
        raise ValueError('Escribe los tramos del original en una línea.')
    if not text.strip():
        return ()
    intervals = []
    pattern = r'\s*(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)?\s*'
    for item in text.split(';'):
        match = re.fullmatch(pattern, item)
        if match is None:
            raise ValueError('Escribe tramos como 5-10; 18-24; 30-. Deja abierto el último para continuar hasta el final.')
        start_text, end_text = match.groups()
        start = float(start_text.replace(',', '.'))
        end = float(end_text.replace(',', '.')) if end_text else total
        if not 0 <= start < end <= total or (intervals and start <= intervals[-1][1]):
            raise ValueError('Ordena los tramos del original, deja espacio entre ellos y mantenlos dentro del reel.')
        intervals.append((start, end))
    return tuple(intervals)


def config(raw, folder=None):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError('La animación ASCII necesita una configuración válida.')
    data = DEFAULTS | raw
    for key, choices in (('figura', FIGURES), ('paleta', PALETTES), ('fuente', SOURCES), ('ajuste', FITS),
                         ('mundo_luz', mundos_ascii.LIGHTING), ('mundo_clima', mundos_ascii.WEATHER),
                         ('movimiento_imagen', IMAGE_MOVEMENTS), ('animacion_fuente', MEDIA_ANIMATIONS), ('giro_video', VIDEO_ROTATIONS),
                         ('estilo_media', MEDIA_STYLES), ('modo_hibrido', HYBRID_MODES), ('modo_color', MEDIA_COLORS), ('sonido', SOUNDS), ('tema_codigo', CODE_THEMES)):
        if data[key] not in choices:
            raise ValueError(f'Selecciona una opción válida para «{key}».')
    for key, low, high in (('duracion', 2, 120), ('tolerancia_color', 5, 50), ('opacidad_panel', 0, 100), ('tamano_mensaje', 0, 52), ('ritmo_flujo_orbital', 1, 40), ('velocidad_video', .25, 3), ('vueltas', -3, 3), ('columnas', 28, 135),
                           ('mensaje_desde', 0, 95), ('mensaje_completo', 0, 96), ('mensaje_hasta', 0, 100),
                           ('contraste', 0.4, 3), ('brillo', -0.5, 0.5), ('inicio', 0, math.inf),
                           ('intensidad_movimiento', 0, 100), ('fundido_video', 0, 3)):
        try:
            value = float(str(data[key]).replace(',', '.'))
        except (ValueError, TypeError):
            value = float('nan')
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError('El inicio del audio debe ser un número positivo o cero.' if key == 'inicio'
                             else f'«{key}» debe estar entre {low} y {high}.')
        if key == 'columnas' and not value.is_integer():
            raise ValueError('Escribe un número entero para las columnas.')
        data[key] = int(value) if key == 'columnas' else value
    if data['mensaje_hasta'] <= data['mensaje_completo']:
        raise ValueError('El mensaje debe terminar después de aparecer completo.')
    if data['mensaje_completo'] <= data['mensaje_desde']:
        raise ValueError('El mensaje completo debe aparecer después de que empiece a escribirse.')
    if data['fin'] in ('', None):
        data['fin'] = None
    else:
        try:
            data['fin'] = float(str(data['fin']).replace(',', '.'))
        except (ValueError, TypeError):
            raise ValueError('El final del audio debe ser un número.') from None
        if not math.isfinite(data['fin']) or data['fin'] <= data['inicio']:
            raise ValueError('El final del audio debe ser posterior al inicio.')
    if data['fin_ascii'] in ('', None):
        data['fin_ascii'] = None
    else:
        try:
            data['fin_ascii'] = float(str(data['fin_ascii']).replace(',', '.'))
        except (TypeError, ValueError):
            raise ValueError('Escribe un segundo válido para mostrar el video original.') from None
        if not (math.isfinite(data['fin_ascii']) and 0 <= data['fin_ascii'] < 120):
            raise ValueError('El segundo de cambio debe ser mayor o igual a cero y menor que 120.')
        if data['fuente'] == 'Video' and data['fin_ascii'] >= data['duracion']:
            raise ValueError('El segundo de cambio debe ser anterior al final del reel.')
    if data['fuente'] == 'Video':
        original_ranges(data['tramos_original'], data['duracion'])
    if data['fuente'] != 'Figura 3D':
        planos.parse(data['planos_camara'], data['duracion'])
        personaje.keyframes(data['movimiento_personaje'], data['duracion'])
    if type(data['balanceo_personaje']) is not bool:
        raise ValueError('El balanceo del personaje debe estar activado o desactivado.')
    if type(data['panel_reactivo']) is not bool:
        raise ValueError('El color del panel según la escena debe estar activado o desactivado.')
    if type(data['navidad_nocturna']) is not bool:
        raise ValueError('La escena navideña debe estar activada o desactivada.')
    for key in ('caracteres', 'mensaje'):
        if not isinstance(data[key], str) or '\n' in data[key] or '\r' in data[key]:
            raise ValueError('Escribe los caracteres y el mensaje en una sola línea.')
    if not any(char in GLYPH_ID and char != ' ' for char in data['caracteres'].upper()) or len(data['caracteres']) > 70:
        raise ValueError('Usa de 1 a 70 caracteres, con al menos una letra A–Z, un número o un símbolo ASCII visible.')
    dance_cues(data['acentos_baile'], data['duracion'])
    dance_cues(data['zooms_video'], data['duracion'])
    exhaust_points(data['puntos_escape'])
    panel_name = data['archivo_panel']
    if not isinstance(panel_name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,35}\.py', panel_name, re.IGNORECASE):
        raise ValueError('El nombre del panel debe terminar en .py.')
    signature = data['firma_ascii']
    if not isinstance(signature, str) or len(signature) > 24 or any(char in signature for char in '\r\n'):
        raise ValueError('Escribe una firma de hasta 24 caracteres en una línea.')
    if len(data['mensaje']) > 96:
        raise ValueError('El mensaje admite hasta 96 caracteres.')
    for key in ('particulas', 'detalles', 'codigo', 'invertir', 'bucle', 'realzar_bordes', 'detalle_sombras', 'panel_compacto', 'polvo_dorado', 'suavizar_bordes', 'nieve_ascii', 'led_navidad', 'estrella_destellos', 'regalos_extra', 'nevada_intensa', 'cierre_invernal', 'mensaje_fundido', 'margen_tiktok', 'lienzo_original', 'fondo_estadio', 'zoom_progresivo', 'movimiento_orbital', 'flujo_orbital', 'flujo_exterior', 'escena_amplia', 'escena_maxima', 'solo_video', 'realce_estela', 'estela_ascenso', 'mantener_codigo', 'repetir_audio', 'prueba_reescalada'):
        if type(data[key]) is not bool:
            raise ValueError('Los interruptores de la animación deben ser verdaderos o falsos.')
    for key in ('color_figura', 'color_fondo', 'color_protagonista'):
        if key in data and (not isinstance(data[key], str) or not re.fullmatch('#[0-9a-fA-F]{6}', data[key])):
            raise ValueError('Elige un color RGB hexadecimal de seis dígitos.')
    ramp = data['rampa']
    if not isinstance(ramp, str) or not 2 <= len(ramp) <= 30 or not ramp.isprintable() or not ramp.strip():
        raise ValueError('La rampa necesita de 2 a 30 caracteres visibles o espacios, de menor a mayor densidad.')
    for key in ('archivo', 'pista', 'archivo_personaje'):
        if not isinstance(data[key], str):
            raise ValueError('Selecciona un archivo local válido.')
        if data[key] and folder is not None:
            data[key] = str((folder / data[key]).resolve())
    result = {key: data[key] for key in (*DEFAULTS, 'color_figura', 'color_fondo') if key in data}
    result['mezcla'] = normalize_mix(data.get('mezcla'), folder)
    return result


def project_mode(project, folder):
    raw = project.get('animacion_ascii')
    mode = project.get('modo', 'ascii' if raw else 'letra')
    if mode not in ('letra', 'ascii'):
        raise ValueError('El modo del proyecto debe ser Letra o ASCII.')
    if project.get('version_proyecto', 1) < 5 and raw and project.get('audio_local'):
        raw = {**raw, 'sonido': 'Archivo de audio', 'pista': project['audio_local'],
               'inicio': project.get('inicio_audio', 0), 'fin': project.get('fin_audio')}
    return mode, config(raw or DEFAULTS, folder)


def full_media_canvas(data):
    return data.get('lienzo_original') and (
        data['fuente'] == 'Video' or
        (data['fuente'] == 'Imagen' and data.get('animacion_fuente', MEDIA_ANIMATIONS[0]) != MEDIA_ANIMATIONS[0])
    )


def media_area(data):
    if data.get('solo_video'):
        return (0, 0, WIDTH, HEIGHT)
    if data.get('escena_maxima') and data['fuente'] == 'Video':
        return (2, 100, 716, 740)
    if data.get('escena_amplia') and data['fuente'] == 'Video':
        return (8, 156, 704, 630)
    if full_media_canvas(data):
        return (0, 0, WIDTH, HEIGHT)
    if data.get('margen_tiktok') and data['fuente'] != 'Figura 3D' and data['codigo']:
        return (22, 152, 676, 685)
    if data['codigo'] and data.get('panel_compacto'):
        return (34, 117, 652, 745)
    return (34, 117, 652, 574 if data['codigo'] else 934)


def audio_path(data):
    if data['sonido'] == 'Archivo de audio':
        if not data['pista']:
            raise ValueError('Elige una pista local en «Audio ASCII».')
        return Path(data['pista'])
    if data['sonido'] == 'Audio del video':
        if data['fuente'] != 'Video' or not data['archivo']:
            raise ValueError('Selecciona un video como fuente para usar su audio.')
        return Path(data['archivo'])
    return None


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def points(position, normal, kind, reveal, rng):
    position = np.asarray(position)
    count = len(position)
    return np.column_stack((position, np.broadcast_to(normal, (count, 3)),
                            np.broadcast_to(kind, count), np.broadcast_to(reveal, count), rng.random(count)))


def cone_radius(level, tier):
    base, top, radius = tier
    height = np.clip((level - base) / (top - base), 0, 1)
    return radius * (1 - height) ** 1.26 + 0.035


TIERS = ((0.76, 2.94, 2.35), (1.82, 3.94, 1.77), (2.98, 4.93, 1.24))


def outer_radius(level):
    return max((cone_radius(level, tier) for tier in TIERS if tier[0] <= level <= tier[1]), default=0.04)


def ring(level, radius, angle, kind, reveal, rng):
    radius = np.broadcast_to(radius, len(angle))
    normal = np.column_stack((np.cos(angle), np.full(len(angle), 0.28), np.sin(angle)))
    xyz = np.column_stack((radius * normal[:, 0], np.broadcast_to(level, len(angle)), radius * normal[:, 2]))
    return points(xyz, normal, kind, reveal, rng)


def build_tree(rng, details, extra_gifts=False):
    # The lower skirts are wider. Their icy edges appear as the tiers grow.
    layers = []
    for level in np.linspace(0.02, 1, 11):
        angle = np.linspace(0, 2 * np.pi, 34, endpoint=False)
        layers.append(ring(level, 0.27, angle, TRUNK, 0.035 + 0.055 * level, rng))
    for tier_index, tier in enumerate(TIERS):
        for i, level in enumerate(np.linspace(tier[0], tier[1], 31)):
            radius = cone_radius(level, tier)
            count = round(18 + radius * 46)
            angle = np.linspace(0, 2 * np.pi, count, endpoint=False) + i * 0.19
            branch = radius * (1 + 0.045 * np.sin(angle * 7 + tier_index) + 0.025 * np.sin(angle * 13 + i))
            kind = np.full(count, LEAF)
            if 2 <= i <= 4:
                kind[:] = SHADE
            if i < 2:
                kind[rng.random(count) > 0.16] = FROST
                branch += 0.018
            elif i < 24:
                kind[rng.random(count) > 0.974] = FROST
            appears = 0.092 + 0.255 * level / 4.93 + rng.uniform(-0.01, 0.045, count)
            layers.append(ring(level, branch, angle, kind, appears, rng))
    if details:
        for i, level in enumerate(np.linspace(0.88, 4.8, 204)):
            angle = np.array([i * 0.174 + 0.2])
            layers.append(ring(level, outer_radius(level) + 0.085, angle, LIGHT, 0.37 + 0.23 * i / 203, rng))
        for i, level in enumerate(rng.uniform(0.98, 3.95, 29)):
            angle = rng.uniform(0, 2 * np.pi)
            radius = outer_radius(level) + 0.09
            center = (radius * math.cos(angle), level, radius * math.sin(angle))
            layers.append(bulb(center, 0.085, RED if i % 3 else GOLD, 0.43 + i * 0.008, rng))
        layers.append(build_emblem('Estrella', rng, False, (0, 5.18, 0), 0.34, STAR, 0.59))
        for i, origin in enumerate(((-1.17, 0, 0.82), (0.91, 0, 0.71), (-0.48, 0, 1.37), (1.34, 0, 0.22))):
            layers.append(gift_box(origin, (0.29, 0.22 + i * 0.043, 0.21), 0.645 + i * 0.028, i, rng))
        if extra_gifts:
            gifts = (
                ((-1.60, 0, -0.42), (0.24, 0.27, 0.23)),
                ((1.55, 0, -0.66), (0.31, 0.19, 0.24)),
                ((0.25, 0, 1.75), (0.22, 0.28, 0.20)),
                ((-0.85, 0, -1.37), (0.33, 0.30, 0.26)),
            )
            for i, (origin, half) in enumerate(gifts):
                layers.append(gift_box(origin, half, 0.69 + i * 0.028, i + 5, rng))
    return np.concatenate(layers)


def bulb(center, radius, kind, appears, rng):
    polar = np.linspace(0.2, np.pi - 0.2, 5)
    angle = np.arange(9) * 2 * np.pi / 9
    polar, angle = np.meshgrid(polar, angle)
    normal = np.column_stack((np.sin(polar.ravel()) * np.cos(angle.ravel()), np.cos(polar.ravel()),
                              np.sin(polar.ravel()) * np.sin(angle.ravel())))
    return points(np.asarray(center) + radius * normal, normal, kind, appears, rng)


def gift_box(origin, half, appears, variant, rng):
    a, b = np.meshgrid(np.linspace(-1, 1, 12), np.linspace(-1, 1, 12))
    a, b = a.ravel(), b.ravel()
    sides = []
    for axis in range(3):
        for side in (-1, 1):
            if axis == 1 and side == -1:
                continue
            xyz = np.zeros((len(a), 3))
            xyz[:, axis] = side
            xyz[:, (axis + 1) % 3], xyz[:, (axis + 2) % 3] = a, b
            normal = np.zeros(3)
            normal[axis] = side
            design = np.where(np.abs(xyz[:, 0]) < 0.19, RIBBON, GIFT if variant % 2 else RED)
            if axis == 0:
                design = np.where(np.abs(xyz[:, 2]) < 0.19, RIBBON, GIFT if variant % 2 else RED)
            if axis == 1:
                design[np.abs(xyz[:, 2]) < 0.18] = RIBBON
            sides.append(points(xyz * half + np.asarray(origin) + (0, half[1] + 0.02, 0), normal, design, appears, rng))
    for sign in (-1, 1):
        angle = np.linspace(0, 2 * np.pi, 22)
        bow = np.column_stack((sign * (0.09 + 0.082 * np.cos(angle)), 0.05 * np.sin(angle), 0.035 * np.sin(angle * 2)))
        sides.append(points(bow + np.asarray(origin) + (0, 2 * half[1] + 0.07, 0), (0, 0.8, 0.6), RIBBON, appears, rng))
    return np.concatenate(sides)


def outline(figure):
    if figure == 'Corazón':
        a = np.linspace(0, 2 * np.pi, 180)
        x = np.sin(a) ** 3
        y = (13 * np.cos(a) - 5 * np.cos(2 * a) - 2 * np.cos(3 * a) - np.cos(4 * a)) / 16 + 0.17
        return np.column_stack((x, y))
    a = np.pi / 2 + np.arange(11) * np.pi / 5
    radius = np.where(np.arange(11) % 2, 0.49, 1.0)
    coarse = np.column_stack((np.cos(a) * radius, np.sin(a) * radius))
    wave = np.linspace(0, 1, 19)[:-1, None]
    return np.concatenate([start + wave * (end - start) for start, end in zip(coarse[:-1], coarse[1:])])


def build_emblem(figure, rng, details, center=(0, 2.62, 0), radius=2.19, kind=EMBLEM, begins=0.10):
    # Two rounded faces and a deep rim keep the silhouette legible as it rotates.
    edge = outline(figure) * radius
    layers = []
    for sign in (-1, 1):
        for fraction in np.linspace(0.04, 1, 34):
            xy = fraction * edge
            depth = sign * radius * (0.12 + 0.08 * (1 - fraction * fraction))
            reveal = begins + 0.23 * (xy[:, 1] / (radius * 2) + 0.55) if kind == EMBLEM else begins
            normal = np.column_stack((xy / (radius * 4), np.full(len(xy), sign * 0.94)))
            material = FROST if fraction > 0.95 and kind == EMBLEM else kind
            layers.append(points(np.column_stack((xy, np.full(len(xy), depth))) + center, normal, material, reveal, rng))
    for z in np.linspace(-0.12, 0.12, 10) * radius:
        xyz = np.column_stack((edge, np.full(len(edge), z))) + center
        normal = np.column_stack((edge / radius, np.zeros(len(edge))))
        reveal = begins + 0.25 * (edge[:, 1] / (radius * 2) + 0.55) if kind == EMBLEM else begins
        layers.append(points(xyz, normal, kind, reveal, rng))
    if details:
        for side in (-1, 1):
            xy = edge[::4] * 1.04
            sparks = np.column_stack((xy, np.full(len(xy), side * radius * 0.15))) + center
            layers.append(points(sparks, (0, 0, side), LIGHT, np.linspace(0.35, 0.65, len(xy)), rng))
    return np.concatenate(layers)


def build_symbol(figure, rng, details):
    # Sample the silhouette on two faces and add a rim without filling any holes.
    samples = 85
    mask = silhouette(figure, samples)
    filled = np.asarray(mask) > 127
    inside = np.asarray(mask.filter(ImageFilter.MinFilter(5))) > 127
    layers = []
    y, x = np.nonzero(filled)
    x, y = (x / (samples - 1) - .5) * 4.85, 5.05 - y / (samples - 1) * 4.85
    height = np.clip((y - .3) / 4.7, 0, 1)
    reveal = .09 + height * .28 + rng.uniform(-.019, .021, len(x))
    for sign in (-1, 1):
        z = sign * (.25 + .11 * (1 - (x / 2.7) ** 2))
        layers.append(points(np.column_stack((x, y, z)), (0, .12, .98 * sign), EMBLEM, reveal, rng))
    rim_y, rim_x = np.nonzero(filled & ~inside)
    gy, gx = np.gradient(np.asarray(mask.filter(ImageFilter.GaussianBlur(2)), dtype=float))
    nx, ny = -gx[rim_y, rim_x], gy[rim_y, rim_x]
    norm = np.maximum(1e-8, np.hypot(nx, ny))
    rim_normal = np.column_stack((nx / norm, ny / norm, np.zeros(len(nx))))
    rx, ry = (rim_x / (samples - 1) - .5) * 4.85, 5.05 - rim_y / (samples - 1) * 4.85
    for z in np.linspace(-.26, .26, 8):
        layers.append(points(np.column_stack((rx, ry, np.full(len(rx), z))), rim_normal, FROST,
                             .10 + np.clip((ry - .3) / 4.7, 0, 1) * .28, rng))
    if details:
        choice = np.linspace(0, len(rx) - 1, min(105, len(rx)), dtype=int)
        for sign in (-1, 1):
            xyz = np.column_stack((rx[choice], ry[choice], np.full(len(choice), sign * .39)))
            layers.append(points(xyz, (0, 0, sign), LIGHT, np.linspace(.42, .70, len(choice)), rng))
    return np.concatenate(layers)


def project(xyz, yaw, scale):
    c, s = math.cos(yaw), math.sin(yaw)
    x, y, z = xyz.T
    across, forward = x * c + z * s, -x * s + z * c
    height, depth = y * 0.989 - forward * 0.148, y * 0.148 + forward * 0.989
    perspective = scale * 11 / (11 - depth)
    return 360 + across * perspective, 658 - height * perspective, depth


def palette(data):
    background, main, light, cold = PALETTES[data['paleta']]
    background = data.get('color_fondo', background)
    main = data.get('color_figura', main)
    colors = [main, '#d4fff7', '#d69c72', light, '#ff7c88', '#ffc466', light, cold, '#fff4d3', main, main]
    return ImageColor.getrgb(background), np.array([ImageColor.getrgb(color) for color in colors]), light, cold


def glyph_atlas(font, glyphs=GLYPHS, width=CELL_W, height=CELL_H):
    masks = []
    for glyph in glyphs:
        tile = Image.new('L', (width, height))
        ImageDraw.Draw(tile).text((width / 2, height / 2 + 0.1), glyph, font=font, fill=255, anchor='mm')
        masks.append(np.asarray(tile))
    return np.asarray(masks)


@lru_cache(maxsize=1)
def source_sections():
    source = Path(__file__).with_name('ascii_art.py').read_text(encoding='utf-8')
    lines = source.splitlines()
    sections = {}
    for item in ast.parse(source).body:
        if isinstance(item, ast.FunctionDef) and item.name in {'build_tree', 'build_emblem', 'project', 'draw_particles',
                                                               'build_symbol', 'draw_glyphs', 'scene_frame', 'draw_media',
                                                               'draw_pixels', 'animate_media', 'animate_cutout'}:
            excerpt = lines[item.lineno - 1:item.end_lineno]
            sections[item.name] = [(item.lineno + i, text) for i, text in enumerate(excerpt)]
    return sections


def stadium_backdrop():
    y, x = np.ogrid[:HEIGHT, :WIDTH]
    red_haze = np.exp(-((y - 180) / 325) ** 2)
    red_haze = red_haze * (.36 + .64 * ((x - WIDTH / 2) / (WIDTH / 2)) ** 2)
    glow = sum(np.exp(-((x - edge) / 104) ** 2 - ((y - 166) / 88) ** 2) for edge in (82, 638))
    foot = np.exp(-((y - 1090) / 152) ** 2)
    rgb = np.stack((13 + 40 * red_haze + 29 * glow + foot * 9,
                    9 + 4 * red_haze + 16 * glow + foot * 3,
                    14 + 9 * red_haze + 15 * glow + foot * 3), axis=-1)
    stage = Image.fromarray(rgb.clip(0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(stage)
    for left in (49, 605):
        draw.rounded_rectangle((left, 158, left + 66, 173), radius=3, fill='#392028')
        for x in range(left + 5, left + 64, 10):
            draw.rectangle((x, 163, x + 4, 167), fill='#f3bcad')
    draw.line((34, 203, 686, 203), fill='#67262f', width=2)
    draw.line((34, 996, 686, 996), fill='#67262f', width=2)
    return stage


def christmas_leds():
    y, x = np.mgrid[-9:10, -9:10]
    alpha = (205 * np.exp(-(x*x + y*y) / 19) + 47 * np.exp(-(x*x + y*y) / 65)).clip(0, 255).astype(np.uint8)
    sprites = []
    for color in ((255, 59, 77), (255, 211, 95), (99, 221, 255), (115, 255, 164)):
        sprite = Image.new('RGB', (19, 19), color)
        sprites.append((sprite, Image.fromarray(alpha), color))
    return sprites


def holiday_stage(background, offset):
    y, x = np.ogrid[:HEIGHT, :WIDTH]
    ribbon = np.exp(-((y - 252 - .20 * (x - 340) - 52 * np.sin(x / 155)) / 153) ** 2)
    ribbon *= np.exp(-((x - 270) / 385) ** 2)
    winter = np.exp(-((x - 366) / 340) ** 2 - ((y - 413 - offset / 2) / 470) ** 2)
    ground = np.exp(-((x - 362) / 274) ** 2 - ((y - 685 - offset) / 124) ** 2)
    colors = np.array(background) + ribbon[..., None] * (9, 20, 26)
    colors += winter[..., None] * (11, 24, 28)
    colors += ground[..., None] * (19, 21, 12)
    return Image.fromarray(colors.clip(0, 255).astype('uint8'))


def is_ascii_world(data):
    return data['fuente'] == 'Figura 3D' and data['figura'] in ASCII_WORLDS


def is_procedural(data):
    return data['fuente'] == 'Figura 3D' and data['figura'] in arte_procedural.NAMES


def prepare(data, font):
    if is_ascii_world(data):
        return {'data': data, 'ascii_world': ASCII_WORLDS[data['figura']](font, glyph_atlas)}
    if is_procedural(data):
        background = arte_procedural.prepare(
            data['figura'], data['estilo_media'], data['caracteres'], data['detalles'],
            data['firma_ascii'], font, glyph_atlas)
        return {'data': data, 'procedural': background}
    rng = np.random.default_rng(6021)
    is_3d = data['fuente'] == 'Figura 3D'
    holiday = is_3d and data['figura'] == 'Árbol' and data.get('navidad_nocturna', False)
    tree_offset = 177 if holiday and data['solo_video'] else 0
    tree_scale = 103 if tree_offset else (94 if holiday else 91)
    model = None
    if is_3d:
        if data['figura'] == 'Árbol':
            model = build_tree(rng, data['detalles'], data['regalos_extra'])
            if holiday:
                branches = np.isin(model[:, 6], (TRUNK, LEAF, FROST, SHADE))
                model[branches, 7] = np.maximum(.012, model[branches, 7] * .73 - .016)
        elif data['figura'] in ('Estrella', 'Corazón'):
            model = build_emblem(data['figura'], rng, data['detalles'])
        else:
            model = build_symbol(data['figura'], rng, data['detalles'])
    background, colors, gold, blue = palette(data)
    y, x = np.ogrid[:HEIGHT, :WIDTH]
    horizon = np.exp(-(((x - 358) / 316) ** 2 + ((y - 624) / 216) ** 2))
    center = np.exp(-(((x - 355) / 288) ** 2 + ((y - 376) / 340) ** 2))
    haze_color = (84, 84, 84) if data['paleta'] == 'Carbón' else (35, 112, 154)
    backdrop = np.stack([channel + center * shade * 0.095 + horizon * cold * 0.125
                         for channel, shade, cold in zip(background, colors[LEAF], haze_color)], axis=-1)
    stage = stadium_backdrop() if data['fondo_estadio'] else Image.fromarray(backdrop.clip(0, 255).astype('uint8'))
    if holiday:
        stage = holiday_stage(background, tree_offset)
    letters = [GLYPH_ID[glyph] for glyph in data['caracteres'].upper() if glyph in GLYPH_ID and glyph != ' ']
    theme = CODE_THEMES[data.get('tema_codigo', 'Terminal')]
    source = raster_code(font('consola.ttf', 16), theme) if data['codigo'] else {}
    cutout = None
    if is_3d:
        atlas = glyph_atlas(font('consola.ttf', 13))
        grid = None
    else:
        _, _, width, height = media_area(data)
        tile_w = max(4, width // data['columnas'])
        tile_h = max(7, round(tile_w * 1.53))
        grid = (tile_w, tile_h, data['columnas'], height // tile_h)
        atlas = glyph_atlas(font('consola.ttf', max(7, round(tile_w * 1.63))), data['rampa'], tile_w, tile_h)
        cutout = load_cutout(data, (width, height))
    return {'data': data, 'model': model, 'colors': colors, 'gold': gold, 'blue': blue, 'stage': stage,
            'holiday': holiday, 'tree_offset': tree_offset, 'tree_scale': tree_scale,
            'particles': rng.random((480 if data['nevada_intensa'] else 250, 5)),
            'leds': christmas_leds() if is_3d and data['led_navidad'] else (), 'letters': np.asarray(letters), 'source': source, 'theme': theme,
            'atlas': atlas, 'grid': grid, 'mono': font('consola.ttf', 20),
            'label': font('consola.ttf', 17), 'caption': font('consola.ttf', 35),
            'dance_cues': dance_cues(data['acentos_baile'], data['duracion']),
            'video_zooms': dance_cues(data['zooms_video'], data['duracion']),
            'cutout_sprite': cutout,
            'cutout_exhaust': prepare_exhaust(cutout, data['puntos_escape']) if cutout is not None and data['estela_ascenso'] else None,
            'snow_final_font': font('consola.ttf', 39) if data['cierre_invernal'] else None,
            'message_font': font('consola.ttf', round(data['tamano_mensaje'])) if data['tamano_mensaje'] >= 12 else None,
            'snow_font': font('consola.ttf', 13) if data['nieve_ascii'] else None,
            'signature': font('seguisym.ttf' if os.name == 'nt' else 'georgia.ttf', 26)
                         if data['firma_ascii'] else None}


def draw_particles(draw, particles, phase, foreground, height=STAGE_HEIGHT):
    for x, y, depth, drift, glow in particles:
        if (depth > 0.74) != foreground:
            continue
        rate = 1 + int(depth * 3)
        sx = (x * WIDTH + 28 * np.sin(2 * np.pi * phase + drift * 10)) % WIDTH
        sy = (y + phase * rate) % 1 * height
        brightness = (0.64 + 0.36 * math.sin(phase * math.tau * (1 + int(4 * glow)) + 13 * glow))
        strength = int(30 + brightness * (141 if foreground else 81) * (0.5 + depth))
        color = (max(0, strength - 19), strength, min(255, strength + 31))
        if foreground and glow > 0.53:
            draw.ellipse((sx - 1, sy - 1, sx + 1, sy + 1), fill=color)
        else:
            draw.point((sx, sy), fill=color)


def draw_floor(draw, opacity, offset=0):
    for row in range(15):
        y = 627 + offset + 97 * (row / 14) ** 1.58
        spread = 0.62 + row * 0.099
        for x in range(-12, 13):
            sx = 360 + x * 23 * spread
            fade = max(0, 1 - abs(x) / 15) * (1 - row / 24) * opacity
            color = tuple(round(tone * fade) for tone in (48, 113, 153))
            draw.line((sx - 2, y, sx + 2, y), fill=color)


def topper_glow(image, phase, color, time=None, scale=91, offset=0, period=1.85):
    amount = float(smooth((phase - 0.595) / 0.045) * (1 - smooth((phase - 0.94) / 0.045)))
    if amount <= 0:
        return
    _, projected_y, _ = project(np.array([(0, 5.18, 0)]), 0, scale)
    y = round(projected_y[0]) + offset
    light = Image.new('L', (129, 129))
    shine = ImageDraw.Draw(light)
    power = max(math.exp(-((phase - 0.65) / 0.047) ** 2), 0.29)
    pulse = 0 if time is None else (.5 + .5 * math.cos(math.tau * time / period)) ** 6
    power = max(power, pulse)
    if time is not None:
        shine.ellipse((42, 42, 86, 86), fill=round((22 + 125 * pulse) * amount))
    for i, angle in enumerate(np.arange(8) * math.tau / 8):
        radius = (29 if i % 2 else 50) * (0.4 + 0.6 * power) + pulse * 11
        shine.line((64 + math.cos(angle) * 9, 64 + math.sin(angle) * 9,
                    64 + math.cos(angle) * radius, 64 + math.sin(angle) * radius), fill=round((75 + 137 * pulse) * amount * power), width=2 if pulse > .35 else 1)
    shine.ellipse((59, 59, 69, 69), fill=round((160 + 95 * pulse) * amount))
    box = (296, y - 64, 425, y + 65)
    image.paste(color, box, light.filter(ImageFilter.GaussianBlur(6)))
    image.paste(color, box, light)


def draw_glyphs(image, prepared, phase):
    model = prepared['model']
    age = smooth((phase - model[:, 7]) / 0.09)
    visible = (age > 0) & (phase < 0.976 + 0.016 * model[:, 8])
    if not visible.any():
        return 0, 0
    chosen = model[visible]
    advance = age[visible]
    tree = prepared['data']['figura'] == 'Árbol'
    orientation = phase if tree else phase - 0.84
    yaw = 0.30 + prepared['data']['vueltas'] * math.tau * orientation
    xyz = chosen[:, :3].copy()
    xyz[:, 1] -= (1 - advance) * 0.28
    topper = chosen[:, 6] == STAR
    if topper.any():
        sx, sz = xyz[topper, 0].copy(), xyz[topper, 2].copy()
        xyz[topper, 0], xyz[topper, 2] = sx * math.cos(yaw) - sz * math.sin(yaw), sx * math.sin(yaw) + sz * math.cos(yaw)
    if not tree:
        xyz[:, 1] += 0.12 * math.sin(phase * math.tau * 2)
    offset = prepared['tree_offset']
    x, y, depth = project(xyz, yaw, prepared['tree_scale'] if tree else 104)
    col, row = (x / CELL_W).astype(int), (y / CELL_H).astype(int)
    kind = chosen[:, 6].astype(int)
    cell = row * COLUMNS + col
    valid = np.flatnonzero((col >= 0) & (col < COLUMNS) & (row >= 7) & (row < ROWS - 7))
    front = valid[np.lexsort((depth[valid], cell[valid]))]
    cells = cell[front]
    top = front[np.r_[cells[1:] != cells[:-1], True]] if len(front) else front
    cell, kind = cell[top], kind[top]
    normals = chosen[top, 3:6]
    nx = normals[:, 0] * math.cos(yaw) + normals[:, 2] * math.sin(yaw)
    nz = -normals[:, 0] * math.sin(yaw) + normals[:, 2] * math.cos(yaw)
    shaded = np.clip(0.57 + 0.36 * (-nx * 0.64 + nz * 0.70 + normals[:, 1] * 0.32), 0.26, 1)
    shaded[kind == SHADE] *= 0.64
    live = np.isin(kind, (LIGHT, STAR, RIBBON, GOLD))
    shaded[live] = 0.77 + 0.23 * np.sin(phase * 57 + chosen[top, 8][live] * 20) ** 2
    color = prepared['colors'][kind] * shaded[:, None]
    rising = ((1 - advance[top]) * 0.53)[:, None]
    color = color * (1 - rising) + np.array((216, 252, 244)) * rising
    fade = float(1 - smooth((phase - 0.94) / 0.045))
    if tree and prepared['leds']:
        for index in np.flatnonzero(kind == LIGHT):
            selected = top[index]
            variant = int(chosen[selected, 8] * 4) % 4
            sprite, halo, hue = prepared['leds'][variant]
            pulse = .55 + .45 * math.sin(phase * 24 + chosen[selected, 8] * math.tau) ** 2
            strength = float(advance[selected] * fade * pulse)
            cx = int(col[selected] * CELL_W + CELL_W / 2)
            cy = int(row[selected] * CELL_H + CELL_H / 2) + offset
            image.paste(sprite, (cx - 9, cy - 9), halo.point([round(v * strength) for v in range(256)]))
            color[index] = np.array(hue) * .62 + 96
    color *= fade
    ids = np.flatnonzero(visible)[top] % len(prepared['letters'])
    glyphs = prepared['letters'][ids]
    for material, glyph in ((FROST, '·'), (LIGHT, '*'), (GOLD, '+'), (RED, '◆'), (STAR, '+'), (RIBBON, '+')):
        glyphs[kind == material] = GLYPH_ID[glyph]
    color_grid = np.zeros((ROWS * COLUMNS, 3), dtype=np.uint8)
    chars = np.zeros(ROWS * COLUMNS, dtype=int)
    color_grid[cell] = color.clip(0, 255).astype(np.uint8)
    chars[cell] = glyphs
    mask = prepared['atlas'][chars].reshape(ROWS, COLUMNS, CELL_H, CELL_W).transpose(0, 2, 1, 3).reshape(ROWS * CELL_H, WIDTH)
    pixels = color_grid.reshape(ROWS, COLUMNS, 3).repeat(CELL_H, 0).repeat(CELL_W, 1)
    if len(cell):
        alpha = Image.fromarray(mask)
        glow = alpha.filter(ImageFilter.GaussianBlur(4)).point(lambda value: int(value * 0.48 * fade))
        main = tuple(int(tone) for tone in prepared['colors'][LEAF])
        image.paste(main, (0, offset, WIDTH, offset + ROWS * CELL_H), glow)
        image.paste(Image.fromarray(pixels), (0, offset), alpha.point(lambda value: int(value * fade)) if fade < 1 else alpha)
    return len(cell), int(np.count_nonzero(kind == LIGHT))


def move_photo(source, phase):
    width, height = source.size
    step = 48
    drift = math.sin(phase * math.tau)
    lift = 1 - math.cos(phase * math.tau)

    def viewpoint(x, y):
        depth = (y / height) ** 2
        source_x = width / 2 + (x - width / 2) * .93
        source_y = height / 2 + (y - height / 2) * .95
        return (source_x + width * drift * (.006 + .022 * depth),
                source_y - height * lift * (.003 + .006 * depth))

    mesh = []
    for y in range(0, height, step):
        bottom = min(y + step, height)
        for x in range(0, width, step):
            edge = min(x + step, width)
            corners = (*viewpoint(x, y), *viewpoint(x, bottom),
                       *viewpoint(edge, bottom), *viewpoint(edge, y))
            mesh.append(((x, y, edge, bottom), corners))
    return source.transform(source.size, Image.Transform.MESH, mesh, Image.Resampling.BICUBIC)


def draw_pixels(image, prepared, source, phase):
    data = prepared['data']
    left, top, width, height = media_area(data)
    columns = data['columnas']
    rows = max(1, round(height * columns / width))
    sampled = source.resize((columns, rows), Image.Resampling.LANCZOS).convert('RGBA')
    if data['realzar_bordes']:
        sampled = sampled.filter(ImageFilter.UnsharpMask(radius=1, percent=115, threshold=2))
    pixels = np.asarray(sampled, dtype=np.float32)
    rgb = pixels[:, :, :3]
    light = np.clip(((rgb @ np.array([.2126, .7152, .0722])) / 255 - .5) * data['contraste']
                    + .5 + data['brillo'], 0, 1)
    if data['invertir']:
        light = 1 - light
        rgb = 255 - rgb
    if data['modo_color'] == 'Original':
        color = np.clip(rgb + (light - (rgb @ np.array([.2126, .7152, .0722])) / 255)[:, :, None] * 140, 0, 255)
    else:
        ink = prepared['colors'][LEAF] if data['modo_color'] == 'Paleta' else np.array((255, 255, 255))
        color = light[:, :, None] * ink
    quantized = np.rint(color / 17) * 17
    field = Image.fromarray(quantized.astype(np.uint8)).resize((width, height), Image.Resampling.NEAREST)
    fade = float(smooth(phase / .035) * (1 - smooth((phase - .96) / .04)))
    mask = Image.fromarray((pixels[:, :, 3] * fade).astype(np.uint8)).resize((width, height), Image.Resampling.NEAREST)
    image.paste(field, (left, top), mask)
    return int(np.count_nonzero(pixels[:, :, 3] > 38))


@lru_cache(maxsize=6)
def edge_feather(width, height):
    x = np.minimum(np.arange(width) + 1, width - np.arange(width)) / 37
    y = np.minimum(np.arange(height) + 1, height - np.arange(height)) / 40
    return (smooth(x)[None, :] * smooth(y)[:, None]).astype(np.float32)


def accent_zoom(source, time, cues):
    for moment, x, y in cues:
        phase = (time - moment) / .95
        if abs(phase) >= 1:
            continue
        strength = (1 - phase * phase) ** 2
        width, height = source.size
        ratio = 1 / (1 + .105 * strength)
        crop_w, crop_h = width * ratio, height * ratio
        left, top = (width - crop_w) * x, (height - crop_h) * y
        return source.resize(source.size, Image.Resampling.LANCZOS,
                             box=(left, top, left + crop_w, top + crop_h))
    return source


def subject_mask(source, data, size):
    # Key on hue so highlights and shadows can share the same selection.
    swatch = Image.new('RGB', (1, 1), data['color_protagonista']).convert('HSV').getpixel((0, 0))
    width, height = size
    sample = source.resize((max(1, width // 3), max(1, height // 3)), Image.Resampling.BILINEAR)
    hsv = np.asarray(sample.convert('HSV'))
    hue_distance = np.abs(hsv[:, :, 0].astype(np.int16) - swatch[0])
    hue_distance = np.minimum(hue_distance, 256 - hue_distance)
    selected = (hue_distance <= data['tolerancia_color'] * 256 / 360) & (hsv[:, :, 1] >= 37)
    mask = Image.fromarray(selected.astype(np.uint8) * 255)
    mask = mask.filter(ImageFilter.MedianFilter(3))
    mask = mask.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(5))
    # Fill enclosed regions such as goggles and patches in the costume.
    padded = Image.new('L', (mask.width + 2, mask.height + 2))
    padded.paste(mask, (1, 1))
    ImageDraw.floodfill(padded, (0, 0), 128)
    mask = padded.crop((1, 1, mask.width + 1, mask.height + 1)).point([0 if i == 128 else 255 for i in range(256)])
    return mask.resize(size, Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(1.2))


def fit_cutout(source, size):
    alpha = source.getchannel('A')
    if alpha.getextrema()[0] >= 128:
        return None
    box = alpha.point(lambda value: 255 if value >= 128 else 0).getbbox()
    if box is None:
        return None
    width, height = size
    sprite = source.crop(box)
    ratio = min(width * .62 / sprite.width, height * .50 / sprite.height)
    fitted = (max(1, round(sprite.width * ratio)), max(1, round(sprite.height * ratio)))
    return sprite.resize(fitted, Image.Resampling.LANCZOS)


def load_cutout(data, size):
    if data['fuente'] != 'Imagen' or data['animacion_fuente'] != 'Ascenso' or not data['archivo']:
        return None
    try:
        with Image.open(data['archivo']) as source:
            if 'A' not in source.getbands() and 'transparency' not in source.info:
                return None
            return fit_cutout(ImageOps.exif_transpose(source).convert('RGBA'), size)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None  # The normal media reader reports unreadable files.


def prepare_exhaust(sprite, points):
    manual = exhaust_points(points)
    if manual:
        return manual, None
    rgba = np.asarray(sprite).astype(np.int16)
    red, green, blue, alpha = rgba.transpose(2, 0, 1)
    height, width = alpha.shape
    visible = alpha >= 128
    start = int(height * .72)
    warm = (red >= 176) & (green >= red * .72) & (red - blue >= 16) & (red >= green)
    cool = (blue >= 195) & (green >= 175) & (blue - red >= 20)
    glow = visible & (warm | cool)
    glow[:start] = False
    edge = glow[int(height * .94):]
    # A painted flame is luminous and continues to the lower edge of the cutout.
    established = (edge.mean(axis=0) >= .40) & (glow[start:].mean(axis=0) >= .18)
    if np.count_nonzero(established) >= max(3, width * .10):
        x = np.flatnonzero(established)
        mask = glow.copy()
        mask[:, :max(0, x[0] - 2)] = False
        mask[:, x[-1] + 3:] = False
        return (), mask
    tail = visible[int(height * .96):]
    supported = tail.mean(axis=0) > .55
    bounds = np.flatnonzero(np.diff(np.r_[False, supported, False]))
    exits = []
    for left, right in bounds.reshape(-1, 2):
        if right - left >= max(3, width * .07):
            center = (left + right - 1) / 2
            rows = np.nonzero(visible[:, left:right])[0]
            exits.append((center / width, (rows[-1] + 1) / height))
    if not exits:
        columns = np.nonzero(tail)[1]
        exits = [(float(np.median(columns)) / width, 1.0)] if columns.size else [(.5, 1.0)]
    return tuple(exits), None


def animate_painted_exhaust(sprite, mask, time):
    y, x = np.ogrid[:sprite.height, :sprite.width]
    pulse = .94 + .065 * np.sin(time * 30 - y * .14 + x * .064)
    pulse += .035 * np.sin(time * 48 + y * .08)
    pixels = np.array(sprite)
    pixels[mask, :3] = np.clip(pixels[mask, :3] * pulse[mask, None], 0, 255).astype(np.uint8)
    return Image.fromarray(pixels)


def animate_cutout(size, sprite, phase, strength, time, exhaust):
    width, height = size
    scene = Image.new('RGBA', size)
    advance = .35 * phase + .65 * float(smooth(phase))
    x = round((width - sprite.width) / 2 + width * .01 * strength * math.sin(time * 1.7))
    y = round(height * (.50 + (.17 - .37 * advance) * strength) - sprite.height / 2)
    exits, flame = exhaust if exhaust is not None else ((), None)
    if flame is not None:
        sprite = animate_painted_exhaust(sprite, flame, time)
    if exits:
        draw = ImageDraw.Draw(scene)
        count = max(16, 52 // len(exits))
        scale = 1 / math.sqrt(len(exits))
        for stream, (outlet_x, outlet_y) in enumerate(exits):
            foot_x, foot_y = x + sprite.width * outlet_x, y + sprite.height * outlet_y
            for index in range(count):
                age = (time * (.71 + (index % 6) * .09) + index / count + stream * .17) % 1
                spread = math.sin(index * 2.399 + age * 4.2 + stream)
                px = foot_x + spread * width * (.012 + .085 * age) * strength * scale
                py = foot_y + age * height * (.09 + .21 * strength)
                radius = max(2, round(width * (.011 - age * .007) * scale))
                color = (255, round(237 - age * 133), round(163 - age * 118), round(245 * (1 - age) ** .9))
                draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color)
            radius = width * .023 * strength * scale
            draw.ellipse((foot_x - radius, foot_y - radius, foot_x + radius, foot_y + radius * 2),
                         fill=(255, 234, 162, 235))
    scene.alpha_composite(sprite, (x, y))
    return scene


def animate_media(source, prepared, phase):
    data = prepared['data']
    motion = data['animacion_fuente']
    strength = data['intensidad_movimiento'] / 100
    if motion == MEDIA_ANIMATIONS[0] or strength == 0:
        return source
    sprite = prepared['cutout_sprite']
    if motion == 'Ascenso' and sprite is not None:
        return animate_cutout(source.size, sprite, phase, strength, phase * data['duracion'],
                              prepared['cutout_exhaust'])
    advance = .35 * phase + .65 * float(smooth(phase))
    width, height = source.size
    zoom = 1 + strength * (.08 + .35 * advance if motion == 'Acercamiento' else .39)
    crop_w, crop_h = width / zoom, height / zoom
    x = .08 + .84 * advance if motion == 'Recorrido lateral' else .5
    y = .08 + .84 * advance if motion == 'Ascenso' else .5
    left, top = (width - crop_w) * x, (height - crop_h) * y
    return source.resize(source.size, Image.Resampling.LANCZOS,
                         box=(left, top, left + crop_w, top + crop_h))


def draw_media(image, prepared, source, phase):
    # One luminance sample selects a glyph. Its original RGB can tint that glyph.
    if source is None:
        return 0
    data = prepared['data']
    left, top, width, height = media_area(data)
    tile_w, tile_h, columns, rows = prepared['grid']
    if data['animacion_fuente'] != MEDIA_ANIMATIONS[0]:
        source = animate_media(source, prepared, phase)
    elif data['fuente'] == 'Imagen' and data['movimiento_imagen'] == 'Balanceo':
        time = phase * data['duracion']
        beat = math.sin(math.tau * time / 2.4)
        sway = math.sin(math.tau * time / 4.8)
        source = source.rotate(3.8 * sway, resample=Image.Resampling.BICUBIC,
                               translate=(round(width * .022 * sway), round(height * .022 * beat)))
    elif data['fuente'] == 'Imagen' and data['movimiento_imagen'] == 'Dúo':
        beat = math.tau * phase * data['duracion'] / 1.6
        step = 32
        mesh = []

        def pose(x, y):
            # Give each dancer a separate sway. Keep their joined hands steady.
            left = math.exp(-((x / width - .34) / .22) ** 4)
            right = math.exp(-((x / width - .71) / .22) ** 4)
            torso = math.exp(-((y / height - .46) / .22) ** 4)
            hand = 1 - math.exp(-((x / width - .53) / .075) ** 2
                                - ((y / height - .61) / .085) ** 2)
            sway = left * math.sin(beat) + right * math.sin(beat + 1.8)
            bounce = left * math.cos(beat * 2) + right * math.cos(beat * 2 + .9)
            return x + width * .033 * torso * hand * sway, y + height * .019 * torso * hand * bounce

        for y in range(0, source.height, step):
            bottom = min(y + step, source.height)
            for x in range(0, source.width, step):
                edge = min(x + step, source.width)
                quad = (*pose(x, y), *pose(x, bottom), *pose(edge, bottom), *pose(edge, y))
                mesh.append(((x, y, edge, bottom), quad))
        source = source.transform(source.size, Image.Transform.MESH, mesh, Image.Resampling.BICUBIC)
    elif data['fuente'] == 'Imagen' and data['movimiento_imagen'] == 'Paralaje suave':
        source = move_photo(source, phase)
    if data['fuente'] == 'Video' and data['movimiento_orbital']:
        angle = phase * math.tau * 1.30
        source_w, source_h = source.size
        source = source.rotate(7 * math.sin(angle), resample=Image.Resampling.BICUBIC,
                               translate=(round(source_w * .044 * math.sin(angle)),
                                          round(source_h * .029 * math.sin(angle * .85))))
    if data['fuente'] == 'Video' and data['zoom_progresivo']:
        source_w, source_h = source.size
        scale = 1.04 + .38 * float(smooth(phase))
        crop_w, crop_h = source_w / scale, source_h / scale
        crop_x, crop_y = (source_w - crop_w) * .5, (source_h - crop_h) * .35
        source = source.resize(source.size, Image.Resampling.LANCZOS,
                               box=(crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
    if data['fuente'] == 'Video' and prepared['video_zooms']:
        source = accent_zoom(source, phase * data['duracion'], prepared['video_zooms'])
    if data['estilo_media'] == 'Pixel art':
        return draw_pixels(image, prepared, source, phase)
    hybrid = data['modo_hibrido'] != HYBRID_MODES[0] and data['fuente'] == 'Video'
    sampled = source.resize((columns, rows), Image.Resampling.LANCZOS)
    if data['realzar_bordes']:
        sampled = sampled.filter(ImageFilter.UnsharpMask(radius=1, percent=115, threshold=2))
    pixels = np.asarray(sampled, dtype=np.float32)
    rgb = pixels[:, :, :3]
    light = np.clip((rgb @ np.array([0.2126, 0.7152, 0.0722]) / 255 - 0.5) * data['contraste']
                    + 0.5 + data['brillo'], 0, 1)
    if data['invertir']:
        light = 1 - light
    if data['detalle_sombras']:
        light = light ** .73
    if data['cierre_invernal'] and phase > .79:
        y, x = np.ogrid[:rows, :columns]
        focus = np.exp(-((x / columns - .51) / .32) ** 4 - ((y / rows - .67) / .36) ** 4)
        strength = math.exp(-((phase - .895) / .048) ** 2)
        contour = np.abs(light - np.roll(light, 1, axis=1)) + np.abs(light - np.roll(light, 1, axis=0))
        light = np.clip(light + np.minimum(contour, .37) * focus * strength * .67, 0, 1)
    dance_light = None
    time = phase * data['duracion']
    for moment, x, y in prepared['dance_cues']:
        if abs(time - moment) > .63:
            continue
        yy, xx = np.ogrid[:rows, :columns]
        shape = np.exp(-((xx / columns - x) / .15) ** 2 - ((yy / rows - y) / .12) ** 2)
        pulse = math.exp(-((time - moment - .10) / .26) ** 2)
        accent = shape * pulse
        dance_light = accent if dance_light is None else np.maximum(dance_light, accent)
    if dance_light is not None:
        footlights = np.abs(light - np.roll(light, 1, axis=1)) + np.abs(light - np.roll(light, 1, axis=0))
        light = np.clip(light + dance_light * (.085 + np.minimum(footlights, .32) * .76), 0, 1)
    if data['movimiento_orbital'] and data['fuente'] == 'Video':
        pulse = .88 + .19 * (1 + math.sin(phase * math.tau * 4.5)) / 2
        light = np.clip(light * pulse, 0, 1)
    orbital_flow = None
    if data['flujo_orbital'] and data['fuente'] == 'Video':
        yy, xx = np.ogrid[:rows, :columns]
        x = (xx / columns - .5) / .164
        y = (yy / rows - .55) / .17
        radius = np.hypot(x, y)
        angle = np.arctan2(y, x)
        track = np.exp(-((radius - .92) / .44) ** 2)
        wave = (.5 + .5 * np.cos(angle * 3 - phase * math.tau * data['ritmo_flujo_orbital'])) ** 4
        luminous = np.clip((light - .16) * 3.3, 0, 1)
        orbital_flow = track * wave * luminous
        if data['flujo_exterior']:
            exterior = np.exp(-((radius - 1.33) / .52) ** 2)
            sweep = angle * 3 - phase * math.tau * data['ritmo_flujo_orbital'] * 2.05
            current = .12 + .88 * (.5 + .5 * np.cos(sweep)) ** 2
            orbital_flow = np.maximum(orbital_flow, exterior * current * luminous)
        light = np.clip(light + orbital_flow * .28, 0, 1)
    plume = None
    if data['realce_estela']:
        blue = rgb[:, :, 2]
        plume = np.clip((blue - rgb[:, :, 0] - 5) / 48, 0, 1) * np.clip((blue - 10) / 70, 0, 1)
        light = np.clip(light + plume * .30, 0, 1)
    ramp = data['rampa']
    index = np.rint(light * (len(ramp) - 1)).astype(np.intp)
    alpha = pixels[:, :, 3] / 255
    fade = float(smooth(phase / 0.035) * (1 - smooth((phase - 0.96) / 0.04)))
    shape = (rows * tile_h, columns * tile_w)
    mask = (prepared['atlas'][index] * alpha[:, :, None, None] * (1 if hybrid else fade)).astype(np.uint8)
    mask = mask.transpose(0, 2, 1, 3).reshape(shape)
    if data['modo_color'] == 'Original':
        color = rgb * 0.82 + 50
    else:
        ink = prepared['colors'][LEAF] if data['modo_color'] == 'Paleta' else np.array((235, 240, 245))
        color = ink * (0.64 + light[:, :, None] * 0.36)
    if data['fondo_estadio']:
        red = np.clip((rgb[:, :, 0] - np.maximum(rgb[:, :, 1], rgb[:, :, 2])) / 85, 0, 1)
        neutral = (light * .78 + .22)[:, :, None] * np.array((255, 237, 228))
        club_red = (light * .68 + .32)[:, :, None] * np.array((255, 65, 71))
        color = neutral * (1 - red[:, :, None]) + club_red * red[:, :, None]
    if dance_light is not None:
        warm = dance_light[:, :, None] * .72
        color = color * (1 - warm) + np.array((255, 215, 150)) * warm
    if plume is not None:
        strength = plume[:, :, None] * .76
        color = color * (1 - strength) + np.array((162, 218, 255)) * strength
    if orbital_flow is not None:
        warm = orbital_flow[:, :, None] * .62
        color = color * (1 - warm) + np.array((255, 198, 103)) * warm
    paint = color.clip(0, 255).astype(np.uint8).repeat(tile_h, 0).repeat(tile_w, 1)
    field = Image.fromarray(paint).resize((width, height), Image.Resampling.NEAREST)
    stencil = Image.fromarray(mask).resize((width, height), Image.Resampling.BILINEAR)
    if data['suavizar_bordes']:
        feather = edge_feather(width, height)
        mask = (np.asarray(stencil, dtype=np.float32) * feather).astype(np.uint8)
        stencil = Image.fromarray(mask)
    image.paste(field, (left, top), stencil)
    if hybrid:
        original = source.resize((width, height), Image.Resampling.LANCZOS).convert('RGB')
        selection = subject_mask(source, data, (width, height))
        if data['modo_hibrido'] == 'Protagonista en ASCII':
            selection = selection.point(lambda value: 255 - value)
        image.paste(original, (left, top), selection)
    return int(np.count_nonzero((np.asarray([char != ' ' for char in ramp])[index]) & (alpha > 0.15)))


def code_color(token, theme):
    if token.startswith('#'):
        return theme.muted
    if token.startswith(('"', "'")):
        return theme.literal
    if token[0].isdigit():
        return theme.literal
    if token in {'def', 'if', 'for', 'else', 'in', 'return', 'not', 'and', 'True', 'False'}:
        return theme.keyword
    return theme.text


def raster_code(font, theme):
    excerpts = {}
    advance = font.getlength('M')
    sections = dict(source_sections())
    media = sections['draw_media']
    conversion = next(i for i, (_, line) in enumerate(media) if 'sampled = source.resize' in line)
    sections['video_conversion'] = media[conversion:]
    for name, lines in sections.items():
        layer = Image.new('RGBA', (640, len(lines) * 27 + 18))
        draw = ImageDraw.Draw(layer)
        for i, (number, line) in enumerate(lines):
            y = 8 + i * 27
            draw.text((10, y), str(number), fill=theme.muted, font=font)
            x = 56
            for token in KEYWORD.findall(line[:65]):
                draw.text((x, y), token, font=font, fill=code_color(token, theme))
                x += advance * len(token)
        excerpts[name] = layer
    return excerpts


def code_panel(image, prepared, phase):
    draw = ImageDraw.Draw(image, 'RGBA')
    theme = prepared['theme']
    compact = prepared['data']['panel_compacto'] and prepared['data']['fuente'] != 'Figura 3D'
    safe = prepared['data']['margen_tiktok'] and prepared['data']['fuente'] != 'Figura 3D'
    full = full_media_canvas(prepared['data'])
    top = 1006 if full else (880 if safe else (934 if compact else 779))
    bottom = (1174 if safe else 1240) if full else (1105 if safe else (1190 if compact else 1188))
    right = 616 if safe else 691
    inset_width = right - 51
    viewport = bottom - top - 77
    opacity = round(prepared['data']['opacidad_panel'] * 255 / 100)
    fill = (*ImageColor.getrgb(theme.panel), opacity)
    draw.rounded_rectangle((29, top, right, bottom), 14, fill=fill, outline=theme.border, width=2)
    draw.line((29, top + 53, right, top + 53), fill=theme.border)
    draw.ellipse((49, top + 24, 58, top + 33), fill=theme.keyword)
    draw.text((72, top + 29), prepared['data']['archivo_panel'], font=prepared['mono'], fill=theme.text, anchor='lm')
    draw.text((right - 20, top + 29), 'PYTHON', font=prepared['label'], fill=theme.keyword, anchor='rm')
    figure = prepared['data']['figura']
    shape = 'build_tree' if figure == 'Árbol' else ('build_emblem' if figure in ('Estrella', 'Corazón') else 'build_symbol')
    names = ('draw_particles', shape, 'project', 'draw_glyphs', 'scene_frame')
    if prepared['data']['fuente'] != 'Figura 3D':
        conversion = 'video_conversion' if prepared['data']['fuente'] == 'Video' else 'draw_media'
        if prepared['data']['estilo_media'] == 'Pixel art':
            conversion = 'draw_pixels'
        names = (conversion,) * 5
        if prepared['data']['animacion_fuente'] != MEDIA_ANIMATIONS[0]:
            motion = 'animate_cutout' if prepared['cutout_sprite'] is not None else 'animate_media'
            names = (motion, motion, conversion, conversion, conversion)
    if not prepared['data']['particulas'] and names[0] == 'draw_particles':
        names = (shape, *names[1:])
    selection = min(4, int(phase * 5))
    excerpt = prepared['source'][names[selection]]
    inset_y = top + 65
    inset = image.crop((39, inset_y, 39 + inset_width, inset_y + viewport))
    inner = ImageDraw.Draw(inset, 'RGBA')
    position = phase if names[0] in ('draw_media', 'video_conversion', 'draw_pixels') else phase * 5 - selection
    drift = int(position * max(0, excerpt.height - viewport))
    active = math.floor(drift / 27) + 2
    y = 8 + active * 27 - drift
    inner.rectangle((0, y - 3, inset_width, y + 23), fill=(*ImageColor.getrgb(theme.active), opacity))
    inner.rectangle((1, y - 3, 3, y + 23), fill=theme.keyword)
    strip = excerpt.crop((0, drift, inset_width, drift + viewport))
    inset.paste(strip, (0, 0), strip)
    image.paste(inset, (39, inset_y))


def golden_dust(image, time, bottom):
    draw = ImageDraw.Draw(image, 'RGBA')
    for i in range(23):
        right_side = i % 2
        base = (615 if right_side else 38) + (i * 37 % 65)
        x = base + 16 * math.sin(time * .62 + i)
        y = 127 + (i * 193 - time * (12 + i % 9)) % max(1, bottom - 139)
        pulse = (.5 + .5 * math.sin(time * 1.5 + i * 1.4)) ** 2
        opacity = round(25 + 115 * pulse)
        draw.rectangle((x, y, x + 1 + i % 3, y + 1 + i % 3), fill=(255, 198, 121, opacity))
        if pulse > .92 and i % 5 == 0:
            draw.line((x - 2, y + 1, x + 5, y + 1), fill=(255, 220, 164, opacity // 2))


def falling_snow(image, prepared, time, phase):
    draw = ImageDraw.Draw(image, 'RGBA')
    x0, top, width, height = media_area(prepared['data'])
    extra = float(smooth((phase - .74) / .20))
    for index, (u, v, depth, sway, brightness) in enumerate(prepared['particles'][:74]):
        if index >= 46 and (index - 45) / 28 > extra:
            continue
        near = index % 7 == 0
        if near:
            x = x0 + (13 + u * 78 if index % 2 else width - 13 - u * 78)
        else:
            x = x0 + u * width
        x += math.sin(time * (.45 + sway) + index) * (10 + 13 * depth)
        y = top + (v * height + time * (19 + depth * (39 if near else 26))) % height
        opacity = round((75 + 80 * brightness if near else 26 + 55 * brightness) *
                        min(1, (y - top) / 18, (top + height - y) / 27))
        if opacity <= 0:
            continue
        draw.text((x, y), '*' if near else ('.' if index % 3 else '+'),
                  font=prepared['label'] if near else prepared['snow_font'],
                  fill=(244, 238, 228, opacity), anchor='mm')


def winter_close(image, prepared, phase):
    if phase < .88:
        return image
    _, top, _, height = media_area(prepared['data'])
    progress = (phase - .88) / .12
    draw = ImageDraw.Draw(image, 'RGBA')
    x = 639 + 18 * math.sin(progress * math.pi * 1.6)
    y = top + height * (.19 + .85 * progress)
    opacity = round(198 * min(1, progress * 10, (1 - progress) * 3))
    draw.text((x, y), '*', font=prepared['snow_final_font'], fill=(255, 241, 217, opacity), anchor='mm')
    darkness = float(smooth((phase - .96) / .04))
    return Image.blend(image, Image.new('RGB', image.size, '#100e20'), darkness)


def scene_frame(time, prepared, media_frame=None):
    data = prepared['data']
    if 'ascii_world' in prepared:
        return prepared['ascii_world'].frame(time, data)
    if 'procedural' in prepared:
        return arte_procedural.frame(prepared['procedural'], data['figura'], time,
                                     data['duracion'], data['particulas'])
    phase = min(1, max(0, time / data['duracion']))
    snow_height = HEIGHT if prepared['holiday'] else STAGE_HEIGHT
    tree_offset = prepared['tree_offset']
    star_time = time if data['estrella_destellos'] else None
    star_period = 1.25 if prepared['holiday'] else 1.85
    if data['solo_video']:
        if data['fuente'] != 'Figura 3D':
            image = Image.new('RGB', (WIDTH, HEIGHT))
            draw_media(image, prepared, media_frame, phase)
            return image
        image = prepared['stage'].copy()
        draw = ImageDraw.Draw(image)
        if data['particulas']:
            draw_particles(draw, prepared['particles'], phase, foreground=False, height=snow_height)
        draw_floor(draw, float(smooth(phase / .10) * (1 - smooth((phase - .96) / .04))), tree_offset)
        draw_glyphs(image, prepared, phase)
        if data['figura'] == 'Árbol' and data['detalles']:
            topper_glow(image, phase, prepared['gold'], star_time, prepared['tree_scale'], tree_offset, star_period)
        if data['particulas']:
            draw_particles(ImageDraw.Draw(image), prepared['particles'], phase, foreground=True, height=snow_height)
        if prepared['holiday']:
            return image
        composition = prepared['stage'].copy()
        composition.paste(image.crop((0, 25, WIDTH, 770)), (0, 227))
        return composition
    image = prepared['stage'].copy()
    draw = ImageDraw.Draw(image)
    is_3d = data['fuente'] == 'Figura 3D'
    if data['particulas']:
        draw_particles(draw, prepared['particles'], phase, foreground=False, height=snow_height)
    if is_3d:
        draw_floor(draw, float(smooth(phase / 0.10) * (1 - smooth((phase - 0.96) / 0.04))))
        glyphs, lamps = draw_glyphs(image, prepared, phase)
        if data['figura'] == 'Árbol' and data['detalles']:
            topper_glow(image, phase, prepared['gold'], star_time, prepared['tree_scale'], period=star_period)
    else:
        glyphs, lamps = draw_media(image, prepared, media_frame, phase), 0
    draw = ImageDraw.Draw(image)
    if data['particulas']:
        draw_particles(draw, prepared['particles'], phase, foreground=True, height=snow_height)
    identity = data['figura'] if is_3d else data['fuente']
    compact = data['panel_compacto'] and data['codigo'] and not is_3d
    if data['polvo_dorado'] and not is_3d:
        _, top, _, height = media_area(data)
        golden_dust(image, time, top + height)
    if data['nieve_ascii'] and not is_3d:
        falling_snow(image, prepared, time, phase)
    treatment = 'ASCII 3D' if is_3d else data['estilo_media'].upper()
    caption = f'{identity.upper()} / {treatment}'
    safe = data['margen_tiktok'] and not is_3d
    header_y = 170 if safe else 51
    if data['firma_ascii']:
        draw.text((42, header_y), data['firma_ascii'], font=prepared['signature'], fill=prepared['gold'], anchor='lm')
    else:
        draw.text((42, header_y), caption, font=prepared['label'], fill=prepared['blue'])
    draw.text((596 if safe else 680, header_y - 3), f'{time:05.2f} s', font=prepared['mono'], fill=prepared['gold'], anchor='ra')
    if not safe:
        draw.line((42, 80, 678, 80), fill='#3c5670')
    start = data['mensaje_desde'] / 100
    complete = data['mensaje_completo'] / 100
    progress = min(1, max(0, (phase - start) / (complete - start)))
    end = data['mensaje_hasta'] / 100
    fade_message = data['mensaje_fundido']
    typed = len(data['mensaje']) if fade_message and start < phase < end else int(progress * len(data['mensaje']))
    if typed and phase < end:
        for i, line in enumerate(textwrap.wrap(data['mensaje'][:typed], 34, break_long_words=True)[:3]):
            baseline = (852 if safe else (882 if compact else 716)) if data['codigo'] else (852 if is_3d else 1080)
            y = baseline + i * (22 if data['codigo'] else 36)
            face = prepared['message_font'] or (prepared['mono'] if data['codigo'] else prepared['caption'])
            if fade_message:
                fade = min(float(smooth(progress)), float(smooth((end - phase) * data['duracion'] / .58)))
                ink = (236, 236, 236, round(255 * fade)) if data['paleta'] == 'Carbón' else (255, 235, 208, round(255 * fade))
                ImageDraw.Draw(image, 'RGBA').text((360, y), line, font=face, fill=ink, anchor='mm')
            else:
                draw.text((360, y), line, font=face, fill=prepared['gold'], anchor='mm')
    if glyphs and not typed and not fade_message:
        y = 881 if compact else (726 if is_3d or data['codigo'] else 1080)
        draw.text((43, y), f'{glyphs:04} ' + ('píxeles' if not is_3d and data['estilo_media'] == 'Pixel art' else 'caracteres'), font=prepared['label'], fill=prepared['blue'])
        if is_3d and data['detalles']:
            draw.text((677, 726), f'{lamps:03} luces', font=prepared['label'], fill=prepared['gold'], anchor='ra')
    if data['codigo']:
        code_panel(image, prepared, phase)
    elif is_3d:
        stage = image.crop((0, 0, WIDTH, 1000))
        gradient = np.minimum(np.arange(1000) / 44, (999 - np.arange(1000)) / 60).clip(0, 1)
        mask = Image.fromarray((gradient[:, None].repeat(WIDTH, axis=1) * 255).astype(np.uint8))
        image = prepared['stage'].copy()
        image.paste(stage, (0, 125), mask)
    if data['cierre_invernal'] and not is_3d:
        image = winter_close(image, prepared, phase)
    return image


def ambient(time, duration):
    envelope = np.minimum(1, time / 1.5) * np.clip((duration - time) / 1.6, 0, 1)
    signal = sum(np.sin(math.tau * note * time) for note in (110.0, 164.81, 220.0)) * 0.017
    for mark, frequency in ((0.38, 659.25), (0.59, 880), (0.73, 783.99)):
        age = time - mark * duration
        ringing = np.maximum(0, age)
        signal += np.sin(math.tau * frequency * age) * np.clip(ringing * 90, 0, 1) * np.exp(-ringing * 4.5) * 0.065
    return envelope * signal
