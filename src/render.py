import argparse
import json
import math
import os
import random
import re
import subprocess
import tempfile
import wave
from bisect import bisect_right
from contextlib import ExitStack
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter, ImageFont

import ascii_art
import audio_mix
import video_reveal
from designs import CODE_THEMES, DESIGNS, CodeTheme, silhouette
from media import BackgroundFrames, PROCESS_OPTIONS, ascii_preview_still, find_ffmpeg, media_settings, move_frame
from reel_clock import ReelClock, visibility, visible_at


ROOT = Path(__file__).resolve().parent
FONT_DIR = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
PROJECT_VERSION = 12
WIDTH, HEIGHT, FPS = 720, 1280, 30
INTRO, HOLD = 1.40, 1.7
FINAL_SIZE, PREVIEW_SIZE = (1080, 1920), (540, 960)
TOKEN = re.compile(r'//.*|"[^"\n]*"|\x27[^\x27\n]*\x27|\d+(?:\.\d+)?|[^\W\d]\w*|\s+|.', re.UNICODE)
THEMES = [
    ((201, 73, 52), '#f3a18a', 430, 123),
    ((218, 63, 78), '#ff9ca9', 486, 98),
    ((108, 138, 227), '#b8c7ff', 556, 78),
]
SHAPES = ('Órbita', *DESIGNS, 'Rombo', 'Sin figura')


@dataclass
class Motif:
    rgb: tuple
    accent: str
    shape: str
    center: tuple
    radius: int
    ink: tuple
    path: tuple = ()


@dataclass
class Artwork:
    combined: Image.Image
    background: Image.Image
    overlay: Image.Image
    motif: Motif
    code: CodeTheme


LINUX_FONTS = {
    'georgia.ttf': ('DejaVuSerif.ttf', 'LiberationSerif-Regular.ttf', 'NotoSerif-Regular.ttf'),
    'georgiai.ttf': ('DejaVuSerif-Italic.ttf', 'LiberationSerif-Italic.ttf', 'NotoSerif-Italic.ttf'),
    'consola.ttf': ('DejaVuSansMono.ttf', 'LiberationMono-Regular.ttf', 'NotoSansMono-Regular.ttf'),
    'seguisb.ttf': ('DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf', 'NotoSans-Bold.ttf'),
}


def animated_title(style):
    enabled = style.get('titulo_animado')
    return style.get('atardecer_animado', False) if enabled is None else enabled


def default_style(index):
    return {'acento': THEMES[min(index, len(THEMES) - 1)][1], 'fondo': '#0a0a11', 'forma': SHAPES[0],
            'tema_codigo': 'Terminal', 'tormenta': False, 'composicion_alta': False, 'gerberas': False, 'cierre_gerbera': False, 'atardecer_animado': False, 'hojas_primer_plano': False, 'marca_agua': '', 'mostrar_marca': True, 'posicion_marca': 'Inferior derecha', 'tamano_marca': 26, 'intensidad_efectos': 100, 'luces_atardecer': True, 'titulo_animado': None, 'hojas_delante': True, 'frecuencia_hojas': 'Normal', 'luz_al_audio': False, 'sensibilidad_graves': 'Media'}


def scene_style(index, custom=None):
    if custom is not None and not isinstance(custom, dict):
        raise ValueError('El estilo de una escena debe ser un objeto.')
    style = default_style(index) | (custom or {})
    for key in ('acento', 'fondo'):
        value = style[key]
        if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError('Usa un color hexadecimal de seis dígitos, por ejemplo #e9a0ff.')
        style[key] = value.lower()
    if style['forma'] not in SHAPES:
        raise ValueError('La figura de la escena no está disponible.')
    if style['tema_codigo'] not in CODE_THEMES:
        raise ValueError('El tema de código no está disponible.')
    if style['sensibilidad_graves'] not in ('Baja', 'Media', 'Alta'):
        raise ValueError('Selecciona una sensibilidad de graves válida.')
    for key, lower, upper in (('intensidad_efectos', 0, 100), ('tamano_marca', 12, 60)):
        if type(style[key]) is not int or not lower <= style[key] <= upper:
            raise ValueError(f'«{key}» debe estar entre {lower} y {upper}.')
    if not isinstance(style['marca_agua'], str) or len(style['marca_agua']) > 32:
        raise ValueError('La firma admite hasta 32 caracteres.')
    return {key: style[key] for key in ('acento', 'fondo', 'forma', 'tema_codigo', 'tormenta', 'composicion_alta', 'gerberas', 'cierre_gerbera', 'atardecer_animado', 'hojas_primer_plano', 'marca_agua', 'mostrar_marca', 'posicion_marca', 'tamano_marca', 'intensidad_efectos', 'luces_atardecer', 'titulo_animado', 'hojas_delante', 'frecuencia_hojas', 'luz_al_audio', 'sensibilidad_graves', 'marcas_palabras') if key in style}


def luminance(color):
    linear = [tone / 3294.6 if tone <= 10 else ((tone / 255 + 0.055) / 1.055) ** 2.4
              for tone in color]
    return sum(part * weight for part, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast_text(color):
    return (23, 16, 24) if luminance(color) > 0.32 else (250, 237, 232)


def audio_timing(project):
    intro = float(project.get('introduccion', INTRO))
    audio_start = float(project.get('inicio_audio', 0))
    raw_end = project.get('fin_audio')
    audio_end = float(raw_end) if raw_end is not None else None
    if not all(math.isfinite(value) and value >= 0 for value in (intro, audio_start)):
        raise ValueError('El inicio de audio y la apertura deben ser números mayores o iguales a cero.')
    if audio_end is not None and (not math.isfinite(audio_end) or audio_end <= audio_start):
        raise ValueError('El final del audio debe ser posterior al inicio.')
    return intro, audio_start, audio_end


def verse_seconds(value):
    try:
        duration = float(str(value).replace(',', '.'))
    except (ValueError, TypeError):
        duration = 0
    if not math.isfinite(duration) or duration < 0.7:
        raise ValueError('Cada verso debe durar al menos 0,7 segundos.')
    return duration


@lru_cache(maxsize=None)
def font_path(name):
    if os.name == 'nt':
        return FONT_DIR / name
    for candidate in LINUX_FONTS[name]:
        for directory in (Path('/usr/share/fonts'), Path('/usr/local/share/fonts'), Path.home() / '.local/share/fonts'):
            match = next(directory.rglob(candidate), None)
            if match is not None:
                return match
    raise ValueError('Faltan las fuentes de Linux. Instala DejaVu completa o Liberation.')


def font(name, size):
    return ImageFont.truetype(str(font_path(name)), size)


def fitted_font(name, size, text, width):
    face = font(name, size)
    while face.getlength(text) > width:
        size -= 1
        if size < 12:
            raise ValueError('Un título, nombre de archivo o línea de código es demasiado largo.')
        face = font(name, size)
    return face


def read_project(path):
    project = json.loads(path.read_text(encoding='utf-8-sig'))
    if project.get('version_proyecto', 1) > PROJECT_VERSION:
        raise ValueError('Este proyecto requiere una versión más reciente del editor.')
    title = project['titulo']
    if not isinstance(title, list) or len(title) != 2 or not all(isinstance(s, str) for s in title):
        raise ValueError('El título necesita dos líneas de texto.')
    mode, settings = ascii_art.project_mode(project, path.parent)
    animation = settings if mode == 'ascii' else None
    scenes = []
    timings = []
    for index, scene in enumerate(project['escenas'] if animation is None else []):
        verses = scene['versos']
        if not 1 <= len(verses) <= 4:
            raise ValueError('Cada escena admite de uno a cuatro versos.')
        cues = []
        for line in verses:
            span = verse_seconds(line[2] if len(line) >= 3 else project['segundos_por_verso'])
            timings.append(span)
            cues.append((line[0], line[1], visibility(line[3] if len(line) >= 4 else None, span)))
        scenes.append((scene['archivo'], cues,
                       scene_style(index, scene.get('estilo')), media_settings(scene.get('fondo_media'), path.parent)))
    if not scenes and animation is None:
        raise ValueError('Agrega al menos una escena.')
    if animation:
        recording = ascii_art.audio_path(animation)
        if animation['fuente'] != 'Figura 3D' and (not animation['archivo'] or not Path(animation['archivo']).is_file()):
            raise ValueError('Selecciona una imagen o video local para convertirlo a ASCII.')
        audio = recording.resolve(strict=True) if recording else None
        return title, scenes, timings, audio, 0, animation['inicio'], animation['fin'], animation, animation['mezcla']
    recording = project.get('audio_local')
    audio = (path.parent / recording).resolve(strict=True) if recording else None
    return title, scenes, timings, audio, *audio_timing(project), None, audio_mix.normalize(project.get('mezcla_audio'), path.parent)


def shape_path(shape, center_x, center_y, radius):
    if shape == 'Corazón':
        angles = np.linspace(0, 2 * np.pi, 145)
        x = np.sin(angles) ** 3
        y = -(13 * np.cos(angles) - 5 * np.cos(2 * angles) - 2 * np.cos(3 * angles)
              - np.cos(4 * angles)) / 16 - 0.15
    elif shape == 'Estrella':
        angles = np.linspace(-np.pi / 2, 3 * np.pi / 2, 11)
        scale = np.where(np.arange(11) % 2 == 0, 1.0, 0.46)
        x, y = np.cos(angles) * scale, np.sin(angles) * scale
    else:
        x, y = [0, 0.84, 0, -0.84, 0], [-1, 0, 1, 0, -1]
    return tuple(zip(center_x + radius * np.asarray(x), center_y + radius * np.asarray(y)))


def trace_shape(image, points, rgb):
    mask = Image.new('L', image.size)
    ImageDraw.Draw(mask).line(points, fill=132, width=4, joint='curve')
    glow = mask.filter(ImageFilter.GaussianBlur(11)).point(lambda intensity: min(215, intensity * 6))
    image.paste(rgb, (0, 0, *image.size), glow)
    image.paste(tuple((tone + 255) // 2 for tone in rgb), (0, 0, *image.size), mask)


def trace_symbol(image, shape, center_x, center_y, radius, rgb):
    tile = silhouette(shape, radius * 2)
    edge = ImageChops.difference(tile.filter(ImageFilter.MaxFilter(5)), tile.filter(ImageFilter.MinFilter(3)))
    mask = Image.new('L', image.size)
    mask.paste(edge.point(lambda n: round(n * .65)), (center_x - radius, center_y - radius))
    glow = mask.filter(ImageFilter.GaussianBlur(10)).point(lambda n: min(255, n * 5))
    image.paste(rgb, (0, 0, *image.size), glow)
    image.paste(tuple((tone + 255) // 2 for tone in rgb), (0, 0, *image.size), mask)


def make_background(index, style):
    default_rgb, default_accent, center_x, radius = THEMES[min(index, len(THEMES) - 1)]
    accent, shape = style['acento'], style['forma']
    rgb = default_rgb if accent == default_accent else ImageColor.getrgb(accent)
    background = ImageColor.getrgb(style['fondo'])
    center_y = 330 - index % 3 * 16
    if shape not in ('Órbita', 'Sin figura'):
        center_x, radius = max(center_x, 524), max(radius, 98)
    y, x = np.ogrid[:HEIGHT, :WIDTH]
    distance = np.hypot((x - center_x) * 0.94, y - center_y)
    bloom = np.exp(-(distance / (radius * 1.48)) ** 2)
    rim = np.exp(-((distance - radius) / 4.7) ** 2)
    angle = np.arctan2(y - center_y, x - center_x)
    lit = np.maximum(0.03, np.cos(angle + 0.78)) ** 2
    edge = np.maximum(0, 1 - (((x - 360) / 610) ** 2 + ((y - 570) / 785) ** 2))
    grain = np.random.default_rng(714 + index).normal(0, 0.95, size=(HEIGHT, WIDTH))
    light = 0.24 * bloom + 0.21 * rim * lit if shape == 'Órbita' else 0.18 * bloom
    if shape == 'Sin figura':
        light = 0
    base = np.stack([channel + light * tint + edge * 5 + grain
                     for channel, tint in zip(background, rgb)], axis=-1)
    image = Image.fromarray(base.clip(0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(image)
    rng = random.Random(117)
    for _ in range(195):
        sx, sy = rng.randrange(18, 702), rng.randrange(87, 1190)
        if shape == 'Órbita' and math.hypot((sx - center_x) * 0.94, sy - center_y) < radius * 0.94:
            continue
        intensity = rng.randrange(13, 72)
        draw.point((sx, sy), tuple(min(255, tone + intensity) for tone in background))
    path = ()
    if shape == 'Órbita':
        for offset in (15, 29):
            orbit = (center_x - radius - offset, center_y - radius - offset,
                     center_x + radius + offset, center_y + radius + offset)
            draw.arc(orbit, 264, 385, fill=tuple(19 + int(tone * 0.22) for tone in rgb))
    elif shape != 'Sin figura':
        if shape in ('Corazón', 'Estrella', 'Rombo'):
            path = shape_path(shape, center_x, center_y, radius)
            trace_shape(image, path, rgb)
        else:
            trace_symbol(image, shape, center_x, center_y, radius, rgb)
    return image, Motif(rgb, accent, shape, (center_x, center_y), radius, contrast_text(background), path)


@lru_cache(maxsize=1)
def media_overlay():
    y, x = np.ogrid[:HEIGHT, :WIDTH]
    title = 0.74 * np.exp(-((y - 345) / 174) ** 4) * np.exp(-((x - 150) / 550) ** 4)
    text = 0.8 * np.exp(-((y - 934) / 119) ** 4)
    alpha = (np.maximum(title, text) * 255).astype(np.uint8)
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), '#090813')
    overlay.putalpha(Image.fromarray(alpha))
    return overlay


def make_base(index, title, name, style, media):
    background, motif = make_background(index, style)
    has_media = media and media['velo'] < 100
    if has_media:
        motif.ink = (250, 237, 232)
    image = media_overlay().copy() if has_media else Image.new('RGBA', background.size)
    accent = motif.accent
    code = CODE_THEMES[style['tema_codigo']]
    draw = ImageDraw.Draw(image)
    main = fitted_font('georgia.ttf', 83, title[0], 540)
    second = fitted_font('georgiai.ttf', 92, title[1], 540)
    if not animated_title(style):
        draw.text((56, 322), title[0], font=main, fill=motif.ink, anchor='ls')
    background_color = '#090813' if has_media else style['fondo']
    shades = sorted((luminance(ImageColor.getrgb(accent)), luminance(ImageColor.getrgb(background_color))))
    outline = 2 if (shades[1] + 0.05) / (shades[0] + 0.05) < 2.5 else 0
    if not animated_title(style):
        draw.text((55, 420), title[1], font=second, fill=accent, anchor='ls',
                  stroke_width=outline, stroke_fill=motif.ink)
    if not animated_title(style):
        draw.line((59, 466, 106, 466), fill=accent, width=2)
    panel_offset = -167 if style.get('composicion_alta') else 0
    draw.rounded_rectangle((51, 548 + panel_offset, 616, 793 + panel_offset), radius=18,
                           fill=code.panel, outline=code.border, width=2)
    draw.line((52, 595 + panel_offset, 615, 595 + panel_offset), fill=code.border)
    draw.ellipse((76, 568 + panel_offset, 83, 575 + panel_offset), fill=code.keyword)
    label = fitted_font('consola.ttf', 19, name, 506)
    draw.text((98, 572 + panel_offset), name, font=label, fill=code.text, anchor='lm')
    combined = background.copy()
    combined.paste(image, (0, 0), image)
    return Artwork(combined, background, image, motif, code)


def moving_light(motif, phase):
    if motif.path:
        position = (phase * 0.84 + 0.07) * (len(motif.path) - 1)
        point = int(position)
        amount = position - point
        return tuple(a + (b - a) * amount for a, b in zip(motif.path[point], motif.path[point + 1]))
    theta = math.radians(245 + 102 * phase)
    cx, cy = motif.center
    return (cx + (motif.radius + 15) * math.cos(theta),
            cy + (motif.radius + 15) * math.sin(theta))


def make_star(rgb, final_scene):
    size = 88
    y, x = np.ogrid[-size:size + 1, -size:size + 1]
    color = np.zeros((size * 2 + 1, size * 2 + 1, 4), dtype=np.uint8)
    color[:, :, :3] = tuple(min(255, tone + 70) for tone in rgb)
    halo = 65 * np.exp(-(x * x + y * y) / (27 ** 2))
    core = 250 * np.exp(-(x * x + y * y) / 9)
    beam = 180 * (np.exp(-abs(x) / 18 - abs(y) / 1.2) + np.exp(-abs(x) / 1.2 - abs(y) / 19))
    color[:, :, 3] = (halo + core + beam * (1 if final_scene else 0.45)).clip(0, 255)
    return Image.fromarray(color)


def wrapped_caption(text):
    size = 46
    available = 555
    words = text.split()
    pairs = [(' '.join(words[:i]), ' '.join(words[i:])) for i in range(1, len(words))]
    while size >= 15:
        face = font('seguisb.ttf', size)
        if face.getlength(text) <= available:
            return [text], face
        if pairs:
            pair = min(pairs, key=lambda parts: max(map(face.getlength, parts)))
            if all(face.getlength(part) <= available for part in pair):
                return pair, face
        size -= 1
    raise ValueError('Una línea de letra es demasiado larga para el video.')


def syntax_color(token, code):
    if token.startswith('//'):
        return code.muted
    if token in {'if', 'new', 'false', 'true', 'null', 'Infinity', 'const', 'let', 'return', 'while', 'await', 'function'}:
        return code.keyword
    if token.startswith(('"', "'")) or token[0].isdigit() or token in {'laVeo', 'porEstarConElla', 'porElla', 'Estrella'}:
        return code.literal
    if token in '().;=':
        return code.muted
    return code.text


def audio_flashes(recording, start, end, total, sensitivities):
    if recording is None:
        return {}
    limit = min(total, end - start) if end is not None else total
    command = [find_ffmpeg(), '-nostdin', '-v', 'error', '-ss', str(start), '-i', str(recording),
               '-t', str(limit), '-map', '0:a:0', '-ac', '1', '-ar', '4000', '-f', 'f32le', 'pipe:1']
    result = subprocess.run(command, capture_output=True, check=True, timeout=max(30, limit), **PROCESS_OPTIONS)
    samples = np.frombuffer(result.stdout, dtype='<f4')
    if len(samples) < 400:
        return {}
    windows = np.lib.stride_tricks.sliding_window_view(samples, 200)[::80]
    power = np.abs(np.fft.rfft(windows * np.hanning(200), axis=1)) ** 2
    bass = np.sqrt(power[:, 2:9].sum(axis=1))
    loud = np.sqrt(power[:, 1:].sum(axis=1))
    attacks = np.maximum(0, np.diff(np.log1p(bass), prepend=np.log1p(bass[0])))
    hits = np.maximum(0, np.diff(np.log1p(loud), prepend=np.log1p(loud[0])))
    activity = np.maximum(attacks, hits * .60)
    presets = {'Baja': (98, 2.8), 'Media': (94, 1.65), 'Alta': (87, .95)}
    result = {}
    for name in sensitivities:
        percentile, gap = presets[name]
        threshold = max(.11, np.percentile(activity, percentile))
        candidates = np.flatnonzero(activity >= threshold)
        chosen = []
        for i in sorted(candidates, key=lambda index: activity[index], reverse=True):
            time = .02 * i + .025
            if all(abs(time - other) >= gap for other, _ in chosen):
                chosen.append((time, min(.18, .065 + .14 * activity[i])))
        result[name] = sorted(chosen)
    return result


def storm_frame(image, time, drops, peaks, sunset=False, intensity=1, fireflies=True):
    flash = max((strength * math.exp(-((time - moment) / .16) ** 2)
                 for moment, strength in peaks if abs(time - moment) < .55), default=0)
    flash *= intensity
    if flash > .002:
        image = Image.blend(image, Image.new('RGB', image.size, '#ffd09a' if sunset else '#879fce'), flash)
    draw = ImageDraw.Draw(image, 'RGBA')
    for x, y, speed, length in drops[:round(len(drops) * intensity)]:
        position = (y + time * speed) % (HEIGHT + 70) - 50
        column = (x - time * 65) % WIDTH
        draw.line((column, position, column - length * .14, position + length),
                  fill=(154, 207, 244, int(30 + length)), width=1 if length < 31 else 2)
    if sunset:
        for i in range(19):
            x = (i * 97 + time * (7 + i % 6)) % WIDTH
            y = 760 + i * 21
            length = 5 + i % 5 * 8
            opacity = int(58 * (0.5 + 0.5 * math.sin(time * 2.2 + i)))
            draw.rectangle((x, y, x + length, y + 2), fill=(255, 185, 99, opacity))
    if sunset and fireflies and intensity:
        positions = ((49, 1005), (92, 1095), (141, 1055), (182, 1165),
                     (340, 1120), (456, 1023), (506, 1190), (608, 1034), (652, 1164))
        for i, (base_x, base_y) in enumerate(positions):
            x = round((base_x + 23 * math.sin(time * .64 + i * 1.7)) / 3) * 3
            y = round((base_y + 19 * math.sin(time * .81 + i * 2.3)) / 3) * 3
            glow = .22 + .44 * (.5 + .5 * math.sin(time * 1.45 + i)) ** 2
            if i in (2, 5):
                glow += flash * 1.5
            draw.rectangle((x - 3, y - 3, x + 5, y + 5), fill=(244, 142, 55, round(40 * glow * intensity)))
            draw.rectangle((x, y, x + 2, y + 2), fill=(255, 208, 112, round(230 * glow * intensity)))
    for i in range(22 if len(drops) else 0):
        x = (i * 137 + time * (9 + i % 6)) % WIDTH
        y = (i * 89 - time * (13 + i % 8)) % HEIGHT
        opacity = int(36 + 52 * (0.5 + 0.5 * math.sin(time * 2.1 + i)))
        radius = 1 + i % 3
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=(255, 172, 122, opacity))
    return image


def sunset_title(image, time, title, face, credit, credit_font, accent):
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((43, 200, 608, 371 if credit else 355), 14, fill=(38, 21, 33))
    x = 59
    sweep = (time % 5.5) / 5.5 * (len(title) + 4) - 2
    for index, letter in enumerate(title):
        age = time - index * .085
        if age >= 0:
            settle = max(0, 1 - age / .24)
            warmth = math.exp(-((sweep - index) / .85) ** 2) * .73
            color = tuple(round(a + (b - a) * warmth)
                          for a, b in zip((255, 239, 218), accent))
            draw.text((x, 316 + round(settle * 18)), letter, font=face, fill=color, anchor='ls')
            if settle:
                draw.rectangle((x + 3, 319, x + 12, 323), fill=accent)
        x += face.getlength(letter)
    if time >= .68 and credit:
        draw.text((62, 337), credit, font=credit_font, fill=(245, 191, 147), anchor='lm')
    for index in range(27):
        x = 59 + index * 18
        if time > .45 + index * .025:
            running = int(time * 10) % 27
            ink = accent if abs(running - index) <= 1 else (115, 65, 72)
            line_y = 358 if credit else 341
            draw.rectangle((x, line_y, x + 10, line_y + 3), fill=ink)


def foreground_leaves(image, time, style):
    draw = ImageDraw.Draw(image, 'RGBA')
    events = ((2.8, 575, 52, 2.9), (11.2, 36, -22, 3.5),
              (19.5, 650, -32, 3.0), (25.6, 118, -91, 3.2))
    freq = style.get('frecuencia_hojas', 'Normal')
    if freq == 'Ocasional':
        events = events[::2]
    elif freq == 'Frecuente':
        events += ((7.1, 610, 61, 3.2), (15.8, 96, -55, 3.1), (23, 669, -41, 2.6))
    outline = ((-8, 0), (-4, -5), (2, -6), (9, -2), (12, 2), (5, 6), (-2, 5))
    for start, origin, drift, duration in events:
        progress = (time - start) / duration
        if not 0 <= progress <= 1:
            continue
        x = origin + drift * progress + 37 * math.sin(progress * math.tau * 1.3)
        y = -35 + (HEIGHT + 72) * progress
        angle = progress * math.tau * 1.6
        c, sn = math.cos(angle), math.sin(angle)

        def transform(px, py):
            py *= .45 + .55 * abs(math.cos(angle * 1.3))
            return (round((x + px * c - py * sn) / 2) * 2,
                    round((y + px * sn + py * c) / 2) * 2)

        draw.polygon([transform(*point) for point in outline], fill=(205, 89, 39, 222),
                     outline=(104, 42, 33, 231))
        draw.line((transform(-8, 0), transform(8, 1)), fill=(255, 170, 81, 221), width=2)
        draw.line((transform(-7, 0), transform(-12, 2)), fill=(138, 69, 36, 234), width=2)


def falling_gerberas(image, time):
    draw = ImageDraw.Draw(image, 'RGBA')
    colors = ((255, 126, 118), (240, 109, 159), (255, 178, 126))
    edges = (32, 668, 693, 43, 675, 28, 682, 42, 684)
    for index, origin in enumerate(edges):
        lifetime = 5.2 + (index % 3) * .65
        age = time - (.2 + index * 3.35)
        if not 0 <= age <= lifetime:
            continue
        phase = age / lifetime
        x = origin + 18 * math.sin(age * 1.15 + index)
        y = -28 + phase * (HEIGHT + 56)
        radius = 7 + (index % 4) * 2
        spin = index * .8 + age * .82
        squash = .7 + .3 * abs(math.cos(age * 1.1 + index))
        rgb = colors[index % len(colors)]
        draw_gerbera(draw, x, y, radius, spin, squash, rgb)


def draw_gerbera(draw, x, y, radius, spin, squash, rgb):
    for petal in range(13):
        angle = spin + petal * math.tau / 13
        dx, dy = math.cos(angle), math.sin(angle) * squash
        draw.line((x + dx * radius * .32, y + dy * radius * .32,
                   x + dx * radius, y + dy * radius), fill=(*rgb, 215), width=max(2, radius // 3))
    core = radius * .35
    draw.ellipse((x - core, y - core * squash, x + core, y + core * squash),
                 fill=(99, 33, 47, 238), outline=(255, 194, 123, 214), width=1)


def closing_gerbera(image, time, landing):
    progress = max(0, min(1, 1 + (time - landing) / 2.25))
    if not progress:
        return
    ease = progress * progress * (3 - 2 * progress)
    x = 415 - 119 * ease + math.sin(progress * math.tau) * 27 * (1 - progress)
    y = 699 + 318 * ease
    if progress == 1:
        y -= 5 * math.exp(-max(0, time - landing) * 9) * abs(math.sin((time - landing) * 15))
    draw = ImageDraw.Draw(image, 'RGBA')
    if progress > .82:
        shadow = min(75, round((progress - .82) * 410))
        draw.ellipse((280, 1015, 313, 1023), fill=(12, 5, 18, shadow))
    draw_gerbera(draw, x, y, 18, progress * 4.6, .85 - ease * .56, (255, 135, 120))


def frame_at(time, prepared, timeline, end, media_frame=None):
    index = max(0, bisect_right(timeline, time) - 1)
    start = timeline[index]
    scene, current_row, duration = prepared['rows'][index]
    art = prepared['bases'][scene]
    motif = art.motif
    scene_start, scene_duration = prepared['bounds'][scene]
    phase = max(0, min(1, (time - scene_start) / scene_duration))
    style = prepared['styles'][scene]
    if media_frame is None:
        image = art.background.copy()
    else:
        media = prepared['media'][scene]
        moved = move_frame(media_frame, media['movimiento'], phase)
        image = Image.blend(moved, art.background, media['velo'] / 100)
    if prepared['storm'][scene] or prepared['sunset'][scene] or prepared['reactive'][scene]:
        peaks = (prepared['audio_peaks'].get(prepared['sensitivity'][scene], ()) if prepared['reactive'][scene]
                 else ((5.4, .12), (14.8, .12), (24.6, .12)))
        image = storm_frame(image, time, prepared['drops'] if prepared['storm'][scene] else (), peaks,
                            prepared['sunset'][scene], style['intensidad_efectos'] / 100,
                            style['luces_atardecer'])
    if prepared['foreground_leaves'][scene] and not style['hojas_delante']:
        foreground_leaves(image, time, style)
    landing = None
    if style.get('cierre_gerbera') and index == len(timeline) - 1:
        marks = prepared['word_marks'][scene]
        last = marks[current_row] if current_row < len(marks) else []
        landing = start + last[-1] if last else end - 2.4
        dusk = min(.34, max(0, (time - landing) / max(.1, end - landing)) * .34)
        if dusk:
            image = Image.blend(image, prepared['black'], dusk)
    if prepared.get('solo_fondo'):
        if style.get('gerberas'):
            falling_gerberas(image, time)
        if landing is not None:
            closing_gerbera(image, time, landing)
        if prepared['foreground_leaves'][scene] and style.get('hojas_delante', True):
            foreground_leaves(image, time, style)
        fade = min(1, 0.3 + time / .65, max(0, (end - time) / .64))
        return Image.blend(prepared['black'], image, fade) if fade < 1 else image
    image.paste(art.overlay, (0, 0), art.overlay)
    if style.get('gerberas'):
        falling_gerberas(image, time)
    if animated_title(style):
        title, face, credit, credit_font = prepared['sunset_header']
        sunset_title(image, time, title, face, credit, credit_font, ImageColor.getrgb(motif.accent))
    rgb, accent = motif.rgb, motif.accent
    code = art.code
    star = prepared['stars'][scene]
    if star is not None:
        sx, sy = moving_light(motif, phase)
        image.paste(star, (round(sx - star.width / 2), round(sy - star.height / 2)), star)
    draw = ImageDraw.Draw(image)
    elapsed = time - start
    panel_offset = -167 if style.get('composicion_alta') else 0
    caption_offset = -186 if style.get('composicion_alta') else 0
    for row, ((source, parts, caption_font), code_font) in enumerate(prepared['verses'][scene][:current_row + 1]):
        y = 621 + row * 44 + panel_offset
        step = typing_step(len(source), duration)
        shown = len(source) if row < current_row else min(len(source), max(0, int(elapsed / step)))
        if row == current_row and shown:
            draw.rounded_rectangle((68, y - 18, 598, y + 18), 7, fill=code.active)
        draw.text((79, y), str(row + 1), font=prepared['line_number'], fill=code.muted, anchor='lm')
        advance = code_font.getlength('M')
        for match in TOKEN.finditer(source):
            offset = match.start()
            if offset >= shown:
                break
            draw.text((115 + offset * advance, y), source[offset:min(shown, match.end())],
                      font=code_font, fill=syntax_color(match.group(), code), anchor='lm')
        if row == current_row and (0 < shown < len(source) or int(time * 2.8) % 2 == 0):
            cursor = round(115 + shown * advance)
            draw.rounded_rectangle((cursor + 2, y - 16, cursor + 11, y + 16), 2, fill=code.keyword)
    if visible_at(elapsed, prepared['visibility'][index]):
        caption_layer = Image.new('RGBA', image.size) if prepared['storm'][scene] or prepared['sunset'][scene] or any(prepared['word_marks'][scene]) else None
        if caption_layer is not None:
            draw = ImageDraw.Draw(caption_layer)
        alpha = min(1, elapsed / 0.22)
        color = tuple(round(low + (high - low) * alpha) for low, high in zip(rgb, motif.ink))
        draw.rounded_rectangle((49, 820 + caption_offset, 642, 847 + 55 * len(parts) + caption_offset), radius=15, fill=(21, 15, 27))
        draw.line((62, 836 + caption_offset, 62, 827 + 55 * len(parts) + caption_offset), fill=accent, width=4)
        visible = prepared['visibility'][index]
        caption_duration = end - start if index == len(timeline) - 1 else duration
        remaining = (visible if visible is not None else caption_duration) - elapsed
        if caption_layer is None:
            for row, line in enumerate(parts):
                draw.text((80, 827 + row * 55 + caption_offset), line, font=caption_font, fill=color)
        else:
            words = [(row, line, token) for row, line in enumerate(parts)
                     for token in re.finditer(r'\S+', line)]
            interval = min(.072, .38 / max(1, len(words) - 1))
            scene_marks = prepared['word_marks'][scene]
            marks = scene_marks[current_row] if current_row < len(scene_marks) else []
            aligned = len(marks) == len(words)
            highlight = ImageColor.getrgb(accent)
            for order, (row, line, token) in enumerate(words):
                age = elapsed - (marks[order] if aligned else order * interval)
                incoming = max(0, min(1, age / (.095 if aligned else .24)))
                outgoing = max(0, min(1, (remaining - order * interval * .32) / .22))
                opacity = min(incoming, outgoing)
                if opacity <= 0:
                    continue
                glow = max(0, 1 - abs(age - .19) / .24)
                x = 80 + caption_font.getlength(line[:token.start()])
                y = 827 + row * 55 + caption_offset + round(13 * (1 - incoming) - 6 * (1 - outgoing))
                ink = tuple(round(a + (b - a) * glow) for a, b in zip(motif.ink, highlight))
                panel = (21, 15, 27)
                tone = tuple(round(a + (b - a) * opacity) for a, b in zip(panel, ink))
                draw.text((x, y), token.group(), font=caption_font, fill=tone)
        if caption_layer is not None:
            amount = max(0, min(1, elapsed / .32, remaining / .29))
            amount = amount * amount * (3 - 2 * amount)
            mask = caption_layer.getchannel('A').point([round(value * amount) for value in range(256)])
            image.paste(caption_layer, (0, round(11 * (1 - amount))), mask)
    if landing is not None:
        closing_gerbera(image, time, landing)
    mark = prepared['watermarks'][scene]
    if mark:
        opacity = .48 + .16 * math.sin(time * 1.4)
        ink = tuple(round(a + (b - a) * opacity) for a, b in zip((40, 29, 38), (255, 220, 172)))
        draw = ImageDraw.Draw(image)
        location = style.get('posicion_marca', 'Inferior derecha')
        x = 615 if location.endswith('derecha') else 59
        y = 1125 if location.startswith('Inferior') else 155
        draw.text((x, y), mark, font=prepared['watermark_fonts'][scene], fill=ink,
                  stroke_width=1, stroke_fill=(38, 24, 33), anchor='rs' if location.endswith('derecha') else 'ls')
    if prepared['foreground_leaves'][scene] and style.get('hojas_delante', True):
        foreground_leaves(image, time, style)
    fade = min(1, 0.3 + time / 0.65, max(0, (end - time) / 0.64))
    if fade < 1:
        image = Image.blend(prepared['black'], image, fade)
    return image


def typing_step(characters, duration):
    return min(0.065, duration * 0.63 / max(1, characters))


def prepare(title, scenes, timings, scene_offset=0, last_scene=True, intro=INTRO):
    bases = [make_base(i + scene_offset, title, name, style, media)
             for i, (name, _, style, media) in enumerate(scenes)]
    verses = []
    bounds = []
    rows = []
    active_times = []
    offset = 0
    for i, (_, scene, _, _) in enumerate(scenes):
        longest = max((cue[0] for cue in scene), key=len)
        code_font = fitted_font('consola.ttf', 25, longest, 470)
        verses.append([((cue[0], *wrapped_caption(cue[1])), code_font) for cue in scene])
        active_times.extend(cue[2] if len(cue) > 2 else None for cue in scene)
        scene_durations = timings[offset:offset + len(scene)]
        bounds.append((intro + sum(timings[:offset]), sum(scene_durations)))
        rows.extend((i, row, duration) for row, duration in enumerate(scene_durations))
        offset += len(scene)
    return dict(bases=bases, verses=verses, bounds=bounds, rows=rows, visibility=active_times,
                media=[scene[3] for scene in scenes],
                storm=[scene[2].get('tormenta', False) for scene in scenes],
                sunset=[scene[2].get('atardecer_animado', False) for scene in scenes],
                foreground_leaves=[scene[2].get('hojas_primer_plano', False) for scene in scenes],
                watermarks=[scene[2].get('marca_agua', '') if scene[2].get('mostrar_marca', True) else '' for scene in scenes],
                styles=[default_style(i) | scene[2] for i, scene in enumerate(scenes)],
                watermark_fonts=[font('seguisym.ttf' if os.name == 'nt' else 'georgia.ttf', scene[2].get('tamano_marca', 26))
                                 if scene[2].get('marca_agua') else None for scene in scenes],
                sunset_header=(title[0], fitted_font('georgia.ttf', 90, title[0], 510),
                               title[1], fitted_font('seguisb.ttf', 23, title[1], 510)),
                reactive=[scene[2].get('luz_al_audio', False) for scene in scenes], audio_peaks={},
                sensitivity=[scene[2].get('sensibilidad_graves', 'Media') for scene in scenes],
                word_marks=[scene[2].get('marcas_palabras', []) for scene in scenes],
                drops=np.random.default_rng(824).uniform((0, 0, 430, 10), (WIDTH, HEIGHT, 1020, 48), (125, 4)),
                stars=[make_star(art.motif.rgb, last_scene and i == len(scenes) - 1)
                       if art.motif.shape != 'Sin figura' else None for i, art in enumerate(bases)],
                line_number=font('consola.ttf', 18), black=Image.new('RGB', (WIDTH, HEIGHT)))


def write_audio(path, prepared, timeline, total):
    rate = 48000
    signal = np.zeros(round(total * rate), dtype=np.float32)
    rng = np.random.default_rng(33)
    click_t = np.arange(int(rate * 0.032)) / rate
    click_envelope = np.exp(-click_t * 160) * np.minimum(1, click_t * 5500)
    for i, (scene, row, duration) in enumerate(prepared['rows']):
        source = prepared['verses'][scene][row][0][0]
        for j, char in enumerate(source, 1):
            if char.isspace():
                continue
            start = round((timeline[i] + typing_step(len(source), duration) * j) * rate)
            click = 0.054 * rng.normal(0, 1, len(click_t))
            click += 0.072 * np.sin(2 * np.pi * rng.uniform(425, 570) * click_t)
            signal[start:start + len(click_t)] += click * click_envelope
    chords = [(130.81, 155.56, 196.00), (116.54, 155.56, 174.61), (103.83, 130.81, 155.56)]
    for i, (start_seconds, duration) in enumerate(prepared['bounds']):
        start = max(0, round((start_seconds - 0.95) * rate))
        stop = min(len(signal), round((start_seconds + duration + 1.5) * rate))
        local = np.arange(stop - start) / rate
        swell = np.sin(np.pi * np.linspace(0, 1, len(local))) ** 1.45
        chord = np.zeros_like(local)
        for f in chords[i % len(chords)]:
            chord += np.sin(2 * np.pi * f * local) + 0.52 * np.sin(2 * np.pi * (f + 0.53) * local)
        signal[start:stop] += 0.023 * chord * swell
    fade = min(len(signal), round(0.65 * rate))
    signal[-fade:] *= np.linspace(1, 0, fade)
    write_wave(path, signal, rate)


def write_wave(path, signal, rate):
    with wave.open(str(path), 'wb') as audio:
        audio.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        audio.writeframes((signal.clip(-1, 1) * 32767).astype('<i2').tobytes())


def lyric_frames(prepared, timeline, frames, fps):
    with ExitStack() as media_resources:
        active_scene = -1
        source_frames = None
        for index in range(frames):
            time = index / fps
            row = max(0, bisect_right(timeline, time) - 1)
            scene = prepared['rows'][row][0]
            if scene != active_scene:
                media_resources.close()
                media = prepared['media'][scene]
                source_frames = media_resources.enter_context(
                    BackgroundFrames(media, (WIDTH, HEIGHT), fps)) if media else None
                active_scene = scene
            frame = source_frames.next_frame() if source_frames else None
            yield frame_at(time, prepared, timeline, frames / fps, frame)


def ascii_frames(prepared, frames, fps):
    data = prepared['data']
    if data['fuente'] == 'Figura 3D':
        yield from (ascii_art.scene_frame(index / fps, prepared) for index in range(frames))
        return
    shots = ascii_art.planos.parse(data['planos_camara'], data['duracion'])
    size = ascii_art.media_area(data)[2:]
    source = {'archivo': data['archivo'], 'tipo': data['fuente'], 'velocidad_video': data['velocidad_video'],
              'giro_video': data['giro_video']}
    with BackgroundFrames(source, size, fps, fit=data['ajuste'], alpha=True, loop=data['bucle']) as reader:
        for index in range(frames):
            time = index / fps
            frame = ascii_art.planos.frame(reader.next_frame(), time, shots)
            yield ascii_art.scene_frame(time, prepared, character_frame(prepared, frame, time))


def ascii_preview_frame(time, prepared, seek_rate=30):
    data = prepared['data']
    if data['fuente'] == 'Figura 3D':
        return ascii_art.scene_frame(time, prepared)
    if not data['archivo']:
        raise ValueError('Selecciona una imagen o video.')
    reveal = prepared.get('video_reveal')
    size = video_reveal.SIZE if reveal else ascii_art.media_area(data)[2:]
    path = Path(data['archivo'])
    stat = path.stat()
    position = round(max(0, time * data['velocidad_video']) * seek_rate) / seek_rate if data['fuente'] == 'Video' else 0
    frame = ascii_preview_still(str(path), data['fuente'], size, data['ajuste'], data['bucle'], position,
                                stat.st_mtime_ns, stat.st_size, data['giro_video'])
    frame = ascii_art.planos.frame(frame, time, ascii_art.planos.parse(data['planos_camara'], data['duracion']))
    frame = character_frame(prepared, frame, time)
    return reveal.frame(time, frame) if reveal else ascii_art.scene_frame(time, prepared, frame)


def prepare_ascii(data):
    if video_reveal.enabled(data):
        prepared = {'data': data, 'video_reveal': video_reveal.VideoReveal(data, font)}
    else:
        prepared = ascii_art.prepare(data, font)
    if data['fuente'] != 'Figura 3D' and data['archivo_personaje']:
        prepared['character'] = ascii_art.personaje.Character(data)
    return prepared


def export_png(source, output, time=0.0):
    if output.suffix.lower() != '.png':
        raise ValueError('La imagen necesita un nombre que termine en .png.')
    if not math.isfinite(time):
        raise ValueError('Indica un segundo válido para capturar el fotograma.')
    TimelinePreview(source).frame(time).save(output, format='PNG')


def character_frame(prepared, image, time):
    character = prepared.get('character')
    return character.composite(image, time) if character else image


def reveal_frames(animation, size, frames, fps):
    prepared = prepare_ascii(animation)
    reveal = prepared['video_reveal']
    shots = ascii_art.planos.parse(animation['planos_camara'], animation['duracion'])
    source = {'archivo': animation['archivo'], 'tipo': 'Video', 'velocidad_video': animation['velocidad_video'],
              'giro_video': animation['giro_video']}
    with BackgroundFrames(source, size, fps, fit=animation['ajuste'], loop=animation['bucle']) as reader:
        for index in range(frames):
            time = index / fps
            frame = ascii_art.planos.frame(reader.next_frame(), time, shots)
            yield reveal.frame(time, character_frame(prepared, frame, time))


class TimelinePreview:
    def __init__(self, project_file):
        title, scenes, spans, self.recording, intro, self.audio_start, self.audio_end, self.animation, _ = read_project(project_file)
        self.cues = []
        if self.animation:
            self.clock = ReelClock.ascii(self.animation['duracion'])
            self.prepared = prepare_ascii(self.animation)
        else:
            self.clock = ReelClock.lyrics(spans, intro, HOLD)
            self.prepared = prepare(title, scenes, spans, intro=intro)
            if any(self.prepared['reactive']):
                self.prepared['audio_peaks'] = audio_flashes(self.recording, self.audio_start, self.audio_end, self.clock.total,
                    {level for level, active in zip(self.prepared['sensitivity'], self.prepared['reactive']) if active})
            labels = (cue[1] for _, rows, _, _ in scenes for cue in rows)
            self.cues = [(start, span, show, label) for start, span, show, label in
                         zip(self.clock.starts, spans, self.prepared['visibility'], labels)]

    def frame(self, requested):
        time = self.clock.sample(requested)
        if self.animation:
            return ascii_preview_frame(time, self.prepared)
        row = self.clock.row_at(time)
        scene, _, _ = self.prepared['rows'][row]
        media = self.prepared['media'][scene]
        still = None
        if media:
            offset = time if scene == 0 else time - self.prepared['bounds'][scene][0]
            still = self.video_frame(media['archivo'], media['tipo'], (WIDTH, HEIGHT), offset + media.get('inicio', 0),
                                     'Recortar', True).convert('RGB')
        return frame_at(time, self.prepared, self.clock.starts, self.clock.total, still)

    @staticmethod
    def video_frame(path, kind, size, time, fit, loop, rotation='Según archivo'):
        known = Path(path).stat()
        return ascii_preview_still(path, kind, size, fit, loop, round(max(0, time) * 30) / 30 if kind == 'Video' else 0,
                                   known.st_mtime_ns, known.st_size, rotation)


EXPORT_QUALITIES = {
    'Máxima nitidez': ('medium', '12', .34),
    'Alta': ('fast', '15', .34),
    'Compacta': ('veryfast', '21', 0),
}
EXPORT_RESOLUTIONS = {'1080 × 1920': FINAL_SIZE, '720 × 1280': (720, 1280),
                      '1080 × 2280': (1080, 2280), '1440 × 2560': (1440, 2560)}


def export_options(project):
    fps = project.get('fps', FPS)
    quality = project.get('calidad_video', 'Máxima nitidez')
    resolution = project.get('resolucion_video', '1080 × 1920')
    if type(fps) is not int or fps not in (30, 60):
        raise ValueError('La exportación admite 30 o 60 fps.')
    if quality not in EXPORT_QUALITIES or resolution not in EXPORT_RESOLUTIONS:
        raise ValueError('Selecciona una calidad y una resolución de exportación válidas.')
    return fps, quality, resolution


def render(source, output, on_progress=None, preview=False, cancel=None):
    ffmpeg = find_ffmpeg()
    title, scenes, timings, recording, intro, audio_start, audio_end, animation, mix = read_project(source)
    secondary = audio_mix.extra_path(mix)
    assets = [Path(media['archivo']) for _, _, _, media in scenes if media]
    if animation and animation['fuente'] != 'Figura 3D':
        assets.append(Path(animation['archivo']))
        if animation['archivo_personaje']:
            assets.append(Path(animation['archivo_personaje']))
    if output in (source.resolve(), recording, secondary, *assets):
        raise ValueError('Elige un nombre de salida distinto al de los archivos del proyecto.')
    measured = audio_mix.validate_track(recording, audio_start, audio_end) if recording else None
    if secondary:
        audio_mix.validate_track(secondary, mix['recorte_extra'])
    clock = ReelClock.ascii(animation['duracion']) if animation else ReelClock.lyrics(timings, intro, HOLD)
    timeline = clock.starts
    project_options = json.loads(source.read_text(encoding='utf-8-sig'))
    requested_fps, quality_name, resolution = export_options(project_options)
    fps = 24 if preview else requested_fps
    frames = math.ceil(clock.total * fps - 1e-8)
    total = frames / fps
    dimensions = PREVIEW_SIZE if preview else EXPORT_RESOLUTIONS[resolution]
    ascii_world = bool(animation and ascii_art.is_ascii_world(animation))
    procedural = bool(animation and ascii_art.is_procedural(animation))
    if procedural:
        dimensions = (540, 720) if preview else ascii_art.arte_procedural.SIZE
    speed, quality, sharpen = ('ultrafast', '24', 0) if preview else EXPORT_QUALITIES[quality_name]
    if procedural or ascii_world:
        sharpen = 0
    mixed = animation and video_reveal.enabled(animation)
    canvas = FINAL_SIZE if dimensions == (1080, 2280) else dimensions
    input_size = ascii_art.arte_procedural.SIZE if procedural else (canvas if mixed else (WIDTH, HEIGHT))
    if ascii_world:
        input_size = ascii_art.caballero_del_faro.SIZE
    if mixed or ((procedural or ascii_world) and input_size == canvas):
        scale = 'null'
    else:
        method = 'neighbor' if procedural or ascii_world else 'lanczos'
        scale = f'scale={canvas[0]}:{canvas[1]}:flags={method}'
    if dimensions == (1080, 2280):
        pad_color = '0x0d090e' if animation and animation.get('fondo_estadio') else '0x14152e'
        scale += f',pad=1080:2280:0:180:color={pad_color}'
    if sharpen:
        scale += f',format=yuv420p,unsharp=5:5:{sharpen}:5:5:0'
    if mixed:
        sequence = reveal_frames(animation, input_size, frames, fps)
    elif animation:
        prepared = prepare_ascii(animation)
        sequence = ascii_frames(prepared, frames, fps)
    else:
        prepared = prepare(title, scenes, timings, intro=intro)
        prepared['solo_fondo'] = bool(project_options.get('solo_fondo', False))
        if any(prepared['reactive']):
            prepared['audio_peaks'] = audio_flashes(recording, audio_start, audio_end, total,
                {level for level, active in zip(prepared['sensitivity'], prepared['reactive']) if active})
        sequence = lyric_frames(prepared, timeline, frames, fps)
    with tempfile.TemporaryDirectory(dir=output.parent) as directory:
        temporary = Path(directory)
        audio = recording or temporary / 'ambientacion.wav'
        if recording is None:
            if animation:
                rate = 48000
                time = np.arange(round(total * rate)) / rate
                samples = np.zeros_like(time) if animation['sonido'] == 'Silencio' else ascii_art.ambient(time, total)
                write_wave(audio, samples, rate)
            else:
                write_audio(audio, prepared, timeline, total)
        video = temporary / 'video.mp4'
        repeat_audio = recording and animation and animation['repetir_audio']
        if repeat_audio and (audio_start or audio_end is not None):
            raise ValueError('Para repetir la pista completa, deja el inicio en cero y el final vacío.')
        audio_trim = ['-stream_loop', '-1'] if repeat_audio else (['-ss', f'{audio_start:.3f}'] if recording and audio_start else [])
        audio_length = audio_end - audio_start if recording and audio_end else None
        if recording and mix['salida'] and not repeat_audio:
            if measured is not None:
                available = max(0, measured - audio_start)
                audio_length = min(audio_length, available) if audio_length is not None else available
        audio_filter = audio_mix.filters(mix, total, audio_length)
        extra_input = (['-protocol_whitelist', 'file,pipe', '-ss', f'{mix["recorte_extra"]:.3f}', '-i', str(secondary)]
                       if secondary else [])
        audio_options = (['-filter_complex', audio_mix.mixing_graph(audio_filter, mix), '-map', '[mezcla]'] if secondary
                         else ['-map', '1:a:0', '-af', audio_filter])
        command = [
            ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-filter_threads', '2',
            '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', f'{input_size[0]}x{input_size[1]}',
            '-framerate', str(fps), '-i', '-', '-protocol_whitelist', 'file,pipe', *audio_trim, '-i', str(audio), *extra_input,
            '-map', '0:v:0', *audio_options, '-vf', scale, '-t', f'{total:.6f}',
            '-c:v', 'libx264', '-crf', quality, '-preset', speed, '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(video),
        ]
        with tempfile.TemporaryFile() as error_log, subprocess.Popen(
                command, stdin=subprocess.PIPE, stderr=error_log, **PROCESS_OPTIONS) as process:
            try:
                with process.stdin:
                    for index, frame in enumerate(sequence):
                        if cancel is not None and cancel.is_set():
                            raise InterruptedError('Operación cancelada.')
                        process.stdin.write(frame.tobytes())
                        if on_progress and index % fps == 0:
                            on_progress(int(index * 100 / frames))
            except BrokenPipeError:
                if process.wait() == 0:
                    raise
            finally:
                sequence.close()
            if process.wait():
                error_log.seek(0)
                errors = error_log.read().decode('utf-8', errors='replace').splitlines()
                if any('1:a:0' in line and 'matches no streams' in line for line in errors):
                    raise ValueError('El archivo seleccionado no tiene una pista de audio. Elige Ambiente, Silencio u otra pista.')
                reason = errors[-1] if errors else 'Revisa el formato del audio.'
                raise ValueError(f'FFmpeg no pudo exportar el video. {reason}')
        if cancel is not None and cancel.is_set():
            raise InterruptedError('Operación cancelada.')
        video.replace(output)
    if on_progress:
        on_progress(100)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Crea un reel sin conexión.')
    parser.add_argument('--proyecto', type=Path, default=ROOT / 'reel.json')
    parser.add_argument('--salida', type=Path, default=ROOT / 'Reel.mp4')
    parser.add_argument('--progreso', action='store_true')
    parser.add_argument('--segundo', type=float, default=0.0, help='Instante para exportar un PNG.')
    args = parser.parse_args()
    try:
        callback = (lambda value: print(f'PROGRESO {value}', flush=True)) if args.progreso else None
        if args.salida.suffix.lower() == '.png':
            export_png(args.proyecto, args.salida.resolve(), args.segundo)
        else:
            render(args.proyecto, args.salida.resolve(), callback)
        print(f'Archivo listo: {args.salida}')
    except (ValueError, OSError, KeyError, IndexError, TypeError) as error:
        raise SystemExit(f'Error: {error}') from None

