#!/usr/bin/env bash
# Install WordPress and import the official theme test data (pinned commit + sha256) into the local demo.
set -euo pipefail
cd "$(dirname "$0")"
set -a; . ./.env; set +a

POD=wpmove-demo
PORT="${WPMOVE_DEMO_PORT:-8088}"
CLI_IMAGE=docker.io/library/wordpress@sha256:7456afaf39a18829d4c9a291b8dea74285d3ee8aaf03f087723aca6bc8b6e3d3  # cli-2.12.0-php8.4
IMPORTER_VERSION=0.9.7
DATA_COMMIT=b47acf980696
DATA_FILES=(
  "themeunittestdata.wordpress.xml 457aace6ec93cf77369bbcc6158996e52da8798bd5e39c83d58dfab9b50d64fa"
  "64-block-test-data.xml 59e0eefd78087740f7ee98253666a7697ad57e1f2e7a80f6b8d74ae397072aea"
)

mkdir -p data
for entry in "${DATA_FILES[@]}"; do
  set -- $entry
  if [ ! -f "data/$1" ]; then
    curl -fsSL "https://raw.githubusercontent.com/WordPress/theme-test-data/${DATA_COMMIT}/$1" -o "data/$1"
  fi
  echo "$2  data/$1" | shasum -a 256 -c -
done

wp() {
  podman run --rm --pod "$POD" --user 33:33 \
    -e WORDPRESS_DB_HOST=127.0.0.1 -e WORDPRESS_DB_NAME=wordpress \
    -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD="$DB_PASSWORD" \
    -v wpmove-wp:/var/www/html -v "$PWD/data:/data:ro" \
    "$CLI_IMAGE" wp "$@"
}

if ! wp core is-installed 2>/dev/null; then
  wp core install --url="http://127.0.0.1:${PORT}" --title="wp-move demo" \
    --admin_user="$WP_ADMIN_USER" --admin_password="$WP_ADMIN_PASSWORD" \
    --admin_email=demo@example.test --skip-email
fi

wp plugin install wordpress-importer --version="$IMPORTER_VERSION" --activate
wp rewrite structure '/%year%/%monthnum%/%postname%/' --hard

if [ "$(wp option get wpmove_seeded 2>/dev/null || echo no)" != "yes" ]; then
  for entry in "${DATA_FILES[@]}"; do
    set -- $entry
    wp import "/data/$1" --authors=create
  done
  wp option add wpmove_seeded yes
fi

# Application Password for authenticated pulls (drafts, scheduled). WP allows it over http only
# because up.sh sets WP_ENVIRONMENT_TYPE=local. Stored in .env, never printed.
if ! grep -q '^WPMOVE_APP_PASSWORD=' .env; then
  pw=$(wp user application-password create "$WP_ADMIN_USER" wp-move-demo --porcelain)
  umask 077
  { echo "WPMOVE_USER=$WP_ADMIN_USER"; echo "WPMOVE_APP_PASSWORD=$pw"; } >> .env
fi
echo "seeded"
