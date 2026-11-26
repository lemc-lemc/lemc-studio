#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
"${EDITOR_PYTHON:-python3}" -m PyInstaller --noconfirm --windowed --onedir \
  --name editor-de-reels --add-data 'reel.json:.' --add-data 'icon.png:.' --add-data 'ascii_art.py:.' --add-data 'jinete_referencia.png:.' editor.py
cp -- LEEME.txt 'Modelo Whisper.txt' 'Ejemplo ASCII.json' 'Ejemplo ASCII desde video.json' 'Ejemplo Biblioteca.json' 'Aurora - Fuente.mp4' dist/editor-de-reels/
if compgen -G 'modelos/*.bin' > /dev/null; then
  cp -R -- modelos dist/editor-de-reels/
fi
"${EDITOR_PYTHON:-python3}" collect_notices.py dist/editor-de-reels/Licencias
