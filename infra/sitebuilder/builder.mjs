// Guide-site builder (D-073). Runs in its own container next to the worker and keeps the live
// guide site in step with the published articles: whenever the article pipeline writes
// <ARTICLES_DIR>/.build-request (see docs/articles-contract.md, section 3), or the image carries
// site code that is not yet live, it builds the Astro site, checks the output, copies it to
// <RELEASES_DIR>/releases/<id>/ and swaps the relative symlink "current" atomically. A failed
// build or check leaves the live release untouched. The result goes to STATUS_FILE, which the
// worker reads (mounted read-only there).
//
// Environment: ARTICLES_DIR (/srv/articles), RELEASES_DIR (/srv/site-releases), STATUS_FILE
// (<RELEASES_DIR>/build-status.json), SITE_DIR (/app/site), POLL_SECONDS (30), KEEP (6),
// SOURCE_REV (git revision baked in at image build), plus the site's own build variables
// SITE_URL, APP_URL and PUBLIC_UMAMI_WEBSITE_ID.
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, symlinkSync, writeFileSync, readlinkSync, unlinkSync } from "node:fs";
import { join } from "node:path";

const ARTICLES_DIR = process.env.ARTICLES_DIR || "/srv/articles";
const RELEASES_DIR = process.env.RELEASES_DIR || "/srv/site-releases";
const STATUS_FILE = process.env.STATUS_FILE || join(RELEASES_DIR, "build-status.json");
const SITE_DIR = process.env.SITE_DIR || "/app/site";
const POLL_MS = Number(process.env.POLL_SECONDS || 30) * 1000;
const KEEP = Number(process.env.KEEP || 6);
const SKIP_DIRS = new Set(["node_modules", "dist", ".astro", "articles", "test-fixtures"]);

/** A fingerprint of the site code and the glossary baked into this image, so a new image with
 * changed site code is built once at start and an unchanged one is not. */
function sourceFingerprint() {
  const hash = createHash("sha256");
  const walk = (dir) => {
    for (const name of readdirSync(dir).sort()) {
      const p = join(dir, name);
      const st = statSync(p);
      if (st.isDirectory()) {
        if (!SKIP_DIRS.has(name)) walk(p);
      } else {
        hash.update(p.slice(dir.length));
        hash.update(readFileSync(p));
      }
    }
  };
  walk(SITE_DIR);
  const glossary = join(SITE_DIR, "..", "content", "glossary");
  if (existsSync(glossary)) walk(glossary);
  return hash.digest("hex").slice(0, 12);
}

const SOURCE_REV = process.env.SOURCE_REV && process.env.SOURCE_REV !== "unknown" ? process.env.SOURCE_REV.slice(0, 12) : sourceFingerprint();
const REQUEST_FILE = join(ARTICLES_DIR, ".build-request");

const log = (...args) => console.log(new Date().toISOString(), ...args);

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

function writeJsonAtomic(path, data) {
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, JSON.stringify(data, null, 2) + "\n");
  renameSync(tmp, path);
}

/** The request the pipeline left, as {requested_at, reason}, or null. */
function currentRequest() {
  if (!existsSync(REQUEST_FILE)) return null;
  const data = readJson(REQUEST_FILE) || {};
  const requested_at = data.requested_at || statSync(REQUEST_FILE).mtime.toISOString();
  return { requested_at, reason: data.reason || "" };
}

function liveRelease() {
  try {
    return readlinkSync(join(RELEASES_DIR, "current")).replace(/^releases\//, "");
  } catch {
    return null;
  }
}

function liveSourceRev() {
  const rel = liveRelease();
  if (!rel) return null;
  const meta = readJson(join(RELEASES_DIR, "releases", rel, ".build.json"));
  return meta?.source_rev ?? null;
}

function run(cmd, args, opts = {}) {
  return new Promise((resolve) => {
    const lines = [];
    const child = spawn(cmd, args, { cwd: SITE_DIR, env: process.env, ...opts });
    const keep = (buf) => {
      for (const line of buf.toString().split("\n")) {
        if (!line.trim()) continue;
        lines.push(line);
        if (lines.length > 200) lines.shift();
      }
    };
    child.stdout.on("data", keep);
    child.stderr.on("data", keep);
    child.on("close", (code) => resolve({ code, tail: lines.slice(-40).join("\n") }));
    child.on("error", (err) => resolve({ code: -1, tail: String(err) }));
  });
}

function stamp() {
  return new Date().toISOString().replace(/[-:]/g, "").replace("T", "-").slice(0, 15);
}

function prune(current) {
  const dir = join(RELEASES_DIR, "releases");
  const all = readdirSync(dir)
    .map((name) => ({ name, mtime: statSync(join(dir, name)).mtimeMs }))
    .filter((r) => r.name !== current)
    .sort((a, b) => b.mtime - a.mtime);
  for (const old of all.slice(Math.max(0, KEEP - 1))) {
    try {
      rmSync(join(dir, old.name), { recursive: true, force: true });
      log("pruned release", old.name);
    } catch (err) {
      log("could not prune", old.name, String(err));
    }
  }
}

function countArticles() {
  try {
    return readdirSync(ARTICLES_DIR, { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .reduce((n, d) => n + readdirSync(join(ARTICLES_DIR, d.name)).filter((f) => f.endsWith(".md")).length, 0);
  } catch {
    return 0;
  }
}

async function build(trigger) {
  const started_at = new Date().toISOString();
  const status = { ok: false, started_at, finished_at: null, release: null, requested_at: trigger.requested_at, reason: trigger.reason, source_rev: SOURCE_REV, error: null };
  log("build start:", trigger.reason || "(no reason)", "articles:", countArticles());
  writeJsonAtomic(STATUS_FILE, { ...status, building: true });

  rmSync(join(SITE_DIR, "dist"), { recursive: true, force: true });
  const steps = [
    ["node", ["node_modules/astro/bin/astro.mjs", "build"]],
    ["node", ["scripts/check-hreflang.mjs"]],
  ];
  for (const [cmd, args] of steps) {
    const res = await run(cmd, args);
    if (res.code !== 0) {
      status.error = `${cmd} ${args.join(" ")} exited ${res.code}\n${res.tail}`;
      status.finished_at = new Date().toISOString();
      writeJsonAtomic(STATUS_FILE, status);
      log("build FAILED:", status.error.split("\n")[0]);
      return status;
    }
  }
  const dist = join(SITE_DIR, "dist");
  for (const must of ["en/index.html", "de/index.html", "sitemap-index.xml", "404.html"]) {
    if (!existsSync(join(dist, must))) {
      status.error = `build output is missing ${must}`;
      status.finished_at = new Date().toISOString();
      writeJsonAtomic(STATUS_FILE, status);
      log("build FAILED:", status.error);
      return status;
    }
  }

  const release = `${stamp()}-${SOURCE_REV.slice(0, 7)}`;
  const target = join(RELEASES_DIR, "releases", release);
  mkdirSync(join(RELEASES_DIR, "releases"), { recursive: true });
  cpSync(dist, target, { recursive: true });
  writeJsonAtomic(join(target, ".build.json"), { release, source_rev: SOURCE_REV, built_at: new Date().toISOString(), reason: trigger.reason, articles: countArticles() });

  // Relative link so it resolves inside the web container too, where RELEASES_DIR is /srv/site.
  const tmpLink = join(RELEASES_DIR, "current.tmp");
  try {
    unlinkSync(tmpLink);
  } catch {}
  symlinkSync(`releases/${release}`, tmpLink);
  renameSync(tmpLink, join(RELEASES_DIR, "current"));
  prune(release);

  status.ok = true;
  status.release = release;
  status.finished_at = new Date().toISOString();
  writeJsonAtomic(STATUS_FILE, status);
  log("build ok, live release", release);
  return status;
}

/** build(), but an unexpected error (disk full, a failed copy or symlink) is recorded in the
 * status file instead of stopping the builder. The live release stays as it was. */
async function safeBuild(trigger) {
  try {
    return await build(trigger);
  } catch (err) {
    const status = { ok: false, started_at: null, finished_at: new Date().toISOString(), release: null, requested_at: trigger.requested_at, reason: trigger.reason, source_rev: SOURCE_REV, error: String(err?.stack || err).slice(0, 4000) };
    try {
      writeJsonAtomic(STATUS_FILE, status);
    } catch {}
    log("build FAILED (exception):", String(err));
    return status;
  }
}

async function main() {
  log(`site builder ${SOURCE_REV}: articles ${ARTICLES_DIR}, releases ${RELEASES_DIR}, status ${STATUS_FILE}`);
  let lastHandled = readJson(STATUS_FILE)?.requested_at ?? null;
  // New site code in this image that is not live yet: build once at start.
  if (liveSourceRev() !== SOURCE_REV) {
    const req = currentRequest();
    const res = await safeBuild({ requested_at: req?.requested_at ?? null, reason: `site code ${SOURCE_REV}` });
    if (res.ok && req) lastHandled = req.requested_at;
  }
  for (;;) {
    const req = currentRequest();
    if (req && req.requested_at !== lastHandled) {
      await safeBuild(req);
      // A failed build is not retried for the same request; the pipeline sees the failure in
      // the status file and asks again (or Chris does, after a fix).
      lastHandled = req.requested_at;
    }
    await new Promise((r) => setTimeout(r, POLL_MS));
  }
}

main().catch((err) => {
  log("builder crashed:", err);
  process.exit(1);
});
