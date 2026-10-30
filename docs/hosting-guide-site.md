# Hosting review: public guide website

Written 30 October 2026. Scope: where to host the static Astro guide site (D-043) at the apex domain, with the app at `app.` (D-004). Prices include VAT where the source says so; anything not read from a provider page is marked "unconfirmed".

## Recommendation

Serve the guide site from the existing Infomaniak VPS through the shared Caddy edge, and do the same on the production server. It costs nothing extra, it is the only option that is fully scriptable (SSH, rsync, a Caddy site block), it keeps visitor requests and analytics in Switzerland, and it gives HTTP/3, compression, automatic Let's Encrypt and exact control of cache headers. Keep Swizzonic for the domain and DNS only. Swizzonic's entry web hosting is very cheap, but its own page shows the data centre in Brussels, the cheapest plan has no SSH, and its public pages do not confirm rsync, SSH keys, HTTP/3 or `.htaccess` control, so it would break both the Swiss-hosting stance and the automated deploy path. The real risk is sharing a small server; mitigate it with the planned separate production VPS and keep Infomaniak web hosting as the fallback.

## Comparison

| Option | CHF per month | Setup effort | Deploy path for an agent | TLS | Performance | Data location | Risks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A. Existing Infomaniak VPS, Caddy serves `/srv/guide` | 0 extra (VPS about 10 to 15, already paid, D-004) | Low: one site block, one directory, one SSH key | rsync over SSH, atomic symlink swap | Caddy, automatic Let's Encrypt | HTTP/3, zstd/gzip, our own headers; no CDN | Switzerland | Shared 2 vCPU / 4 GB box; one fault takes down guide and app; we patch the OS |
| B. Separate Infomaniak VPS for production, same method | About 10 to 15 (unconfirmed) | Low to medium: provision, harden, Caddy, backups | Same as A | Same as A | Same as A, isolated from other apps | Switzerland | Extra server to maintain |
| C. Swizzonic Linux web hosting (Starter / Advanced) | 1.26 / 2.83 first-year promo (list 5.02 / 10.04; renewal not shown) | Low in the panel; medium to prove automation | Starter: File Manager/FTP only. Advanced: SSH listed. rsync and key login unconfirmed | "SSL certificate included"; Let's Encrypt not named | Varnish cache listed; HTTP/2, HTTP/3, `.htaccess` not stated | Brussels (Belgium) per its page | Not Swiss; automation unproven; promo ends after year one |
| D. Infomaniak Web+Email hosting | From about 13.20 (own page via search snippet; a third party says 10.91) | Low | FTP and SSH listed; rsync unconfirmed | Free Let's Encrypt | Standard shared hosting | Switzerland (Infomaniak states it; not re-read today) | Dearer than A for the same job; another thing to manage |
| E. Infomaniak Public Cloud object storage plus CDN | Unconfirmed (price page would not load) | Medium to high | S3 API sync, scriptable | Needs a front; unconfirmed | No Infomaniak CDN confirmed | Switzerland for storage | Static-website mode and CDN not confirmed; more parts than a directory |
| F. Cloudflare Pages | 0 (free plan; 20,000 files per site per Cloudflare changelog) | Low | `wrangler pages deploy` or git push, token in CI | Automatic | Global CDN, HTTP/3 | Global edge, US company | Conflicts with Swiss-hosting stance |
| G. Netlify | 0 free but credit-based (about 300 credits a month; a third-party review says 20 production deploys can use them up); Personal about USD 9 | Low | CLI or git push | Automatic | Global CDN | Global, US company | Credit limits on a site rebuilt on every content change; same stance conflict |
| H. GitHub Pages | 0 for public repositories (unconfirmed today) | Low | git push or Actions | Automatic | Global CDN | Global, US company | Public source repo; no header control; same stance conflict |

## Findings by provider

**Swizzonic** (read 30 October 2026, https://www.swizzonic.ch/hosting/webhosting/?lang=en): three Linux plans with 50 / 200 / 500 GB NVMe, 1 / 5 / 10 sites, unlimited traffic, SSL certificate included, PHP 7.3 to 8.2, own control panel, Varnish cache, backups kept 12 to 24 hours, 30-day free trial. Starter lists "File Manager/FTP"; Advanced and Expert add SSH. The page names a Brussels data centre. A separate "SWIZZHosting cPanel" product is described as located in Switzerland, but its plans were not read. No static-site, "pages" or object-storage product appears. A user-submitted directory (whtop.com, undated) lists a free Let's Encrypt certificate for one domain; Swizzonic does not say so. Not found: rsync, SSH key login, HTTP/2 or HTTP/3, `.htaccess`, redirect rules, subdomain handling, ALIAS/ANAME support. A third-party guide (support.saldia.ch, "link domain swizzonic 121", undated) shows the DNS panel accepting an A record for an external host, which is all this plan needs.

**Existing VPS** (D-004, 30 October 2026): Infomaniak VPS Lite in Switzerland, 2 vCPU, 4 GB, shared edge Caddy. A static site adds a few megabytes of disk and almost no CPU or memory. Caddy 2 serves HTTP/3, zstd/gzip, automatic certificates and per-path `Cache-Control` and redirects, so language defaults and hreflang need no extra software. The risk is blast radius: one 4 GB machine runs the tutor app, civics staging, Postgres, Redis, workers and possibly analytics. A full disk, memory pressure or a Caddy mistake affects every site at once. Production is already planned to get its own server (D-004), which resolves most of this.

**Infomaniak web hosting** (search snippets, 30 October 2026; the product pages did not render in the fetch tool): Web+Email hosting from CHF 13.20 a month (https://www.infomaniak.com/en/hosting/web-and-mail/web-and-mail-hosting); a comparison site gives CHF 10.91, 250 GB, 20 sites, FTP and SSH, free Let's Encrypt (https://infoswitch.fr/en/blog/infomaniak-pricing-2026-all-services). rsync not confirmed. A fallback only.

**Infomaniak Public Cloud** (https://www.infomaniak.com/en/hosting/public-cloud/prices, search result of 30 October 2026): bandwidth is free except object storage billed above 10 TB. The CHF object-storage price, static-website mode and any CDN could not be confirmed. A reseller blog quotes Swiss Backup S3 in euros (250 GB at 2.49 EUR), which is a different product. Not worth pursuing for a site of a few megabytes.

**Non-Swiss hosts** (search results of 30 October 2026, plus https://developers.cloudflare.com/changelog/post/2026-01-23-pages-file-limit-increase/ and https://www.netlify.com/changelog/2026-04-14-pricing-updates-april-2026/): free or near-free and simple. The catch is that every visitor request is served by a US company's global network, which contradicts the Swiss-hosting stance in PLAN.md, and the privacy notice would have to name a third-party processor. Cookie-free analytics would still need our own Swiss server, so they gain nothing there. Comparison only.

**Analytics** (third-party blogs, 30 October 2026: https://use-apify.com/blog/plausible-vs-umami-2026, https://www.ssdnodes.com/learn/self-hosted-web-analytics-vps): Plausible Community Edition needs ClickHouse; sources say at least 2 GB RAM recommended and about 1.8 GB resident on a fresh deployment. Umami (app plus PostgreSQL) is measured at about 400 MB idle. None of these figures are from vendor documentation; verify before installing. On the shared 4 GB staging VPS, Plausible would crowd the other stacks, so use Umami there, or run Plausible only on the production server with 2 GB reserved. Either runs as its own Compose project behind Caddy at `stats.<domain>`, and it does not change the choice to host the static site on the VPS.

## Recommended architecture

```
Browser -> Caddy (VPS, :443, HTTP/3)
            |- <apex>, www.<apex>  -> file_server /srv/guide/current
            |- app.<apex>          -> civics web container (network edge)
            |- stats.<apex>        -> analytics container
```

Caddy site block (production names; staging uses `civics-staging.swisssciencetutors.ch`, D-004):

```
www.example.ch { redir https://example.ch{uri} permanent }
example.ch {
    root * /srv/guide/current
    encode zstd gzip
    header /assets/* Cache-Control "public, max-age=31536000, immutable"
    header Cache-Control "public, max-age=300, must-revalidate"
    file_server
    handle_errors {
        rewrite * /404.html
        file_server
    }
}
```

Language defaults: Astro generates `/de/`, `/en/` and so on, with hreflang and `x-default` in the HTML and sitemap. Make `/` a real page that lists the languages (best for search engines). If automatic redirects by `Accept-Language` are wanted, add a Caddy `header_regexp` matcher with a temporary `redir` and `Vary: Accept-Language`, and never redirect crawlers away from hreflang URLs.

**Deploy flow (CI job on push to main touching `site/`):**
1. `npm ci && npm run build` in `site/` (Astro writes `dist/`); fail on broken links, and on Lighthouse under 90 if that check is wired in.
2. `rsync -az --delete dist/ deploy@<vps>:/srv/guide/releases/<git-sha>/` over SSH with a pinned host key.
3. `ssh deploy@<vps> 'ln -sfn /srv/guide/releases/<git-sha> /srv/guide/current.tmp && mv -Tf /srv/guide/current.tmp /srv/guide/current'` for an atomic swap; Caddy needs no reload.
4. Smoke test: `curl -fsS` the home page and the sitemap, expect 200; delete releases beyond the last five.

**Secrets (CI store, never in the repository):** `DEPLOY_SSH_KEY` (ed25519, used only by this job), `DEPLOY_KNOWN_HOSTS` (the server's host key line), `DEPLOY_HOST`. The `deploy` user can write to `/srv/guide` only, has no sudo, and its key is restricted in `authorized_keys` (source address and no port forwarding at least).

**Rollback:** `ssh deploy@<vps> 'ln -sfn /srv/guide/releases/<previous-sha> /srv/guide/current'`, or re-run the CI job on an earlier commit. It takes seconds and needs no rebuild. No separate backup of releases is needed: the repository is the source.

**If the VPS becomes crowded:** move only the apex block to a second small VPS; the same CI job works with a different `DEPLOY_HOST`.

## DNS at Swizzonic

Swizzonic keeps the registration and DNS, so nothing is transferred. Only A/AAAA records are needed because the target is an IP address:

| Host | Type | Value | Notes |
| --- | --- | --- | --- |
| `@` (apex) | A | VPS IPv4 (staging today `83.228.196.57`; production IP when it exists) | Add AAAA if the VPS has IPv6 |
| `www` | CNAME to the apex name, or A | Same IP | A CNAME is allowed on `www` |
| `app` | A | Same IP | App host (D-004) |
| `stats` | A | Same IP | Analytics host |
| `civics-staging`, `app.civics-staging` | A | `83.228.196.57` | Staging names from D-004 |

A CNAME cannot sit at the apex because it clashes with the SOA and NS records. ALIAS/ANAME flattening is the usual workaround, but I found no documentation of Swizzonic supporting it, and it is not needed with a fixed IP. Lower the TTL to 300 seconds a day before any IP change. Leave the existing mail records (MX, SPF) untouched.

## Cost, year one

| Item | Staging (now) | Production |
| --- | --- | --- |
| Static site hosting | CHF 0 (existing VPS) | CHF 0 on the production VPS already planned; about CHF 120 to 180 a year only if a second server is added for the site alone (unconfirmed) |
| TLS | 0 | 0 |
| DNS at Swizzonic | already paid | already paid; a new brand domain would add a yearly registration (unconfirmed) |
| Analytics (Umami) | 0 | 0 (Plausible CE needs 2 GB headroom, part of VPS sizing) |
| Swizzonic hosting (not recommended) | not used | CHF 15 to 34 first year, then list price around CHF 60 to 120 (renewal unconfirmed) |

## What Chris must do

1. Confirm D-043 (Astro) so the build can be wired into CI.
2. Decide whether production gets its own VPS now (recommended) and confirm its price on the Infomaniak order page.
3. At Swizzonic, add the A (and AAAA) records above, note whether the DNS panel offers ALIAS, and lower the TTL before cut-over.
4. Allow Claude an SSH account on the VPS (or authorise a `deploy` user) and add the three CI secrets.
5. Confirm the brand domain name, since host names and the Caddy block depend on it.
6. Choose analytics: Umami on staging, Plausible CE only where 2 GB can be reserved.
7. Optional: ask Swizzonic support whether Advanced hosting offers rsync, SSH keys and a Swiss data centre; only needed if the VPS route is dropped.

## Not confirmed on 30 October 2026

Swizzonic renewal prices, HTTP/2 and HTTP/3, `.htaccess`, rsync, SSH key login, and the location of the cPanel product; Infomaniak web hosting price and rsync; Infomaniak object-storage CHF price, static-website mode and CDN; Plausible and Umami memory figures (blogs only); GitHub Pages current terms; the current VPS Lite price. Infomaniak's own product pages did not render in the fetch tool, so its figures come from search snippets.
