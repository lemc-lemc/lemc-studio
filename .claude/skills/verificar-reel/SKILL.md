---
name: verificar-reel
description: Comprueba los MP4 y el editable de un reel LEMC Studio antes de entregarlo, incluidos fps, dimensiones, duración, variantes y fuentes.
---

Lee las expectativas del encargo y el informe de LEMC Studio. Usa las rutas de los MP4 que enumere el informe. Usa el ffprobe local del paquete. Para la prueba 1440p ejecuta otra comprobación con sus dimensiones. El tercer MP4 tiene resolución distinta al par principal.

~~~powershell
& $verificador -Videos $mp4s -Proyecto $editable -FFprobe $ffprobe `
  -Variantes 2 -Fps 60 -Ancho 1080 -Alto 1920 -Duracion 21.8 -AudioRequerido
~~~

El script está en `scripts/Verificar-Reel.ps1` junto a este archivo. `-AudioRequerido` verifica presencia de una pista. Verifica por separado cuál pista se oye. El script devuelve 1 cuando falla una comprobación. Ajusta los valores a lo que pidió el usuario y conserva los MP4 elegidos.

Mira fotogramas del inicio, cambios y cierre. Comprueba encuadre, orientación, color, texto y panel. Si hay panel dinámico, compara la misma zona en dos escenas con paletas distintas. Escucha fuente, cortes y sincronía. Abre el editable para confirmar que reproduce el montaje acordado. El resultado técnico y la inspección audiovisual deben corresponder a los mismos MP4.
