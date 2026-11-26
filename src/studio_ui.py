import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageTk

import audio_mix
from designs import CODE_THEMES, DESIGNS, MOODS, PALETTES, silhouette


BG, FIELD, TEXT, MUTED, ACCENT = '#111019', '#23222d', '#f5edf1', '#bcafbf', '#ffb4a3'


def modal(root, title):
    window = tk.Toplevel(root, bg=BG)
    window.title(title)
    window.transient(root)
    window.grab_set()
    panel = ttk.Frame(window, padding=(18, 14))
    panel.pack(fill='both', expand=True)
    return window, panel


def sample_image(shape, palette_name, code_name, font):
    bg, ink, glow, cold = PALETTES[palette_name]
    code = CODE_THEMES[code_name]
    canvas = Image.new('RGB', (310, 201), bg)
    icon = silhouette(shape, 112)
    canvas.paste((ImageColor.getrgb(ink)), (99, 10, 211, 122), icon.filter(ImageFilter.GaussianBlur(9)))
    halo = icon.point(lambda value: int(value * .45))
    canvas.paste(ImageColor.getrgb(glow), (99, 10, 211, 122), halo)
    edge = icon.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
    canvas.paste(ImageColor.getrgb(ink), (99, 10, 211, 122), edge)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((12, 132, 298, 190), 8, fill=code.panel, outline=code.border)
    draw.ellipse((24, 145, 30, 151), fill=code.keyword)
    draw.text((39, 144), 'escena.js', font=font('consola.ttf', 12), fill=code.muted)
    draw.text((24, 162), 'const', font=font('consola.ttf', 15), fill=code.keyword)
    draw.text((78, 162), 'mensaje =', font=font('consola.ttf', 15), fill=code.text)
    draw.text((168, 162), '"…";', font=font('consola.ttf', 15), fill=code.literal)
    return canvas


class DesignLibrary:
    def __init__(self, root, font, mode, on_apply):
        self.window, panel = modal(root, 'Biblioteca de diseños')
        self.font = font
        self.on_apply = on_apply
        self.visible_shapes = []
        self.shape = None
        self.picture = None
        self.category = tk.StringVar(self.window, 'Todos')
        self.palette = tk.StringVar(self.window, 'Invierno')
        self.code = tk.StringVar(self.window, 'Terminal')
        self.phrase = tk.StringVar(self.window)
        self.phrase_label = tk.StringVar(self.window)
        self.title = tk.StringVar(self.window)

        panel.columnconfigure(1, weight=1)
        filters = ttk.Frame(panel)
        filters.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        ttk.Label(filters, text='Ánimo', style='Muted.TLabel').pack(side='left', padx=(0, 8))
        moods = ttk.Combobox(filters, textvariable=self.category, values=('Todos', *MOODS), state='readonly', width=19)
        moods.pack(side='left')
        moods.bind('<<ComboboxSelected>>', lambda _: self.refresh_shapes())
        ttk.Label(filters, text='Aplicar a ASCII' if mode == 'ascii' else 'Aplicar a la escena de letra',
                  style='Muted.TLabel').pack(side='right')

        left = ttk.Frame(panel)
        left.grid(row=1, column=0, rowspan=2, sticky='ns', padx=(0, 16))
        self.shapes = tk.Listbox(left, height=15, width=20, bg=FIELD, fg=TEXT, exportselection=False, activestyle='none',
                                 selectbackground='#594150', selectforeground='#ffe1cf', relief='flat', borderwidth=0,
                                 highlightthickness=1, highlightbackground='#464054', font=('Segoe UI', 11))
        scroll = ttk.Scrollbar(left, orient='vertical', command=self.shapes.yview)
        self.shapes.configure(yscrollcommand=scroll.set)
        self.shapes.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.shapes.bind('<<ListboxSelect>>', lambda _: self.select_shape())

        right = ttk.Frame(panel)
        right.grid(row=1, column=1, sticky='ew')
        right.columnconfigure(1, weight=1)
        ttk.Label(right, textvariable=self.title, style='Section.TLabel').grid(row=0, column=0, columnspan=2, sticky='w')
        self.thumbnail = ttk.Label(right)
        self.thumbnail.grid(row=1, column=0, columnspan=2, pady=(4, 8))
        for i, (name, variable, choices) in enumerate((('Paleta de escena', self.palette, tuple(PALETTES)),
                                                         ('Tema de código', self.code, tuple(CODE_THEMES))), 2):
            ttk.Label(right, text=name, style='Muted.TLabel').grid(row=i, column=0, sticky='w', padx=(0, 8), pady=3)
            field = ttk.Combobox(right, textvariable=variable, values=choices, state='readonly', width=20)
            field.grid(row=i, column=1, sticky='ew', pady=3)
            field.bind('<<ComboboxSelected>>', lambda _: self.update_picture())
        ttk.Label(right, text='Frase', style='Muted.TLabel').grid(row=4, column=0, sticky='w', pady=(4, 0))
        self.phrases = ttk.Combobox(right, textvariable=self.phrase, state='readonly', width=37)
        self.phrases.grid(row=4, column=1, sticky='ew', pady=(5, 0))
        self.phrases.bind('<<ComboboxSelected>>', lambda _: self.phrase_label.set(self.phrase.get()))
        ttk.Label(right, textvariable=self.phrase_label, wraplength=360, style='Muted.TLabel').grid(
            row=5, column=0, columnspan=2, sticky='w', pady=(5, 1))

        actions = ttk.Frame(panel)
        actions.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(14, 0))
        ttk.Button(actions, text='Cerrar', command=self.window.destroy).pack(side='left')
        ttk.Button(actions, text='Aplicar diseño y frase', command=lambda: self.apply(True), style='Export.TButton').pack(side='right')
        ttk.Button(actions, text='Aplicar diseño', command=lambda: self.apply(False)).pack(side='right', padx=(0, 8))
        self.refresh_shapes()

    def refresh_shapes(self):
        category = self.category.get()
        self.visible_shapes = [name for name, design in DESIGNS.items() if category == 'Todos' or category in design.phrases]
        self.shapes.delete(0, 'end')
        for name in self.visible_shapes:
            self.shapes.insert('end', f'  {name}')
        pick = self.visible_shapes.index(self.shape) if self.shape in self.visible_shapes else 0
        self.shapes.selection_set(pick)
        self.shapes.see(pick)
        self.select_shape()

    def select_shape(self):
        selection = self.shapes.curselection()
        if not selection:
            return
        self.shape = self.visible_shapes[selection[0]]
        design = DESIGNS[self.shape]
        category = self.category.get()
        phrases = design.phrases[category] if category != 'Todos' else tuple(
            phrase for group in design.phrases.values() for phrase in group)
        self.palette.set(design.palette)
        self.code.set(design.code)
        self.title.set(self.shape)
        self.phrases.configure(values=phrases)
        self.phrase.set(phrases[0])
        self.phrase_label.set(phrases[0])
        self.update_picture()

    def update_picture(self):
        if self.shape:
            self.picture = ImageTk.PhotoImage(sample_image(self.shape, self.palette.get(), self.code.get(), self.font))
            self.thumbnail.configure(image=self.picture)

    def apply(self, with_phrase):
        if self.shape and self.on_apply(self.shape, self.palette.get(), self.code.get(), self.phrase.get() if with_phrase else ''):
            self.window.destroy()


def edit_mix(root, data, on_apply, on_listen):
    window, panel = modal(root, 'Mezcla de audio')
    settings = audio_mix.normalize(data)
    fields = ('ganancia', 'entrada', 'salida', 'ganancia_extra', 'retardo_extra', 'recorte_extra')
    vars_by_name = {name: tk.StringVar(window, str(settings[name])) for name in fields}
    level = tk.BooleanVar(window, settings['nivelar'])
    second = tk.StringVar(window, settings['pista_extra'])
    file_label = tk.StringVar(window)
    for row, (key, label, limits) in enumerate((('ganancia', 'Volumen (dB)', (-24, 12)),
                                                ('entrada', 'Fundido de entrada (s)', (0, 12)),
                                                ('salida', 'Fundido de salida (s)', (0, 12)))):
        ttk.Label(panel, text=label).grid(row=row, column=0, sticky='w', pady=4, padx=(0, 14))
        ttk.Spinbox(panel, from_=limits[0], to=limits[1], increment=1 if row == 0 else .25,
                    textvariable=vars_by_name[key], width=10).grid(row=row, column=1, sticky='w')
    ttk.Checkbutton(panel, text='Nivelar diferencias de volumen', variable=level).grid(row=3, column=0, columnspan=2,
                                                                                       sticky='w', pady=(7, 12))
    ttk.Separator(panel).grid(row=4, column=0, columnspan=2, sticky='ew', pady=(0, 8))
    ttk.Label(panel, text='Segunda pista opcional', style='Section.TLabel').grid(row=5, column=0, columnspan=2, sticky='w')

    def show_file():
        file_label.set(Path(second.get()).name if second.get() else 'Sin segunda pista')

    def choose():
        value = filedialog.askopenfilename(parent=window, filetypes=[('Audio y video', '*.mp3 *.wav *.m4a *.ogg *.flac *.aac *.mp4 *.mov'), ('Todos', '*.*')])
        if value:
            second.set(value)
            show_file()

    def clear():
        second.set('')
        show_file()

    ttk.Label(panel, textvariable=file_label, style='Muted.TLabel', wraplength=340).grid(row=6, column=0, columnspan=2, sticky='w', pady=(4, 0))
    paths = ttk.Frame(panel)
    paths.grid(row=7, column=0, columnspan=2, sticky='w', pady=(5, 4))
    ttk.Button(paths, text='Elegir segunda pista…', command=choose).pack(side='left')
    ttk.Button(paths, text='Quitar', command=clear).pack(side='left', padx=(7, 0))
    for row, (key, title, limits) in enumerate((('ganancia_extra', 'Volumen de segunda pista (dB)', (-48, 6)),
                                               ('retardo_extra', 'Entrada de segunda pista en el reel (s)', (0, 600)),
                                               ('recorte_extra', 'Empezar el segundo archivo en (s)', (0, 3600))), 8):
        ttk.Label(panel, text=title).grid(row=row, column=0, sticky='w', pady=3, padx=(0, 13))
        ttk.Spinbox(panel, from_=limits[0], to=limits[1], increment=1 if row == 8 else .25,
                    textvariable=vars_by_name[key], width=10).grid(row=row, column=1, sticky='w')
    show_file()

    def submit(listen=False):
        try:
            options = audio_mix.normalize({**{name: var.get() for name, var in vars_by_name.items()},
                                           'nivelar': level.get(), 'pista_extra': second.get()})
            if listen:
                on_listen(options)
            else:
                on_apply(options)
                window.destroy()
        except (OSError, ValueError) as error:
            messagebox.showerror('Mezcla de audio', str(error), parent=window)

    actions = ttk.Frame(panel)
    actions.grid(row=11, column=0, columnspan=2, sticky='ew', pady=(11, 0))
    ttk.Button(actions, text='Escuchar pista principal', command=lambda: submit(True)).pack(side='left')
    ttk.Button(actions, text='Aplicar', style='Export.TButton', command=submit).pack(side='right', padx=(10, 0))
