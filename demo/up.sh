#!/usr/bin/env bash
# Local WordPress demo for wp-move: MariaDB + WordPress in one podman pod, bound to 127.0.0.1 only.
set -euo pipefail
cd "$(dirname "$0")"

POD=wpmove-demo
PORT="${WPMOVE_DEMO_PORT:-8088}"
WP_IMAGE=docker.io/library/wordpress@sha256:e6d455d4a733131f44d4e33037a7f5f3897ed100d30518a0b09d27fa96d589bd   # 7.1.3-php8.4-apache
DB_IMAGE=docker.io/library/mariadb@sha256:3607e75203fd9f69fb7e0829ec2d8fe55c30ec9d8aa266f7580719711bb4a4e1     # 11.8.9

# Test-only secrets, generated once and kept in .env (gitignored).
if [ ! -f .env ]; then
  umask 077
  {
    echo "DB_PASSWORD=$(openssl rand -hex 16)"
    echo "DB_ROOT_PASSWORD=$(openssl rand -hex 16)"
    echo "WP_ADMIN_USER=demo-admin"
    echo "WP_ADMIN_PASSWORD=$(openssl rand -hex 16)"
  } > .env
fi
set -a; . ./.env; set +a

if podman pod exists "$POD"; then
  podman pod start "$POD" >/dev/null
else
  podman pod create --name "$POD" -p "127.0.0.1:${PORT}:80" >/dev/null
  podman volume create wpmove-db >/dev/null 2>&1 || true
  podman volume create wpmove-wp >/dev/null 2>&1 || true
  podman run -d --pod "$POD" --name wpmove-db \
    -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress \
    -e MARIADB_PASSWORD="$DB_PASSWORD" -e MARIADB_ROOT_PASSWORD="$DB_ROOT_PASSWORD" \
    -v wpmove-db:/var/lib/mysql "$DB_IMAGE" >/dev/null
  podman run -d --pod "$POD" --name wpmove-wp \
    -e WORDPRESS_DB_HOST=127.0.0.1 -e WORDPRESS_DB_NAME=wordpress \
    -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD="$DB_PASSWORD" \
    -e WORDPRESS_CONFIG_EXTRA="define('WP_ENVIRONMENT_TYPE', 'local');" \
    -v wpmove-wp:/var/www/html "$WP_IMAGE" >/dev/null
fi

for _ in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/" || true)
  case "$code" in 200|301|302) echo "up: http://127.0.0.1:${PORT}/ (HTTP $code)"; exit 0;; esac
  sleep 2
done
echo "WordPress did not answer on port ${PORT}" >&2
exit 1
