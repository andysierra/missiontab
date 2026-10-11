#!/bin/bash
# Construye dist/missiontab_<versión>_all.deb (Python puro: arquitectura "all").
#   /usr/bin/missiontab                                   lanzador
#   /usr/lib/missiontab/{missiontab,resources}/           programa
#   /usr/share/applications/missiontab.desktop            menú / rofi (abre la vista)
#   /etc/xdg/autostart/missiontab.desktop                 proceso residente en cada inicio de sesión
#   /usr/share/icons/hicolor/scalable/apps/missiontab.svg ícono
#   /usr/share/doc/missiontab/                            README y copyright
# El atajo Ctrl+Super+↑ lo crea la propia app al arrancar (un paquete no puede tocar la sesión del usuario).
# Uso: packaging/build-deb.sh
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(python3 -c "import re; print(re.search(r'__version__ = \"(.+)\"', open('missiontab/__init__.py').read())[1])")
PKG=missiontab
OUT=dist/${PKG}_${VERSION}_all.deb
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT

install -d "$ROOT/DEBIAN" "$ROOT/etc/xdg/autostart" "$ROOT/usr/bin" "$ROOT/usr/lib/$PKG" \
           "$ROOT/usr/share/applications" "$ROOT/usr/share/icons/hicolor/scalable/apps" "$ROOT/usr/share/doc/$PKG"
cp -r missiontab resources "$ROOT/usr/lib/$PKG/"
find "$ROOT/usr/lib/$PKG" -name __pycache__ -type d -prune -exec rm -rf {} +

cat > "$ROOT/usr/bin/missiontab" <<'SH'
#!/bin/sh
exec env PYTHONPATH=/usr/lib/missiontab${PYTHONPATH:+:$PYTHONPATH} python3 -m missiontab "$@"
SH
install -m644 resources/missiontab.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/missiontab.svg"

cat > "$ROOT/usr/share/applications/missiontab.desktop" <<'DESK'
[Desktop Entry]
Type=Application
Name=MissionTab
GenericName=Mission Control
Comment=Escritorios y ventanas a la vista: ir, mover y organizar (Ctrl+Super+Arriba)
Exec=missiontab
Icon=missiontab
Terminal=false
Categories=Utility;
Keywords=mission control;expose;workspaces;escritorios;ventanas;spaces;
StartupNotify=false
DESK
cat > "$ROOT/etc/xdg/autostart/missiontab.desktop" <<'DESK'
[Desktop Entry]
Type=Application
Name=MissionTab
Comment=Mission Control (proceso residente; Ctrl+Super+Arriba muestra la vista)
Exec=missiontab --daemon
Icon=missiontab
OnlyShowIn=MATE;
X-MATE-Autostart-enabled=true
NoDisplay=true
DESK

install -m644 README.md "$ROOT/usr/share/doc/$PKG/README.md"
{ echo "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
  echo "Upstream-Name: MissionTab"
  echo "Source: https://github.com/andysierra/missiontab"
  echo
  echo "Files: *"
  echo "License: MIT"
  sed 's/^$/./; s/^/ /' LICENSE; } > "$ROOT/usr/share/doc/$PKG/copyright"

cat > "$ROOT/DEBIAN/control" <<CTRL
Package: $PKG
Version: $VERSION
Architecture: all
Maintainer: andysierra <camilo-hormiga@hotmail.com>
Homepage: https://github.com/andysierra/missiontab
Section: x11
Priority: optional
Installed-Size: $(du -sk "$ROOT/usr" | cut -f1)
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, python3-cairo, gir1.2-gtk-3.0, gir1.2-wnck-3.0
Description: Mission Control for the MATE desktop (X11)
 A macOS-style Mission Control: Ctrl+Super+Up shows every workspace at the top
 and the windows of the current one tiled with their live contents. Click a
 window to go there, drag windows between workspaces (or onto + for a new
 one), add and remove workspaces, hover a workspace to preview it.
 .
 Starts automatically at every login. Right after installing, open it once
 from the applications menu (or log out and back in).
CTRL

for s in postinst postrm; do
cat > "$ROOT/DEBIAN/$s" <<'HOOK'
#!/bin/sh
set -e
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
exit 0
HOOK
done
chmod -R u+rwX,go+rX,go-w "$ROOT"
chmod 755 "$ROOT/usr/bin/missiontab" "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/postrm"
mkdir -p dist
fakeroot dpkg-deb --build --root-owner-group "$ROOT" "$OUT" >/dev/null
echo "$OUT"
