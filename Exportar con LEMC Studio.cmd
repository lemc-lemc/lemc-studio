@echo off
setlocal
set "APP=%~dp0LEMC Studio.exe"
if not exist "%APP%" (
    echo No se encontro LEMC Studio.exe junto al lanzador.
    exit /b 1
)
if "%~1"=="" (
    echo Uso: "%~nx0" --proyecto "Proyecto.json" --salida "Reel.mp4" --variantes una --informe "Informe nuevo.json"
    exit /b 2
)
if defined LEMC_STUDIO_TEMP (
    if not exist "%LEMC_STUDIO_TEMP%\." mkdir "%LEMC_STUDIO_TEMP%"
    if not exist "%LEMC_STUDIO_TEMP%\." exit /b 1
    set "TEMP=%LEMC_STUDIO_TEMP%"
    set "TMP=%LEMC_STUDIO_TEMP%"
)
start "" /b /wait "%APP%" --exportar %*
exit /b %errorlevel%
