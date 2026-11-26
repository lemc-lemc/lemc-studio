[CmdletBinding()]
param(
    [Parameter(Mandatory)][string[]]$Videos,
    [Parameter(Mandatory)][string]$Proyecto,
    [Parameter(Mandatory)][string]$FFprobe,
    [Parameter(Mandatory)][ValidateRange(1,3)][int]$Variantes,
    [Parameter(Mandatory)][ValidateRange(30,60)][int]$Fps,
    [Parameter(Mandatory)][ValidateRange(1,16384)][int]$Ancho,
    [Parameter(Mandatory)][ValidateRange(1,16384)][int]$Alto,
    [Parameter(Mandatory)][ValidateRange(0.1,3600.0)][double]$Duracion,
    [switch]$AudioRequerido
)

$ErrorActionPreference = 'Stop'
$failures = [Collections.Generic.List[string]]::new()
function Add-Problem([string]$Message) {
    $failures.Add($Message)
}
function Require-Media([string]$Name, [string]$Value) {
    if (-not $Value) { return }
    $candidate = if ([IO.Path]::IsPathRooted($Value)) { $Value } else { Join-Path $baseDir $Value }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        Add-Problem "$Name no disponible en $candidate"
    }
}

try {
    $probe = (Get-Item -LiteralPath $FFprobe).FullName
    $projectPath = (Get-Item -LiteralPath $Proyecto).FullName
    $baseDir = Split-Path -Parent $projectPath
    $data = Get-Content -LiteralPath $projectPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Fps -notin @(30,60)) { Add-Problem 'LEMC Studio admite 30 o 60 fps.' }
    if ($Videos.Count -ne $Variantes) {
        Add-Problem "Variantes esperadas $Variantes, recibidas $($Videos.Count)."
    }
    if ($null -eq $data.titulo -or @($data.titulo).Count -ne 2 -or -not $data.escenas) {
        Add-Problem 'El editable requiere un título de dos líneas y al menos una escena.'
    }
    if ($data.version_proyecto -gt 12) { Add-Problem 'El formato del editable supera la versión 12.' }
    if ($data.fps -and $data.fps -ne $Fps) { Add-Problem "FPS del editable $($data.fps), esperados $Fps." }
    if ($data.modo -eq 'ascii' -or (-not $data.modo -and $data.animacion_ascii)) {
        $settings = $data.animacion_ascii
        if ($settings.fuente -in @('Video','Imagen') -and -not $settings.archivo) {
            Add-Problem 'El editable ASCII no identifica su fuente.'
        }
        if ($settings.sonido -eq 'Archivo de audio' -and -not $settings.pista) {
            Add-Problem 'El editable selecciona Archivo de audio sin indicar una pista.'
        }
        Require-Media 'Fuente ASCII' $settings.archivo
        Require-Media 'Pista ASCII' $settings.pista
        Require-Media 'Personaje' $settings.archivo_personaje
        Require-Media 'Pista secundaria ASCII' $settings.mezcla.pista_extra
    } elseif ($data.modo -eq 'letra' -or -not $data.modo) {
        Require-Media 'Pista de letra' $data.audio_local
        Require-Media 'Pista secundaria de letra' $data.mezcla_audio.pista_extra
        foreach ($scene in $data.escenas) { Require-Media 'Fondo de escena' $scene.fondo_media.archivo }
    } else {
        Add-Problem "Modo de proyecto desconocido $($data.modo)."
    }
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($video in $Videos) {
        if (-not (Test-Path -LiteralPath $video -PathType Leaf)) {
            Add-Problem "No existe $video"
            continue
        }
        $file = (Get-Item -LiteralPath $video).FullName
        if (-not $seen.Add($file)) {
            Add-Problem "Variante repetida $file"
            continue
        }
        $json = & $probe -v error -show_entries 'stream=codec_type,width,height,avg_frame_rate,duration:format=duration' -of json $file
        if ($LASTEXITCODE -ne 0) {
            Add-Problem "ffprobe no pudo leer $file"
            continue
        }
        $metadata = ($json -join "`n") | ConvertFrom-Json
        $stream = $metadata.streams | Where-Object codec_type -eq 'video' | Select-Object -First 1
        if (-not $stream) {
            Add-Problem "No hay pista de video en $file"
            continue
        }
        if ($stream.width -ne $Ancho -or $stream.height -ne $Alto) {
            Add-Problem "$file tiene $($stream.width) × $($stream.height). Se esperaba $Ancho × $Alto."
        }
        $rate = $stream.avg_frame_rate -split '/'
        if ($rate.Count -ne 2 -or [double]$rate[1] -le 0 -or [math]::Abs(([double]$rate[0]/[double]$rate[1])-$Fps) -gt .01) {
            Add-Problem "$file tiene $($stream.avg_frame_rate) fps. Se esperaba $Fps."
        }
        $durationText = if ($stream.duration -and $stream.duration -ne 'N/A') { $stream.duration } else { $metadata.format.duration }
        $seconds = 0.0
        if (-not [double]::TryParse($durationText,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$seconds) -or
            [math]::Abs($seconds-$Duracion) -gt [math]::Max(.08,1.5/$Fps)) {
            Add-Problem "$file tiene duración $durationText s. Se esperaba $Duracion s."
        }
        if ($AudioRequerido -and -not ($metadata.streams | Where-Object codec_type -eq 'audio')) {
            Add-Problem "Falta la pista de audio en $file"
        }
        Write-Output "$file | $($stream.width) × $($stream.height) | $($stream.avg_frame_rate) fps | $durationText s"
    }
} catch {
    Add-Problem $_.Exception.Message
}

if ($failures.Count) {
    foreach ($failure in $failures) { [Console]::Error.WriteLine($failure) }
    exit 1
}
Write-Output 'Comprobación técnica aprobada. Revisa fotogramas, pista correcta y efectos antes de entregar.'
exit 0
