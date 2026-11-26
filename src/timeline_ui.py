import subprocess
import tkinter as tk
from tkinter import ttk

import numpy as np
from PIL import Image, ImageDraw, ImageTk

from media import PROCESS_OPTIONS, find_ffmpeg
from studio_ui import modal


def waveform(track, start, stop, total, columns=360):
    result = np.zeros(columns)
    if track is None:
        return result
    rate = 4000
    length = min(total, stop - start) if stop is not None else total
    cmd = [find_ffmpeg(), '-nostdin', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-ss', f'{start:.3f}',
           '-i', str(track), '-map', '0:a:0', '-vn', '-t', f'{length:.3f}', '-ar', str(rate), '-ac', '1',
           '-f', 's16le', 'pipe:1']
    run = subprocess.run(cmd, check=True, capture_output=True, timeout=20, **PROCESS_OPTIONS)
    data = np.frombuffer(run.stdout, dtype='<i2').astype(np.float32) / 32768
    samples = round(total * rate)
    data = np.pad(data[:samples], (0, max(0, samples - len(data))))
    result[:] = [max(np.abs(chunk), default=0) for chunk in np.array_split(data, columns)]
    return result


class TimelineWindow:
    def __init__(self, parent, preview, listen):
        self.window, pane = modal(parent, 'Línea de tiempo del reel')
        self.preview = preview
        self.listen = listen
        self.seconds = 0.0
        self.pending = None
        self.thumbnail = None
        self.marks = ttk.Treeview(pane, columns=('start', 'end', 'text'), show='headings', selectmode='browse', height=12)
        for col, label, size in (('start', 'Inicio', 62), ('end', 'Fin visible', 80), ('text', 'Verso', 294)):
            self.marks.heading(col, text=label)
            self.marks.column(col, width=size, stretch=(col == 'text'))
        self.canvas = tk.Canvas(pane, width=650, height=90, bg='#191823', highlightthickness=0)
        self.canvas.grid(row=0, column=0, columnspan=2, sticky='ew')
        self.canvas.bind('<Button-1>', self.seek)
        self.canvas.bind('<B1-Motion>', self.seek)
        self.frame = ttk.Label(pane)
        self.frame.grid(row=1, column=0, rowspan=2, padx=(0, 12), pady=8)
        self.marks.grid(row=1, column=1, sticky='nsew', pady=8)
        self.marks.bind('<<TreeviewSelect>>', self.select_mark)
        self.position = tk.StringVar(self.window)
        self.guides = tk.BooleanVar(self.window, False)
        tools = ttk.Frame(pane)
        tools.grid(row=2, column=1, sticky='nw')
        ttk.Label(tools, textvariable=self.position).pack(anchor='w', pady=(0, 8))
        ttk.Checkbutton(tools, text='Guía central orientativa', variable=self.guides, command=self.refresh).pack(anchor='w')
        ttk.Button(tools, text='Escuchar desde el cursor', command=self.listen_here,
                   state='normal' if preview.recording else 'disabled').pack(anchor='w', pady=6)
        self.verse_button = ttk.Button(tools, text='Escuchar verso seleccionado',
                                       command=self.listen_verse, state='disabled')
        self.verse_button.pack(anchor='w')
        try:
            self.wave = waveform(preview.recording, preview.audio_start, preview.audio_end, preview.clock.total)
        except (OSError, ValueError, subprocess.SubprocessError):
            self.wave = np.zeros(360)
        for index, (start, span, show, label) in enumerate(preview.cues):
            end = start + (show if show is not None else span)
            self.marks.insert('', 'end', iid=str(index), values=(f'{start:.2f} s', f'{end:.2f} s', label))
        self.refresh()

    def seek(self, event):
        width = max(1, self.canvas.winfo_width() - 22)
        self.move((event.x - 11) / width * self.preview.clock.total)

    def select_mark(self, _):
        selected = self.marks.selection()
        self.verse_button.configure(state='normal' if selected and self.preview.recording else 'disabled')
        if selected:
            self.move(self.preview.cues[int(self.marks.selection()[0])][0])

    def move(self, seconds):
        self.seconds = self.preview.clock.sample(seconds)
        self.paint()
        if self.pending:
            self.window.after_cancel(self.pending)
        self.pending = self.window.after(100, self.refresh)

    def paint(self):
        cv = self.canvas
        cv.delete('all')
        total = self.preview.clock.total
        width = max(628, cv.winfo_width() - 22)
        def x(time):
            return 11 + time / total * width
        cv.create_text(11, 9, anchor='w', text='Pista principal y tramos visibles', fill='#d8ccdf')
        for i, peak in enumerate(self.wave):
            baseline = 39
            height = min(18, peak * 36)
            cx = x(i / len(self.wave) * total)
            cv.create_line(cx, baseline - height, cx, baseline + height, fill='#82c7ca')
        for start, span, show, _ in self.preview.cues:
            cv.create_rectangle(x(start), 64, x(start + span), 82, fill='#34314b', outline='')
            end = start + (show if show is not None else span)
            cv.create_rectangle(x(start), 66, x(end), 80, fill='#ac73a6', outline='')
        if self.preview.animation:
            cv.create_rectangle(11, 66, x(total), 80, fill='#545385', outline='')
        cv.create_line(x(self.seconds), 19, x(self.seconds), 86, fill='#ffe5aa', width=2)
        self.position.set(f'{self.seconds:.2f} / {total:.2f} s · audio local')

    def refresh(self):
        self.pending = None
        self.paint()
        try:
            frame = self.preview.frame(self.seconds)
            if self.guides.get():
                layer = ImageDraw.Draw(frame)
                layer.rectangle((54, 162, frame.width - 86, frame.height - 305), outline='#ffe5aa', width=4)
            self.thumbnail = ImageTk.PhotoImage(frame.resize((180, 320), Image.Resampling.LANCZOS))
            self.frame.configure(image=self.thumbnail, text='')
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.frame.configure(image='', text=str(error), wraplength=180)

    def listen_here(self):
        start = self.preview.audio_start + self.seconds
        end = start + 5
        if self.preview.audio_end is not None:
            end = min(end, self.preview.audio_end)
        self.listen(start, end)

    def listen_verse(self):
        selected = self.marks.selection()
        if not selected or not self.preview.recording:
            return
        start, span, visible, _ = self.preview.cues[int(selected[0])]
        start += self.preview.audio_start
        end = start + (visible if visible is not None else span)
        if self.preview.audio_end is not None:
            end = min(end, self.preview.audio_end)
        if end > start:
            self.listen(start, end)
