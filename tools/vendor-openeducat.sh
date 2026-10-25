#!/bin/bash
# Vendor OpenEduCat (LGPL-3) for ICTERP Education at a pinned commit, with ICTERP presentation:
#  - app icons replaced with the ICTERP tiles from icterp_education/static/img
#  - static/description/index.html (OpenEduCat marketing pages) removed, so Apps shows our summary
#  - manifest display names "OpenEduCat X" -> "Education: X"
# Copyright headers, authors and the LICENSE file are left exactly as they are (LGPL attribution).
#   bash vendor-openeducat.sh <dest-dir>
set -e
PIN=46a5d7d400820d471b67b8c019997bfa5d3c873e   # openeducat_erp 19.0, 2026-10-13
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:?usage: vendor-openeducat.sh <dest-dir>}"
IMG="$HERE/../addons/icterp_education/static/img"
TMP=$(mktemp -d)
git clone -q -b 19.0 https://github.com/openeducat/openeducat_erp.git "$TMP/oe"
git -C "$TMP/oe" checkout -q $PIN
rm -rf "$TMP/oe/.git" "$TMP/oe/theme_web_openeducat"

declare -A ICON=(
  [openeducat_core]=education [openeducat_erp]=education [openeducat_admission]=admissions
  [openeducat_timetable]=timetable [openeducat_attendance]=attendance [openeducat_assignment]=assignments
  [openeducat_exam]=exams [openeducat_library]=library [openeducat_fees]=education
  [openeducat_parent]=students [openeducat_activity]=students [openeducat_classroom]=education
  [openeducat_facility]=education
)
for m in "$TMP"/oe/openeducat_*; do
  n=$(basename "$m")
  d="$m/static/description"
  [ -d "$d" ] || continue
  cp "$IMG/${ICON[$n]:-education}.png" "$d/icon.png"
  rm -f "$d/index.html"
done
cp "$IMG/education.png" "$TMP/oe/openeducat_core/static/description/sis.png"
cp "$IMG/students.png" "$TMP/oe/openeducat_core/static/description/icon_student.png"
# display names only
sed -i -E "s/^(\s*'name':\s*[\"'])OpenEduCat ERP([\"'])/\1Education\2/; s/^(\s*'name':\s*[\"'])OpenEduCat ([A-Za-z ]+)([\"'])/\1Education: \2\3/" "$TMP"/oe/openeducat_*/__manifest__.py
# never phone home to OpenEduCat (icterp_education also overrides the call)
sed -i -E "s|^OEC_API_ENDPOINT = .*|OEC_API_ENDPOINT = \"\"  # ICTERP: telemetry disabled|" "$TMP/oe/openeducat_core/models/update.py"
grep -q "^OEC_API_ENDPOINT = \"\"" "$TMP/oe/openeducat_core/models/update.py" || { echo "telemetry endpoint NOT blanked"; exit 1; }
rm -rf "$DEST" && mkdir -p "$(dirname "$DEST")" && mv "$TMP/oe" "$DEST" && rm -rf "$TMP"
echo "vendored openeducat $PIN -> $DEST"
grep -h "'name'" "$DEST"/openeducat_*/__manifest__.py | head -20
