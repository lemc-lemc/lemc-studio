# LEMC Studio 8.3.7

Editor local de Windows para convertir fotos y videos en ASCII o pixel art, montar reels con letras sincronizadas y crear mundos ASCII animados. La aplicación, el render y la transcripción pueden ejecutarse sin conexión después de descargar el paquete completo.

## Empezar

1. Descarga **LEMC-Studio-8.3.7-Windows-x64-offline.zip** desde [Releases](https://github.com/lemc-lemc/lemc-studio/releases).
2. Extrae todo el ZIP. Abre **LEMC Studio.exe** y conserva las carpetas del programa junto al ejecutable.
3. Para convertir un clip, usa **Video rápido…**. Para aprender con una muestra, abre **Ejemplo ASCII desde video.json** o **Ver demostraciones…**.
4. Guarda el proyecto JSON junto a sus fuentes y usa **Exportar MP4** o **Exportar variantes**.

- [Manual para personas](docs/USO.md)
- [Automatización, CLI y proyectos JSON para asistentes](docs/AUTOMATIZACION.md)
- [Compilación, verificación y dependencias](docs/DESARROLLO.md)
- [Skill de producción para Claude Code](.claude/skills/lemc-studio/SKILL.md)
- [Skill y script de control de calidad](.claude/skills/verificar-reel/SKILL.md)
- [Manual incluido con el editor](src/LEEME.txt)

## Estructura

| Ruta | Contenido |
| --- | --- |
| `src/` | Editor Python, recursos, ejemplos y scripts de compilación |
| `docs/` | Uso, automatización y desarrollo |
| `.claude/skills/` | Instrucciones de producción y verificación |

El ZIP de Windows reúne el ejecutable, su entorno, FFmpeg, ffprobe, el modelo local de Whisper y sus avisos incluidos. El código se mantiene por separado para facilitar la revisión y la compilación.
