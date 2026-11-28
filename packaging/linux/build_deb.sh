#!/usr/bin/env bash
# Build the Ubuntu package from dist/JournalIssueBuilder (made by build_app.py).
#   bash packaging/linux/build_deb.sh 0.1.0
set -euo pipefail

VERSION="${1:?version, e.g. 0.1.0}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PKG="$ROOT/packaging/build/deb/journal-issue-builder_${VERSION}_amd64"

rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/journal-issue-builder" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/256x256/apps" \
         "$PKG/usr/share/doc/journal-issue-builder" "$PKG/usr/share/fonts/opentype/manjari"

cp -a "$ROOT/dist/JournalIssueBuilder/." "$PKG/opt/journal-issue-builder/"
ln -s /opt/journal-issue-builder/JournalIssueBuilder "$PKG/usr/bin/journal-issue-builder"
cp "$ROOT/packaging/build/icon.png" "$PKG/usr/share/icons/hicolor/256x256/apps/journal-issue-builder.png"
cp "$ROOT/LICENSE" "$PKG/usr/share/doc/journal-issue-builder/copyright"
cp "$ROOT/THIRD_PARTY_NOTICES.md" "$PKG/usr/share/doc/journal-issue-builder/THIRD_PARTY_NOTICES.md"
cp "$ROOT/packaging/linux/fonts/manjari/"*.otf "$PKG/usr/share/fonts/opentype/manjari/"
cp "$ROOT/packaging/linux/fonts/manjari/OFL.txt" \
   "$PKG/usr/share/doc/journal-issue-builder/Manjari-OFL.txt"

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v fc-cache >/dev/null 2>&1; then
    fc-cache -f >/dev/null 2>&1 || true
fi
exit 0
EOF
cat > "$PKG/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if command -v fc-cache >/dev/null 2>&1; then
    fc-cache -f >/dev/null 2>&1 || true
fi
exit 0
EOF
chmod 755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"

cat > "$PKG/usr/share/applications/journal-issue-builder.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Journal Issue Builder
Comment=Assemble journal issues from Word, ODT and PDF articles
Exec=journal-issue-builder
Icon=journal-issue-builder
Terminal=false
Categories=Office;Publishing;
EOF

SIZE_KB=$(du -sk "$PKG/opt" | cut -f1)
cat > "$PKG/DEBIAN/control" <<EOF
Package: journal-issue-builder
Version: ${VERSION}
Section: editors
Priority: optional
Architecture: amd64
Installed-Size: ${SIZE_KB}
Maintainer: Journal Issue Builder <noreply@example.org>
Depends: libxcb-cursor0, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1, libegl1, libgl1, libfontconfig1, libdbus-1-3
Recommends: libreoffice-writer, fonts-noto-core, ghostscript
Description: Assemble journal issues from Word, ODT and PDF articles
 Offline program that turns submitted articles into a finished journal
 issue: electronic PDF with bookmarks, print files for stapled or glued
 binding, covers with spine, and single-article offprints.
EOF

dpkg-deb --root-owner-group --build "$PKG" "$ROOT/dist/journal-issue-builder_${VERSION}_amd64.deb"
echo "Built $ROOT/dist/journal-issue-builder_${VERSION}_amd64.deb"
