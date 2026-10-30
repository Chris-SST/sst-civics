#!/usr/bin/env bash
# Deploy the guide site (site/dist) to the server and swap the "current" symlink atomically.
# Used by CI (job guide-site-deploy) and from a laptop. See docs/runbooks/deploy-guide-site.md.
#
#   DEPLOY_HOST=83.228.196.57 DEPLOY_USER=deploy scripts/deploy_site.sh            # build output in site/dist
#   DEPLOY_HOST=... DEPLOY_USER=... scripts/deploy_site.sh --rollback <sha>        # repoint "current"
#
# Environment:
#   DEPLOY_HOST (required), DEPLOY_USER (default deploy)
#   DEPLOY_PATH  default /opt/civics/site-releases
#   SITE_DIST    default site/dist
#   RELEASE_ID   default: the short git SHA
#   KEEP         releases to keep, default 5
# Needs ssh and rsync locally (on Windows use WSL) and rsync on the server.
set -euo pipefail

HOST="${DEPLOY_HOST:?set DEPLOY_HOST}"
USER_="${DEPLOY_USER:-deploy}"
BASE="${DEPLOY_PATH:-/opt/civics/site-releases}"
KEEP="${KEEP:-5}"
REMOTE="$USER_@$HOST"

if [ "${1:-}" = "--rollback" ]; then
  REL="${2:?usage: --rollback <release id>}"
  # shellcheck disable=SC2029
  ssh "$REMOTE" "set -e; cd '$BASE'; test -d 'releases/$REL'; ln -sfn 'releases/$REL' current.tmp; mv -Tf current.tmp current; echo \"current -> \$(readlink current)\""
  exit 0
fi

DIST="${SITE_DIST:-site/dist}"
REL="${RELEASE_ID:-$(git rev-parse --short=12 HEAD)}"
[ -f "$DIST/de/index.html" ] || { echo "No build in $DIST (run npm run build in site/ first)" >&2; exit 1; }

# 1. Upload into a new release directory (the live one is untouched).
ssh "$REMOTE" "mkdir -p '$BASE/releases/$REL'"
rsync -az --delete "$DIST"/ "$REMOTE:$BASE/releases/$REL/"

# 2. Swap the symlink. The link is relative (releases/<id>) so it also resolves inside the
#    container, where $BASE is mounted at /srv/site. mv -T renames over the old link atomically.
# 3. Keep the newest $KEEP releases (never the current one).
# shellcheck disable=SC2029
ssh "$REMOTE" "set -e; cd '$BASE'
  touch 'releases/$REL'
  ln -sfn 'releases/$REL' current.tmp
  mv -Tf current.tmp current
  cur=\$(readlink current)
  ls -1dt releases/*/ | sed 's#/\$##' | grep -vx \"\$cur\" | tail -n +\$(( $KEEP )) | xargs -r rm -rf
  echo \"current -> \$cur\"; ls -1 releases"

# 4. Smoke test through the public name when SMOKE_URL is set.
if [ -n "${SMOKE_URL:-}" ]; then
  curl -fsS -o /dev/null "$SMOKE_URL/de/" && curl -fsS -o /dev/null "$SMOKE_URL/sitemap-index.xml" && echo "smoke test ok"
fi
