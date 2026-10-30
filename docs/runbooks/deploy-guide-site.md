# Runbook: deploy the guide site

The guide site (`site/`, Astro) is served by the civics `web` container's Caddy from
`/srv/site/current`, which is the host directory `/opt/civics/site-releases` mounted read-only.
The shared edge Caddy already sends the guide host to that container (D-004, D-056).

```
/opt/civics/site-releases/
  releases/<sha>/      one directory per release (last five kept)
  current -> releases/<sha>     relative symlink, swapped atomically
```

## First deploy

1. On the server, as the deploy user:
   `mkdir -p /opt/civics/site-releases/releases` (create it before the first `up`, or Docker
   creates it owned by root). The user needs write access there and `rsync` installed.
2. Rebuild the web image, because the Caddyfile is copied into it at build time and the compose
   file gained the volume mount:
   `cd /opt/civics && docker compose -p civics -f infra/docker-compose.yml --env-file .env up -d --build web`
3. Upload the first release, from a laptop with ssh and rsync (WSL on Windows):
   `cd site && npm ci && npm run build && cd ..`
   `DEPLOY_HOST=83.228.196.57 DEPLOY_USER=<user> SMOKE_URL=https://civics-staging.swisssciencetutors.ch scripts/deploy_site.sh`
4. Open `https://civics-staging.swisssciencetutors.ch/` (redirects to `/de/`), a guide page, `/sitemap-index.xml` and a wrong URL (expect the 404 page).
5. For CI: set repository variable `STAGING_DEPLOY_ENABLED=true` and the existing secrets
   `STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_KEY`. Optional variables `SITE_URL` and `APP_URL`
   override the staging names at build time. Pushing a `v*` tag then builds and releases the site
   (job `guide-site-deploy`); every push only runs `astro check` and the build (job `guide-site`).

## Later releases

Tag a version, or run `scripts/deploy_site.sh` from a laptop. The script uploads to
`releases/<sha>/`, swaps `current`, and deletes all but the five newest releases (never the live one).
No container restart is needed. Only changes to `infra/Caddyfile` or `infra/docker-compose.yml`
need step 2 again (rebuild `web`).

## Rollback

`DEPLOY_HOST=... DEPLOY_USER=... scripts/deploy_site.sh --rollback <sha>` (a name from
`ls /opt/civics/site-releases/releases`), or on the server:
`cd /opt/civics/site-releases && ln -sfn releases/<sha> current.tmp && mv -Tf current.tmp current`.
Always use a relative link target, or it will not resolve inside the container.

## Go-live: brand domain at Swizzonic

Swizzonic stays registrar and DNS only (D-056).

1. A day before: lower the TTL of the records to 300 seconds.
2. At Swizzonic add `A` (and `AAAA` if the server has IPv6) for the apex `@` and for `www`, pointing
   at the production server's IP; `app` stays as for staging. A CNAME at the apex is not allowed;
   `www` may be a CNAME to the apex. Leave MX and SPF records alone.
3. Edit the host list in both Caddyfiles, replacing the staging name:
   - `infra/edge-snippet.Caddyfile` (the shared edge, on the server in the tutor stack): add the
     apex, `www.<domain>` and `app.<domain>`; reload the edge (`caddy reload`). Certificates are issued once DNS resolves.
   - `infra/Caddyfile` (civics web container): change `http://civics-staging...` to
     `http://<domain>` and add the `www` redirect block shown in the comment.
   Then rebuild `web` as in step 2 above.
4. Build with the production values: set `SITE_URL=https://<domain>` and
   `APP_URL=https://app.<domain>` (repository variables) and release a new tag. Check the hreflang
   links and the sitemap show the new host, and update `Sitemap:` expectations in monitoring.
5. When the Umami container exists, uncomment the script tag in `site/src/layouts/Base.astro`
   and add the stats host to `script-src` and `connect-src` in `infra/Caddyfile`.
