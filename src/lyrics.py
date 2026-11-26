import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from media import PROCESS_OPTIONS, find_ffmpeg


LANGUAGES = {'Español': 'es', 'Detectar idioma': 'auto', 'Inglés': 'en', 'Portugués': 'pt'}
MODEL_NAMES = ('ggml-small-q5_1.bin', 'ggml-base-q5_1.bin')
VOICE_BAND = ('highpass=f=105', 'lowpass=f=6300',
              'acompressor=threshold=0.10:ratio=3:attack=12:release=145:makeup=1.8',
              'alimiter=limit=0.94:level=0:latency=1')
PROFILES = {'Voz con música': VOICE_BAND, 'Voz centrada en estéreo': (
    'aformat=channel_layouts=stereo', 'pan=mono|c0=0.5*c0+0.5*c1', *VOICE_BAND), 'Mezcla original': ()}
AUTO_PROFILES = ('Automático', 'Comparar dos lecturas')
MIN_LINE = 0.7
TIMESTAMP = re.compile(r'(\d+):(\d{2}):(\d{2})[,.](\d{3})')
LRC_TIMESTAMP = re.compile(r'\[(\d+):([0-5]\d)(?:[.,](\d{1,3}))?\]')
NOISE = re.compile(r'^(?:\[.+?\]|\(.+?\)|[♪♫\s]+)$', re.DOTALL)
SENTENCE_END = re.compile(r'[.!?…][”\x22\x27)\]]*$')


@dataclass(frozen=True)
class Line:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class AudioEvidence:
    seconds: float
    level: float
    peak: float
    side_ratio: float
    returns: tuple


@dataclass(frozen=True)
class Transcript:
    lines: list
    profile: str
    notes: tuple


def model_in(root):
    folder = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else root
    return next((folder / 'modelos' / name for name in MODEL_NAMES if (folder / 'modelos' / name).is_file()), None)


def timestamp(raw):
    hours, minutes, seconds, milliseconds = map(int, TIMESTAMP.fullmatch(raw).groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def parse_srt(raw):
    raw_lines = raw.replace('\r', '').strip().split('\n')
    found = []
    start = end = None
    fragments = []

    def save_line():
        text = ' '.join(fragments).strip(' ♪♫\t')
        if start is not None and end > start and text and not NOISE.fullmatch(text):
            found.append(Line(start, end, text))

    for i, value in enumerate(raw_lines):
        line = value.strip()
        marks = TIMESTAMP.findall(line) if '-->' in line else []
        if len(marks) == 2:
            save_line()
            first, second = TIMESTAMP.finditer(line)
            start, end = timestamp(first.group()), timestamp(second.group())
            fragments = []
        elif start is not None and line:
            next_line = raw_lines[i + 1] if i + 1 < len(raw_lines) else ''
            if not (line.isdecimal() and '-->' in next_line):
                fragments.append(line)
    save_line()
    return compact_lines(found)


def compact_lines(lines):
    compact = []
    for line in sorted(lines, key=lambda item: item.start):
        if compact and line.start - compact[-1].start < MIN_LINE:
            before = compact.pop()
            compact.append(Line(before.start, max(before.end, line.end), f'{before.text} {line.text}'))
        else:
            compact.append(line)
    return compact


def parse_lrc(raw):
    entries = []
    for line in raw.splitlines():
        matches = list(LRC_TIMESTAMP.finditer(line))
        text = LRC_TIMESTAMP.sub('', line).strip()
        if text:
            for match in matches:
                minute, second, fraction = match.groups()
                start = int(minute) * 60 + int(second) + int((fraction or '0').ljust(3, '0')) / 1000
                entries.append((start, text))
    entries.sort(key=lambda row: row[0])
    found = []
    for i, (start, text) in enumerate(entries):
        end = entries[i + 1][0] if i + 1 < len(entries) else start + 3.05
        found.append(Line(start, max(start + MIN_LINE, end), text))
    return compact_lines(found)


def format_transcript(lines):
    phrases = []
    words = []

    def finish_phrase():
        if words:
            words_text = ' '.join(word[0] for word in words)
            phrases.append(Line(words[0][1], words[-1][2], words_text))
            words.clear()

    previous_end = None
    char_count = 0
    for line in lines:
        if previous_end is not None and line.start - previous_end > 0.48:
            finish_phrase()
            char_count = 0
        scale = (line.end - line.start) / len(line.text)
        for match in re.finditer(r'\S+', line.text):
            word = match.group()
            if words and char_count + 1 + len(word) > 66:
                finish_phrase()
                char_count = 0
            words.append((word, line.start + match.start() * scale, line.start + match.end() * scale))
            char_count += len(word) + bool(len(words) > 1)
            if SENTENCE_END.search(word):
                finish_phrase()
                char_count = 0
        previous_end = line.end
    finish_phrase()
    return compact_lines(phrases)


def timeline_for(lines, edited_count):
    begin = lines[0].start
    end = max(lines[-1].end, lines[-1].start + MIN_LINE)
    if edited_count != len(lines):
        return begin, [round(max(MIN_LINE, (end - begin) / edited_count), 3)] * edited_count
    starts = [line.start for line in lines] + [end]
    return begin, [round(max(MIN_LINE, right - left), 3) for left, right in zip(starts, starts[1:])]


def subtitle_timings(lines, edited_count):
    begin, spans = timeline_for(lines, edited_count)
    if edited_count != len(lines):
        return begin, spans, [None] * edited_count
    visible = [round(min(span, max(.001, line.end - line.start)), 3) for line, span in zip(lines, spans)]
    return begin, spans, visible


def optional_seconds(value):
    try:
        value = float(str(value).replace(',', '.'))
    except (ValueError, TypeError):
        raise ValueError('Escribe un número de segundos mayor o igual a cero.') from None
    if not math.isfinite(value) or value < 0:
        raise ValueError('Escribe un número de segundos mayor o igual a cero.')
    return value


def run_transcription(command, directory, cancel):
    deadline = time.monotonic() + 1200
    with subprocess.Popen(command, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **PROCESS_OPTIONS) as process:
        while True:
            if cancel is not None and cancel.is_set():
                process.kill()
                process.communicate()
                raise InterruptedError('Transcripción cancelada.')
            if time.monotonic() > deadline:
                process.kill()
                process.communicate()
                raise ValueError('La transcripción tardó demasiado. Prueba con un fragmento más corto.')
            try:
                stdout, stderr = process.communicate(timeout=0.35)
                return process.returncode, stdout, stderr
            except subprocess.TimeoutExpired:
                continue


def transcribe_song(source, model, language, start=0, stop=None, profile='Voz con música', cancel=None, queue_seconds=24, word_chunks=False):
    if not source.is_file():
        raise ValueError('No se encontró el archivo de audio.')
    if not model.is_file():
        raise ValueError('Selecciona un archivo de modelo Whisper que exista en esta PC.')
    if language not in LANGUAGES.values() or (stop is not None and stop <= start):
        raise ValueError('Revisa el idioma y el intervalo del fragmento.')
    if profile not in PROFILES:
        raise ValueError('Selecciona un perfil de audio válido.')
    ffmpeg = find_ffmpeg()
    capability = subprocess.run([ffmpeg, '-hide_banner', '-filters'], capture_output=True, timeout=12,
                                **PROCESS_OPTIONS)
    if not re.search(rb'\bwhisper\s+A->A', capability.stdout):
        raise ValueError('Esta versión de FFmpeg no incluye el filtro whisper. La letra también se puede pegar manualmente.')
    with tempfile.TemporaryDirectory() as directory:
        working = Path(directory)
        local = working / 'modelo.bin'
        try:
            os.link(model, local)
        except OSError:
            shutil.copyfile(model, local)
        # Fixed relative names keep Windows drive letters and apostrophes out of filter syntax.
        whisper = (f'whisper=model=modelo.bin:language={language}:use_gpu=false:queue={queue_seconds:g}:max_len={8 if word_chunks else 58}'
                   ':destination=letra.srt:format=srt')
        audio_filter = ','.join((*PROFILES[profile], 'aformat=sample_rates=16000:channel_layouts=mono',
                                 'asetpts=PTS-STARTPTS', whisper))
        trim = ['-t', f'{stop - start:.3f}'] if stop is not None else []
        command = [ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-progress', 'pipe:1', '-nostats',
                   '-protocol_whitelist', 'file,pipe',
                   '-ss', f'{start:.3f}', *trim, '-i', str(source.resolve()), '-map', '0:a:0', '-vn', '-sn', '-dn',
                   '-af', audio_filter, '-f', 'null', '-']
        status, output_text, errors_text = run_transcription(command, working, cancel)
        output = working / 'letra.srt'
        if status:
            errors = errors_text.decode('utf-8', errors='replace').splitlines()
            reason = next((line for line in errors if 'Error' in line), '')
            raise ValueError(f'No se pudo transcribir este audio con el modelo seleccionado. {reason}'.strip())
        lines = parse_srt(output.read_text(encoding='utf-8-sig', errors='replace')) if output.is_file() else []
        progress = output_text.decode('ascii', errors='replace').splitlines()
        measured = next((value[12:] for value in reversed(progress)
                         if value.startswith('out_time_us=') and value[12:].isdecimal()), None)
        if measured:
            duration = int(measured) / 1_000_000
            lines = [Line(line.start, min(line.end, duration), line.text) for line in lines if line.start < duration]
    if not lines:
        raise ValueError('No se detectaron versos. Prueba un tramo donde se oiga la voz o pega la letra.')
    return lines if word_chunks else format_transcript(lines)


def inspect_signal(source, start, stop, cancel):
    rate = 8000
    length = min(120.0, stop - start) if stop is not None else 120.0
    command = [find_ffmpeg(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-protocol_whitelist', 'file,pipe',
               '-ss', f'{start:.3f}', '-i', str(source.resolve()), '-map', '0:a:0', '-vn', '-t', f'{length:.3f}',
               '-af', 'highpass=f=100,lowpass=f=3650', '-ac', '2', '-ar', str(rate), '-f', 'f32le', 'pipe:1']
    status, raw, _ = run_transcription(command, source.parent, cancel)
    if status or len(raw) < 8:
        raise ValueError('El archivo o tramo elegido no contiene audio legible.')
    stereo = np.frombuffer(raw, dtype='<f4').reshape(-1, 2)
    center = (stereo[:, 0] + stereo[:, 1]) * 0.5
    side = (stereo[:, 0] - stereo[:, 1]) * 0.5
    level = float(np.sqrt(np.mean(center ** 2)))
    side_ratio = float(np.sqrt(np.mean(side ** 2)) / max(level, 1e-6))
    peak = float(np.max(np.abs(stereo)))
    window = 320
    whole = len(center) // window * window
    returns = []
    if whole >= window * 6:
        envelope = np.sqrt(np.mean(center[:whole].reshape(-1, window) ** 2, axis=1))
        floor, loud = np.quantile(envelope, [.19, .82])
        if loud > max(.002, floor * 2.2):
            quiet = envelope < max(.001, min(.026, floor * 1.65 + .001, loud * .32))
            pause = 0
            for index, is_quiet in enumerate(quiet):
                if is_quiet:
                    pause += 1
                else:
                    if pause >= 5:
                        returns.append(index * window / rate)
                    pause = 0
    return AudioEvidence(len(center) / rate, level, peak, side_ratio, tuple(returns))


def quality(lines):
    text = ' '.join(line.text for line in lines)
    words = re.findall(r'[^\W\d]+', text.lower(), re.UNICODE)
    if not words:
        return (-1, 0)
    runs = sum(left == right for left, right in zip(words, words[1:]))
    trigrams = list(zip(words, words[1:], words[2:]))
    loops = 1 - len(set(trigrams)) / len(trigrams) if trigrams else 0
    diversity = len(set(words)) / len(words)
    coverage = sum(max(0, line.end - line.start) for line in lines)
    return (diversity - min(.6, 2 * runs / len(words)) - .45 * loops, coverage)


def refine_entries(lines, evidence):
    result = []
    for i, line in enumerate(lines):
        lower = result[-1].start + MIN_LINE if result else 0
        upper = min(line.end - .22, lines[i + 1].start - MIN_LINE) if i + 1 < len(lines) else line.end - .22
        window = .42 if i else .75
        options = [value for value in evidence.returns if lower <= value <= upper and abs(value - line.start) <= window]
        nearest = min(options, key=lambda value: abs(value - line.start)) if options else line.start
        result.append(Line(round(nearest, 3), line.end, line.text))
    return result


def transcribe_project(source, model, language, start, stop, profile, cancel, on_stage=None):
    if on_stage:
        on_stage('Analizando nivel, estéreo y pausas…')
    evidence = inspect_signal(source, start, stop, cancel)
    if evidence.peak < .0001 and evidence.seconds < 119.9:
        raise ValueError('El fragmento está prácticamente en silencio. Cambia el recorte o elige otra pista.')
    automatic = 'Voz centrada en estéreo' if .16 < evidence.side_ratio < 1.38 else 'Voz con música'
    if evidence.side_ratio >= 1.38:
        automatic = 'Mezcla original'
    primary = automatic if profile in AUTO_PROFILES else profile
    alternate = 'Mezcla original' if primary != 'Mezcla original' else 'Voz con música'
    notes = []
    if evidence.level < .009:
        notes.append('La señal medida tiene un nivel bajo. Escucha el fragmento al revisar la letra.')
    attempts = (primary, alternate) if profile in AUTO_PROFILES else (primary,)
    results = []
    last_error = None
    for engine in attempts:
        if on_stage:
            on_stage(f'Escuchando con «{engine}»…')
        try:
            recovered = transcribe_song(source, model, language, start, stop, engine, cancel)
        except ValueError as error:
            last_error = error
            continue
        results.append((engine, recovered))
        score, covered = quality(recovered)
        if profile != 'Comparar dos lecturas' and score >= .40 and covered >= min(3, .35 * evidence.seconds):
            break
    if not results:
        raise last_error or ValueError('No se detectaron versos en el fragmento.')
    selected, lines = results[0]
    if len(results) == 2:
        first_quality, first_coverage = quality(lines)
        other, candidate = results[1]
        other_quality, other_coverage = quality(candidate)
        if (other_quality > first_quality + .16 and other_coverage >= .66 * first_coverage
                or other_coverage > 1.55 * max(.7, first_coverage) and other_quality >= first_quality - .06):
            selected, lines = other, candidate
        notes.append('Se compararon dos lecturas por cobertura y repeticiones. Revisa los versos con el audio.')
    if quality(lines)[1] < min(5, .27 * evidence.seconds):
        notes.append('Se detectó letra en una parte pequeña del tramo.')
    return Transcript(refine_entries(lines, evidence), selected, tuple(notes))
