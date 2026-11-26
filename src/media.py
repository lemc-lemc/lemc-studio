import os
import json
import math
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps


MOTIONS = ('Fijo', 'Acercar', 'Alejar', 'Desplazar a la izquierda', 'Desplazar a la derecha')
FITS = ('Encajar', 'Recortar', 'Recorte inferior')
VIDEO_ROTATIONS = {'Según archivo': '', '90° a la izquierda': 'transpose=cclock',
                   '90° a la derecha': 'transpose=clock', '180°': 'hflip,vflip'}


def external_process_options():
    if os.name == 'nt':
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    if getattr(sys, 'frozen', False):
        environment = os.environ.copy()
        original = environment.pop('LD_LIBRARY_PATH_ORIG', None)
        if original is None:
            environment.pop('LD_LIBRARY_PATH', None)
        else:
            environment['LD_LIBRARY_PATH'] = original
        return {'env': environment}
    return {}


PROCESS_OPTIONS = external_process_options()


def find_program(command):
    name = f'{command}.exe' if os.name == 'nt' else command
    if getattr(sys, 'frozen', False):
        folder = Path(sys.executable).resolve().parent
        for candidate in (folder / name, folder / 'bin' / name):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return shutil.which(name)


def find_ffmpeg():
    executable = find_program('ffmpeg')
    if not executable:
        raise ValueError('FFmpeg no está disponible. Instálalo o colócalo junto al ejecutable.')
    return executable


def inspect_video(path):
    probe = find_program('ffprobe')
    if not path.is_file() or not probe:
        raise ValueError('Selecciona un video local y comprueba que FFprobe esté disponible.')
    try:
        result = subprocess.run(
            [probe, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_entries',
             'stream=codec_type,duration:stream_disposition=attached_pic:format=duration',
             '-of', 'json', str(path)], capture_output=True, timeout=12, check=True, **PROCESS_OPTIONS)
        data = json.loads(result.stdout)
        streams = data.get('streams', [])
        picture = next(stream for stream in streams if stream['codec_type'] == 'video'
                       and not stream.get('disposition', {}).get('attached_pic'))
        for value in (picture.get('duration'), data.get('format', {}).get('duration')):
            try:
                duration = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(duration) and duration > 0:
                return duration, any(stream['codec_type'] == 'audio' for stream in streams)
        raise ValueError
    except (OSError, ValueError, StopIteration, KeyError, subprocess.SubprocessError):
        raise ValueError(f'No se pudo leer la duración del video «{path.name}».') from None


def media_settings(settings, folder):
    if settings is None:
        return None
    if not isinstance(settings, dict):
        raise ValueError('El fondo multimedia debe indicar su tipo, archivo y movimiento.')
    filename = settings.get('archivo')
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError('Selecciona un archivo local para el fondo.')
    kind = settings.get('tipo')
    if kind not in ('Imagen', 'Video'):
        raise ValueError('El fondo debe ser una imagen o un video.')
    movement = settings.get('movimiento', 'Fijo')
    if movement not in MOTIONS:
        raise ValueError('El movimiento de fondo no está disponible.')
    veil = settings.get('velo', 55)
    if type(veil) is not int or not 0 <= veil <= 100:
        raise ValueError('La intensidad del velo de color debe estar entre 0 y 100.')
    try:
        start = float(str(settings.get('inicio', 0)).replace(',', '.')) if kind == 'Video' else 0.0
    except (TypeError, ValueError):
        start = -1
    if not math.isfinite(start) or start < 0:
        raise ValueError('El inicio del video debe ser un número mayor o igual a cero.')
    return {'tipo': kind, 'archivo': str((folder / filename).resolve()), 'movimiento': movement, 'velo': veil, 'inicio': start}


def open_image(path, size, *, fit='Recortar', alpha=False):
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert('RGBA')
            if alpha:
                if fit in ('Recortar', 'Recorte inferior'):
                    center = (.5, .88) if fit == 'Recorte inferior' else (.5, .5)
                    return ImageOps.fit(image, size, Image.Resampling.LANCZOS, centering=center)
                centered = Image.new('RGBA', size)
                image = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
                centered.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
                return centered
            opaque = Image.new('RGBA', image.size, (0, 0, 0, 255))
            opaque.alpha_composite(image)
            return ImageOps.fit(opaque.convert('RGB'), size, Image.Resampling.LANCZOS)
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise ValueError(f'No se pudo abrir la imagen «{Path(path).name}».') from error


def video_command(path, size, fps=None, *, fit='Recortar', alpha=False, loop=True, seek=0, speed=1,
                  rotation='Según archivo'):
    width, height = size
    pixel = 'rgba' if alpha else 'rgb24'
    if fit == 'Encajar':
        conversion = (f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,'
                      f'format={pixel},pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black@0,setsar=1')
    else:
        crop_y = ':(iw-ow)/2:(ih-oh)*0.88' if fit == 'Recorte inferior' else ''
        conversion = (f'scale={width}:{height}:force_original_aspect_ratio=increase:force_divisible_by=2,'
                      f'crop={width}:{height}{crop_y},setsar=1')
    turn = VIDEO_ROTATIONS[rotation]
    if turn:
        conversion = f'{turn},{conversion}'
    loops = ['-stream_loop', '-1'] if fps and loop else []
    seek_options = ['-ss', f'{seek:.4f}'] if seek else []
    if fps:
        conversion = f'fps={fps},{conversion}'
        if speed != 1:
            conversion = f'setpts=(PTS-STARTPTS)/{speed:.8f},{conversion}'
    return [find_ffmpeg(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-threads', '2',
            '-filter_threads', '1', *loops, *seek_options, '-protocol_whitelist', 'file,pipe', '-i', str(path),
            '-map', '0:v:0', '-an', '-sn', '-dn', '-vf', conversion,
            *([] if fps else ['-frames:v', '1']), '-threads', '1', '-pix_fmt', pixel, '-f', 'rawvideo', 'pipe:1']


@lru_cache(maxsize=5)
def preview_still(path, kind, size, modified_ns, byte_size):
    if kind == 'Imagen':
        return open_image(path, size)
    result = subprocess.run(video_command(path, size), capture_output=True, timeout=9, **PROCESS_OPTIONS)
    if result.returncode or len(result.stdout) != size[0] * size[1] * 3:
        raise ValueError(f'No se pudo leer el video «{Path(path).name}».')
    return Image.frombytes('RGB', size, result.stdout)


@lru_cache(maxsize=12)
def video_duration(path, modified_ns, byte_size):
    probe = find_program('ffprobe')
    if not probe:
        adjacent = Path(find_ffmpeg()).with_name('ffprobe.exe' if os.name == 'nt' else 'ffprobe')
        probe = str(adjacent) if adjacent.is_file() else None
    if not probe:
        return None
    try:
        result = subprocess.run([probe, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-select_streams', 'v:0',
                                 '-show_entries', 'stream=duration:format=duration', '-of', 'csv=p=0', str(path)],
                                capture_output=True, check=True, timeout=10, **PROCESS_OPTIONS)
        candidates = result.stdout.decode().strip().splitlines()
        duration = next((float(value) for value in candidates if value and value != 'N/A'), None)
        return duration if duration and math.isfinite(duration) and duration > 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


@lru_cache(maxsize=9)
def ascii_preview_still(path, kind, size, fit, loop, seconds, modified_ns, byte_size, rotation='Según archivo'):
    if kind == 'Imagen':
        return open_image(path, size, fit=fit, alpha=True)
    duration = video_duration(path, modified_ns, byte_size)
    seek = seconds
    if duration:
        seek = seconds % duration if loop else seconds
        seek = min(seek, max(0, duration - 0.08))
    for time in (seek, 0) if seek else (0,):
        result = subprocess.run(video_command(path, size, fit=fit, alpha=True, seek=time, rotation=rotation),
                                capture_output=True, timeout=10, **PROCESS_OPTIONS)
        if not result.returncode and len(result.stdout) == size[0] * size[1] * 4:
            return Image.frombytes('RGBA', size, result.stdout)
    raise ValueError(f'No se pudo leer el video ASCII «{Path(path).name}».')


class BackgroundFrames:
    def __init__(self, settings, size, fps, *, fit='Recortar', alpha=False, loop=True):
        self.path = Path(settings['archivo'])
        if not self.path.is_file():
            raise ValueError(f'No se encontró el fondo «{self.path.name}».')
        self.size = size
        self.mode = 'RGBA' if alpha else 'RGB'
        self.channels = 4 if alpha else 3
        self.loop = loop
        self.finished = False
        self.process = None
        self.image = None
        if settings['tipo'] == 'Imagen':
            self.image = open_image(self.path, size, fit=fit, alpha=alpha)
        else:
            self.process = subprocess.Popen(video_command(self.path, size, fps, fit=fit, alpha=alpha, loop=loop,
                                                          seek=settings.get('inicio', 0), speed=settings.get('velocidad_video', 1),
                                                          rotation=settings.get('giro_video', 'Según archivo')), stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, **PROCESS_OPTIONS)

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
            self.process.stdout.close()
            self.process.wait()

    def next_frame(self):
        if self.process is None or self.finished:
            return self.image
        expected = self.size[0] * self.size[1] * self.channels
        data = self.process.stdout.read(expected)
        if len(data) != expected:
            if not data and not self.loop and self.image is not None and self.process.wait() == 0:
                self.finished = True
                return self.image
            raise ValueError(f'No se pudo leer o repetir el video «{self.path.name}».')
        self.image = Image.frombytes(self.mode, self.size, data)
        return self.image


def move_frame(image, movement, phase):
    if movement == 'Fijo':
        return image
    phase = phase * phase * (3 - 2 * phase)
    width, height = image.size
    if movement in ('Acercar', 'Alejar'):
        zoom = 1 + 0.25 * (phase if movement == 'Acercar' else 1 - phase)
        x = y = 0.5
    else:
        zoom = 1.22
        x = phase if movement == 'Desplazar a la izquierda' else 1 - phase
        y = 0.5
    crop_width, crop_height = width / zoom, height / zoom
    left, top = (width - crop_width) * x, (height - crop_height) * y
    return image.transform(image.size, Image.Transform.EXTENT, (left, top, left + crop_width, top + crop_height),
                           resample=Image.Resampling.BICUBIC)
