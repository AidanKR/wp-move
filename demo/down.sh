#!/usr/bin/env bash
# Stop the demo pod. Add --purge to also delete containers and volumes (all demo data).
set -euo pipefail
POD=wpmove-demo
podman pod exists "$POD" && podman pod stop "$POD" >/dev/null && echo "stopped $POD"
if [ "${1:-}" = "--purge" ]; then
  podman pod rm -f "$POD" >/dev/null 2>&1 || true
  podman volume rm -f wpmove-db wpmove-wp >/dev/null 2>&1 || true
  echo "purged containers and volumes"
fi
