#!/bin/bash
# Fetch OCA Payroll 19.0 (LGPL-3) at the commit ICTERP is tested with.
#   bash tools/fetch-oca-payroll.sh <dest-dir>
set -e
PIN=58f8a39799383ef98d50097f81f4abcc6dd03782   # OCA/payroll 19.0, 2026-10-05
DEST="${1:?usage: fetch-oca-payroll.sh <dest-dir>}"
rm -rf "$DEST" && mkdir -p "$(dirname "$DEST")"
git clone -q -b 19.0 https://github.com/OCA/payroll.git "$DEST"
git -C "$DEST" checkout -q $PIN
rm -rf "$DEST/.git"
echo "OCA payroll $PIN -> $DEST"
