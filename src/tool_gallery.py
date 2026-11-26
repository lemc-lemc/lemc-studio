import subprocess
import tkinter as tk
from functools import lru_cache
from pathlib import Path
from time import monotonic
from tkinter import ttk

from PIL import Image, ImageDraw, ImageOps, ImageTk

import ascii_art
import render
from media import PROCESS_OPTIONS, find_ffmpeg
from studio_ui import modal


# Each demonstration uses a scratch scene and the same drawing functions as MP4 export.
DEMOS = (
    ('Guion y escenas', 'Dos escenas de muestra. Al cambiar de verso, comienza a escribirse su línea de código.', 'guion', {}),
    ('Letra automática', 'Ejemplo del resultado tras transcribir una canción y crear escenas con marcas de palabra.', 'audio', {'marcas_palabras': [[0, .32, .76, 1.28], [0, .37, .82, 1.3]]}),
    ('Tiempos por palabra', 'Cada palabra entra en su marca. Arrastra el cursor para verlas aparecer una a una.', 'palabras', {'marcas_palabras': [[0, .32, .76, 1.28], [0, .37, .82, 1.3]]}),
    ('Línea de tiempo', 'Reproduce o arrastra el cursor para inspeccionar el cambio de verso. En un proyecto puedes escuchar el verso seleccionado.', 'linea', {}),
    ('Paletas y figuras', 'Muestra cómo cambian la figura, el color del acento y el panel de código.', 'diseno', {'forma': 'Estrella', 'fondo': '#281520', 'acento': '#ffc16c', 'tema_codigo': 'Ciruela'}),
    ('Fondo en movimiento', 'La imagen ocupa el encuadre vertical y se acerca suavemente durante la escena.', 'fondo', {}),
    ('Lluvia y partículas', 'Las gotas y motas se dibujan detrás de la letra. Compara con el fondo solo.', 'efectos', {'tormenta': True}),
    ('Reflejos y luciérnagas', 'Los reflejos se mueven sobre el paisaje y las luciérnagas brillan cerca del borde inferior.', 'efectos', {'atardecer_animado': True, 'titulo_animado': False}),
    ('Hojas de primer plano', 'La hoja gira mientras cae por delante del diseño. En Efectos puedes enviarla detrás del texto.', 'efectos', {'hojas_primer_plano': True}),
    ('Destellos al ritmo', 'El fondo se ilumina en dos golpes de muestra. En tu proyecto los golpes se detectan en el audio.', 'efectos', {'luz_al_audio': True}),
    ('Título animado', 'El nombre entra letra por letra y un brillo cálido recorre el encabezado.', 'efectos', {'titulo_animado': True}),
    ('Firma opcional', 'Una firma pequeña pulsa en la esquina. Puedes cambiar su posición, tamaño y visibilidad.', 'efectos', {'marca_agua': '\U0001d50f\U0001d508\U0001d510\u212d'}),
    ('ASCII · Figura 3D', 'Una estrella gira y se dibuja con caracteres. La ventana inferior muestra el procesamiento.', 'ascii', {'figura': 'Estrella', 'paleta': 'Aurora'}),
    ('ASCII · Imagen', 'Una foto se convierte en caracteres. Puedes elegir densidad, color y movimiento.', 'ascii', {'fuente': 'Imagen', 'movimiento_imagen': 'Balanceo'}),
    ('ASCII · Animar y extender', 'Un cohete con fondo transparente asciende y deja una estela de caracteres. Reproduce o recorre el tramo para ver el movimiento.', 'animar', {'fuente': 'Imagen', 'animacion_fuente': 'Ascenso', 'intensidad_movimiento': 82, 'estela_ascenso': True, 'solo_video': True, 'codigo': False, 'detalle_sombras': True}),
    ('ASCII · Video', 'El paisaje cambia con cada fotograma. «Antes» muestra la fuente que está convirtiendo el editor.', 'ascii', {'fuente': 'Video', 'modo_color': 'Original'}),
    ('ASCII · Mensaje', 'El texto empieza en el 20 % y queda completo en el 46 % de la animación.', 'ascii', {'figura': 'Estrella', 'mensaje': 'QUE SIGA LA LUZ', 'mensaje_desde': 20, 'mensaje_completo': 46}),
    ('Pixel art · Video', 'El movimiento original se conserva con bloques de color. Activa o quita el resultado para comparar.', 'ascii', {'fuente': 'Video', 'estilo_media': 'Pixel art', 'realzar_bordes': True}),
    ('Mezcla y audio', 'La mezcla cambia el volumen y los fundidos de la pista principal. Puedes sumar una segunda pista con su propio nivel y retardo.', 'mezcla', {}),
    ('Exportar MP4', 'El MP4 final es vertical. Puedes elegir 30 o 60 fps. La vista de esta galería es una muestra ligera.', 'exportar', {}),
)
DURATION = 6.0
SAMPLE_SIZE = (243, 432)


def rocket_sample():
    image = Image.new('RGBA', (180, 310))
    draw = ImageDraw.Draw(image)
    draw.polygon([(90, 12), (54, 66), (48, 214), (67, 254), (113, 254), (132, 214), (126, 66)],
                 fill='#e5eafa')
    draw.polygon([(90, 12), (54, 66), (126, 66)], fill='#f08463')
    draw.polygon([(90, 67), (126, 66), (132, 214), (113, 254), (90, 254)], fill='#aebee2')
    draw.ellipse((67, 97, 113, 143), fill='#294478', outline='#f3e3a6', width=6)
    draw.ellipse((76, 103, 89, 116), fill='#94eeed')
    draw.polygon([(52, 184), (22, 252), (22, 280), (61, 251)], fill='#fa866c')
    draw.polygon([(128, 184), (158, 252), (158, 280), (119, 251)], fill='#d86359')
    draw.rounded_rectangle((63, 239, 117, 272), radius=7, fill='#7c9ac6')
    draw.rectangle((72, 265, 108, 280), fill='#d8d9de')
    return image


@lru_cache(maxsize=1)
def landmark_frames(asset):
    width, height = 180, 320
    command = [find_ffmpeg(), '-nostdin', '-v', 'error', '-stream_loop', '-1', '-i', str(asset),
               '-vf', f'fps=6,scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}',
               '-t', str(DURATION), '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1']
    data = subprocess.run(command, check=True, capture_output=True, timeout=12, **PROCESS_OPTIONS).stdout
    size = width * height * 3
    frames = tuple(Image.frombytes('RGB', (width, height), data[i:i+size])
                   for i in range(0, len(data) - size + 1, size))
    if not frames:
        raise ValueError('El clip de demostración está vacío.')
    return frames


class ToolGallery:
    def __init__(self, parent, actions, asset, initial=0, listen=None):
        self.window, pane = modal(parent, 'Demostraciones de herramientas')
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.bind('<Escape>', lambda _: self.close())
        self.parent = parent
        self.actions = actions
        self.asset = Path(asset)
        self.listen = listen
        self.index = -1
        self.timer = None
        self.started = None
        self.images = ()
        self.position = tk.DoubleVar(self.window, 0)
        self.after = tk.BooleanVar(self.window, True)
        self.heading = tk.StringVar(self.window)
        self.description = tk.StringVar(self.window)
        self.time_label = tk.StringVar(self.window)
        choice = ttk.Frame(pane)
        choice.grid(row=0, column=0, sticky='ns', padx=(0, 16))
        self.tools = tk.Listbox(choice, height=21, width=25, exportselection=False,
                                bg='#211c2a', fg='#f7eaf1', selectbackground='#784659', selectforeground='#fff8ec',
                                relief='flat', highlightthickness=0, activestyle='none')
        self.tools.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(choice, orient='vertical', command=self.tools.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        self.tools.configure(yscrollcommand=scroll.set)
        for title, _, _, _ in DEMOS:
            self.tools.insert('end', title)
        self.tools.bind('<<ListboxSelect>>', self.choose)

        right = ttk.Frame(pane)
        right.grid(row=0, column=1, sticky='nsew')
        ttk.Label(right, textvariable=self.heading, style='Heading.TLabel').pack(anchor='w')
        ttk.Label(right, textvariable=self.description, wraplength=335,
                  style='Muted.TLabel').pack(anchor='w', pady=(4, 8))
        self.picture = ttk.Label(right)
        self.picture.pack()
        ttk.Scale(right, from_=0, to=DURATION - .05, variable=self.position,
                  command=self.scrub).pack(fill='x', pady=(7, 0))
        ttk.Label(right, textvariable=self.time_label).pack(anchor='w')
        controls = ttk.Frame(right)
        controls.pack(fill='x', pady=(8, 3))
        self.play_button = ttk.Button(controls, text='Reproducir', command=self.play)
        self.play_button.pack(side='left')
        ttk.Checkbutton(controls, text='Ver resultado', variable=self.after,
                        command=self.draw).pack(side='right')
        self.listen_button = ttk.Button(controls, text='Escuchar muestra',
                                        command=lambda: self.listen(self.after.get()))
        self.action = ttk.Button(right, text='Abrir herramienta', command=self.open_tool, style='Export.TButton')
        self.action.pack(anchor='e', pady=(6, 0))
        self.tools.selection_set(initial)
        self.tools.see(initial)
        self.choose()

    def frames(self):
        try:
            return landmark_frames(self.asset)
        except (OSError, ValueError, subprocess.SubprocessError):
            return ()

    def choose(self, _=None):
        selection = self.tools.curselection()
        if not selection or selection[0] == self.index:
            return
        self.pause()
        self.index = selection[0]
        title, description, feature, settings = DEMOS[self.index]
        self.heading.set(title)
        self.description.set(description)
        self.after.set(True)
        if feature == 'mezcla' and self.listen:
            self.listen_button.pack(side='left', padx=6)
        else:
            self.listen_button.pack_forget()
        self.position.set(3.3 if settings.get('hojas_primer_plano') else 1.1)
        self.images = ((rocket_sample(),) if feature == 'animar' else
                       self.frames() if feature in ('fondo', 'ascii', 'efectos') else ())
        try:
            if feature in ('ascii', 'animar'):
                data = ascii_art.config({'duracion': DURATION, 'columnas': 67, **settings})
                if data['fuente'] != 'Figura 3D' and not self.images:
                    raise ValueError('El video de demostración no está disponible.')
                self.prepared = ascii_art.prepare(data, render.font)
                if feature == 'animar':
                    sprite = ascii_art.fit_cutout(self.images[0], ascii_art.media_area(data)[2:])
                    self.prepared['cutout_sprite'] = sprite
                    self.prepared['cutout_exhaust'] = ascii_art.prepare_exhaust(sprite, data['puntos_escape'])
                quiet = data | {'mensaje': '', 'codigo': False, 'particulas': False}
                self.base = ascii_art.prepare(quiet, render.font) if data['fuente'] == 'Figura 3D' else None
            else:
                verses = [('const luz = volver();', 'La luz vuelve despacio', 2.7),
                          ('if (quedaLuz) sigo();', 'El cielo guarda algo', 2.7)]
                scenes = [('luz.js', verses, render.scene_style(0), None)]
                if feature == 'guion':
                    scenes = [('luz.js', verses[:1], render.scene_style(0), None),
                              ('cielo.js', verses[1:], render.scene_style(1), None)]
                elif feature in ('fondo', 'efectos'):
                    scenes = [('luz.js', verses, render.scene_style(0, {'forma': 'Sin figura'}), None)]
                if feature == 'efectos' and self.images:
                    scenes = [(name, rows, style, {'movimiento': 'Fijo', 'velo': 25})
                              for name, rows, style, _ in scenes]
                self.base = render.prepare(['La última', 'luz'], scenes, [3, 3], intro=0)
                sample = []
                for name, rows, style, _ in scenes:
                    media = {'movimiento': 'Acercar' if feature == 'fondo' else 'Fijo', 'velo': 25} if self.images else None
                    sample.append((name, rows, render.scene_style(0, style | settings), media))
                self.prepared = render.prepare(['La última', 'luz'], sample, [3, 3], intro=0)
                if settings.get('luz_al_audio'):
                    self.prepared['audio_peaks'] = {'Media': [(1.15, .18), (4.1, .15)]}
            self.action.state(['!disabled'] if feature in self.actions else ['disabled'])
            self.draw()
        except (OSError, ValueError) as error:
            self.prepared = None
            self.picture.configure(image='', text=str(error))
            self.action.state(['!disabled'] if feature in self.actions else ['disabled'])

    def draw(self):
        if self.index < 0 or self.prepared is None:
            return
        t = self.position.get()
        _, _, feature, settings = DEMOS[self.index]
        self.time_label.set(f'{t:.1f} / {DURATION:g} s · {"Con efecto" if self.after.get() else "Antes"}')
        if feature in ('ascii', 'animar'):
            source = None
            data = self.prepared['data']
            if data['fuente'] != 'Figura 3D':
                image = self.images[0 if data['fuente'] == 'Imagen' else min(len(self.images) - 1, int(t * 6))]
                size = ascii_art.media_area(data)[2:]
                source = ImageOps.contain(image, size, Image.Resampling.LANCZOS).convert('RGBA')
                canvas = Image.new('RGBA', size)
                canvas.alpha_composite(source, ((size[0] - source.width)//2, (size[1] - source.height)//2))
                source = canvas
                if not self.after.get():
                    self.display(image)
                    return
            prepared = self.prepared if self.after.get() else self.base
            frame = ascii_art.scene_frame(t, prepared, source)
        else:
            media = None
            if self.images:
                index = 0 if feature == 'fondo' else min(len(self.images) - 1, int(t * 6))
                media = self.images[index].resize((render.WIDTH, render.HEIGHT), Image.Resampling.LANCZOS)
            prepared = self.prepared if self.after.get() else self.base
            frame = render.frame_at(t, prepared, (0, 3), DURATION + .6, media if self.after.get() or feature == 'efectos' else None)
        if feature in ('mezcla', 'exportar'):
            draw = ImageDraw.Draw(frame)
            draw.rounded_rectangle((40, 1000, 680, 1130), 14, fill='#1d1525')
            if feature == 'mezcla':
                caption = '–8 dB · fundidos de 1 s' if self.after.get() else '0 dB · entrada y salida directas'
            else:
                caption = '1080 × 1920 · 60 fps' if self.after.get() else '540 × 960 · vista previa ligera'
            draw.text((360, 1065), caption, font=render.font('seguisb.ttf', 29), fill='#ffcb9c', anchor='mm')
        self.display(frame)

    def display(self, frame):
        self.image = ImageTk.PhotoImage(frame.resize(SAMPLE_SIZE, Image.Resampling.LANCZOS))
        self.picture.configure(image=self.image, text='')

    def scrub(self, _=None):
        self.pause()
        self.draw()

    def play(self):
        if self.started is not None:
            self.pause()
            return
        self.started = monotonic() - self.position.get()
        self.play_button.configure(text='Pausar')
        self.tick()

    def tick(self):
        self.timer = None
        self.position.set((monotonic() - self.started) % (DURATION - .05))
        self.draw()
        self.timer = self.window.after(100, self.tick)

    def pause(self):
        if self.timer is not None:
            self.window.after_cancel(self.timer)
            self.timer = None
        self.started = None
        self.play_button.configure(text='Reproducir')

    def close(self):
        self.pause()
        self.window.destroy()
        if isinstance(self.parent, tk.Toplevel) and self.parent.winfo_exists():
            self.parent.grab_set()

    def open_tool(self):
        action = self.actions.get(DEMOS[self.index][2])
        if action:
            self.close()
            action()
