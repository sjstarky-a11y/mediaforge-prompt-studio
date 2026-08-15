#!/usr/bin/env bash
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEDIAFORGE_HOME="$PACKAGE_ROOT/MediaForge-System"
if [ ! -f "$MEDIAFORGE_HOME/install.sh" ]; then
    MEDIAFORGE_HOME="$PACKAGE_ROOT"
fi

action="${1-}"
if [ "$#" -gt 0 ]; then
    shift
fi

case "$action" in
    "")
        if [ -f "$MEDIAFORGE_HOME/.env" ]; then
            exec "$MEDIAFORGE_HOME/start.sh"
        fi
        exec "$MEDIAFORGE_HOME/install.sh"
        ;;
    install) exec "$MEDIAFORGE_HOME/install.sh" "$@" ;;
    start) exec "$MEDIAFORGE_HOME/start.sh" "$@" ;;
    status) exec "$MEDIAFORGE_HOME/status.sh" "$@" ;;
    doctor) exec "$MEDIAFORGE_HOME/doctor.sh" "$@" ;;
    stop) exec "$MEDIAFORGE_HOME/stop.sh" "$@" ;;
    *)
        printf 'Usage: ./MediaForge-Linux.sh [install|start|status|doctor|stop]\n' >&2
        exit 2
        ;;
esac
