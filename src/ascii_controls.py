import math
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

import ascii_art
import audio_mix
import juego_ascii
import render
from designs import CODE_THEMES
from media import FITS, VIDEO_ROTATIONS, video_duration


class AsciiControls:
    def __init__(self, parent, on_change, image_types, video_types, audio_types, on_mix, on_reveal_mark):
        self.parent = parent
        self.on_change = on_change
        self.on_mix = on_mix
        self.on_reveal_mark = on_reveal_mark
        self.types = {'Imagen': image_types, 'Video': video_types, 'Audio': audio_types}
        self.loading = False
        self.colors = {}
        self.mix = audio_mix.DEFAULT_MIX.copy()
        self.variables = {key: tk.BooleanVar(parent, value) if type(value) is bool else tk.StringVar(parent, '')
                          for key, value in ascii_art.DEFAULTS.items()}
        self.asset_label = tk.StringVar(parent)
        self.audio_label = tk.StringVar(parent)
        self.color_label = tk.StringVar(parent)
        self.build()
        for variable in self.variables.values():
            variable.trace_add('write', self.changed)
        self.set(ascii_art.DEFAULTS)

    def section(self, notebook, title):
        panel = ttk.Frame(notebook, style='Panel.TFrame', padding=(15, 11))
        notebook.add(panel, text=title)
        panel.columnconfigure(1, weight=1)
        return panel

    def field(self, panel, row, label, key, choices=None, width=23, column=0):
        ttk.Label(panel, text=label, style='PanelMuted.TLabel').grid(row=row, column=column, sticky='w', padx=(0, 9), pady=4)
        variable = self.variables[key]
        if choices:
            widget = ttk.Combobox(panel, width=width, textvariable=variable, values=choices, state='readonly')
        else:
            widget = ttk.Entry(panel, width=width, textvariable=variable)
        widget.grid(row=row, column=column + 1, sticky='ew', pady=3)
        return widget

    def toggle(self, panel, row, key, label):
        check = ttk.Checkbutton(panel, text=label, variable=self.variables[key], style='Panel.TCheckbutton')
        check.grid(row=row, column=0, columnspan=4, sticky='w', pady=3)
        return check

    def build(self):
        self.sections = sections = ttk.Notebook(self.parent, style='Settings.TNotebook')
        sections.pack(fill='both', expand=True, padx=9, pady=9)
        main = self.section(sections, 'Composición')
        self.world_tab = self.section(sections, 'Mundos ASCII')
        worlds = ascii_art.mundos_ascii
        self.world_choice = tk.StringVar(self.parent, worlds.NAMES[0])
        ttk.Label(self.world_tab, text='Escenario', style='PanelMuted.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Combobox(self.world_tab, textvariable=self.world_choice, values=worlds.NAMES,
                     state='readonly').grid(row=0, column=1, sticky='ew', pady=4)
        ttk.Button(self.world_tab, text='Cargar mundo', command=self.load_world).grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(3, 10))
        self.field(self.world_tab, 2, 'Iluminación', 'mundo_luz', worlds.LIGHTING)
        self.field(self.world_tab, 3, 'Clima', 'mundo_clima', worlds.WEATHER)
        self.field(self.world_tab, 4, 'Segundos', 'duracion')
        self.toggle(self.world_tab, 5, 'particulas', 'Lluvia, salpicaduras y partículas')
        ttk.Label(self.world_tab, text='La ruta del vigía recorre tres escenarios. Selecciona uno para reproducirlo por separado.',
                  style='PanelMuted.TLabel', wraplength=415).grid(row=6, column=0, columnspan=2, sticky='w', pady=8)
        ttk.Button(self.world_tab, text='Jugar · Campo de práctica', command=self.play_world).grid(
            row=7, column=0, columnspan=2, sticky='w', pady=(4, 9))
        main.columnconfigure(3, weight=1)
        media = self.section(sections, 'Conversión de archivos')
        sound = self.section(sections, 'Audio ASCII')
        effects = self.section(sections, 'Efectos y formato')
        effects.columnconfigure(3, weight=1)
        self.field(effects, 0, 'Nombre del panel Python', 'archivo_panel')
        self.field(effects, 1, 'Ocultar mensaje (%)', 'mensaje_hasta')
        self.toggle(effects, 2, 'mensaje_fundido', 'Fundir la entrada y salida del mensaje')
        self.field(effects, 3, 'Zooms del video', 'zooms_video')
        self.field(effects, 4, 'Destellos localizados', 'acentos_baile')
        ttk.Label(effects, text='Marcas: tiempo,x,y; tiempo,x,y. Usa punto decimal y posiciones de 0 a 1.',
                  style='PanelMuted.TLabel', wraplength=490).grid(row=5,column=0,columnspan=4,sticky='w',pady=(2, 10))
        for i, (key, label) in enumerate((
            ('nieve_ascii', 'Nieve de caracteres'),
            ('nevada_intensa', 'Nieve más densa'),
            ('cierre_invernal', 'Copo y fundido al final'),
            ('led_navidad', 'Guirnalda LED'),
            ('estrella_destellos', 'Estrella intermitente'),
            ('regalos_extra', 'Regalos adicionales'),
            ('margen_tiktok', 'Márgenes para TikTok'),
            ('lienzo_original', 'Video a lienzo completo'),
            ('fondo_estadio', 'Fondo y tonos de estadio'),
            ('navidad_nocturna', 'Escena navideña nocturna'),
        )):
            ttk.Checkbutton(effects, text=label, variable=self.variables[key], style='Panel.TCheckbutton').grid(
                row=6+i//2, column=2*(i%2), columnspan=2, sticky='w', pady=4)


        self.field(main, 0, 'Fuente', 'fuente', ascii_art.SOURCES)
        self.asset_button = ttk.Button(main, text='Elegir archivo…', command=self.choose_asset)
        self.asset_button.grid(row=0, column=2, columnspan=2, sticky='e', padx=(12, 0))
        ttk.Label(main, textvariable=self.asset_label, style='PanelMuted.TLabel', wraplength=450).grid(
            row=1, column=0, columnspan=4, sticky='w', pady=(0, 7))
        self.figure_fields = [self.field(main, 2, 'Figura o escena', 'figura', ascii_art.FIGURES),
                              self.field(main, 3, 'Caracteres de figura', 'caracteres')]
        self.field(main, 2, '   Paleta', 'paleta', tuple(ascii_art.PALETTES), width=14, column=2)
        self.field(main, 3, '   Segundos', 'duracion', width=14, column=2)
        self.field(main, 4, 'Mensaje final', 'mensaje')
        self.figure_fields.append(self.field(main, 4, '   Vueltas', 'vueltas', width=14, column=2))
        colors = ttk.Frame(main, style='Panel.TFrame')
        colors.grid(row=5, column=0, columnspan=4, sticky='ew', pady=(9, 4))
        for key, label in (('color_figura', 'Color de caracteres…'), ('color_fondo', 'Color de fondo…')):
            ttk.Button(colors, text=label, command=lambda name=key, title=label: self.select_color(name, title)).pack(side='left', padx=(0, 6))
        ttk.Button(colors, text='Restaurar paleta', command=self.reset_colors).pack(side='left')
        ttk.Label(main, textvariable=self.color_label, style='PanelMuted.TLabel').grid(row=6, column=0, columnspan=4, sticky='w')
        self.particles_toggle = self.toggle(main, 7, 'particulas', 'Nieve y partículas')
        self.figure_fields.append(self.toggle(main, 8, 'detalles', 'Luces y detalles de figura 3D'))
        self.code_toggle = self.toggle(main, 9, 'codigo', 'Panel de código Python')
        self.field(main, 10, 'Tema de código', 'tema_codigo', tuple(CODE_THEMES))

        self.field(main, 11, 'Inicio del mensaje (%)', 'mensaje_desde')
        self.field(main, 12, 'Mensaje completo (%)', 'mensaje_completo')

        self.field(media, 0, 'Acabado', 'estilo_media', ascii_art.MEDIA_STYLES, width=12, column=2)
        ttk.Checkbutton(media, text='Realzar contornos', variable=self.variables['realzar_bordes'],
                        style='Panel.TCheckbutton').grid(row=1, column=2, columnspan=2, sticky='w', padx=(12, 0))
        self.field(media, 2, 'Movimiento de imagen', 'movimiento_imagen', ascii_art.IMAGE_MOVEMENTS, width=14, column=2)
        for row, key, label in (
            (3, 'detalle_sombras', 'Detalle en sombras'),
            (4, 'panel_compacto', 'Panel de código compacto'),
            (5, 'polvo_dorado', 'Partículas doradas'),
            (6, 'suavizar_bordes', 'Fundir bordes del video'),
        ):
            ttk.Checkbutton(media, text=label, variable=self.variables[key], style='Panel.TCheckbutton').grid(
                row=row, column=2, columnspan=2, sticky='w', padx=(12, 0))
        self.field(media, 7, 'Velocidad del video', 'velocidad_video', width=10, column=2)
        self.field(media, 8, 'Firma superior', 'firma_ascii', width=12, column=2)
        self.field(media, 0, 'Encuadre', 'ajuste', FITS)
        self.field(media, 1, 'Color de caracteres', 'modo_color', ascii_art.MEDIA_COLORS)
        self.field(media, 2, 'Columnas', 'columnas')
        self.field(media, 3, 'Contraste', 'contraste')
        self.field(media, 4, 'Brillo', 'brillo')
        self.field(media, 5, 'Rampa de caracteres', 'rampa')
        self.toggle(media, 6, 'invertir', 'Invertir claro y oscuro')
        self.toggle(media, 7, 'bucle', 'Repetir el video al terminar')
        self.duration_button = ttk.Button(media, text='Usar duración del video', command=self.use_video_duration)
        self.duration_button.grid(row=8, column=0, columnspan=2, sticky='w', pady=(8, 0))
        ttk.Label(media, text='Más columnas dibujan detalles más pequeños. La rampa va de menor a mayor densidad.',
                  style='PanelMuted.TLabel', wraplength=440).grid(row=9, column=0, columnspan=2, sticky='w', pady=(8, 0))

        hybrid = self.section(sections, 'Modo híbrido')
        self.field(hybrid, 0, 'Área en ASCII', 'modo_hibrido', ascii_art.HYBRID_MODES)
        self.field(hybrid, 1, 'Color del protagonista', 'color_protagonista', width=12)
        ttk.Button(hybrid, text='Elegir color…', command=self.choose_subject_color).grid(
            row=1, column=2, sticky='w', padx=(12, 0))
        self.field(hybrid, 2, 'Tolerancia de tono (°)', 'tolerancia_color', width=12)
        ttk.Label(hybrid, text='Modo híbrido para video ASCII. Elige un color distintivo del traje u objeto y ajusta la tolerancia en la vista previa.',
                  style='PanelMuted.TLabel', wraplength=440).grid(row=3, column=0, columnspan=4, sticky='w', pady=(8, 0))

        self.motion_tab = motion = self.section(sections, 'Animar y extender')
        ttk.Label(motion, text='Elige una imagen o un video en Composición. Recorre la barra de la vista previa para probar el movimiento.',
                  style='PanelMuted.TLabel', wraplength=455).grid(
                      row=0, column=0, columnspan=4, sticky='w', pady=(0, 10))
        self.motion_field = self.field(motion, 1, 'Movimiento', 'animacion_fuente', ascii_art.MEDIA_ANIMATIONS)
        self.motion_strength = self.field(motion, 2, 'Intensidad (%)', 'intensidad_movimiento', width=10)
        self.motion_duration = self.field(motion, 3, 'Duración final (s)', 'duracion', width=10)
        self.motion_audio = ttk.Button(motion, text='Igualar al tramo de audio…', command=self.use_audio_duration)
        self.motion_audio.grid(row=4, column=0, columnspan=2, sticky='w', pady=(6, 7))
        self.motion_loop = self.toggle(motion, 5, 'bucle', 'Repetir el video hasta completar la duración')
        self.motion_canvas = self.toggle(motion, 6, 'lienzo_original', 'Fuente a lienzo completo')
        self.motion_trail = self.toggle(motion, 7, 'estela_ascenso', 'Animar el escape en el ascenso')
        self.motion_exits = self.field(motion, 8, 'Salidas del escape (opcional)', 'puntos_escape')
        ttk.Label(motion, text='En imágenes transparentes, el escape se adapta a las llamas o a la forma de la base. Para colocar las estelas manualmente, escribe puntos x,y de 0 a 100 sobre el recorte. Ejemplo: 25,95;75,95.',
                  style='PanelMuted.TLabel', wraplength=455).grid(
                      row=9, column=0, columnspan=4, sticky='w', pady=(8, 0))
        ttk.Label(motion, text='En fotos opacas y videos, Ascenso mueve el encuadre.',
                  style='PanelMuted.TLabel', wraplength=455).grid(
                      row=10, column=0, columnspan=4, sticky='w', pady=(6, 0))

        self.video_tab = video = self.section(sections, 'Montaje de video')
        self.video_rotation = self.field(video, 0, 'Giro manual', 'giro_video', tuple(VIDEO_ROTATIONS))
        self.reveal_at = self.field(video, 1, 'Mostrar el original desde (s)', 'fin_ascii', width=12)
        self.reveal_duration = self.field(video, 2, 'Duración del fundido (s)', 'fundido_video', width=12)
        self.reveal_mark = ttk.Button(video, text='Usar posición de la vista previa', command=self.on_reveal_mark)
        self.reveal_mark.grid(row=3, column=0, columnspan=2, sticky='w', pady=(3, 6))
        self.keep_code = self.toggle(video, 4, 'mantener_codigo', 'Mantener código y firma al mostrar el original')
        self.repeat_audio = self.toggle(video, 5, 'repetir_audio', 'Repetir la pista de audio completa')
        self.extra_scale = self.toggle(video, 6, 'prueba_reescalada', 'Añadir prueba con código a 1440 × 2560')
        self.original_ranges = self.field(video, 7, 'Tramos con video original (s)', 'tramos_original', width=30)
        ttk.Label(video, text='Ejemplo 5-10; 18-24; 30-. Fuera de los tramos se muestra ASCII. '
                  'Cuando hay tramos, se usan en lugar del cambio único.',
                  style='PanelMuted.TLabel', wraplength=455).grid(
                      row=8, column=0, columnspan=4, sticky='w', pady=(7, 0))
        self.reactive_panel = self.toggle(video, 9, 'panel_reactivo', 'Adaptar el color del panel a la escena')
        camera = self.section(sections, 'Planos de cámara')
        self.field(camera, 0, 'Montaje de cámara', 'planos_camara', width=40)
        ttk.Label(camera, text='Ejemplo: 0-5,1,.5,.5,1.3,.6,.65; 5-10,1.2,.5,.4,1,.5,.5. '
                  'Cada plano tiene inicio y fin en segundos, y zoom, x, y de entrada y salida. '
                  'Usa punto decimal. El audio conserva su posición.',
                  style='PanelMuted.TLabel', wraplength=455).grid(row=1, column=0, columnspan=4, sticky='w')
        character = self.section(sections, 'Personaje')
        self.character_path = self.field(character, 0, 'Imagen transparente', 'archivo_personaje', width=34)
        self.character_button = ttk.Button(character, text='Elegir personaje…', command=self.choose_character)
        self.character_button.grid(row=1, column=0, sticky='w', pady=4)
        self.character_clear = ttk.Button(character, text='Quitar personaje',
                                          command=lambda: self.variables['archivo_personaje'].set(''))
        self.character_clear.grid(row=1, column=1, sticky='w', pady=4)
        self.character_motion = self.field(character, 2, 'Trayectoria', 'movimiento_personaje', width=38)
        self.character_sway = self.toggle(character, 3, 'balanceo_personaje', 'Balanceo suave')
        ttk.Label(character, text='Usa PNG, APNG o WebP con transparencia sobre una imagen o video. '
                  'Un sprite animado reproduce sus fotogramas en bucle. Ejemplo '
                  '0,.22,.55,.28,-8; 4,.65,.40,.34,8. Las marcas usan segundos, x, y, '
                  'tamaño relativo al ancho y giro en grados.',
                  style='PanelMuted.TLabel', wraplength=455).grid(row=4, column=0, columnspan=4, sticky='w')

        self.field(sound, 0, 'Sonido en ASCII', 'sonido', ascii_art.SOUNDS)
        self.audio_button = ttk.Button(sound, text='Elegir pista local…', command=self.choose_audio)
        self.audio_button.grid(row=1, column=0, columnspan=2, sticky='w', pady=(6, 3))
        ttk.Button(sound, text='Mezcla y fundidos…', command=self.on_mix).grid(row=1, column=1, sticky='e', pady=(6, 3))
        ttk.Label(sound, textvariable=self.audio_label, style='PanelMuted.TLabel', wraplength=430).grid(row=2, column=0,
                                                                                                        columnspan=2, sticky='w')
        self.audio_start = self.field(sound, 3, 'Inicio de la pista (s)', 'inicio')
        self.audio_end = self.field(sound, 4, 'Fin de la pista (s), opcional', 'fin')
        ttk.Label(sound, text='Este audio es independiente de la pista de Letra. Elige «Audio del video» para usar el sonido de la fuente.',
                  style='PanelMuted.TLabel', wraplength=440).grid(row=5, column=0, columnspan=2, sticky='w', pady=(10, 0))

    def choose_character(self):
        path = filedialog.askopenfilename(parent=self.parent, title='Elegir personaje transparente',
                                          filetypes=[('Sprites', '*.png *.apng *.webp')])
        if path:
            self.variables['archivo_personaje'].set(path)

    def choose_asset(self):
        kind = self.variables['fuente'].get()
        if kind == 'Figura 3D':
            return
        result = filedialog.askopenfilename(parent=self.parent, filetypes=self.types[kind])
        if result:
            self.variables['archivo'].set(result)

    def choose_audio(self):
        result = filedialog.askopenfilename(parent=self.parent, filetypes=self.types['Audio'])
        if result:
            self.variables['pista'].set(result)

    def use_video_duration(self):
        value = self.variables['archivo'].get()
        if not value or self.variables['fuente'].get() != 'Video':
            return
        try:
            meta = Path(value).stat()
            duration = video_duration(value, meta.st_mtime_ns, meta.st_size)
            if duration is None:
                raise ValueError('Escribe la duración manualmente. FFprobe no devolvió la duración de este video.')
            speed = float(self.variables['velocidad_video'].get().replace(',', '.'))
            if not .25 <= speed <= 3:
                raise ValueError('La velocidad debe estar entre 0,25 y 3.')
            self.variables['duracion'].set(f'{min(120, max(2, duration / speed)):.2f}')
        except (OSError, ValueError) as error:
            messagebox.showinfo('Duración del video', str(error), parent=self.parent)

    def use_audio_duration(self):
        sound = self.variables['sonido'].get()
        path = self.variables['pista' if sound == 'Archivo de audio' else 'archivo'].get()
        try:
            measured = audio_mix.duration(Path(path))
            if measured is None:
                raise ValueError('No se pudo leer la duración de la pista. Escribe los segundos manualmente.')
            start = float(self.variables['inicio'].get().replace(',', '.'))
            text = self.variables['fin'].get().strip().replace(',', '.')
            end = float(text) if text else measured
            if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= measured + .04):
                raise ValueError('Revisa el inicio y el fin seleccionados en Audio ASCII.')
            duration = min(end, measured) - start
            if not 2 <= duration <= 120:
                raise ValueError('El tramo debe durar entre 2 y 120 segundos. Ajusta el recorte en Audio ASCII.')
            self.variables['duracion'].set(f'{duration:.3f}'.rstrip('0').rstrip('.'))
        except (OSError, ValueError) as error:
            messagebox.showinfo('Duración del audio', str(error), parent=self.parent)

    def choose_subject_color(self):
        variable = self.variables['color_protagonista']
        _, value = colorchooser.askcolor(color=variable.get(), title='Color del protagonista', parent=self.parent)
        if value:
            variable.set(value)

    def select_color(self, key, title):
        palette = ascii_art.PALETTES[self.variables['paleta'].get()]
        _, value = colorchooser.askcolor(color=self.colors.get(key, palette[0 if key == 'color_fondo' else 1]),
                                         title=title, parent=self.parent)
        if value:
            self.colors[key] = value
            self.changed()

    def reset_colors(self):
        self.colors.clear()
        self.changed()

    def changed(self, *_):
        if not self.loading:
            self.update_labels()
            self.on_change()

    def update_labels(self):
        source = self.variables['fuente'].get()
        path = self.variables['archivo'].get()
        sound = self.variables['sonido'].get()
        track = self.variables['pista'].get()
        figure = {'fuente': source, 'figura': self.variables['figura'].get()}
        procedural = ascii_art.is_procedural(figure)
        ascii_world = ascii_art.is_ascii_world(figure)
        self.particles_toggle.configure(text='Animación ambiental' if procedural or ascii_world else 'Nieve y partículas')
        static_art = procedural and figure['figura'] in ascii_art.arte_procedural.ASCII_SIGNATURES
        self.particles_toggle.state(['disabled'] if static_art else ['!disabled'])
        self.code_toggle.state(['disabled'] if procedural else ['!disabled'])
        if source == 'Figura 3D':
            description = 'Escena ASCII animada · 9:16' if ascii_world else 'Generación de figura en perspectiva'
            if procedural:
                description = 'Ilustración ASCII · 3:4' if static_art else 'Escena programada · 3:4'
            self.asset_label.set(description)
        else:
            self.asset_label.set(Path(path).name if path else 'Elige una imagen o un video local')
        if sound == 'Audio del video':
            self.audio_label.set('Pista de la fuente de video' if source == 'Video' and path else 'Selecciona un video en Composición')
        else:
            self.audio_label.set(Path(track).name if track else 'Selecciona una pista local para usarla en ASCII')
        if self.colors:
            palette = ascii_art.PALETTES[self.variables['paleta'].get()]
            figure = self.colors.get('color_figura', palette[1])
            background = self.colors.get('color_fondo', palette[0])
            self.color_label.set(f'Caracteres {figure} · Fondo {background}')
        else:
            self.color_label.set('Colores predeterminados de la paleta')
        self.asset_button.state(['disabled'] if source == 'Figura 3D' else ['!disabled'])
        for widget in self.figure_fields:
            widget.state(['!disabled'] if source == 'Figura 3D' else ['disabled'])
        self.duration_button.state(['!disabled'] if source == 'Video' and path else ['disabled'])
        animation = self.variables['animacion_fuente'].get()
        has_ranges = bool(self.variables['tramos_original'].get().strip())
        has_reveal = source == 'Video' and (has_ranges or bool(self.variables['fin_ascii'].get()))
        for widget, enabled in (
            (self.motion_field, source != 'Figura 3D'),
            (self.motion_duration, source != 'Figura 3D'),
            (self.motion_strength, source != 'Figura 3D' and animation != ascii_art.MEDIA_ANIMATIONS[0]),
            (self.motion_loop, source == 'Video'),
            (self.motion_canvas, source == 'Video' or (source == 'Imagen' and animation != ascii_art.MEDIA_ANIMATIONS[0])),
            (self.motion_trail, source == 'Imagen' and animation == 'Ascenso'),
            (self.motion_exits, source == 'Imagen' and animation == 'Ascenso' and self.variables['estela_ascenso'].get()),
            (self.motion_audio, source != 'Figura 3D' and ((sound == 'Archivo de audio' and track)
                                                           or (sound == 'Audio del video' and source == 'Video' and path))),
            (self.video_rotation, source == 'Video'),
            (self.original_ranges, source == 'Video'),
            (self.reveal_at, source == 'Video' and not has_ranges),
            (self.reveal_mark, source == 'Video' and not has_ranges),
            (self.reveal_duration, has_reveal),
            (self.keep_code, has_reveal),
            (self.reactive_panel, has_reveal or ascii_world),
            (self.repeat_audio, source != 'Figura 3D' and sound in ('Archivo de audio', 'Audio del video')),
            (self.extra_scale, source != 'Figura 3D'),
            (self.character_path, source != 'Figura 3D'),
            (self.character_button, source != 'Figura 3D'),
            (self.character_clear, source != 'Figura 3D' and bool(self.variables['archivo_personaje'].get())),
            (self.character_motion, source != 'Figura 3D'),
            (self.character_sway, source != 'Figura 3D'),
        ):
            widget.state(['!disabled'] if enabled else ['disabled'])
        self.audio_button.state(['!disabled'] if sound == 'Archivo de audio' else ['disabled'])
        for widget in (self.audio_start, self.audio_end):
            widget.state(['!disabled'] if sound in ('Archivo de audio', 'Audio del video') else ['disabled'])

    def play_world(self):
        name = self.world_choice.get()
        area = juego_ascii.AREAS.index(name) if name in juego_ascii.AREAS else 1
        juego_ascii.open_window(self.parent, render.font, ascii_art.glyph_atlas, area,
                                self.variables['mundo_luz'].get(), self.variables['mundo_clima'].get(),
                                self.variables['particulas'].get())

    def load_world(self):
        data = self.settings()
        name = self.world_choice.get()
        data.update(fuente='Figura 3D', figura=name, estilo_media='ASCII', codigo=False,
                    firma_ascii='', archivo_panel='mundos_ascii.py', panel_reactivo=True, solo_video=True,
                    duracion=max(30, data['duracion']))
        self.set(data)
        self.on_change()

    def set(self, data):
        self.loading = True
        for key, variable in self.variables.items():
            variable.set('' if data[key] is None else data[key])
        if data['fuente'] == 'Figura 3D' and data['figura'] in ascii_art.mundos_ascii.NAMES:
            self.world_choice.set(data['figura'])
            self.sections.select(self.world_tab)
        self.colors = {key: data[key] for key in ('color_figura', 'color_fondo') if key in data}
        self.mix = audio_mix.normalize(data.get('mezcla'))
        self.loading = False
        self.update_labels()

    def settings(self):
        return ascii_art.config({**{key: value.get() for key, value in self.variables.items()}, **self.colors,
                                 'mezcla': self.mix})

