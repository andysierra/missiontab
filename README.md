# MissionTab

**Mission Control de macOS para Linux MATE (X11).** Hermano de [ListTab](https://github.com/andysierra/Listtab).

`Ctrl+Super+↑` abre una vista a pantalla completa: arriba los escritorios virtuales, abajo las ventanas del
escritorio actual en mosaico, con su contenido real.

| Acción | Cómo |
|---|---|
| Ir a una ventana | clic en ella · flechas + Enter |
| Mover ventana a otro escritorio | arrastrarla sobre ese escritorio |
| Escritorio nuevo con una ventana | arrastrarla sobre **+** |
| Crear escritorio | **+** |
| Borrar escritorio | pasar el mouse → **×** (sus ventanas pasan al de la izquierda) |
| Ir a un escritorio | clic en él · `1`–`9` |
| Cambiar de escritorio sin salir | `Ctrl+←/→` |
| Salir | `Esc`, el atajo otra vez, o clic en el fondo |

## Cómo funciona

- Proceso residente (`missiontab --daemon`, autoarranque) que guarda miniaturas; el atajo (`missiontab`) solo le
  pide mostrar/ocultar la vista (Gtk.Application, una instancia) → abre al instante.
- Miniaturas: con el compositor de Marco se puede leer el contenido de cada ventana visible aunque esté tapada.
  Las de otros escritorios o minimizadas están desmapeadas (darían imagen vacía): se muestra la **última captura**
  guardada, o el ícono de la app si nunca se vio (igual que hace macOS).
- Ventanas y escritorios con libwnck; crear/borrar escritorios cambia `org.mate.Marco.general num-workspaces`.

## Desarrollo

```bash
bin/missiontab --list              # escritorios y ventanas
bin/missiontab --render=/tmp/x.png # dibujar la vista en un PNG sin mostrarla
touch ~/.missiontab-debug          # log en ~/.cache/missiontab.log
```

Requiere Python 3, GTK 3, libwnck, compositor activo (todo viene en Linux Mint MATE).
