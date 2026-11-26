$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $target = 'dist/LEMC Studio'
    python -m PyInstaller --noconfirm --windowed --onedir --name 'LEMC Studio' --icon icon.ico --add-data 'reel.json:.' --add-data 'icon.png:.' --add-data 'ascii_art.py:.' --add-data 'jinete_referencia.png:.' editor.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Copy-Item -LiteralPath 'LEEME.txt','Modelo Whisper.txt','Ejemplo ASCII.json','Ejemplo ASCII desde video.json','Ejemplo Biblioteca.json','Aurora - Fuente.mp4' -Destination $target
    if (Get-ChildItem -LiteralPath 'modelos' -Filter '*.bin' -ErrorAction SilentlyContinue | Select-Object -First 1) {
        Copy-Item -LiteralPath 'modelos' -Destination $target -Recurse
    }
    python collect_notices.py "$target/Licencias"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $ff = Get-Command ffmpeg -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    $fp = Get-Command ffprobe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ff -and $fp) {
        New-Item -ItemType Directory -Path "$target/bin" -Force | Out-Null
        Copy-Item -LiteralPath $ff.Source,$fp.Source -Destination "$target/bin"
        $license = Join-Path (Split-Path (Split-Path $ff.Source)) 'LICENSE.txt'
        if (Test-Path -LiteralPath $license) {
            Copy-Item -LiteralPath $license -Destination "$target/Licencias/FFmpeg-LICENSE.txt"
        }
    }
} finally {
    Pop-Location
}
