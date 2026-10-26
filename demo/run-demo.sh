#!/usr/bin/env bash
# End-to-end demo: local WordPress -> wp-move pull -> report, then break a copy and show the report catch it,
# then serve the generated nginx redirects and request every old URL.
set -uo pipefail
cd "$(dirname "$0")/.."
NGINX_IMAGE=docker.io/library/nginx@sha256:3abad30db61dfb2a339ea21acc9f3e6bbe78e291fcff2f835f4510c8fdfcbd83  # 1.30.5-alpine

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

step "1. Start the demo WordPress and seed it"
demo/up.sh && demo/seed.sh | tail -1 || exit 1
set -a; . demo/.env; set +a

step "2. Move it: wp-move pull (authenticated, so drafts and scheduled posts come too)"
rm -rf out out-broken
uv run wp-move pull http://127.0.0.1:8088 --out out
echo "exit code: $?"

step "3. Break a copy: delete one image and one post, then re-check"
cp -R out out-broken
rm out-broken/public/media/2008/06/windmill.jpg out-broken/content/posts/verse.md
uv run wp-move report --out out-broken
echo "exit code: $?"

step "4. Serve the generated nginx redirects and request every old URL"
mkdir -p out/.nginx
printf 'events {}\nhttp {\n  include /redirects/nginx-maps.conf;\n  server {\n    listen 8090;\n    root /site;\n    include /redirects/nginx-server.conf;\n  }\n}\n' > out/.nginx/nginx.conf
podman rm -f wpmove-nginx >/dev/null 2>&1
podman run -d --name wpmove-nginx -p 127.0.0.1:8090:8090 \
  -v "$PWD/out/.nginx/nginx.conf:/etc/nginx/nginx.conf:ro" -v "$PWD/out/redirects:/redirects:ro" \
  -v "$PWD/out/public:/site:ro" "$NGINX_IMAGE" >/dev/null
sleep 2
uv run wp-move report --out out --server http://127.0.0.1:8090
echo "exit code: $?"
podman rm -f wpmove-nginx >/dev/null

step "Done. Open out/report.html and out-broken/report.html. Stop with: demo/down.sh && podman machine stop"
