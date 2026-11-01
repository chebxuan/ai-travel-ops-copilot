#!/bin/sh
set -eu
DEPLOY_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ ! -f "$DEPLOY_DIR/.env.production" ]; then
    echo 'First run: python3 deploy/configure.py --site http://SERVER_IP' >&2
    exit 1
fi
exec docker compose --env-file "$DEPLOY_DIR/.env.production" -f "$DEPLOY_DIR/compose.yaml" "$@"
