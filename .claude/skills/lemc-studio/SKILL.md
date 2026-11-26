---
name: lemc-studio
description: Usa LEMC Studio en el proyecto Reels de Windows para abrir, preparar, editar, exportar o verificar reels ASCII, composiciones híbridas, video lyrics y mundos ASCII. Aplica cuando el usuario pide trabajar con el editor, reutilizar proyectos o añadir una capacidad concreta de LEMC Studio.
argument-hint: "[tarea, fuentes y resultados esperados]"
---

# LEMC Studio en el proyecto activo

Respeta las rutas y las instrucciones del proyecto del encargo. Separa las fuentes, los temporales y los finales. Configura TEMP y TMP para los procesos que lances. Verifica qué versión ejecutas y abre el manual de esa instalación antes de cambiar el editor. Para la versión de este repositorio consulta el [manual de uso](../../../docs/USO.md) y la [guía de automatización](../../../docs/AUTOMATIZACION.md).

El ZIP de Windows trae ejecutable, FFmpeg, ffprobe y Whisper local. Desde fuente usa el editor y sus dependencias documentadas. Mantén el render y la transcripción en local. Usa el lanzador de la instalación extraída o llama al ejecutable con --exportar como primer argumento. Lee los nombres devueltos por el informe. Antes de entregar, usa /verificar-reel.
## Flujo normal

1. Inspecciona la fuente con el `ffprobe` del paquete. Revisa dimensiones, duración, fps, audio y metadatos de rotación. En clips girados verifica fotogramas para elegir el sentido. Localiza un proyecto editable del mismo tipo o un `Ejemplo*.json` del editor.
2. Usa primero los controles existentes o adapta el JSON válido. Consulta `LEEME.txt` antes de añadir parámetros. Usa el lanzador de exportación para tareas repetibles y la interfaz para encuadre, máscaras, sincronía o inspección visual. Una prueba corta en Z: sirve para validar antes de gastar tiempo en una exportación completa.
3. En PowerShell, desde la raíz, estas son dos rutas comprobables. Sustituye las rutas por archivos reales y usa un informe con nombre nuevo. Con el .cmd se omite `--exportar`. Si llamas al exe directamente, inclúyelo.

~~~powershell
& '.\Exportar con LEMC Studio.cmd' --help
& '.\Exportar con LEMC Studio.cmd' --video '.\fuente.mp4' --salida '.\outputs\Reels emparejados\Nombre\Reel.mp4' --variantes dos
& '.\Exportar con LEMC Studio.cmd' --proyecto '.\outputs\Reels emparejados\Nombre\Proyecto ASCII.json' --salida '.\outputs\Reels emparejados\Nombre\Reel.mp4' --variantes una --informe '.\Temporales\LEMC Studio\Nombre-informe.json'
~~~

- `--video` sirve para el flujo rápido y guarda su JSON. `--proyecto` conserva la composición que preparaste. Usa `--variantes dos` para la pareja habitual si el modo la admite. Usa `una` para una variante explícita y comprueba que el JSON lleve el ajuste de panel correspondiente. `tres` agrega una prueba a 1440p cuando se solicita y la versión lo admite.
- La interfaz admite duración, encuadre, panel y mezcla. El lanzador reciente también ofrece `--duracion`, `--giro`, `--repetir`, `--cambio-original` y `--fundido`. Para varios tramos ASCII/original, pista externa o ajustes finos, usa el JSON real de la versión. Verifica las opciones de audio antes de usar `--repetir`, que puede activar la repetición de la pista completa.
- Para reels ASCII aplica 1080 × 1920, 60 fps y Máxima nitidez como punto de partida. Respeta el encuadre, formato, pista, duración y variantes que indique el usuario. Si hay panel, activa «Adaptar el color del panel a la escena» donde esté disponible y comprueba la legibilidad. Solo ASCII va a pantalla completa, sin panel ni firma. Para video lyrics, conserva transcripción y tiempos editables y comprueba la sincronía con el canto.
- Verifica el código de salida y el informe cuando lo uses. Comprueba resolución, fps, duración y audio con ffprobe. Mira fotogramas del inicio, las transiciones y el cierre, y comprueba que el editable reabra con sus fuentes. Entrega en `outputs\Reels emparejados\<reel>` los MP4 pedidos, el proyecto y las fuentes que requiera. Usa referencias relativas si las fuentes están junto al proyecto. Retira únicamente tus pruebas e intermedios identificados una vez verificados los finales.

## Solo si hace falta añadir capacidad

Busca primero la función en la versión detectada. Puntos de entrada habituales:

| Necesidad | Código existente |
| --- | --- |
| Carga y guardado, interfaz y exportación por comando | `editor.py`, `ascii_controls.py`, `render.py` |
| Composición ASCII, híbrido, encuadre y fundido al original | `ascii_art.py`, `video_reveal.py`, `media.py`, `planos.py` |
| Audio y letras | `audio_mix.py`, `lyrics.py`, `reel_clock.py` |
| Figuras, escenas y personaje | `arte_procedural.py`, `personaje.py`, `movimiento_fondo.py`; para Mundos ASCII busca los módulos disponibles en la versión abierta |

Aplica el cambio mínimo al editor real y prueba el flujo que usará el usuario, incluido abrir proyectos anteriores cuando cambie el esquema. Evita crear un renderizador paralelo, un segundo editor o un instalador para una tarea que ya resuelve LEMC Studio. Diferencia en la entrega qué versión usaste, qué verificaste y qué depende de funciones de otra versión.

