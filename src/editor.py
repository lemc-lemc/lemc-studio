import argparse
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import unicodedata
from copy import deepcopy
from difflib import SequenceMatcher
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageTk

import ascii_art
import audio_mix
import render
import movimiento_fondo
import video_reveal
from ascii_controls import AsciiControls
from designs import CODE_THEMES, PALETTES
from lyrics import AUTO_PROFILES, LANGUAGES, MIN_LINE, PROFILES, Line, Transcript, format_transcript, model_in, optional_seconds, parse_lrc, parse_srt, subtitle_timings, transcribe_project, transcribe_song
from media import MOTIONS, PROCESS_OPTIONS, VIDEO_ROTATIONS, ascii_preview_still, find_ffmpeg, inspect_video, media_settings
from reel_clock import ReelClock, visibility
from studio_ui import DesignLibrary, edit_mix
from timeline_ui import TimelineWindow
from tool_gallery import ToolGallery


ROOT = Path(__file__).resolve().parent
VERSION = '8.3.7'
PREVIEW_DIMENSIONS = (250, 444)
BG, PANEL, FIELD = '#111019', '#191821', '#23222d'
TEXT, MUTED, ACCENT = '#f5edf1', '#bcafbf', '#ffb4a3'
DEFAULT_SECONDS = 3.05
PROJECT_TYPES = [('Proyecto de reel', '*.json')]
AUDIO_TYPES = [('Archivos de audio', '*.mp3 *.wav *.m4a *.ogg *.flac *.aac *.opus'), ('Todos', '*.*')]
IMAGE_TYPES = [('Imágenes', '*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff'), ('Todos', '*.*')]
VIDEO_TYPES = [('Videos', '*.mp4 *.mov *.mkv *.webm *.avi *.m4v'), ('Todos', '*.*')]
UI_FONT = 'Segoe UI' if os.name == 'nt' else 'TkDefaultFont'
MONO_FONT = 'Consolas' if os.name == 'nt' else 'DejaVu Sans Mono'


def scene_name(index):
    return f'escena_{index + 1:02}.js'


def blank_project():
    return {'version_proyecto': render.PROJECT_VERSION, 'titulo': ['', ''], 'audio_local': '', 'segundos_por_verso': DEFAULT_SECONDS,
            'introduccion': render.INTRO, 'inicio_audio': 0.0, 'fin_audio': None,
            'modo': 'letra', 'animacion_ascii': ascii_art.config(ascii_art.DEFAULTS), 'mezcla_audio': audio_mix.DEFAULT_MIX.copy(),
            'escenas': [{'archivo': scene_name(0), 'versos': []}]}


def normalized_words(text):
    lower = unicodedata.normalize('NFKD', text.lower())
    return ''.join(char for char in lower if not unicodedata.combining(char))


def quick_video_project(path):
    path = path.resolve()
    duration, with_audio = inspect_video(path)
    name = re.sub(r'[^a-z0-9]+', '_', normalized_words(path.stem)).strip('_')[:35] or 'video_ascii'
    animation = ascii_art.config({
        'fuente': 'Video', 'archivo': str(path), 'duracion': round(min(120, max(2, duration)), 3),
        'ajuste': 'Recortar', 'bucle': False, 'lienzo_original': True, 'mensaje': '',
        'particulas': False, 'codigo': True, 'panel_compacto': True, 'opacidad_panel': 73,
        'tema_codigo': 'Grafito', 'firma_ascii': '\U0001d50f\U0001d508\U0001d510\u212d',
        'archivo_panel': f'{name}.py', 'mensaje_fundido': True,
        'columnas': 128, 'brillo': .14, 'contraste': 1.22, 'realzar_bordes': True, 'detalle_sombras': True,
        'sonido': 'Audio del video' if with_audio else 'Silencio',
    })
    return blank_project() | {'modo': 'ascii', 'titulo': [path.stem, ''], 'fps': 60,
                              'calidad_video': 'Máxima nitidez', 'resolucion_video': '1080 × 1920',
                              'animacion_ascii': animation}


def suggest_code(verse):
    lower = normalized_words(verse)
    suggestions = [
        ('brillan mis ojos', 'const secreto = luzEnMisOjos;'),
        ('sonrojo', 'if (ellaSeAcerca) meFaltaElAire();'),
        ('mi delirio', '// En mi mundo, ella nunca lo supo'),
        ('despierta', 'const latido = silencio + suNombre;'),
        ('diera la vida', 'const precio = todoLoQueSoy;'),
        ('suspiro', 'if (meMira) guardoLoQueSiento();'),
        ('miro', '// La miré sin atreverme a hablar'),
        ('enciende', 'const incendio = unaSolaMirada;'),
        ('tan lejos', 'const distancia = Infinity;'),
        ('distancia', 'const distancia = Infinity;'),
        ('alcanz', 'const alcance = sueño ?? realidad;'),
        ('estrella', 'const ella = cielo.lejosDeMí;'),
        ('cobardia', 'const valor = voz || silencio;'),
        ('te extrano', '// Aún guardo el lugar que dejaste'),
        ('recuerdo', 'const ayer = loQueNoSolté;'),
        ('otra vez', 'while (duela) vuelvoAEmpezar();'),
        ('para siempre', 'const promesa = { final: null };'),
        ('mi corazon', 'const refugio = miCorazón;'),
        ('nunca', '// Todavía quedaba una esperanza'),
        ('manana', 'const mañana = otraOportunidad;'),
    ]
    for phrase, code in suggestions:
        if phrase in lower:
            return code
    words = verse.split()
    excerpt = ' '.join(words)
    while len(excerpt) > 23 and len(words) > 1:
        words.pop()
        excerpt = ' '.join(words)
    if excerpt != verse or len(excerpt) > 23:
        excerpt = f'{excerpt[:23]}…'
    return f'const loQueSiento = {json.dumps(excerpt, ensure_ascii=False)};'


def scenes_from_lyrics(text, timings=None, captions=None):
    stanzas = []
    current = []
    for line in [*text.splitlines(), '']:
        lyric = line.strip()
        if lyric:
            current.append([suggest_code(lyric), lyric])
        elif current:
            stanzas.extend(current[i:i + 4] for i in range(0, len(current), 4))
            current = []
    if timings is not None:
        rows = (row for stanza in stanzas for row in stanza)
        for index, (row, duration) in enumerate(zip(rows, timings)):
            row.append(duration)
            if captions is not None and captions[index] is not None:
                row.append(captions[index])
    return [{'archivo': scene_name(i), 'versos': verses} for i, verses in enumerate(stanzas)]


def title_lines(filename):
    words = Path(filename).stem.replace('_', ' ').replace('-', ' ').split()
    if len(words) < 2:
        return [' '.join(words)[:70] or 'Mi reel', '']
    split = min(range(1, len(words)), key=lambda i: abs(len(' '.join(words[:i])) - len(' '.join(words[i:]))))
    return [' '.join(words[:split])[:70], ' '.join(words[split:])[:70]]


def recommend_scene(scene, default_duration):
    lines = [row for row in scene['versos'] if row[1]]
    lyric = normalized_words(' '.join(row[1] for row in lines))
    if any(word in lyric for word in ('estrella', 'luna', 'noche', 'cielo', 'lejos')):
        palette = ('Azul nocturno', {'acento': '#b7c8ff', 'fondo': '#10182f', 'forma': 'Estrella'})
    elif any(word in lyric for word in ('amor', 'corazon', 'beso', 'suspiro')):
        palette = ('Rosa cálido', {'acento': '#ffaaa6', 'fondo': '#27141e', 'forma': 'Corazón'})
    elif any(word in lyric for word in ('fuego', 'sol', 'brilla', 'enciende')):
        palette = ('Ámbar', {'acento': '#ffcf98', 'fondo': '#27190e', 'forma': 'Rombo'})
    else:
        palette = ('Verde suave', {'acento': '#9fe2ca', 'fondo': '#102220', 'forma': 'Órbita'})
    tips = []
    if any(len(row[1]) > 65 for row in lines):
        tips.append('Divide los versos largos para que se lean mejor en el móvil.')
    try:
        durations = [render.verse_seconds(row[2] if len(row) >= 3 and row[2] else default_duration) for row in lines]
        if durations and min(durations) < 1.3:
            tips.append('Los versos de menos de 1,3 s pasan rápido. Revisa su ritmo en la vista con audio.')
    except (ValueError, TypeError):
        tips.append('Revisa los segundos de los versos. Cada uno necesita al menos 0,7 s.')
    media = scene.get('fondo_media')
    if media and media['tipo'] == 'Imagen' and media['movimiento'] == 'Fijo':
        tips.append('Prueba «Acercar» para dar movimiento a la imagen.')
    if media and media['velo'] < 25:
        tips.append('Si el fondo distrae, sube el velo de color para destacar la letra.')
    return palette, tips or ['Revisa la entrada del primer verso en la vista con audio.']


def load_project(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('version_proyecto', 1) > render.PROJECT_VERSION:
        raise ValueError('Este proyecto requiere una versión más reciente del editor.')
    title = data['titulo']
    scenes = data['escenas']
    if (not isinstance(title, list) or len(title) != 2 or not all(isinstance(line, str) for line in title)
            or not isinstance(scenes, list) or not scenes):
        raise ValueError('El proyecto necesita un título de dos líneas y al menos una escena.')
    default = render.verse_seconds(data['segundos_por_verso'])
    for index, scene in enumerate(scenes):
        if not isinstance(scene['archivo'], str) or not isinstance(scene['versos'], list) or len(scene['versos']) > 4:
            raise ValueError('Cada escena necesita un nombre y admite hasta cuatro versos.')
        for row in scene['versos']:
            if not isinstance(row, list) or len(row) not in (2, 3, 4) or not all(isinstance(value, str) for value in row[:2]):
                raise ValueError('Cada verso debe contener código y letra, con duración y visibilidad opcionales.')
        if 'estilo' in scene:
            scene['estilo'] = render.scene_style(index, scene['estilo'])
        if scene.get('fondo_media'):
            scene['fondo_media'] = media_settings(scene['fondo_media'], path.parent)
    audio = data.get('audio_local', '')
    intro, audio_start, audio_end = render.audio_timing(data)
    mode, ascii_settings = ascii_art.project_mode(data, path.parent)
    fps, quality, resolution = render.export_options(data)
    return {'version_proyecto': render.PROJECT_VERSION, 'titulo': title, 'escenas': scenes, 'segundos_por_verso': default,
            'introduccion': intro, 'inicio_audio': audio_start, 'fin_audio': audio_end,
            'fps': fps, 'calidad_video': quality, 'resolucion_video': resolution,
            'modo': mode, 'animacion_ascii': ascii_settings, 'mezcla_audio': audio_mix.normalize(data.get('mezcla_audio'), path.parent),
            'audio_local': str((path.parent / audio).resolve()) if audio else ''}


def save_project(path, project):
    data = {**project, 'version_proyecto': render.PROJECT_VERSION, 'escenas': []}
    data['mezcla_audio'] = audio_mix.portable(audio_mix.normalize(project.get('mezcla_audio')), path.parent)
    if data['audio_local']:
        audio = Path(data['audio_local'])
        if audio.parent == path.parent:
            data['audio_local'] = audio.name
    if data.get('animacion_ascii'):
        animation = data['animacion_ascii'].copy()
        animation['mezcla'] = audio_mix.portable(audio_mix.normalize(animation.get('mezcla')), path.parent)
        for key in ('archivo', 'pista', 'archivo_personaje'):
            if animation.get(key):
                asset = Path(animation[key])
                if asset.parent == path.parent:
                    animation[key] = asset.name
        data['animacion_ascii'] = animation
    for scene in project['escenas']:
        stored = {**scene}
        if scene.get('fondo_media'):
            media = {**scene['fondo_media']}
            asset = Path(media['archivo'])
            if asset.parent == path.parent:
                media['archivo'] = asset.name
            stored['fondo_media'] = media
        data['escenas'].append(stored)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as temporary:
        name = Path(temporary.name)
        try:
            json.dump(data, temporary, ensure_ascii=False, indent=2)
            temporary.write('\n')
        except Exception:
            temporary.close()
            name.unlink(missing_ok=True)
            raise
    try:
        name.replace(path)
    finally:
        name.unlink(missing_ok=True)


def project_for_export(project):
    if project['modo'] == 'ascii':
        animation = ascii_art.config(project.get('animacion_ascii'))
        audio_mix.extra_path(animation['mezcla'])
        if animation['fuente'] != 'Figura 3D' and (not animation['archivo'] or not Path(animation['archivo']).is_file()):
            raise ValueError('Elige una imagen o video existente en la pestaña ASCII.')
        audio = ascii_art.audio_path(animation)
        if audio and not audio.is_file():
            raise ValueError('Elige una pista local existente en «Audio ASCII».')
        return {**project, 'animacion_ascii': animation}
    audio_mix.extra_path(audio_mix.normalize(project.get('mezcla_audio')))
    if not any(project['titulo']):
        raise ValueError('Escribe un título antes de exportar.')
    scenes = []
    for i, scene in enumerate(project['escenas'], 1):
        lines = []
        for j, row in enumerate(scene['versos'], 1):
            code, lyric = row[:2]
            if not (code or lyric):
                continue
            if not lyric:
                raise ValueError(f'Completa la letra de la escena {i}, verso {j}.')
            try:
                duration = render.verse_seconds(row[2] if len(row) >= 3 else project['segundos_por_verso'])
            except (ValueError, TypeError):
                raise ValueError(f'Revisa la duración de la escena {i}, verso {j}. Usa 0,7 segundos o más.') from None
            try:
                shown = visibility(row[3] if len(row) >= 4 else None, duration)
            except ValueError as error:
                raise ValueError(f'Escena {i}, verso {j}. {error}') from None
            lines.append([code or suggest_code(lyric), lyric, duration, shown])
        if lines:
            media = scene.get('fondo_media')
            if media and not Path(media['archivo']).is_file():
                raise ValueError(f'No se encontró el archivo de fondo de la escena {i}. Vuelve a seleccionarlo.')
            scenes.append({**scene, 'versos': lines, 'estilo': render.scene_style(i - 1, scene.get('estilo'))})
    if not scenes:
        raise ValueError('Agrega al menos un verso antes de exportar.')
    return {**project, 'escenas': scenes}


def align_words(rows, starts, chunks):
    heard, timestamps = [], []
    for chunk in chunks:
        tokens = chunk.text.split()
        weight = sum(map(len, tokens))
        offset = 0
        for token in tokens:
            heard.append(normalized_words(token).strip('.,;:!?¿¡"'))
            timestamps.append(chunk.start + (chunk.end - chunk.start) * offset / weight)
            offset += len(token)
    verses = [[normalized_words(word).strip('.,;:!?¿¡"') for word in row[1].split()] for row in rows]
    expected = [word for verse in verses for word in verse]
    matcher = SequenceMatcher(None, expected, heard, autojunk=False)
    matched = {a + i: timestamps[b + i] for a, b, count in matcher.get_matching_blocks() for i in range(count)}
    result = []
    offset = 0
    for index, verse in enumerate(verses):
        stamps = [matched.get(offset + i) for i in range(len(verse))]
        offset += len(verse)
        limit = rows[index][3] if rows[index][3] is not None else rows[index][2]
        if all(t is not None and starts[index] - .12 <= t < starts[index] + limit for t in stamps):
            result.append([round(max(0, t - starts[index]), 3) for t in stamps])
        else:
            result.append([])
    return result


def supports_ascii_pair(animation):
    return bool(animation and (animation['fuente'] in ('Video', 'Imagen') or ascii_art.is_ascii_world(animation)))


def render_ascii_pair(project, target, progress=None, cancel=None, *, solo_fit="Encajar"):
    animation = project.get('animacion_ascii')
    if project.get('modo') != 'ascii' or not supports_ascii_pair(animation):
        raise ValueError('La exportación doble requiere una imagen, un video o un mundo ASCII.')
    target = target.resolve()
    with_test = animation.get('prueba_reescalada', False)
    if with_test and project.get('resolucion_video') == '1440 × 2560':
        raise ValueError('Elige una resolución base menor para comparar con la prueba a 1440p.')
    mixed = video_reveal.enabled(animation)
    suffixes = ('con código', 'sin código' if mixed else 'solo ASCII') + (('prueba 1440p',) if with_test else ())
    if mixed:
        solo_fit = animation['ajuste']
    for counter in range(1, 10000):
        token = '' if counter == 1 else f' ({counter})'
        paths = tuple(target.with_name(f'{target.stem}{token} - {suffix}.mp4') for suffix in suffixes)
        if not any(path.exists() for path in paths):
            break
    else:
        raise FileExistsError('Elige otro nombre para la pareja de videos.')
    common = {'estilo_media': 'ASCII'}
    with_code = common | {'codigo': True, 'solo_video': False}
    settings = [with_code, common | {'codigo': False, 'solo_video': True, 'ajuste': solo_fit}]
    if with_test:
        settings.append(with_code)
    with tempfile.TemporaryDirectory(dir=target.parent) as directory:
        stage = Path(directory)
        staged = []
        for index, options in enumerate(settings):
            src = stage / f'proyecto-{index}.json'
            video = stage / f'version-{index}.mp4'
            profile = {'resolucion_video': '1440 × 2560'} if index == 2 else {}
            save_project(src, project | profile | {'animacion_ascii': animation | options})
            report = (lambda value, i=index: progress((i * 100 + value) // len(settings))) if progress else None
            render.render(src, video, report, cancel=cancel)
            staged.append(video)
        if cancel is not None and cancel.is_set():
            raise InterruptedError('Operación cancelada.')
        if any(path.exists() for path in paths):
            raise FileExistsError('El nombre de salida empezó a usarse. Elige otro nombre.')
        for video, path in zip(staged, paths):
            video.rename(path)
    return paths


class Editor:
    def __init__(self, root):
        self.root = root
        self.project = load_project(ROOT / 'reel.json')
        self.model = model_in(ROOT)
        self.previews = tempfile.TemporaryDirectory(prefix='vista-reel-', ignore_cleanup_errors=True)
        self.preview_count = 0
        self.path = None
        self.scene = self.selected_row = 0
        self.dirty = self.loading = False
        self.operation = ''
        self.preview_timer = None
        self.preview_image = None
        self.preview_frame = None
        self.ascii_prepared = None
        self.last_export = None
        self.last_export_pair = ()
        self.events = queue.Queue()
        self.cancel_task = threading.Event()
        self.title_vars = [tk.StringVar(), tk.StringVar()]
        self.scene_var = tk.StringVar()
        self.filename_var = tk.StringVar()
        self.shape_var = tk.StringVar()
        self.code_theme_var = tk.StringVar()
        self.audio_var = tk.StringVar()
        self.background_var = tk.StringVar()
        self.status = tk.StringVar(value='Ejemplo cargado')
        self.preview_status = tk.StringVar()
        self.preview_title = tk.StringVar(value='Vista previa del verso')
        self.mode_label = tk.StringVar(value='Letra y código')
        self.ascii_position = tk.DoubleVar(value=0.86)
        self.progress = tk.DoubleVar()
        self.export_quality = tk.StringVar(self.root)
        self.export_resolution = tk.StringVar(self.root)
        self.procedural_resolution = tk.StringVar(self.root, value='1080 × 1440')
        self.export_fps = tk.StringVar(self.root)
        self.export_detail = tk.StringVar(self.root)
        self.rows = [[tk.StringVar() for _ in range(4)] for _ in range(4)]
        self.configure_window()
        self.build()
        for var in [*self.title_vars, self.filename_var, *(v for row in self.rows for v in row)]:
            var.trace_add('write', self.on_edit)
        self.show_project()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.bind('<Control-s>', lambda _: self.save())
        self.root.bind('<Control-Key-1>', lambda _: self.workspace.select(0))
        self.root.bind('<Control-Key-2>', lambda _: self.workspace.select(1))

    def configure_window(self):
        self.root.title(f'LEMC Studio {VERSION}')
        self.root.configure(bg=BG)
        self.root.geometry('1250x740')
        self.root.minsize(1060, 700)
        self.window_icon = tk.PhotoImage(file=str(ROOT / 'icon.png'))
        self.root.iconphoto(True, self.window_icon)
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=(UI_FONT, 10), background=BG, foreground=TEXT)
        style.configure('TFrame', background=BG)
        style.configure('Panel.TFrame', background=PANEL)
        style.configure('Heading.TLabel', font=(UI_FONT, 22, 'bold'), background=BG)
        style.configure('Section.TLabel', font=(UI_FONT, 14, 'bold'), background=BG, foreground=TEXT)
        style.configure('Mode.TLabel', font=(UI_FONT, 10), background=BG, foreground=ACCENT)
        style.configure('Panel.TLabel', background=PANEL)
        style.configure('Muted.TLabel', foreground=MUTED)
        style.configure('PanelMuted.TLabel', background=PANEL, foreground=MUTED)
        style.configure('Panel.TCheckbutton', background=PANEL, foreground=TEXT)
        style.map('Panel.TCheckbutton', background=[('active', PANEL)], foreground=[('disabled', MUTED)])
        for notebook in ('Workspace', 'Settings'):
            style.configure(f'{notebook}.TNotebook', background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
            style.configure(f'{notebook}.TNotebook.Tab', background=FIELD, foreground=MUTED,
                            padding=(17, 8) if notebook == 'Workspace' else (12, 6), borderwidth=0)
            style.map(f'{notebook}.TNotebook.Tab', background=[('selected', PANEL)],
                      foreground=[('selected', ACCENT), ('active', TEXT)], expand=[('selected', (0, 0, 0, 0))])
        style.configure('TButton', padding=(12, 7), background=FIELD, foreground=TEXT,
                        borderwidth=0, focuscolor=ACCENT)
        style.map('TButton', background=[('active', '#383440')], foreground=[('disabled', '#918793')])
        style.configure('Tool.TButton', font=(UI_FONT, 10, 'bold'), padding=(10, 6), background='#2b2637')
        style.map('Tool.TButton', background=[('active', '#43374b'), ('disabled', '#201d2a')])
        style.configure('PanelHeading.TLabel', font=(UI_FONT, 11, 'bold'), background=PANEL, foreground=TEXT)
        style.configure('Export.TButton', font=(UI_FONT, 11, 'bold'), background=ACCENT,
                        foreground='#2a1921', padding=(16, 8))
        style.map('Export.TButton', background=[('disabled', FIELD), ('active', '#ffd1c6')],
                  foreground=[('disabled', MUTED)])
        for name in ('TEntry', 'TCombobox'):
            style.configure(name, fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT,
                            bordercolor='#413849', lightcolor=FIELD, darkcolor=FIELD,
                            selectbackground='#70536a', selectforeground=TEXT, padding=(6, 7))
        style.map('TCombobox', fieldbackground=[('readonly', FIELD)], foreground=[('readonly', TEXT)],
                  selectbackground=[('readonly', FIELD)], selectforeground=[('readonly', TEXT)])
        style.configure('Horizontal.TProgressbar', background=ACCENT, troughcolor=FIELD,
                        borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT)
        self.root.option_add('*TCombobox*Listbox.background', FIELD)
        self.root.option_add('*TCombobox*Listbox.foreground', TEXT)

    def build(self):
        shell = ttk.Frame(self.root, padding=(24, 14))
        shell.pack(fill='both', expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(2, weight=1)
        header = ttk.Frame(shell)
        header.grid(row=0, column=0, sticky='ew', pady=(0, 9))
        ttk.Label(header, text='LEMC Studio', style='Heading.TLabel').pack(side='left')
        ttk.Label(header, textvariable=self.mode_label, style='Mode.TLabel').pack(side='left', padx=(15, 0))
        self.project_buttons = []
        for label, action in [('Guardar proyecto', self.save), ('Abrir proyecto', self.open),
                              ('Nuevo', self.new), ('Video rápido…', self.open_quick_video)]:
            button = ttk.Button(header, text=label, command=action)
            button.pack(side='right', padx=(8, 0))
            self.project_buttons.append(button)
        gallery = ttk.Button(header, text='Ver demostraciones…', command=self.open_tool_gallery, style='Tool.TButton')
        gallery.pack(side='right', padx=(8, 0))
        self.project_buttons.append(gallery)
        timeline_button = ttk.Button(header, text='Línea de tiempo…', command=self.open_timeline)
        timeline_button.pack(side='right', padx=(8, 0))
        self.project_buttons.append(timeline_button)

        self.toolbar = ttk.Frame(shell, style='Panel.TFrame', padding=(9, 7))
        self.toolbar.grid(row=1, column=0, sticky='ew', pady=(0, 9))
        self.lyric_shortcuts = ttk.Frame(self.toolbar, style='Panel.TFrame')
        self.ascii_shortcuts = ttk.Frame(self.toolbar, style='Panel.TFrame')
        shortcuts = [
            (self.lyric_shortcuts, (
                ('Guion', lambda: self.lyric_tools.select(0)),
                ('Elegir audio', self.choose_audio),
                ('Letra automática', self.transcription_dialog),
                ('Tiempos por palabra', self.edit_word_times),
                ('Fondo', self.edit_background),
                ('Efectos y firma', self.scene_effects),
                ('Paletas y figuras', self.open_design_library),
            )),
            (self.ascii_shortcuts, (
                ('Composición', lambda: self.ascii_controls.sections.select(0)),
                ('Elegir archivo', self.ascii_controls_choose_asset),
                ('Conversión de archivos', lambda: self.ascii_controls.sections.select(1)),
                ('Audio ASCII', lambda: self.ascii_controls.sections.select(2)),
                ('Efectos y formato', lambda: self.ascii_controls.sections.select(3)),
                ('Paletas y figuras', self.open_design_library),
            )),
        ]
        self.shortcut_buttons = []
        for frame, commands in shortcuts:
            for label, action in commands:
                button = ttk.Button(frame, text=label, command=action, style='Tool.TButton')
                button.pack(side='left', padx=(0, 5))
                self.shortcut_buttons.append(button)

        content = ttk.Frame(shell)
        content.grid(row=2, column=0, sticky='nsew')
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        self.workspace = ttk.Notebook(content, style='Workspace.TNotebook')
        self.workspace.grid(row=0, column=0, sticky='nsew', padx=(0, 15))
        form = ttk.Frame(self.workspace, style='Panel.TFrame', padding=(15, 12))
        ascii_form = ttk.Frame(self.workspace, style='Panel.TFrame')
        self.workspace.add(form, text='Letra y código')
        self.workspace.add(ascii_form, text='ASCII')
        self.ascii_controls = AsciiControls(ascii_form, self.ascii_changed, IMAGE_TYPES, VIDEO_TYPES, AUDIO_TYPES,
                                            lambda: self.open_mix('ascii'), self.mark_video_reveal)
        self.workspace.bind('<<NotebookTabChanged>>', self.switch_mode)
        form.columnconfigure(0, weight=1)
        form.rowconfigure(0, weight=1)
        self.lyric_tools = ttk.Notebook(form, style='Settings.TNotebook')
        self.lyric_tools.grid(row=0, column=0, sticky='nsew')
        script_form, audio_form, design_form = (ttk.Frame(self.lyric_tools, style='Panel.TFrame', padding=(13, 12)) for _ in range(3))
        for group, title_text in ((script_form, 'Guion y escenas'), (audio_form, 'Audio y transcripción'),
                                  (design_form, 'Diseño y código')):
            group.columnconfigure(0, weight=1)
            self.lyric_tools.add(group, text=title_text)

        title = ttk.Frame(script_form, style='Panel.TFrame')
        title.grid(row=0, column=0, sticky='ew', pady=(0, 13))
        for col, var in enumerate(self.title_vars):
            title.columnconfigure(col, weight=1)
            ttk.Label(title, text=f'Título · línea {col + 1}', style='PanelMuted.TLabel').grid(row=0, column=col, sticky='w')
            ttk.Entry(title, textvariable=var).grid(row=1, column=col, padx=(0, 8 if col == 0 else 0), pady=(4, 0), sticky='ew')

        scene_bar = ttk.Frame(script_form, style='Panel.TFrame')
        scene_bar.grid(row=1, column=0, sticky='ew', pady=(0, 11))
        scene_bar.columnconfigure(2, weight=1)
        ttk.Label(scene_bar, text='Escena', style='PanelMuted.TLabel').grid(row=0, column=0, padx=(0, 7))
        self.scene_select = ttk.Combobox(scene_bar, textvariable=self.scene_var, state='readonly', width=6)
        self.scene_select.grid(row=0, column=1)
        self.scene_select.bind('<<ComboboxSelected>>', self.switch_scene)
        name = ttk.Entry(scene_bar, textvariable=self.filename_var, width=11, font=(MONO_FONT, 10))
        name.grid(row=0, column=2, sticky='ew', padx=8)
        for col, label, action in [(3, 'Anterior', lambda: self.step_scene(-1)), (4, 'Siguiente', lambda: self.step_scene(1))]:
            ttk.Button(scene_bar, text=label, command=action).grid(row=0, column=col, padx=(0 if col == 3 else 6, 0))
        scene_actions = ttk.Frame(scene_bar, style='Panel.TFrame')
        scene_actions.grid(row=1, column=0, columnspan=5, sticky='ew', pady=(7, 0))
        for label, action in [('Pegar letra', self.paste_lyrics), ('Añadir escena', self.add_scene), ('Quitar escena', self.remove_scene)]:
            ttk.Button(scene_actions, text=label, command=action).pack(side='left', padx=(0, 7))
        for label, action in (
            ('Duplicar', self.duplicate_scene), ('Mover antes', lambda: self.move_scene(-1)),
            ('Mover después', lambda: self.move_scene(1)),
        ):
            ttk.Button(scene_actions, text=label, command=action, style='Tool.TButton').pack(side='left', padx=(0, 5))

        grid = ttk.Frame(script_form, style='Panel.TFrame')
        grid.grid(row=2, column=0, sticky='ew')
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(2, weight=1)
        self.row_labels = []
        for col, label in enumerate(['', 'Código en pantalla', 'Letra', 'Hasta sig. (s)', 'Visible (s)']):
            ttk.Label(grid, text=label, style='PanelMuted.TLabel').grid(row=0, column=col, sticky='w', padx=(0, 6), pady=(0, 4))
        for row, variables in enumerate(self.rows):
            marker = ttk.Label(grid, text=str(row + 1), style='PanelMuted.TLabel', width=3)
            marker.grid(row=row + 1, column=0, sticky='w')
            marker.bind('<Button-1>', lambda _, index=row: self.select_row(index))
            self.row_labels.append(marker)
            for col, var in enumerate(variables):
                face = (MONO_FONT if col == 0 else UI_FONT, 10)
                entry = ttk.Entry(grid, textvariable=var, width=8 if col >= 2 else 18, font=face)
                entry.grid(row=row + 1, column=col + 1, sticky='ew', padx=(0, 6 if col < 3 else 0), pady=(0, 5))
                entry.bind('<FocusIn>', lambda _, index=row: self.select_row(index))
        ttk.Label(script_form, text='«Visible» controla cuándo desaparece la letra. Déjalo vacío para mantenerla hasta el siguiente verso.',
                  style='PanelMuted.TLabel', wraplength=560).grid(row=4, column=0, sticky='w', pady=(8, 0))

        guidance = ttk.Frame(script_form, style='Panel.TFrame')
        guidance.grid(row=3, column=0, sticky='ew', pady=(10, 0))
        ttk.Button(guidance, text='Elegir pista o transcribir…', command=lambda: self.lyric_tools.select(1)).pack(side='left')
        ttk.Button(guidance, text='Diseñar la escena…', command=lambda: self.lyric_tools.select(2)).pack(side='left', padx=(8, 0))

        audio = ttk.Frame(audio_form, style='Panel.TFrame')
        audio.grid(row=0, column=0, sticky='ew')
        audio.columnconfigure(0, weight=1)
        ttk.Label(audio, text='Pista principal de letra', style='PanelMuted.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(audio, textvariable=self.audio_var, style='Panel.TLabel', wraplength=500).grid(row=1, column=0, sticky='w', pady=(4, 10))
        audio_actions = ttk.Frame(audio, style='Panel.TFrame')
        audio_actions.grid(row=2, column=0, sticky='w')
        self.audio_buttons = []
        for col, label, action in [(1, 'Elegir audio', self.choose_audio), (2, 'Letra automática…', self.transcription_dialog),
                                   (3, 'Inicio…', self.edit_audio_start), (4, 'Mezcla…', lambda: self.open_mix('letra')),
                                   (5, 'Quitar', self.clear_audio)]:
            button = ttk.Button(audio_actions, text=label, command=action)
            button.grid(row=0, column=col, padx=(0, 7))
            self.audio_buttons.append(button)
        ttk.Label(audio_form, text='«Inicio» recorta la pista. En «Mezcla» puedes ajustar el volumen y añadir una segunda pista.',
                  style='PanelMuted.TLabel', wraplength=490).grid(row=1, column=0, sticky='w', pady=(12, 0))

        appearance = ttk.Frame(design_form, style='Panel.TFrame')
        appearance.grid(row=0, column=0, sticky='ew')
        appearance.columnconfigure(4, weight=1)
        for col, label in enumerate(('Figura animada', 'Acento', 'Fondo', 'Tema de código')):
            ttk.Label(appearance, text=label, style='PanelMuted.TLabel').grid(row=0, column=col, sticky='w', pady=(0, 4))
        self.shape_select = ttk.Combobox(appearance, textvariable=self.shape_var, values=render.SHAPES,
                                         state='readonly', width=13)
        self.shape_select.grid(row=1, column=0, padx=(0, 9), sticky='w')
        self.shape_select.bind('<<ComboboxSelected>>', lambda _: self.change_style(forma=self.shape_var.get()))
        self.swatches = {}
        for col, key in enumerate(('acento', 'fondo'), 1):
            swatch = tk.Button(appearance, command=lambda name=key: self.choose_color(name), width=9,
                               font=(MONO_FONT, 10), relief='flat', borderwidth=1, pady=7,
                               highlightthickness=1, highlightbackground='#51465a')
            swatch.grid(row=1, column=col, padx=(0, 9), sticky='w')
            self.swatches[key] = swatch
        code_theme = ttk.Combobox(appearance, textvariable=self.code_theme_var, values=tuple(CODE_THEMES), state='readonly', width=12)
        code_theme.grid(row=1, column=3, padx=(0, 8), sticky='w')
        code_theme.bind('<<ComboboxSelected>>', lambda _: self.change_style(tema_codigo=self.code_theme_var.get()))
        ttk.Button(appearance, text='Aplicar a todas', command=self.apply_style_to_all).grid(row=1, column=5, padx=(0, 7))
        ttk.Button(appearance, text='Restaurar', command=self.restore_style).grid(row=1, column=6)

        backgrounds = ttk.Frame(design_form, style='Panel.TFrame')
        backgrounds.grid(row=1, column=0, sticky='ew', pady=(13, 0))
        backgrounds.columnconfigure(0, weight=1)
        ttk.Label(backgrounds, text='Fondo multimedia', style='PanelMuted.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(backgrounds, textvariable=self.background_var, style='Panel.TLabel', wraplength=410).grid(row=1, column=0, sticky='w')
        ttk.Button(backgrounds, text='Imagen o video…', command=self.edit_background).grid(row=0, column=1, rowspan=2)
        ttk.Button(backgrounds, text='Sugerencias…', command=self.suggestions_dialog).grid(row=0, column=2, rowspan=2, padx=(7, 0))
        ttk.Button(backgrounds, text='Efectos, título y firma…', command=self.scene_effects).grid(row=2, column=0, sticky='w', pady=(6, 0))
        ttk.Button(backgrounds, text='Tiempos por palabra…', command=self.edit_word_times).grid(row=2, column=1, columnspan=2, sticky='e', pady=(6, 0))
        ttk.Button(design_form, text='Explorar paletas, figuras y frases…', command=self.open_design_library).grid(
            row=2, column=0, sticky='w', pady=(14, 0))

        preview = ttk.Frame(content)
        preview.grid(row=0, column=1, sticky='n')
        ttk.Label(preview, textvariable=self.preview_title, style='Muted.TLabel').pack(anchor='w', pady=(0, 5))
        self.canvas = tk.Canvas(preview, width=PREVIEW_DIMENSIONS[0], height=PREVIEW_DIMENSIONS[1], bg='#0a0910', highlightthickness=0)
        self.canvas.pack()
        self.canvas_image = self.canvas.create_image(0, 0, anchor='nw')
        self.canvas.bind('<Configure>', self.fit_preview)
        ttk.Label(preview, textvariable=self.preview_status, style='Muted.TLabel', width=30).pack(anchor='w', pady=(5, 0))
        self.ascii_scrub = ttk.Scale(preview, orient='horizontal', from_=0, to=0.999,
                                     variable=self.ascii_position, command=lambda _: self.schedule_preview())
        self.preview_actions = ttk.Frame(preview)
        self.preview_actions.pack(anchor='w', fill='x', pady=(8, 0))
        self.preview_button = ttk.Button(self.preview_actions, text='Reel con audio', command=self.preview_reel)
        self.preview_button.pack(side='left', fill='x', expand=True)
        self.scene_preview_button = ttk.Button(self.preview_actions, text='Ver escena', command=self.preview_scene)

        footer = ttk.Frame(shell, style='Panel.TFrame', padding=(12, 7))
        footer.grid(row=3, column=0, sticky='ew', pady=(9, 0))
        footer.columnconfigure(4, weight=1)
        ttk.Label(footer, text='Exportación', style='PanelHeading.TLabel').grid(row=0, column=0, rowspan=2, padx=(0, 14))
        self.export_fields = []
        for col, label, variable, values, width in (
            (1, 'Calidad', self.export_quality, tuple(render.EXPORT_QUALITIES), 17),
            (2, 'Resolución', self.export_resolution, tuple(render.EXPORT_RESOLUTIONS), 13),
            (3, 'Fotogramas por segundo', self.export_fps, ('30', '60'), 6),
        ):
            ttk.Label(footer, text=label, style='PanelMuted.TLabel').grid(row=0, column=col, sticky='w', padx=(0, 10))
            field = ttk.Combobox(footer, textvariable=variable, values=values, state='readonly', width=width)
            field.grid(row=1, column=col, sticky='w', padx=(0, 10))
            field.bind('<<ComboboxSelected>>', self.update_export_options)
            self.export_fields.append(field)
        ttk.Label(footer, textvariable=self.export_detail, style='PanelMuted.TLabel',
                  wraplength=240).grid(row=1, column=4, sticky='w')
        self.open_video = ttk.Button(footer, text='Ver último MP4', state='disabled', command=self.play_export)
        self.open_video.grid(row=1, column=5, padx=(5, 7))
        self.export_button = ttk.Button(footer, text='Exportar MP4', command=self.export, style='Export.TButton')
        self.export_button.grid(row=1, column=6)
        self.dual_export_button = ttk.Button(footer, text='Exportar variantes', command=self.export_ascii_pair,
                                             style='Tool.TButton')
        self.dual_export_button.grid(row=0, column=5, columnspan=2, sticky='e', pady=(0, 4))
        self.dual_export_button.grid_remove()
        self.png_export_button = ttk.Button(footer, text='Exportar PNG', command=self.export_current_png,
                                            style='Tool.TButton')
        self.png_export_button.grid(row=0, column=5, columnspan=2, sticky='e', pady=(0, 4))
        self.png_export_button.grid_remove()
        status = ttk.Frame(shell)
        status.grid(row=4, column=0, sticky='ew', pady=(5, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status, style='Muted.TLabel').grid(row=0, column=0, sticky='w')
        self.progress_bar = ttk.Progressbar(status, variable=self.progress, length=140)
        self.progress_bar.grid(row=0, column=1, padx=8)
        self.progress_bar.grid_remove()
        self.cancel_button = ttk.Button(status, text='Cancelar', command=self.cancel_operation)
        self.cancel_button.grid(row=0, column=2)
        self.cancel_button.grid_remove()
        self.background_task_buttons = [self.export_button, self.dual_export_button, self.png_export_button,
                                        self.preview_button, self.scene_preview_button,
                                        *self.project_buttons, *self.audio_buttons, *self.shortcut_buttons,
                                        *self.export_fields]

    def ascii_controls_choose_asset(self):
        self.ascii_controls.sections.select(0)
        if self.ascii_controls.variables['fuente'].get() != 'Figura 3D':
            self.ascii_controls.choose_asset()
            return
        filename = filedialog.askopenfilename(parent=self.root, filetypes=IMAGE_TYPES[:1] + VIDEO_TYPES)
        if filename:
            video_extensions = VIDEO_TYPES[0][1].split()
            kind = 'Video' if f'*{Path(filename).suffix.lower()}' in video_extensions else 'Imagen'
            self.ascii_controls.variables['fuente'].set(kind)
            self.ascii_controls.variables['archivo'].set(filename)

    def mark_video_reveal(self):
        try:
            duration = render.verse_seconds(self.ascii_controls.variables['duracion'].get())
            mark = min(duration - .01, max(0, self.ascii_position.get() * duration))
            self.ascii_controls.variables['fin_ascii'].set(f'{mark:.2f}')
        except ValueError as error:
            messagebox.showinfo('Montaje de video', str(error), parent=self.root)

    def update_export_options(self, _=None):
        choice = self.export_quality.get()
        self.project.update(fps=int(self.export_fps.get()), calidad_video=choice,
                            resolucion_video=self.export_resolution.get())
        self.export_detail.set({
            'Máxima nitidez': 'Menos compresión · archivo más grande',
            'Alta': 'Enfoque suave · tamaño intermedio',
            'Compacta': 'Archivo más ligero',
        }[choice])
        if self.procedural_selected():
            self.export_detail.set('Escena 3:4 · 1080 × 1440')
        if not self.loading:
            self.dirty = True

    def show_project(self):
        self.loading = True
        fps, quality, resolution = render.export_options(self.project)
        self.export_fps.set(str(fps))
        self.export_quality.set(quality)
        self.export_resolution.set(resolution)
        self.update_export_options()
        for var, title in zip(self.title_vars, self.project['titulo']):
            var.set(title)
        self.update_audio()
        self.ascii_controls.set(self.project['animacion_ascii'])
        self.workspace.select(1 if self.project['modo'] == 'ascii' else 0)
        self.show_scene()
        self.update_ascii_mode()
        self.loading = False

    def show_scene(self):
        self.loading = True
        scenes = self.project['escenas']
        self.scene_select.configure(values=[f'{i + 1:02} · {scene["archivo"]}' for i, scene in enumerate(scenes)], width=14)
        self.scene_select.current(self.scene)
        self.filename_var.set(scenes[self.scene]['archivo'])
        default = self.project['segundos_por_verso']
        verses = scenes[self.scene]['versos']
        for i, (code, lyric, duration, shown) in enumerate(self.rows):
            row = verses[i] if i < len(verses) else ['', '']
            code.set(row[0])
            lyric.set(row[1])
            duration.set(str(row[2] if len(row) >= 3 else default).replace('.', ','))
            shown.set(str(row[3]).replace('.', ',') if len(row) >= 4 and row[3] is not None else '')
        self.update_style()
        self.update_background()
        self.loading = False
        self.select_row(0)

    def commit(self):
        self.project['titulo'] = [var.get().strip() for var in self.title_vars]
        lines = [[value.get().strip() for value in row] for row in self.rows]
        while lines and not any(lines[-1][:2]):
            lines.pop()
        self.project['escenas'][self.scene] = {
            **self.project['escenas'][self.scene],
            'archivo': self.filename_var.get().strip() or scene_name(self.scene), 'versos': lines,
        }

    def on_edit(self, *_):
        if not self.loading:
            self.dirty = True
            self.schedule_preview()

    def select_row(self, row):
        self.selected_row = row
        for i, marker in enumerate(self.row_labels):
            marker.configure(text=f'▸{i + 1}' if i == row else f' {i + 1}')
        self.schedule_preview()

    def schedule_preview(self):
        if self.preview_timer:
            self.root.after_cancel(self.preview_timer)
        self.preview_timer = self.root.after(230, self.refresh_preview)

    def refresh_preview(self):
        self.preview_timer = None
        self.commit()
        if self.project['modo'] == 'ascii':
            try:
                animation = self.ascii_controls.settings()
                if self.ascii_prepared is None or self.ascii_prepared['data'] != animation:
                    self.ascii_prepared = render.prepare_ascii(animation)
                time = self.ascii_position.get() * animation['duracion']
                self.set_preview_frame(render.ascii_preview_frame(time, self.ascii_prepared, seek_rate=8))
                name = animation['figura'] if animation['fuente'] == 'Figura 3D' else animation['fuente']
                self.preview_status.set(f'{name} · {time:.1f} / {animation["duracion"]:g} s')
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                self.preview_frame = None
                self.canvas.itemconfigure(self.canvas_image, image='')
                self.preview_status.set(str(error))
            return
        scene = self.project['escenas'][self.scene]
        verses = scene['versos']
        title = self.project['titulo']
        if not any(title):
            title = ['Tu título', '']
        try:
            values, durations = [], []
            for row in range(max(len(verses), self.selected_row + 1)):
                cue = verses[row] if row < len(verses) else ('', '')
                code, lyric = cue[:2]
                span = render.verse_seconds(cue[2] if len(cue) >= 3 else self.project['segundos_por_verso'])
                durations.append(span)
                shown = visibility(cue[3] if len(cue) >= 4 else None, span)
                values.append((code or (suggest_code(lyric) if lyric else ''), lyric, shown))
            media = scene.get('fondo_media')
            intro = self.project['introduccion'] if self.scene == 0 else 0
            clock = ReelClock.lyrics(durations, intro, render.HOLD)
            prepared = render.prepare(title, [(scene['archivo'], values, self.current_style(), media)], durations, scene_offset=self.scene,
                                      last_scene=self.scene == len(self.project['escenas']) - 1, intro=intro)
            shown = values[self.selected_row][2]
            time = clock.starts[self.selected_row] + (shown or durations[self.selected_row]) * 0.70
            media_frame = None
            media_error = ''
            if media:
                try:
                    meta = Path(media['archivo']).stat()
                    media_frame = ascii_preview_still(media['archivo'], media['tipo'], (render.WIDTH, render.HEIGHT),
                                                      'Recortar', True, time + media.get('inicio', 0) if media['tipo'] == 'Video' else 0,
                                                      meta.st_mtime_ns, meta.st_size).convert('RGB')
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    media_error = ' · fondo no disponible'
            frame = render.frame_at(time, prepared, clock.starts, clock.total, media_frame)
            self.set_preview_frame(frame)
            self.preview_status.set(f'Escena {self.scene + 1} · verso {self.selected_row + 1}{media_error}')
        except ValueError as error:
            self.preview_frame = None
            self.canvas.itemconfigure(self.canvas_image, image='')
            self.preview_status.set(str(error))

    def set_preview_frame(self, frame):
        self.preview_frame = frame
        self.fit_preview()

    def fit_preview(self, _=None):
        if self.preview_frame is None:
            return
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if min(width, height) < 2:
            return
        ratio = min(width / self.preview_frame.width, height / self.preview_frame.height)
        size = (round(self.preview_frame.width * ratio), round(self.preview_frame.height * ratio))
        self.preview_image = ImageTk.PhotoImage(self.preview_frame.resize(size, Image.Resampling.LANCZOS))
        self.canvas.coords(self.canvas_image, (width - size[0]) // 2, (height - size[1]) // 2)
        self.canvas.itemconfigure(self.canvas_image, image=self.preview_image)

    def update_ascii_mode(self):
        self.update_procedural_actions()
        if self.project['modo'] == 'ascii':
            self.lyric_shortcuts.pack_forget()
            self.ascii_shortcuts.pack(anchor='w')
            self.mode_label.set('Composición ASCII')
            self.preview_title.set('Vista previa ASCII')
            self.scene_preview_button.pack_forget()
            self.ascii_scrub.pack(anchor='w', fill='x', pady=(5, 0), before=self.preview_actions)
        else:
            self.ascii_shortcuts.pack_forget()
            self.lyric_shortcuts.pack(anchor='w')
            self.mode_label.set('Letra y código')
            self.preview_title.set('Vista previa del verso')
            self.ascii_scrub.pack_forget()
            self.scene_preview_button.pack(side='left', padx=(6, 0))
            self.ascii_prepared = None

    def ascii_changed(self):
        self.dirty = True
        if self.project['modo'] == 'ascii':
            self.update_procedural_actions()
            self.schedule_preview()

    def procedural_selected(self):
        return self.project['modo'] == 'ascii' and ascii_art.is_procedural(
            {key: self.ascii_controls.variables[key].get() for key in ('fuente', 'figura')})

    def update_procedural_actions(self):
        procedural = self.procedural_selected()
        world = self.project['modo'] == 'ascii' and ascii_art.is_ascii_world(
            {key: self.ascii_controls.variables[key].get() for key in ('fuente', 'figura')})
        if procedural or world:
            self.png_export_button.grid()
        else:
            self.png_export_button.grid_remove()
        if self.project['modo'] == 'ascii' and not procedural:
            self.dual_export_button.grid()
        else:
            self.dual_export_button.grid_remove()
        self.export_fields[1].configure(
            state='disabled' if procedural else 'readonly',
            textvariable=self.procedural_resolution if procedural else self.export_resolution)
        was_dirty = self.dirty
        self.update_export_options()
        self.dirty = was_dirty

    def open_design_library(self):
        DesignLibrary(self.root, render.font, self.project['modo'], self.apply_design)

    def apply_design(self, figure, palette_name, code_theme, phrase):
        if self.project['modo'] == 'ascii':
            try:
                options = self.ascii_controls.settings()
                options.update(fuente='Figura 3D', figura=figure, paleta=palette_name, tema_codigo=code_theme,
                               caracteres=normalized_words(figure).upper())
                options.pop('color_figura', None)
                options.pop('color_fondo', None)
                if phrase:
                    options['mensaje'] = phrase
                self.ascii_controls.set(ascii_art.config(options))
            except ValueError as error:
                messagebox.showerror('Biblioteca de diseños', str(error), parent=self.root)
                return False
            self.ascii_position.set(.87)
            self.ascii_changed()
        else:
            background, accent, *_ = PALETTES[palette_name]
            if phrase:
                target = next((i for i, row in enumerate(self.rows) if not row[0].get().strip() and not row[1].get().strip()), None)
                if target is None:
                    self.add_scene()
                    target = 0
                code, verse, duration, _ = self.rows[target]
                code.set(suggest_code(phrase))
                verse.set(phrase)
                duration.set(f'{min(6, max(2.5, len(phrase) / 18)):.2f}'.replace('.', ','))
                if not any(var.get().strip() for var in self.title_vars):
                    self.title_vars[0].set(figure)
                self.select_row(target)
            self.change_style(forma=figure, fondo=background, acento=accent, tema_codigo=code_theme)
        self.status.set(f'Diseño aplicado · {figure} · {palette_name}')
        return True

    def switch_mode(self, _=None):
        mode = 'ascii' if self.workspace.index(self.workspace.select()) == 1 else 'letra'
        if self.loading or mode == self.project['modo']:
            return
        self.commit()
        self.project['modo'] = mode
        self.dirty = True
        self.update_ascii_mode()
        self.schedule_preview()

    def step_scene(self, delta):
        target = self.scene + delta
        if 0 <= target < len(self.project['escenas']):
            self.commit()
            self.scene = target
            self.show_scene()

    def switch_scene(self, _):
        self.commit()
        self.scene = self.scene_select.current()
        self.show_scene()

    def add_scene(self):
        self.commit()
        self.scene = len(self.project['escenas'])
        self.project['escenas'].append({'archivo': scene_name(self.scene), 'versos': []})
        self.dirty = True
        self.show_scene()

    def duplicate_scene(self):
        self.commit()
        scenes = self.project['escenas']
        clone = deepcopy(scenes[self.scene])
        filename = Path(clone['archivo'])
        occupied = {scene['archivo'] for scene in scenes}
        suffix = filename.suffix or '.js'
        counter = 1
        while (suggestion := f'{filename.stem}_copia{counter if counter > 1 else ""}{suffix}') in occupied:
            counter += 1
        clone['archivo'] = suggestion
        self.scene += 1
        scenes.insert(self.scene, clone)
        self.dirty = True
        self.show_scene()
        self.status.set('Escena duplicada')

    def move_scene(self, delta):
        target = self.scene + delta
        scenes = self.project['escenas']
        if 0 <= target < len(scenes):
            self.commit()
            scenes[self.scene], scenes[target] = scenes[target], scenes[self.scene]
            self.scene = target
            self.dirty = True
            self.show_scene()

    def remove_scene(self):
        self.commit()
        scenes = self.project['escenas']
        if scenes[self.scene]['versos'] and not messagebox.askyesno('Quitar escena', '¿Quitar esta escena y sus versos?', parent=self.root):
            return
        scenes.pop(self.scene)
        if not scenes:
            scenes.extend(blank_project()['escenas'])
        self.scene = min(self.scene, len(scenes) - 1)
        self.dirty = True
        self.show_scene()

    def replace_lyrics(self, lyrics, timings=None, keep_times=False, captions=None):
        self.commit()
        previous = self.project['escenas']
        if keep_times and timings is None:
            old_rows = [row for scene in previous for row in scene['versos'] if row[1]]
            new_count = sum(bool(line.strip()) for line in lyrics.splitlines())
            if new_count == len(old_rows):
                default = self.project['segundos_por_verso']
                timings = [row[2] if len(row) >= 3 else default for row in old_rows]
                captions = [row[3] if len(row) >= 4 else None for row in old_rows]
        scenes = scenes_from_lyrics(lyrics, timings, captions)
        if not scenes:
            return False
        for index, after in enumerate(scenes):
            before = previous[min(index, len(previous) - 1)]
            if 'fondo_media' in before:
                after['fondo_media'] = deepcopy(before['fondo_media'])
            if 'estilo' in before:
                after['estilo'] = {key: value for key, value in before['estilo'].items() if key != 'marcas_palabras'}
        self.project['escenas'] = scenes
        self.scene = 0
        self.dirty = True
        self.show_scene()
        self.status.set(f'Letra cargada · {len(scenes)} escenas. Puedes editar el código sugerido.')
        return True

    def paste_lyrics(self):
        window = tk.Toplevel(self.root, bg=BG)
        window.title('Pegar letra')
        window.transient(self.root)
        window.grab_set()
        pane = ttk.Frame(window, padding=16)
        pane.pack(fill='both', expand=True)
        ttk.Label(pane, text='Escribe un verso por línea y deja una línea en blanco entre estrofas.').pack(anchor='w')
        box = ScrolledText(pane, width=57, height=13, wrap='word', bg=FIELD, fg=TEXT,
                           insertbackground=TEXT, font=(UI_FONT, 11), relief='flat', padx=7, pady=7)
        box.pack(fill='both', expand=True, pady=10)
        box.focus_set()
        keep_times = tk.BooleanVar(value=True)
        ttk.Checkbutton(pane, text='Conservar tiempos si coincide la cantidad de versos', variable=keep_times).pack(anchor='w', pady=(0, 8))
        imported = []
        import_status = tk.StringVar()

        def read_timed_lyrics():
            selected = filedialog.askopenfilename(parent=window, filetypes=[('Letra con tiempos', '*.srt *.lrc')])
            if not selected:
                return
            path = Path(selected)
            try:
                payload = path.read_bytes()
                try:
                    content = payload.decode('utf-8-sig')
                except UnicodeDecodeError:
                    content = payload.decode('cp1252')
                lines = parse_lrc(content) if path.suffix.lower() == '.lrc' else parse_srt(content)
                if not lines:
                    raise ValueError('El archivo no contiene versos con marcas de tiempo.')
            except (OSError, ValueError) as error:
                messagebox.showerror('No se pudo importar la letra', str(error), parent=window)
                return
            imported[:] = lines
            box.delete('1.0', 'end')
            box.insert('1.0', '\n'.join(line.text for line in lines))
            import_status.set(f'{len(lines)} versos de {path.name}')

        ttk.Label(pane, textvariable=import_status, style='Muted.TLabel', wraplength=420).pack(anchor='w')

        def apply():
            text = box.get('1.0', 'end-1c')
            if not text.strip():
                return
            self.commit()
            if any(scene['versos'] for scene in self.project['escenas']):
                if not messagebox.askyesno('Cambiar letra', '¿Reemplazar las escenas actuales con esta letra?', parent=window):
                    return
            times = shown = None
            if imported:
                count = sum(bool(line.strip()) for line in text.splitlines())
                first, times, shown = subtitle_timings(imported, count)
                if self.project['audio_local']:
                    self.project.update(inicio_audio=first, introduccion=0.0, fin_audio=None)
                    self.update_audio()
            if self.replace_lyrics(text, timings=times, keep_times=keep_times.get(), captions=shown):
                window.destroy()

        ttk.Button(pane, text='Importar SRT o LRC…', command=read_timed_lyrics).pack(side='left')
        ttk.Button(pane, text='Crear escenas', command=apply, style='Export.TButton').pack(side='right')
        ttk.Button(pane, text='Cancelar', command=window.destroy).pack(side='right', padx=(0, 8))

    def update_audio(self):
        audio = self.project['audio_local']
        start = self.project['inicio_audio']
        end = self.project['fin_audio']
        label = Path(audio).name if audio else 'Ambientación original y tecleo'
        if audio and start:
            label += f' · desde {start:.2f} s'
        if audio and end is not None:
            label += f' · hasta {end:.2f} s'
        self.audio_var.set(label)

    def edit_audio_start(self):
        window = tk.Toplevel(self.root, bg=BG)
        window.title('Inicio del audio')
        window.transient(self.root)
        window.grab_set()
        pane = ttk.Frame(window, padding=16)
        pane.pack(fill='both', expand=True)
        start = tk.StringVar(value=str(self.project['inicio_audio']))
        intro = tk.StringVar(value=str(self.project['introduccion']))
        end = tk.StringVar(value=str(self.project['fin_audio']) if self.project['fin_audio'] is not None else '')
        fields = [('Empezar la pista en (s)', start), ('Terminar la pista en (s), opcional', end),
                  ('Apertura antes del primer verso (s)', intro)]
        for i, (label, value) in enumerate(fields):
            ttk.Label(pane, text=label).grid(row=i, column=0, sticky='w', pady=5, padx=(0, 12))
            ttk.Entry(pane, textvariable=value, width=10).grid(row=i, column=1, sticky='w')

        def apply():
            try:
                new_start, new_intro = optional_seconds(start.get()), optional_seconds(intro.get())
                new_end = optional_seconds(end.get()) if end.get().strip() else None
                if new_end is not None and new_end <= new_start:
                    raise ValueError('El final debe ser posterior al inicio.')
            except ValueError as error:
                messagebox.showerror('Revisa los tiempos', str(error), parent=window)
                return
            self.project.update(inicio_audio=new_start, fin_audio=new_end, introduccion=new_intro)
            self.dirty = True
            self.update_audio()
            window.destroy()

        ttk.Button(pane, text='Aplicar', command=apply, style='Export.TButton').grid(row=3, column=1, sticky='e', pady=(10, 0))

    def transcription_dialog(self):
        if not self.project['audio_local']:
            self.choose_audio()
        if not self.project['audio_local']:
            return
        source = Path(self.project['audio_local'])
        window = tk.Toplevel(self.root, bg=BG)
        window.title('Letra automática')
        window.transient(self.root)
        window.grab_set()
        pane = ttk.Frame(window, padding=16)
        pane.pack(fill='both', expand=True)
        language = tk.StringVar(value='Español')
        profile = tk.StringVar(value='Automático')
        sync_words = tk.BooleanVar(window, value=True)
        start = tk.StringVar(value=str(self.project['inicio_audio']))
        finish = tk.StringVar(value=str(self.project['fin_audio']) if self.project['fin_audio'] is not None else '')
        model_name = tk.StringVar(value=self.model.name if self.model else 'Selecciona un modelo Whisper .bin')
        ttk.Label(pane, text=source.name, wraplength=390).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))
        fields = [('Idioma', language, list(LANGUAGES)), ('Perfil de voz', profile, (*AUTO_PROFILES, *PROFILES)),
                  ('Desde (s)', start, None), ('Hasta (s), opcional', finish, None)]
        for i, (label, var, choices) in enumerate(fields, 1):
            ttk.Label(pane, text=label).grid(row=i, column=0, sticky='w', pady=5, padx=(0, 12))
            field = (ttk.Combobox(pane, textvariable=var, values=choices, state='readonly', width=26)
                     if choices else ttk.Entry(pane, textvariable=var, width=26))
            field.grid(row=i, column=1, sticky='w')

        def choose_model():
            selected = filedialog.askopenfilename(parent=window, filetypes=[('Modelo Whisper', '*.bin')])
            if selected:
                self.model = Path(selected)
                model_name.set(self.model.name)

        def run():
            try:
                begin = optional_seconds(start.get())
                end = optional_seconds(finish.get()) if finish.get().strip() else None
                if end is not None and end <= begin:
                    raise ValueError('El final debe ser posterior al inicio.')
                if not self.model or not self.model.is_file():
                    raise ValueError('Selecciona el modelo Whisper en formato .bin.')
            except ValueError as error:
                messagebox.showerror('Revisa la configuración', str(error), parent=window)
                return
            language_code = LANGUAGES[language.get()]
            audio_profile = profile.get()
            use_word_times = sync_words.get()
            window.destroy()
            self.begin_task('Transcribiendo audio', self.transcription_worker,
                            (source, self.model, language_code, begin, end, audio_profile, use_word_times), indeterminate=True)

        ttk.Label(pane, textvariable=model_name, style='Muted.TLabel').grid(row=5, column=0, columnspan=2, sticky='w', pady=(8, 3))
        ttk.Button(pane, text='Elegir modelo…', command=choose_model).grid(row=6, column=0, sticky='w')
        ttk.Label(pane, text='Con marcas por palabra, los perfiles automáticos usan la mezcla original. Desmarca la opción para usar la comparación por verso.',
                  style='Muted.TLabel', wraplength=390).grid(row=7, column=0, columnspan=2, sticky='w', pady=(10, 8))
        ttk.Checkbutton(pane, text='Sincronizar palabras y crear escenas automáticamente',
                        variable=sync_words).grid(row=8, column=0, columnspan=2, sticky='w', pady=(0, 8))
        ttk.Button(pane, text='Detectar letra y tiempos', command=run, style='Export.TButton').grid(row=9, column=1, sticky='e')

    def transcription_worker(self, source, model, language, begin, end, profile, sync_words=False):
        try:
            chunks = None
            if sync_words:
                selected = 'Mezcla original' if profile in AUTO_PROFILES else profile
                self.events.put(('stage', 'Detectando voz y entradas por palabra'))
                chunks = transcribe_song(source, model, language, begin, end, selected,
                                         self.cancel_task, queue_seconds=30, word_chunks=True)
                result = Transcript(format_transcript(chunks), selected,
                                    ('Escucha y corrige la letra antes de crear las escenas.',))
            else:
                result = transcribe_project(source, model, language, begin, end, profile, self.cancel_task,
                                            lambda label: self.events.put(('stage', label)))
            self.events.put(('lyrics', (source, begin, end, result, chunks)))
        except InterruptedError as error:
            self.events.put(('cancel', str(error)))
        except (ValueError, OSError, subprocess.TimeoutExpired) as error:
            self.events.put(('error', str(error)))

    def review_transcription(self, source, source_start, source_end, result, chunks=None):
        lines = result.lines.copy()
        window = tk.Toplevel(self.root, bg=BG)
        window.title('Revisar letra transcrita')
        window.transient(self.root)
        window.grab_set()
        pane = ttk.Frame(window, padding=16)
        pane.pack(fill='both', expand=True)
        ttk.Label(pane, text='Revisa cada marca con el audio y corrige la letra, un verso por línea.').pack(anchor='w')
        ttk.Label(pane, text=f'{len(lines)} versos · «{result.profile}» · primera entrada en {source_start + lines[0].start:.2f} s',
                  style='Muted.TLabel').pack(anchor='w', pady=(4, 0))
        for note in result.notes:
            ttk.Label(pane, text=note, wraplength=665, style='Muted.TLabel').pack(anchor='w', pady=(4, 0))
        review = ttk.Frame(pane)
        review.pack(fill='both', expand=True, pady=8)
        timing_panel = ttk.Frame(review)
        timing_panel.pack(side='left', fill='y', padx=(0, 10))
        marks = ttk.Treeview(timing_panel, columns=('numero', 'inicio'), show='headings', selectmode='browse', height=11)
        marks.heading('numero', text='Verso')
        marks.heading('inicio', text='Inicio (s)')
        marks.column('numero', width=48, anchor='center', stretch=False)
        marks.column('inicio', width=79, anchor='center', stretch=False)
        for i, line in enumerate(lines):
            marks.insert('', 'end', iid=str(i), values=(i + 1, f'{source_start + line.start:.2f}'))
        marks.selection_set('0')
        mark_scroll = ttk.Scrollbar(timing_panel, orient='vertical', command=marks.yview)
        marks.configure(yscrollcommand=mark_scroll.set)
        marks.grid(row=0, column=0, sticky='ns')
        mark_scroll.grid(row=0, column=1, sticky='ns')
        box = ScrolledText(review, width=57, height=14, wrap='word', bg=FIELD, fg=TEXT,
                           insertbackground=TEXT, font=(UI_FONT, 11), relief='flat', padx=7, pady=7)
        box.insert('1.0', '\n'.join(line.text for line in lines))
        box.pack(side='left', fill='both', expand=True)
        mark_value = tk.StringVar(value=f'{source_start + lines[0].start:.2f}')

        def select_mark(_=None):
            if marks.selection():
                number = int(marks.selection()[0])
                box.see(f'{number + 1}.0')
                mark_value.set(f'{source_start + lines[number].start:.2f}')

        def edit_mark():
            if not marks.selection():
                return
            number = int(marks.selection()[0])
            try:
                stamp = optional_seconds(mark_value.get()) - source_start
                left = lines[number - 1].start + MIN_LINE if number else 0
                right = lines[number + 1].start - MIN_LINE if number + 1 < len(lines) else lines[-1].end - MIN_LINE
                if not left - 1e-7 <= stamp <= right + 1e-7:
                    raise ValueError('Conserva el orden y deja al menos 0,7 s entre versos.')
                line = lines[number]
                lines[number] = Line(round(max(0, stamp), 3), line.end, line.text)
                marks.item(str(number), values=(number + 1, f'{source_start + lines[number].start:.2f}'))
            except ValueError as error:
                messagebox.showerror('Ajustar entrada', str(error), parent=window)

        marks.bind('<<TreeviewSelect>>', select_mark)
        ttk.Entry(timing_panel, textvariable=mark_value, width=11).grid(row=1, column=0, columnspan=2, sticky='ew', pady=(6, 3))
        ttk.Button(timing_panel, text='Ajustar entrada', command=edit_mark).grid(row=2, column=0, columnspan=2, sticky='ew')
        replace_title = tk.BooleanVar(value=True)
        ttk.Checkbutton(pane, text='Usar el nombre del audio como título', variable=replace_title).pack(anchor='w')
        ttk.Label(pane, text='Si cambia la cantidad de versos, se estiman nuevos tiempos para ese tramo.',
                  style='Muted.TLabel', wraplength=430).pack(anchor='w', pady=(5, 10))

        def apply():
            if self.apply_transcription(source, source_start, source_end, lines, box.get('1.0', 'end-1c'), replace_title.get(), chunks):
                window.destroy()

        def listen():
            if not marks.selection():
                return
            line = lines[int(marks.selection()[0])]
            start = max(source_start, source_start + line.start - .20)
            stop = source_start + line.end + .25
            if source_end is not None:
                stop = min(source_end, stop)
            try:
                self.listen_audio(source, start, stop, audio_mix.DEFAULT_MIX)
            except (OSError, ValueError) as error:
                messagebox.showerror('Escuchar verso', str(error), parent=window)

        ttk.Button(pane, text='Escuchar verso', command=listen).pack(side='left')
        ttk.Button(pane, text='Crear escenas automáticamente', command=apply, style='Export.TButton').pack(side='right')
        ttk.Button(pane, text='Cancelar', command=window.destroy).pack(side='right', padx=(0, 8))

    def apply_transcription(self, source, source_start, source_end, lines, text, replace_title, chunks=None):
        count = sum(bool(line.strip()) for line in text.splitlines())
        if not count:
            return False
        first, durations, shown = subtitle_timings(lines, count)
        if replace_title or not any(var.get().strip() for var in self.title_vars):
            for var, title in zip(self.title_vars, title_lines(source.name)):
                var.set(title)
        self.project.update(audio_local=str(source), inicio_audio=round(source_start, 3),
                            fin_audio=source_end, introduccion=first)
        self.update_audio()
        self.replace_lyrics(text, timings=durations, captions=shown)
        synced = 0
        if chunks and count == len(lines):
            starts = [first]
            for duration in durations:
                starts.append(starts[-1] + duration)
            original = [('', line.text, span, visible) for line, span, visible in zip(lines, durations, shown)]
            marks = iter(align_words(original, starts, chunks))
            for index, scene in enumerate(self.project['escenas']):
                scene_marks = []
                for row in scene['versos']:
                    times = next(marks)
                    if len(times) != len(row[1].split()):
                        times = []
                    scene_marks.append(times)
                synced += sum(map(bool, scene_marks))
                scene['estilo'] = render.scene_style(index, (scene.get('estilo') or {}) | {'marcas_palabras': scene_marks})
        self.status.set(f'{len(self.project["escenas"])} escenas creadas · {synced}/{count} versos con marcas por palabra.'
                        if chunks else 'Letra y tiempos cargados. Revisa el resultado en «Reel con audio».')
        return True

    def suggestions_dialog(self):
        self.commit()
        scene = self.project['escenas'][self.scene]
        (palette_name, palette), tips = recommend_scene(scene, self.project['segundos_por_verso'])
        window = tk.Toplevel(self.root, bg=BG)
        window.title('Sugerencias para la escena')
        window.transient(self.root)
        window.grab_set()
        pane = ttk.Frame(window, padding=16)
        pane.pack(fill='both', expand=True)
        ttk.Label(pane, text=f'{palette_name} · figura de {palette["forma"].lower()}', font=(UI_FONT, 11, 'bold')).pack(anchor='w')
        chips = ttk.Frame(pane)
        chips.pack(anchor='w', pady=7)
        for name in ('acento', 'fondo'):
            tk.Label(chips, text='  ' + palette[name] + '  ', bg=palette[name], fg='#191821' if name == 'acento' else TEXT).pack(side='left', padx=(0, 5))
        for tip in tips:
            ttk.Label(pane, text=tip, style='Muted.TLabel', wraplength=370).pack(anchor='w', pady=(0, 5))

        def use_style():
            self.change_style(**palette)
            window.destroy()

        ttk.Button(pane, text='Aplicar estilo', command=use_style, style='Export.TButton').pack(side='right', pady=(7, 0))

        def fill_code():
            self.complete_code()
            window.destroy()

        ttk.Button(pane, text='Completar código', command=fill_code).pack(side='left', padx=(0, 8), pady=(7, 0))

    def complete_code(self):
        count = 0
        for code, lyric, _, _ in self.rows:
            verse = lyric.get().strip()
            if verse and not code.get().strip():
                code.set(suggest_code(verse))
                count += 1
        self.status.set(f'Código sugerido en {count} verso(s)' if count else 'Todos los versos de la escena ya tienen código')

    def update_background(self):
        media = self.project['escenas'][self.scene].get('fondo_media')
        if media:
            self.background_var.set(f'{Path(media["archivo"]).name} · {media["movimiento"]}')
        else:
            self.background_var.set('Fondo generado por el editor')

    def set_background(self, data):
        scene = self.project['escenas'][self.scene]
        if data is None:
            scene.pop('fondo_media', None)
        else:
            scene['fondo_media'] = media_settings(data, ROOT)
        self.dirty = True
        self.update_background()
        self.schedule_preview()

    def edit_background(self):
        existing = self.project['escenas'][self.scene].get('fondo_media') or {}
        video_or_image = dict(existing)
        window = tk.Toplevel(self.root, bg=BG)
        window.title('Fondo multimedia')
        window.transient(self.root)
        window.grab_set()
        pane = ttk.Frame(window, padding=18)
        pane.pack(fill='both', expand=True)
        filename = tk.StringVar(value=Path(existing['archivo']).name if existing else 'Selecciona un archivo local')
        movement = tk.StringVar(value=existing.get('movimiento', 'Fijo'))
        veil = tk.IntVar(value=existing.get('velo', 55))
        storm = tk.BooleanVar(value=self.current_style()['tormenta'])
        sensitivity = tk.StringVar(value=self.current_style()['sensibilidad_graves'])
        reactive_light = tk.BooleanVar(value=self.current_style()['luz_al_audio'])
        video_start = tk.StringVar(value=str(existing.get('inicio', 0)))

        def choose(kind, types):
            selected = filedialog.askopenfilename(parent=window, filetypes=types)
            if selected:
                video_or_image.update(tipo=kind, archivo=selected)
                video_start.set('0')
                filename.set(Path(selected).name)
                apply_button.state(['!disabled'])

        def apply():
            try:
                self.set_background({**video_or_image, 'movimiento': movement.get(), 'velo': veil.get(), 'inicio': video_start.get()})
            except ValueError as error:
                messagebox.showerror('Fondo multimedia', str(error), parent=window)
                return
            self.change_style(tormenta=storm.get(), luz_al_audio=reactive_light.get(),
                                  sensibilidad_graves=sensitivity.get())
            window.destroy()

        def clear():
            self.set_background(None)
            window.destroy()

        ttk.Label(pane, textvariable=filename, wraplength=370).grid(row=0, column=0, columnspan=3, sticky='w')
        ttk.Button(pane, text='Abrir imagen', command=lambda: choose('Imagen', IMAGE_TYPES)).grid(row=1, column=0, sticky='w', pady=9)
        ttk.Button(pane, text='Abrir video', command=lambda: choose('Video', VIDEO_TYPES)).grid(row=1, column=1, sticky='w', padx=(7, 0))
        ttk.Label(pane, text='Movimiento').grid(row=2, column=0, sticky='w', pady=(7, 0))
        ttk.Combobox(pane, textvariable=movement, values=MOTIONS, state='readonly', width=23).grid(row=3, column=0, columnspan=2, sticky='w')
        ttk.Label(pane, text='Inicio del video (s)').grid(row=2, column=2, sticky='w', padx=(8, 0))
        ttk.Entry(pane, textvariable=video_start, width=11).grid(row=3, column=2, sticky='w', padx=(8, 0))
        ttk.Label(pane, text='Velo de color · 0 muestra el archivo completo').grid(row=4, column=0, columnspan=3, sticky='w', pady=(10, 2))
        tk.Scale(pane, from_=0, to=100, variable=veil, orient='horizontal', length=345, bg=BG,
                 fg=TEXT, troughcolor=FIELD, highlightthickness=0).grid(row=5, column=0, columnspan=3, sticky='ew')
        ttk.Label(pane, text='El video de fondo se repite y su audio queda silenciado.', style='Muted.TLabel').grid(
            row=6, column=0, columnspan=3, sticky='w', pady=(4, 11))
        ttk.Checkbutton(pane, text='Destellos al ritmo del audio', variable=reactive_light).grid(
            row=7, column=0, columnspan=3, sticky='w', pady=(0, 8))
        ttk.Label(pane, text='Sensibilidad a los graves').grid(row=8, column=0, sticky='w')
        ttk.Combobox(pane, textvariable=sensitivity, values=('Baja', 'Media', 'Alta'), state='readonly',
                     width=10).grid(row=8, column=1, sticky='w', pady=(0, 10))
        ttk.Checkbutton(pane, text='Lluvia y partículas animadas', variable=storm).grid(
            row=9, column=0, columnspan=3, sticky='w', pady=(0, 8))
        ttk.Button(pane, text='Quitar archivo', command=clear, state='normal' if existing else 'disabled').grid(row=10, column=0, sticky='w')
        ttk.Button(pane, text='Cancelar', command=window.destroy).grid(row=10, column=1, sticky='e', padx=7)
        apply_button = ttk.Button(pane, text='Aplicar', command=apply, style='Export.TButton',
                                  state='normal' if existing else 'disabled')
        apply_button.grid(row=10, column=2, sticky='e')

    def open_tool_gallery(self, initial=0, parent=None):
        def show_lyrics(tab):
            self.workspace.select(0)
            self.lyric_tools.select(tab)
            self.switch_mode()

        def show_ascii():
            self.workspace.select(1)
            self.switch_mode()

        def show_motion():
            show_ascii()
            self.ascii_controls.sections.select(self.ascii_controls.motion_tab)

        def listen_sample(mixed):
            track = Path(self.previews.name) / 'Muestra de mezcla.wav'
            if not track.is_file():
                time = render.np.arange(4 * 48000) / 48000
                render.write_wave(track, ascii_art.ambient(time + 1.6, 8), 48000)
            mix = dict(ganancia=-8, entrada=1, salida=1) if mixed else {}
            try:
                self.listen_audio(track, 0, 4, audio_mix.DEFAULT_MIX | mix)
            except (ValueError, OSError) as error:
                messagebox.showerror('Demostración de mezcla', str(error), parent=self.root)

        actions = {
            'guion': lambda: show_lyrics(0), 'audio': lambda: (show_lyrics(1), self.transcription_dialog()),
            'palabras': self.edit_word_times, 'linea': self.open_timeline, 'diseno': self.open_design_library,
            'fondo': self.edit_background, 'efectos': self.scene_effects, 'ascii': show_ascii, 'animar': show_motion,
            'mezcla': lambda: self.open_mix(self.project['modo']), 'exportar': self.choose_export_fps,
        } if parent is None else {}
        asset_root = Path(os.sys.executable).resolve().parent if getattr(os.sys, 'frozen', False) else ROOT
        ToolGallery(parent or self.root, actions, asset_root / 'Aurora - Fuente.mp4', initial, listen_sample)

    def scene_effects(self):
        self.commit()
        window = tk.Toplevel(self.root, bg=BG)
        window.title('Efectos, título y firma')
        window.transient(self.root)
        window.grab_set()
        pane = ttk.Frame(window, padding=16)
        pane.pack(fill='both', expand=True)
        original = self.current_style()
        toggles = {
            'composicion_alta': 'Composición alta para dejar visible el fondo',
            'gerberas': 'Gerberas en movimiento', 'cierre_gerbera': 'Gerbera final',
            'tormenta': 'Lluvia y partículas de tormenta', 'atardecer_animado': 'Reflejos de atardecer',
            'luces_atardecer': 'Luciérnagas', 'hojas_primer_plano': 'Hojas animadas',
            'luz_al_audio': 'Destellos al ritmo del audio', 'titulo_animado': 'Título animado',
            'mostrar_marca': 'Mostrar firma',
        }
        vars = {}
        for row, (key, label) in enumerate(toggles.items()):
            value = render.animated_title(original) if key == 'titulo_animado' else original[key]
            vars[key] = tk.BooleanVar(window, value=value)
            ttk.Checkbutton(pane, text=label, variable=vars[key]).grid(row=row, column=0, columnspan=2, sticky='w')
        fields = (
            ('intensidad_efectos', 'Intensidad de efectos (%)', ()),
            ('sensibilidad_graves', 'Sensibilidad de graves', ('Baja', 'Media', 'Alta')),
            ('frecuencia_hojas', 'Frecuencia de hojas', ('Ocasional', 'Normal', 'Frecuente')),
            ('hojas_delante', 'Capa de hojas', ('Primer plano', 'Detrás del texto')),
            ('marca_agua', 'Texto de la firma', ()),
            ('posicion_marca', 'Posición de firma', ('Inferior derecha', 'Inferior izquierda', 'Superior derecha', 'Superior izquierda')),
            ('tamano_marca', 'Tamaño de firma', ()),
        )
        def fill(style):
            for key, var in vars.items():
                value = style[key]
                if key == 'hojas_delante':
                    value = 'Primer plano' if value else 'Detrás del texto'
                if key == 'titulo_animado':
                    value = render.animated_title(style)
                var.set(value)

        for row, (key, label, options) in enumerate(fields, len(toggles)):
            vars[key] = tk.StringVar(window)
            ttk.Label(pane, text=label).grid(row=row, column=0, sticky='w', pady=2)
            field = ttk.Combobox(pane, textvariable=vars[key], values=options, state='readonly') if options else ttk.Entry(pane, textvariable=vars[key])
            field.grid(row=row, column=1, sticky='ew', padx=(8, 0), pady=2)
        fill(original if original['marca_agua'] else original | {'marca_agua': '\U0001d50f\U0001d508\U0001d510\u212d', 'mostrar_marca': False})
        presets = {
            'Atardecer pixelado': dict(tormenta=False, atardecer_animado=True, luces_atardecer=True,
                                      hojas_primer_plano=True, luz_al_audio=True, sensibilidad_graves='Baja', titulo_animado=True),
            'Tormenta nocturna': dict(tormenta=True, atardecer_animado=False, hojas_primer_plano=False,
                                     luz_al_audio=True, sensibilidad_graves='Baja', titulo_animado=False),
        }
        preset = tk.StringVar(window)
        row = len(toggles) + len(fields)
        chooser = ttk.Combobox(pane, textvariable=preset, values=tuple(presets), state='readonly')
        chooser.grid(row=row, column=0, sticky='ew', pady=(9, 4))
        ttk.Button(pane, text='Cargar plantilla…', command=lambda: load_template()).grid(row=row, column=1, sticky='e')
        chooser.bind('<<ComboboxSelected>>', lambda _: fill(collect() | presets[preset.get()]))

        def collect():
            result = {key: var.get() for key, var in vars.items()}
            result['hojas_delante'] = result['hojas_delante'] == 'Primer plano'
            result['marca_agua'] = result['marca_agua'].strip()
            for key, low, high in (('intensidad_efectos', 0, 100), ('tamano_marca', 12, 60)):
                value = int(result[key])
                if not low <= value <= high:
                    raise ValueError(f'Usa un valor entre {low} y {high} para {key}.')
                result[key] = value
            if len(result['marca_agua']) > 32:
                raise ValueError('La firma admite hasta 32 caracteres.')
            return result

        def load_template():
            target = filedialog.askopenfilename(parent=window, filetypes=PROJECT_TYPES)
            if not target:
                return
            try:
                data = json.loads(Path(target).read_text(encoding='utf-8-sig'))
                style = render.scene_style(self.scene, original | data)
                fill(style)
            except (ValueError, OSError, TypeError) as error:
                messagebox.showerror('Plantilla', str(error), parent=window)

        def save_template():
            try:
                data = collect()
                target = filedialog.asksaveasfilename(parent=window, defaultextension='.json', filetypes=PROJECT_TYPES)
                if target:
                    Path(target).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')
            except (ValueError, OSError) as error:
                messagebox.showerror('Plantilla', str(error), parent=window)

        def apply():
            try:
                changes = collect()
                if all_scenes.get():
                    for i, scene in enumerate(self.project['escenas']):
                        scene['estilo'] = render.scene_style(i, (scene.get('estilo') or {}) | changes)
                    self.appearance_changed()
                else:
                    self.change_style(**changes)
            except ValueError as error:
                messagebox.showerror('Efectos', str(error), parent=window)
                return
            window.destroy()

        all_scenes = tk.BooleanVar(window)
        ttk.Checkbutton(pane, text='Aplicar a todas las escenas', variable=all_scenes).grid(row=row + 1, column=0, sticky='w')
        ttk.Button(pane, text='Ver ejemplos…', command=lambda: self.open_tool_gallery(6, window)).grid(
            row=row + 1, column=1, sticky='e')
        ttk.Button(pane, text='Guardar plantilla…', command=save_template).grid(row=row + 2, column=0, sticky='w')
        ttk.Button(pane, text='Aplicar', command=apply, style='Export.TButton').grid(row=row + 2, column=1, sticky='e')

    def edit_word_times(self, detected=None):
        self.commit()
        try:
            project = project_for_export(self.project)
            scene_index = sum(any(row[1] for row in sc['versos']) for sc in self.project['escenas'][:self.scene])
            if project['modo'] != 'letra' or not any(row[1] for row in self.project['escenas'][self.scene]['versos']):
                raise ValueError('Agrega versos a la escena en Letra y código.')
            scene = project['escenas'][scene_index]
            before = project['introduccion'] + sum(row[2] for sc in project['escenas'][:scene_index] for row in sc['versos'])
        except (ValueError, KeyError, IndexError) as error:
            messagebox.showerror('Tiempos por palabra', str(error), parent=self.root)
            return
        recording = Path(project['audio_local']) if project['audio_local'] else None
        source_start = project['inicio_audio'] + before
        starts = [0]
        for row in scene['versos']:
            starts.append(starts[-1] + row[2])
        window = tk.Toplevel(self.root, bg=BG)
        window.title('Tiempos por palabra')
        window.transient(self.root)
        window.grab_set()
        pane = ttk.Frame(window, padding=16)
        pane.pack(fill='both', expand=True)
        ttk.Label(pane, text='Una marca en segundos por palabra, relativa al inicio del verso. Separa las marcas con espacios.',
                  wraplength=600).pack(anchor='w', pady=(0, 8))
        current = scene['estilo'].get('marcas_palabras', [])
        controls = []

        def listen(index):
            start = source_start + starts[index]
            end = min(source_start + starts[index + 1], project['fin_audio'] or float('inf'))
            if end <= start:
                return
            try:
                self.listen_audio(recording, start, end, audio_mix.DEFAULT_MIX)
            except (OSError, ValueError) as error:
                messagebox.showerror('Escuchar verso', str(error), parent=window)

        for index, (_, lyric, span, shown) in enumerate(scene['versos']):
            ttk.Label(pane, text=lyric, wraplength=600).pack(anchor='w', pady=(5, 0))
            row = ttk.Frame(pane)
            row.pack(fill='x')
            marks = detected[index] if detected and detected[index] else (current[index] if index < len(current) else [])
            var = tk.StringVar(window, value=' '.join(f'{t:.3f}' for t in marks))
            controls.append(var)
            ttk.Entry(row, textvariable=var, width=65).pack(side='left', fill='x', expand=True)
            if recording:
                ttk.Button(row, text='Escuchar', command=lambda i=index: listen(i)).pack(side='right', padx=(7, 0))

        if detected is not None:
            count = sum(bool(row) for row in detected)
            ttk.Label(pane, text=f'{count} de {len(controls)} versos alineados. Revisa las marcas antes de guardar.').pack(anchor='w', pady=6)

        def apply(preview=False):
            try:
                marks = []
                for field, (_, lyric, span, shown) in zip(controls, scene['versos']):
                    times = [optional_seconds(raw) for raw in field.get().split()]
                    if times and (len(times) != len(lyric.split()) or times != sorted(times)
                                  or times[-1] >= (shown if shown is not None else span)):
                        raise ValueError('Usa una marca ordenada por palabra dentro de la duración visible del verso.')
                    marks.append(times)
            except ValueError as error:
                messagebox.showerror('Tiempos por palabra', str(error), parent=window)
                return
            self.change_style(marcas_palabras=marks)
            window.destroy()
            if preview:
                self.preview_reel()

        def detect():
            model = model_in(ROOT)
            if not model:
                messagebox.showerror('Tiempos por palabra', 'No se encontró el modelo Whisper local.', parent=window)
                return
            stop = min(source_start + starts[-1], project['fin_audio'] or float('inf'))
            if stop <= source_start:
                messagebox.showerror('Tiempos por palabra', 'La escena empieza fuera del recorte de audio.', parent=window)
                return
            window.destroy()
            self.begin_task('Detectando palabras', self.detect_word_worker,
                            (recording, model, source_start, stop, scene['versos'], starts, self.project, self.scene),
                            indeterminate=True)

        bar = ttk.Frame(pane)
        bar.pack(fill='x', pady=(12, 0))
        ttk.Button(pane, text='Ver ejemplo…', command=lambda: self.open_tool_gallery(2, window)).pack(anchor='w', pady=(8, 0))
        ttk.Button(bar, text='Detectar desde el audio', command=detect, state='normal' if recording else 'disabled').pack(side='left')
        ttk.Button(bar, text='Guardar y ver con audio', command=lambda: apply(True)).pack(side='right')
        ttk.Button(bar, text='Guardar marcas', command=apply).pack(side='right', padx=6)

    def detect_word_worker(self, recording, model, start, stop, rows, starts, project, scene):
        try:
            chunks = transcribe_song(recording, model, 'auto', start, stop, 'Mezcla original',
                                     self.cancel_task, word_chunks=True)
            marks = align_words(rows, starts, chunks)
            self.events.put(('word_times', (project, scene, marks)))
        except InterruptedError as error:
            self.events.put(('cancel', str(error)))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.events.put(('error', str(error)))

    def current_style(self):
        return render.scene_style(self.scene, self.project['escenas'][self.scene].get('estilo'))

    def update_style(self):
        style = self.current_style()
        self.shape_var.set(style['forma'])
        self.code_theme_var.set(style['tema_codigo'])
        for key, swatch in self.swatches.items():
            color = style[key]
            rgb = tuple(tone // 257 for tone in self.root.winfo_rgb(color))
            ink = '#{:02x}{:02x}{:02x}'.format(*render.contrast_text(rgb))
            swatch.configure(text=color, bg=color, fg=ink, activebackground=color, activeforeground=ink)

    def choose_color(self, key):
        title = 'Color del acento' if key == 'acento' else 'Color del fondo'
        _, color = colorchooser.askcolor(color=self.current_style()[key], title=title, parent=self.root)
        if color:
            self.change_style(**{key: color})

    def change_style(self, **changes):
        scene = self.project['escenas'][self.scene]
        scene['estilo'] = render.scene_style(self.scene, self.current_style() | changes)
        self.appearance_changed()

    def apply_style_to_all(self):
        style = self.current_style()
        style.pop('marcas_palabras', None)
        for scene in self.project['escenas']:
            marks = (scene.get('estilo') or {}).get('marcas_palabras', [])
            scene['estilo'] = style | {'marcas_palabras': marks}
        self.appearance_changed()
        self.status.set('Apariencia aplicada a todas las escenas')

    def restore_style(self):
        self.project['escenas'][self.scene].pop('estilo', None)
        self.appearance_changed()

    def appearance_changed(self):
        self.dirty = True
        self.update_style()
        self.schedule_preview()

    def choose_audio(self):
        target = filedialog.askopenfilename(parent=self.root, filetypes=AUDIO_TYPES)
        if target and target != self.project['audio_local']:
            self.project.update(audio_local=target, inicio_audio=0.0, fin_audio=None)
            self.dirty = True
            self.update_audio()

    def open_mix(self, mode):
        if mode == 'ascii':
            mix = self.ascii_controls.mix
        else:
            mix = self.project['mezcla_audio']

        def apply(options):
            if mode == 'ascii':
                self.ascii_controls.mix = options
            else:
                self.project['mezcla_audio'] = options
            self.dirty = True
            self.status.set('Mezcla de audio aplicada')

        def listen(options):
            if mode == 'ascii':
                settings = self.ascii_controls.settings()
                track = ascii_art.audio_path(settings)
                start, end = settings['inicio'], settings['fin']
            else:
                track = Path(self.project['audio_local']) if self.project['audio_local'] else None
                start, end = self.project['inicio_audio'], self.project['fin_audio']
            self.listen_audio(track, start, end, options)

        edit_mix(self.root, mix, apply, listen)

    def listen_audio(self, track, start, end, options):
        if track is None or not track.is_file():
            raise ValueError('Elige una pista local para escuchar la prueba, o usa «Reel con audio» para el ambiente.')
        self.preview_count += 1
        target = Path(self.previews.name) / f'Audio {self.preview_count}.wav'
        seconds = min(12, end - start) if end is not None else 12
        if seconds <= 0:
            raise ValueError('El fragmento de escucha está vacío.')
        try:
            audio_mix.listening_clip(track, target, start, seconds, options)
        except subprocess.TimeoutExpired as error:
            raise ValueError('El archivo tardó demasiado al preparar la escucha.') from error
        self.play_file(target)

    def clear_audio(self):
        if self.project['audio_local']:
            self.project.update(audio_local='', inicio_audio=0.0, fin_audio=None)
            self.dirty = True
            self.update_audio()

    def maybe_save(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel('Cambios pendientes', '¿Guardar el proyecto antes de continuar?', parent=self.root)
        return answer is False or (answer is True and self.save())

    def new(self):
        if self.maybe_save():
            self.project = blank_project()
            self.path = None
            self.scene = 0
            self.dirty = False
            self.show_project()
            self.status.set('Proyecto nuevo')

    def open_quick_video(self):
        target = filedialog.askopenfilename(parent=self.root, filetypes=VIDEO_TYPES, title='Video rápido')
        if not target:
            return
        try:
            project = quick_video_project(Path(target))
        except (OSError, ValueError) as error:
            messagebox.showerror('Video rápido', str(error), parent=self.root)
            return
        if self.maybe_save():
            self.project, self.path = project, None
            self.scene = 0
            self.dirty = True
            self.show_project()
            self.ascii_controls.sections.select(self.ascii_controls.video_tab)
            self.status.set('Video listo para ajustar o exportar variantes')

    def open(self, target=None):
        if not self.maybe_save():
            return
        target = target or filedialog.askopenfilename(parent=self.root, filetypes=PROJECT_TYPES)
        if not target:
            return
        try:
            project = load_project(Path(target))
        except (ValueError, OSError, TypeError, KeyError, IndexError) as error:
            messagebox.showerror('No se pudo abrir', str(error), parent=self.root)
            return
        self.project, self.path = project, Path(target)
        self.scene = 0
        self.dirty = False
        self.show_project()
        self.status.set(f'Proyecto abierto · {self.path.name}')

    def save(self):
        self.commit()
        try:
            self.project['animacion_ascii'] = self.ascii_controls.settings()
        except ValueError as error:
            messagebox.showerror('Revisa la configuración ASCII', str(error), parent=self.root)
            return False
        path = self.path
        if path is None:
            target = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json',
                                                 filetypes=PROJECT_TYPES, initialfile='Mi reel.json')
            if not target:
                return False
            path = Path(target)
        try:
            save_project(path, self.project)
        except OSError as error:
            messagebox.showerror('No se pudo guardar', str(error), parent=self.root)
            return False
        self.path = path
        self.dirty = False
        self.status.set(f'Proyecto guardado · {path.name}')
        return True

    def project_to_render(self):
        self.commit()
        try:
            if self.project['modo'] == 'ascii':
                self.project['animacion_ascii'] = self.ascii_controls.settings()
            project = project_for_export(self.project)
            find_ffmpeg()
            if project['modo'] == 'ascii':
                data = project['animacion_ascii']
                track = ascii_art.audio_path(data)
                start, end, mix = data['inicio'], data['fin'], data['mezcla']
            else:
                track = Path(project['audio_local']) if project['audio_local'] else None
                _, start, end = render.audio_timing(project)
                mix = project['mezcla_audio']
            if track:
                audio_mix.validate_track(track, start, end)
            if secondary := audio_mix.extra_path(mix):
                audio_mix.validate_track(secondary, mix['recorte_extra'])
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            messagebox.showerror('Revisa el proyecto', str(error), parent=self.root)
            return None
        return project

    def open_timeline(self):
        project = self.project_to_render()
        if project is None:
            return
        try:
            with tempfile.TemporaryDirectory() as directory:
                snapshot = Path(directory) / 'proyecto.json'
                save_project(snapshot, project)
                preview = render.TimelinePreview(snapshot)
            def listen(start, end):
                try:
                    self.listen_audio(preview.recording, start, end, audio_mix.DEFAULT_MIX)
                except (OSError, ValueError) as error:
                    messagebox.showinfo('Escuchar fragmento', str(error), parent=self.root)
            TimelineWindow(self.root, preview, listen)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            messagebox.showerror('Línea de tiempo', str(error), parent=self.root)

    def choose_export_fps(self):
        self.export_fields[2].focus_set()
        self.status.set('Elige la calidad, la resolución y los fps en el panel Exportación.')

    def export_current_png(self):
        try:
            data = self.ascii_controls.settings()
            if not (ascii_art.is_procedural(data) or ascii_art.is_ascii_world(data)):
                return
            target = filedialog.asksaveasfilename(parent=self.root, defaultextension='.png',
                                                 filetypes=[('Imagen PNG', '*.png')],
                                                 initialfile=f'{data["figura"]}.png')
            if not target:
                return
            prepared = render.prepare_ascii(data)
            frame = render.ascii_preview_frame(self.ascii_position.get() * data['duracion'], prepared)
            frame.save(target, format='PNG')
            self.status.set(f'PNG exportado · {Path(target).name}')
        except (ValueError, OSError) as error:
            messagebox.showerror('No se pudo exportar el PNG', str(error), parent=self.root)

    def export(self):
        project = self.project_to_render()
        if project is None:
            return
        title = ' '.join(part for part in project['titulo'] if part)
        if project['modo'] == 'ascii':
            animation = project['animacion_ascii']
            title = animation['mensaje'] or (Path(animation['archivo']).stem if animation['archivo'] else animation['figura'])
        title = ''.join(char for char in title if char not in '<>:"/\\|?*').strip().rstrip('.') or 'Reel'
        target = filedialog.asksaveasfilename(parent=self.root, defaultextension='.mp4',
                                             filetypes=[('Video MP4', '*.mp4')], initialfile=f'{title}.mp4')
        if target:
            self.begin_task('Exportando video', self.render_worker, (project, Path(target), False))

    def export_ascii_pair(self):
        project = self.project_to_render()
        if project is None:
            return
        animation = project['animacion_ascii']
        if project['modo'] != 'ascii' or not supports_ascii_pair(animation):
            messagebox.showinfo('Exportar ambas versiones', 'Elige un video, una imagen o un mundo ASCII en el editor.',
                                parent=self.root)
            return
        name = animation['figura'] if ascii_art.is_ascii_world(animation) else Path(animation['archivo']).stem
        target = filedialog.asksaveasfilename(parent=self.root, defaultextension='.mp4',
                                               filetypes=[('Video MP4', '*.mp4')],
                                               title='Nombre común para los videos', initialfile=f'{name}.mp4')
        if target:
            self.begin_task('Exportando variantes', self.render_ascii_pair_worker, (project, Path(target)))

    def render_ascii_pair_worker(self, project, target):
        try:
            paths = render_ascii_pair(project, target, lambda value: self.events.put(('progress', value)),
                                      self.cancel_task)
            self.events.put(('pair_done', paths))
        except InterruptedError as error:
            self.events.put(('cancel', str(error)))
        except (OSError, ValueError, TypeError, KeyError, IndexError, subprocess.SubprocessError) as error:
            self.events.put(('error', str(error)))

    def preview_reel(self):
        project = self.project_to_render()
        if project is not None:
            self.render_preview(project)

    def preview_scene(self):
        project = self.project_to_render()
        if project is None or project['modo'] != 'letra':
            return
        scenes = self.project['escenas']
        if not any(row[1] for row in scenes[self.scene]['versos']):
            messagebox.showinfo('Vista de la escena', 'Agrega un verso a esta escena.', parent=self.root)
            return
        index = sum(any(row[1] for row in scene['versos']) for scene in scenes[:self.scene])
        before = project['escenas'][:index]
        if index:
            offset = project['introduccion'] + sum(row[2] for scene in before for row in scene['versos'])
            start = project['inicio_audio'] + offset
            if project['audio_local'] and project['fin_audio'] is not None and start >= project['fin_audio']:
                messagebox.showinfo('Vista de la escena', 'El recorte de audio termina antes de esta escena. Usa «Reel con audio» para verla en contexto.', parent=self.root)
                return
            project.update(inicio_audio=start, introduccion=0)
            mix = audio_mix.normalize(project.get('mezcla_audio'))
            if mix['pista_extra']:
                shift = offset - mix['retardo_extra']
                mix['retardo_extra'] = max(0, -shift)
                mix['recorte_extra'] += max(0, shift)
                length = audio_mix.duration(Path(mix['pista_extra']))
                if length is not None and mix['recorte_extra'] >= length - .001:
                    mix['pista_extra'] = ''
                project['mezcla_audio'] = mix
        project['escenas'] = [project['escenas'][index]]
        self.render_preview(project)

    def render_preview(self, project):
        self.preview_count += 1
        target = Path(self.previews.name) / f'Vista previa {self.preview_count}.mp4'
        self.begin_task('Preparando vista con audio', self.render_worker, (project, target, True))

    def begin_task(self, label, worker, args, indeterminate=False):
        if self.operation:
            return
        self.operation = label
        self.cancel_task.clear()
        for button in self.background_task_buttons:
            button.state(['disabled'])
        self.progress.set(0)
        self.progress_bar.configure(mode='indeterminate' if indeterminate else 'determinate')
        self.progress_bar.grid()
        self.cancel_button.state(['!disabled'])
        self.cancel_button.grid()
        if indeterminate:
            self.progress_bar.start(14)
        self.status.set(f'{label}…')
        threading.Thread(target=worker, args=args, daemon=True).start()
        self.root.after(100, self.poll_task)

    def render_worker(self, project, target, preview):
        try:
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / 'reel.json'
                save_project(source, project)
                render.render(source, target.resolve(), lambda value: self.events.put(('progress', value)),
                              preview=preview, cancel=self.cancel_task)
            self.events.put(('preview' if preview else 'done', target))
        except InterruptedError as error:
            self.events.put(('cancel', str(error)))
        except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
            self.events.put(('error', str(error)))

    def cancel_operation(self):
        if self.operation:
            self.cancel_task.set()
            self.status.set('Cancelando…')
            self.cancel_button.state(['disabled'])

    def poll_task(self):
        while True:
            try:
                event, value = self.events.get_nowait()
            except queue.Empty:
                break
            if event == 'progress':
                self.progress.set(value)
                if not self.cancel_task.is_set():
                    self.status.set(f'{self.operation} · {value} %')
                continue
            if event == 'stage':
                if not self.cancel_task.is_set():
                    self.status.set(value)
                continue
            self.operation = ''
            for button in self.background_task_buttons:
                button.state(['!disabled'])
            self.progress_bar.stop()
            self.progress_bar.grid_remove()
            self.cancel_button.grid_remove()
            if event == 'done':
                self.last_export = value
                self.last_export_pair = ()
                self.open_video.configure(state='normal', text='Ver último MP4')
                self.status.set(f'Video listo · {value.name}')
            elif event == 'pair_done':
                self.last_export_pair = value
                self.last_export = value[0]
                self.open_video.configure(state='normal', text='Ver últimos MP4')
                self.status.set(f'{len(value)} MP4 listos')
            elif event == 'preview':
                self.status.set('Vista con audio lista')
                self.play_file(value)
            elif event == 'word_times':
                project, scene, marks = value
                if self.project is project and self.scene == scene:
                    self.status.set('Marcas de palabras listas para revisar')
                    self.edit_word_times(marks)
                else:
                    self.status.set('Vuelve a la escena original para detectar sus marcas')
            elif event == 'lyrics':
                self.status.set('Transcripción lista para revisar')
                self.review_transcription(*value)
            elif event == 'cancel':
                self.status.set(value)
            else:
                self.status.set('No se pudo completar la operación')
                messagebox.showerror('Editor de reels', value, parent=self.root)
        if self.operation:
            self.root.after(100, self.poll_task)

    def play_export(self):
        if not self.last_export_pair:
            self.play_file(self.last_export)
            return
        window = tk.Toplevel(self.root, bg=BG)
        window.title('Ver últimas exportaciones')
        window.transient(self.root)
        window.grab_set()
        pane = ttk.Frame(window, padding=16)
        pane.pack(fill='both', expand=True)
        for path in self.last_export_pair:
            ttk.Button(pane, text=path.name, command=lambda video=path: self.play_file(video)).pack(fill='x', pady=3)

    def play_file(self, path):
        try:
            if os.name == 'nt':
                os.startfile(path)
            else:
                subprocess.Popen(['xdg-open', str(path)], **PROCESS_OPTIONS)
        except OSError as error:
            messagebox.showerror('No se pudo abrir el video', str(error), parent=self.root)

    def close(self):
        if self.operation:
            messagebox.showinfo('Operación en curso', 'Espera a que termine antes de cerrar el editor.', parent=self.root)
        elif self.maybe_save():
            self.previews.cleanup()
            self.root.destroy()


def export_command(arguments):
    parser = argparse.ArgumentParser(description='Exporta con LEMC Studio sin abrir la ventana.')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--video', type=Path)
    source.add_argument('--proyecto', type=Path)
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--variantes', choices=('una', 'dos', 'tres'))
    parser.add_argument('--duracion', type=float)
    parser.add_argument('--cambio-original', type=float)
    parser.add_argument('--fundido', type=float)
    rotations = dict(zip(('auto', 'izquierda', 'derecha', '180'), VIDEO_ROTATIONS))
    parser.add_argument('--giro', choices=rotations)
    parser.add_argument('--repetir', action='store_true')
    parser.add_argument('--informe', type=Path)
    args = parser.parse_args(arguments)
    report_path = None
    try:
        target = args.salida.resolve()
        if target.suffix.lower() != '.mp4':
            raise ValueError('La salida debe terminar en .mp4.')
        saved = target.with_name(f'{target.stem} - Proyecto ASCII.json') if args.video else None
        protected = {path.resolve() for path in (args.video, args.proyecto, target, saved) if path is not None}
        if args.informe:
            candidate = args.informe.resolve()
            if candidate.suffix.lower() != '.json' or candidate in protected or candidate.exists():
                raise ValueError('El informe necesita una ruta .json nueva y distinta del proyecto.')
            report_path = candidate
        project = quick_video_project(args.video) if args.video else load_project(args.proyecto)
        target.parent.mkdir(parents=True, exist_ok=True)
        animation = project['animacion_ascii']
        if project['modo'] == 'ascii':
            for key, value in (('duracion', args.duracion), ('fin_ascii', args.cambio_original),
                               ('fundido_video', args.fundido), ('giro_video', rotations.get(args.giro))):
                if value is not None:
                    animation[key] = value
            if args.repetir:
                animation['bucle'] = True
                animation['repetir_audio'] = animation['sonido'] in ('Archivo de audio', 'Audio del video')
            if args.variantes:
                animation['prueba_reescalada'] = args.variantes == 'tres'
        elif any(value is not None for value in (args.duracion, args.cambio_original, args.fundido, args.giro)) or args.repetir:
            raise ValueError('Estos ajustes requieren un proyecto ASCII.')
        variant_count = args.variantes
        if variant_count is None:
            variant_count = 'dos' if project['modo'] == 'ascii' and supports_ascii_pair(animation) else 'una'
        project = project_for_export(project)
        if saved and saved.exists():
            raise FileExistsError(f'Elige otro nombre de salida. Ya existe «{saved.name}».')
        if variant_count == 'una':
            if target.exists():
                raise FileExistsError(f'Ya existe «{target.name}».')
            with tempfile.TemporaryDirectory(dir=target.parent) as directory:
                snapshot = Path(directory) / 'proyecto.json'
                save_project(snapshot, project)
                render.render(snapshot, target)
            outputs = (target,)
        else:
            outputs = render_ascii_pair(project, target, solo_fit=animation['ajuste'])
        if saved:
            save_project(saved, project)
        report = {'ok': True, 'videos': [str(path) for path in outputs], 'proyecto': str(saved) if saved else None}
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        report = {'ok': False, 'error': str(error)}
    result = json.dumps(report, ensure_ascii=False, indent=2)
    if report_path:
        try:
            with report_path.open('x', encoding='utf-8') as stream:
                stream.write(result + '\n')
        except OSError as error:
            if sys.stderr is not None:
                print(f'No se pudo guardar el informe. {error}', file=sys.stderr)
            if report['ok']:
                return 1
    if sys.stdout is not None:
        print(result)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--mover-fondo':
        movimiento_fondo.command(sys.argv[2:])
        raise SystemExit(0)
    if len(sys.argv) > 1 and sys.argv[1] == '--exportar':
        raise SystemExit(export_command(sys.argv[2:]))
    root = tk.Tk()
    app = Editor(root)
    if len(sys.argv) == 2:
        app.open(sys.argv[1])
    root.mainloop()
