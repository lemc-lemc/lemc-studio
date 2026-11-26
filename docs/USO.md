# Manual de uso de LEMC Studio 8.3.7

## Abrir y guardar

En Windows x64, extrae el ZIP completo y abre **LEMC Studio.exe**. Mantén **_internal**, **bin** y **modelos** junto al ejecutable. Guarda cada proyecto en su propia carpeta con el JSON y sus videos, imágenes y audios. Si vas a moverlo, mueve también sus fuentes. **Ctrl+S** guarda y **Ctrl+1 / Ctrl+2** cambia entre Letra y código y ASCII. La pestaña activa determina qué se exporta.

## Convertir video o imagen en ASCII

1. Pulsa **Video rápido…** para partir de un clip local con el audio de origen cuando esté disponible, o elige **Imagen**, **Video** o **Figura 3D** en **ASCII → Composición**.
2. En **Conversión de archivos**, compara **Encajar** y **Recortar**. Verifica la orientación con un fotograma, en especial cuando el archivo trae rotación. Ajusta columnas, contraste, brillo, color y rampa de caracteres. Comprueba planos oscuros y claros. Para conservar textura, prueba primero contraste, sombras o contornos antes de aumentar mucho el brillo.
3. Elige **ASCII** o **Pixel art**. En **Modo híbrido** puedes convertir **Entorno en ASCII** o **Protagonista en ASCII** con una selección por color. Comprueba la tolerancia durante el clip si hay objetos de tono parecido.
4. Usa el deslizador para revisar el inicio, los cambios y el cierre. Para una previsualización con audio, pulsa **Reel con audio**.

### Animación, cámara y montaje

- **Animar y extender** ofrece Ascenso, Acercamiento y Recorrido lateral. En video, activa la repetición si quieres extenderlo a velocidad normal. Sin bucle, el último fotograma puede quedar fijo. Para humo o estela de una imagen, configura los puntos de salida según su forma.
- **Planos de cámara** acepta marcas de inicio y fin, zoom y posición. Ejemplo `0-5,1,.5,.5,1.3,.6,.65; 5-10,1.2,.5,.4,1,.5,.5`.
- **Personaje** admite PNG transparente o APNG/WebP animado, con posición, escala y giro propios. Ejemplo de marcas `0,.22,.55,.28,-8; 4,.65,.40,.34,8`.
- **Montaje de video** permite pasar de ASCII al original o alternar intervalos como `5-10; 18-24; 30-`. Ajusta el fundido, escucha el golpe musical y verifica cada cambio. El panel puede permanecer encima del original. El panel dinámico de este flujo tiñe marco, fondo y línea activa con los colores del clip. Compruébalo en escenas de colores distintos.
- **Efectos y formato** reúne opciones como nieve, luces y destellos marcados. **Ver demostraciones…** muestra ejemplos y enlaza con sus controles.

### Audio y salida

En **Audio ASCII** elige **Audio del video**, **Archivo de audio**, **Silencio** o **Ambiente**. Conserva el audio de origen por defecto cuando así lo requiera el encargo. Con **Mezcla y fundidos** puedes ajustar niveles, recortar y añadir una pista secundaria. Escucha la pista final y las uniones de repeticiones.

En **Exportación**, elige resolución, 30 o 60 fps y calidad. El perfil habitual de Reels vertical es **1080 × 1920, 60 fps, Máxima nitidez**. El selector del editor ofrece formatos verticales. El Campo de práctica usa una ventana horizontal independiente. Cambiar los fps de salida no recupera fotogramas que falten en la fuente.

**Exportar variantes** genera con código y solo ASCII, o con código y sin código si ambos incluyen tramos originales. La versión limpia omite panel, firma y texto de composición. Comprueba que el editable corresponde al montaje y guarda los dos MP4 juntos cuando se pidan.

## Letra y código

1. En **Audio y transcripción**, elige la pista local. Usa **Letra automática…** o **Transcribir…** y selecciona el tramo. El modelo local requiere el soporte Whisper de FFmpeg. También puedes importar texto, SRT o LRC.
2. Revisa palabras y tiempos sobre el canto. En **Tiempos por palabra…**, escucha, ajusta y vuelve a previsualizar. Las marcas automáticas son un punto de partida. En **Guion y escenas** se editan y reordenan las escenas.
3. En **Diseño y código** configura fondos, figuras, fuentes y temas. **Imagen o video…** permite usar medios locales y ajustar el velo. Ajusta los destellos reactivos a bajos con sensibilidad y espaciado para que se distingan los golpes.
4. Prueba **Ver escena** y **Reel con audio** antes de exportar. Si el encargo pide solo el título de canción u omitir firma, aplícalo en el editable.

## Mundos ASCII y Campo de práctica

En **ASCII → Mundos ASCII**, elige **La ruta del vigía**, **Bosque de la lluvia**, **Vado de la luna** o **Puerta de las brasas**. Ajusta iluminación, clima, partículas y duración. **Cargar mundo** prepara una composición exportable. **Jugar · Campo de práctica** abre la vista interactiva horizontal en 16:9. El caballo del Campo de práctica se representa de perfil en 2.5D a partir de una imagen articulada. Los mundos exportables y el Campo de práctica tienen flujos distintos.

| Acción | Control |
| --- | --- |
| Avanzar y frenar | W / S o ↑ / ↓ |
| Girar al cabalgar | A / D o ← / → |
| Zoom | + / − |
| Armadura | 1, 2, 3 |
| Vista de inspección lateral | V |
| Volver o cerrar | V para volver de inspección, Esc para cerrar |

Clima, iluminación y escenario se eligen en sus controles. La inspección de esta versión desplaza el perfil, y el personaje cambia de lado mediante espejado. La ventana de práctica no se exporta como recorrido controlado mediante el comando de mundo.

## Entrega y actualización

Abre el MP4 final, mira inicio, cambios y cierre. Escucha el audio y vuelve a abrir el editable desde la carpeta que entregarás. Conserva originales y artefactos finales. Extrae una versión nueva en otra carpeta para mantener recuperables tanto la instalación anterior como tus proyectos.
