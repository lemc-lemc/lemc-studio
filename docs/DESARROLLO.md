# Compilar, mantener y verificar

## Desde código fuente

Usa Python 3 con Tkinter y las dependencias de `src/requirements.txt`. Instala `src/requirements-build.txt` solo al empaquetar. El render requiere FFmpeg con libx264 y ffprobe. Para correr sin red, prepara esos componentes con antelación. Fuentes del sistema, Tk y medios disponibles afectan la vista previa.

~~~powershell
Set-Location src
python -m pip install -r requirements.txt
python editor.py
# Para compilar en Windows, instala las dependencias de compilación.
python -m pip install -r requirements-build.txt
& '.\build_windows.ps1'
~~~

El resultado del script de Windows queda en `src/dist/LEMC Studio`. El script incorpora FFmpeg y ffprobe si están en PATH, y el modelo de voz si está en `src/modelos`. Conserva el árbol completo al moverlo. Para Linux, usa `bash abrir-linux.sh` o `bash build-linux.sh` con Tkinter, FFmpeg y las fuentes indicadas en [LEEME](../src/LEEME.txt). El paquete oficial de esta entrega es Windows x64. Para el modelo local y su huella consulta [Modelo Whisper](../src/Modelo%20Whisper.txt).

## Mapa del código

| Área | Entradas |
| --- | --- |
| App, validación de proyectos, CLI y variantes | `editor.py`, `render.py`, `studio_ui.py` |
| ASCII, pixel art y mezcla ASCII/original | `ascii_art.py`, `ascii_controls.py`, `video_reveal.py` |
| Medios, cámara y personaje | `media.py`, `planos.py`, `personaje.py`, `movimiento_fondo.py` |
| Letra, tiempo y audio | `lyrics.py`, `audio_mix.py`, `reel_clock.py`, `timeline_ui.py` |
| Biblioteca y ejemplos | `designs.py`, `tool_gallery.py`, `arte_procedural.py` |
| Mundos y Campo de práctica | `mundos_ascii.py`, `juego_ascii.py`, `modelo_jinete.py`, `retrato_jinete.py`, `locomocion_ecuestre.py` |

Prueba la carga de los JSON de ejemplo antes de modificar formatos. Si cambias un control, verifica la vista previa y el render final por el camino que usa el editor. Para una entrega nueva, exporta una muestra corta desde una copia del ZIP extraído, abre el informe y comprueba el archivo con ffprobe. Reabre el editable desde su destino final.

## Distribución

Los binarios se publican en Releases y se acompañan con su SHA-256. El ZIP completo incluye los avisos disponibles de Python, NumPy, Pillow, PyInstaller, FFmpeg y Whisper. La procedencia del FFmpeg empaquetado está en [FFmpeg-origen](../src/FFmpeg-origen.txt). El modelo y su huella están documentados por separado. Conserva estos avisos al copiar o preparar una compilación. El repositorio se publica en modo privado.
