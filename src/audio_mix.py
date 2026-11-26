import math
import subprocess
from pathlib import Path

from media import PROCESS_OPTIONS, find_ffmpeg, find_program


DEFAULT_MIX = {'ganancia': 0.0, 'entrada': 0.0, 'salida': 0.0, 'nivelar': False,
               'pista_extra': '', 'ganancia_extra': -12.0, 'retardo_extra': 0.0, 'recorte_extra': 0.0}


def normalize(raw, folder=None):
    if raw is not None and not isinstance(raw, dict):
        raise ValueError('La mezcla de audio debe tener una configuración válida.')
    data = DEFAULT_MIX | (raw or {})
    for field, low, high in (('ganancia', -24, 12), ('entrada', 0, 12), ('salida', 0, 12),
                             ('ganancia_extra', -48, 6), ('retardo_extra', 0, 600), ('recorte_extra', 0, 3600)):
        try:
            value = float(str(data[field]).replace(',', '.'))
        except (ValueError, TypeError):
            value = float('nan')
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'«{field}» debe estar entre {low} y {high}.')
        data[field] = value
    if type(data['nivelar']) is not bool:
        raise ValueError('Nivelar el audio debe ser una opción activada o desactivada.')
    if not isinstance(data['pista_extra'], str):
        raise ValueError('Elige un archivo local para la segunda pista.')
    if data['pista_extra'] and folder is not None:
        data['pista_extra'] = str((folder / data['pista_extra']).resolve())
    return {key: data[key] for key in DEFAULT_MIX}


def extra_path(mix):
    filename = mix['pista_extra']
    if not filename:
        return None
    path = Path(filename)
    if not path.is_file():
        raise ValueError('No se encontró la segunda pista. Vuelve a elegirla en Mezcla de audio.')
    return path.resolve()


def portable(mix, folder):
    data = mix.copy()
    if data['pista_extra']:
        asset = Path(data['pista_extra'])
        if asset.parent == folder:
            data['pista_extra'] = asset.name
    return data


def duration(path):
    probe = find_program('ffprobe')
    if not probe:
        return None
    try:
        run = subprocess.run([probe, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-select_streams', 'a:0',
                              '-show_entries', 'stream=duration:format=duration', '-of', 'csv=p=0', str(path)],
                             capture_output=True, timeout=10, check=True, **PROCESS_OPTIONS)
        parsed = (float(value) for value in run.stdout.decode().split() if value not in ('N/A', ''))
        return next((value for value in parsed if math.isfinite(value) and value > 0), None)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def validate_track(path, start, end=None):
    if not path.is_file():
        raise ValueError(f'No se encontró la pista «{path.name}».')
    measured = duration(path)
    if measured is not None and start >= measured - .001:
        raise ValueError(f'El recorte empieza en {start:.2f} s, pero «{path.name}» dura {measured:.2f} s.')
    if measured is not None and end is not None and end > measured + .04:
        raise ValueError(f'El recorte termina en {end:.2f} s, pero «{path.name}» dura {measured:.2f} s.')
    args = [find_ffmpeg(), '-nostdin', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-ss', f'{start:.4f}',
            '-i', str(path), '-map', '0:a:0', '-vn', '-t', '0.075', '-ar', '8000', '-ac', '1', '-f', 's16le', 'pipe:1']
    result = subprocess.run(args, capture_output=True, timeout=12, **PROCESS_OPTIONS)
    if result.returncode or not result.stdout:
        raise ValueError(f'«{path.name}» no tiene audio decodificable desde {start:.2f} s.')
    return measured


def filters(mix, total, track_limit=None):
    limit = min(total, track_limit) if track_limit is not None else total
    chain = []
    if track_limit is not None:
        chain.append(f'atrim=duration={max(.001, limit):.5f}')
    if mix['nivelar']:
        chain.append('acompressor=threshold=0.14:ratio=2.7:attack=15:release=160:makeup=1.7')
    if mix['ganancia']:
        chain.append(f'volume={mix["ganancia"]:+.3f}dB')
    if mix['ganancia'] > 0 or mix['nivelar']:
        chain.append('alimiter=limit=0.95:latency=1:level=0')
    fades = mix['entrada'] + mix['salida']
    factor = min(1, limit / fades) if fades else 1
    if mix['entrada'] and factor > 0:
        chain.append(f'afade=t=in:st=0:d={mix["entrada"] * factor:.5f}')
    if mix['salida'] and factor > 0:
        tail = mix['salida'] * factor
        chain.append(f'afade=t=out:st={max(0, limit - tail):.5f}:d={tail:.5f}')
    return ','.join((*chain, 'apad'))


def mixing_graph(primary, mix):
    delay = round(mix['retardo_extra'] * 1000)
    volume = f'{mix["ganancia_extra"]:+.3f}dB'
    stereo = 'aresample=48000,aformat=channel_layouts=stereo'
    return (f'[1:a:0]{primary},{stereo}[principal];'
            f'[2:a:0]{stereo},volume={volume},adelay={delay}:all=1,apad[segunda];'
            '[principal][segunda]amix=inputs=2:duration=longest:normalize=0,'
            'alimiter=limit=0.96:latency=1:level=0[mezcla]')


def listening_clip(source, target, start, length, mix):
    cmd = [find_ffmpeg(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-protocol_whitelist', 'file,pipe',
           '-ss', f'{start:.3f}', '-i', str(source), '-map', '0:a:0', '-vn', '-t', f'{length:.3f}',
           '-af', filters(mix, length, length), '-c:a', 'pcm_s16le', str(target)]
    result = subprocess.run(cmd, capture_output=True, timeout=18, **PROCESS_OPTIONS)
    if result.returncode or not target.is_file():
        raise ValueError('No se pudo preparar el fragmento para escuchar.')
