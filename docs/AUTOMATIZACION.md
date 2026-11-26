# Automatización de LEMC Studio 8.3.7

## Contrato de ejecución

Usa la carpeta de trabajo del encargo. El ejecutable empaquetado es una aplicación de ventana. El primer argumento **`--exportar`** activa el flujo sin interfaz. El lanzador `Exportar con LEMC Studio.cmd` del ZIP ya añade ese argumento. `editor.py --exportar` expone el mismo comando al trabajar desde fuente.

Elige exactamente una entrada, `--video` o `--proyecto`. Usa rutas absolutas para la llamada y conserva las referencias relativas en el JSON si sus medios viajan con él. El directorio del informe debe existir y su ruta debe ser nueva. Cuando el ejecutable no muestre texto, toma el código de salida y el informe JSON como evidencia. La pareja puede aparecer solo después de terminar ambas variantes.

~~~powershell
# Desde la raíz extraída del paquete. Sustituye las variables por rutas reales.
$exe = (Resolve-Path '.\LEMC Studio.exe').Path
$proyecto = (Resolve-Path '.\Ejemplo ASCII desde video.json').Path
$carpeta = Join-Path (Get-Location).Path 'pruebas'
New-Item -ItemType Directory -Path $carpeta -Force | Out-Null
$env:TEMP = $carpeta
$env:TMP = $carpeta
$salida = Join-Path $carpeta 'Muestra.mp4'
$informe = Join-Path $carpeta ('Muestra-' + [guid]::NewGuid() + '.json')
& '.\Exportar con LEMC Studio.cmd' --proyecto $proyecto --salida $salida --variantes una --duracion 3 --informe $informe
$codigo = $LASTEXITCODE
Get-Content -LiteralPath $informe -Raw -Encoding utf8
~~~

Usa una ruta de salida MP4 nueva al repetir la prueba. Para seguir un proceso de fondo en PowerShell 7, conserva su objeto y consulta `HasExited` antes de leer `ExitCode`:

~~~powershell
$psi = [Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $exe
$psi.WorkingDirectory = Split-Path -Parent $exe
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
foreach ($arg in @('--exportar','--proyecto',$proyecto,'--salida',$salida,
                   '--variantes','una','--duracion','3','--informe',$informe)) {
    $psi.ArgumentList.Add($arg)
}
$proceso = [Diagnostics.Process]::Start($psi)
$proceso.Id
# Comprueba en la misma sesión si $proceso.HasExited es $true.
# En ese caso, lee $proceso.ExitCode y el informe asociado.
~~~

Si la terminal usa un límite y devuelve 124, comprueba si el proceso y FFmpeg siguen activos antes de volver a lanzar el trabajo. Los archivos intermedios se pueden crear junto a la salida elegida. Para que una prueba quede en temporales, dirige también allí `--salida`.

## Argumentos

| Opción | Uso |
| --- | --- |
| `--proyecto RUTA.json` | Carga un editable existente |
| `--video RUTA.mp4` | Prepara Video rápido y escribe el editable junto al resultado |
| `--salida RUTA.mp4` | Archivo único o nombre base para variantes |
| `--variantes una\|dos\|tres` | Una salida con los ajustes del proyecto, pareja ASCII, o pareja más prueba 1440p. La pareja requiere una fuente o mundo compatible |
| `--duracion SEGUNDOS` | Sobrescribe la duración ASCII de esa ejecución |
| `--cambio-original SEGUNDOS` | Marca el cambio al original en una composición de video |
| `--fundido SEGUNDOS` | Ajusta el fundido al cambiar entre ASCII y video |
| `--giro auto\|izquierda\|derecha\|180` | Ajusta el giro de video según lo comprobado |
| `--repetir` | Activa bucle y, con una fuente de audio compatible, repetición de la pista completa. La repetición de pista completa exige inicio en cero y final vacío |
| `--informe NUEVO.json` | Escribe un informe independiente con las rutas reales o el error |

La exportación única rechaza sobrescribir un archivo. La pareja puede elegir un nombre numerado si la salida ya existe. Para proyectos guardados con `--proyecto`, el informe puede devolver `"proyecto": null` porque el comando no crea otro editable. Conserva el proyecto de entrada. Los informes de éxito tienen `ok: true` y `videos`. Cuando el error ocurre durante la exportación y se pudo habilitar el informe, recibes `ok: false` y `error`. Errores de argumentos previos a ese punto pueden ocurrir sin informe.

El modo especial `--mover-fondo montañas|luna FUENTE.mp4 DESTINO.mp4` sirve para los dos montajes navideños documentados en [LEEME](../src/LEEME.txt). Sus ajustes dependen del encuadre de esas fuentes.

## Editables JSON y decisiones de montaje

Parte de los [ejemplos](../src/) y escribe con un serializador UTF-8. La revisión del formato de proyecto de esta versión es 12. Conserva otros campos del proyecto cuando ajustes una sección. El modo de nivel superior es `ascii` o `letra`. La sección `animacion_ascii` contiene la composición ASCII. Los ajustes de salida están en la raíz:

~~~json
{
  "fps": 60,
  "calidad_video": "Máxima nitidez",
  "resolucion_video": "1080 × 1920"
}
~~~

| Sección ASCII | Campos frecuentes |
| --- | --- |
| Fuente y montaje | `fuente`, `archivo`, `figura`, `duracion`, `giro_video`, `ajuste`, `bucle`, `velocidad_video` |
| Aspecto | `estilo_media`, `modo_color`, `columnas`, `contraste`, `brillo`, `rampa`, `detalle_sombras`, `realzar_bordes` |
| Panel | `codigo`, `panel_compacto`, `opacidad_panel`, `archivo_panel`, `firma_ascii`, `panel_reactivo`, `mantener_codigo` |
| Original e híbrido | `fin_ascii`, `tramos_original`, `fundido_video`, `modo_hibrido`, `color_protagonista`, `tolerancia_color` |
| Audio | `sonido`, `pista`, `inicio`, `fin`, `repetir_audio` y objeto `mezcla` |
| Animación | `animacion_fuente`, `intensidad_movimiento`, `puntos_escape`, `planos_camara`, `archivo_personaje`, `movimiento_personaje` |
| Mundos | `figura`, `mundo_luz`, `mundo_clima`, `particulas` |

La duración ASCII es de 2 a 120 s. Los fps disponibles son 30 y 60. Las calidades son Máxima nitidez, Alta y Compacta. Resoluciones del selector: 720 × 1280, 1080 × 1920, 1080 × 2280 y 1440 × 2560. Ciertas escenas procedurales heredadas tienen salida fija de 1080 × 1440. Para los valores y límites completos consulta [la normalización ASCII](../src/ascii_art.py) y [el perfil de exportación](../src/render.py).

Para un video con audio de origen usa `sonido: "Audio del video"`. Para una pista externa usa `sonido: "Archivo de audio"` y `pista`. `Ambiente` añade una pista del editor. `Silencio` conserva el resultado sin sonido audible. La mezcla admite `ganancia`, `entrada`, `salida`, `nivelar`, `pista_extra`, `ganancia_extra`, `retardo_extra` y `recorte_extra`.

Para montaje mixto usa `tramos_original` como `5-10; 18-24; 30-` o el punto único `fin_ascii`. Activa `panel_reactivo` y comprueba distintos planos en el archivo. En conversión común, el flujo reactivo de video se activa al configurar un tramo original o un punto de cambio. Algunos mundos dibujan su panel por separado. Conserva el tratamiento que pidió el usuario y señala las limitaciones de cada modo.

## Verificación y entrega

Usa los nombres que devuelva el informe. Comprueba que el MP4 tenga la resolución, duración y frecuencia acordadas. Distingue 60 fps de codificación de un aumento real de movimiento cuando la fuente tiene menos fps. Abre el editable y resuelve sus medios. Escucha la pista para confirmar si es la original o la externa. Revisa cuadros claros y oscuros, encuadre, panel, texto y todas las transiciones. El [verificador](../.claude/skills/verificar-reel/SKILL.md) automatiza comprobaciones medibles.

En Claude Code, abre la raíz del repositorio e invoca **/lemc-studio** para producir y **/verificar-reel** para comprobar la entrega. Otros agentes pueden leer esta guía y los mismos archivos de skill directamente. Las rutas de producción y los medios del usuario quedan en el proyecto donde se realice el encargo.
