#!/bin/sh
set -eu
umask 077
DEPLOY_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKUP_DIR="$DEPLOY_DIR/../.local/backups"
mkdir -p "$BACKUP_DIR"
FILE="$BACKUP_DIR/travel-$(date -u +%Y%m%dT%H%M%SZ).dump"
TEMP="$FILE.tmp"
trap 'rm -f "$TEMP"' EXIT HUP INT TERM
sh "$DEPLOY_DIR/compose.sh" exec -T db pg_dump -U travel_owner -d travel_copilot -Fc < /dev/null > "$TEMP"
test -s "$TEMP"
mv "$TEMP" "$FILE"
echo "Backup saved: $FILE"
