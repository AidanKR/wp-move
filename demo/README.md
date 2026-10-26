# wp-move local demo site

A throwaway WordPress on `http://127.0.0.1:8088`, seeded with the official theme test data. It is the migration source for wp-move demos and tests. It binds to localhost only.

```bash
./up.sh             # start MariaDB + WordPress pod (creates .env with random test passwords on first run)
./seed.sh           # install WP, pin importer 0.9.7, import test data (sha256-checked), set permalinks
./down.sh           # stop the pod
./down.sh --purge   # also delete containers and volumes
```

Needs podman with a running machine (`podman machine start`; stop it with `podman machine stop` when done).

## Pinned inputs

| Input | Pin |
|---|---|
| WordPress | `wordpress:7.1.3-php8.4-apache` @ `sha256:e6d455d4…d589bd` |
| wp-cli | `wordpress:cli-2.12.0-php8.4` @ `sha256:7456afaf…b6e3d3` |
| MariaDB | `mariadb:11.8.9` @ `sha256:3607e752…b4a4e1` |
| WordPress Importer | 0.9.7 (wordpress.org) |
| Test data | `WordPress/theme-test-data` @ `b47acf980696`: `themeunittestdata.wordpress.xml` (sha256 `457aace6…`), `64-block-test-data.xml` (sha256 `59e0eefd…`) |

The test data repository states no license, so it is downloaded at seed time into `data/` (gitignored) and never committed or redistributed.

## Baseline inventory (measured 2026-10-26 after `seed.sh`)

This is the ground truth that the wp-move verification report must reproduce.

| Item | Count | Notes |
|---|---|---|
| Posts | 120 | 118 publish, 1 draft ("Draft"), 1 future ("Scheduled"). 119 from XML + WP's default "Hello world!" |
| Pages | 24 | 23 publish, 1 draft ("Privacy Policy"). 22 from XML + 2 WP defaults |
| Attachments | 37 | XML declares 46, but 9 in the block file reuse IDs already imported. 0 missing files on disk |
| Files under uploads/ | 158 | originals + generated sizes |
| Categories / tags | 73 / 118 | REST totals |
| Users | 3 | REST total |
| Comments | 29 | REST total |
| Menu items | 70 | `nav_menu_item` |
| Posts/pages containing blocks | 83 | `<!-- wp:` in content |
| Posts/pages containing shortcodes | 10 | `[name ...]` pattern |
| Permalink structure | `/%year%/%monthnum%/%postname%/` | |

Public REST (`/wp-json/wp/v2/...`, no auth) returns 118 posts and 23 pages. The draft and scheduled items are only reachable with credentials, which is why wp-move takes an optional Application Password.
