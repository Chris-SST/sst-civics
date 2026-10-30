// Checks the built guide site (dist/): every page's hreflang alternates point at pages that
// exist, include the page itself and x-default, and are reciprocal (the target lists this page
// back). Run after `npm run build`: npm run check:hreflang
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const dist = resolve(fileURLToPath(new URL("..", import.meta.url)), process.argv[2] ?? "dist");
if (!existsSync(dist)) {
  console.error(`No ${dist}: run npm run build first.`);
  process.exit(1);
}

function pages(dir) {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return name === "_astro" || name === "fonts" ? [] : pages(p);
    return name === "index.html" ? [p] : [];
  });
}

const attr = (tag, name) => tag.match(new RegExp(`${name}="([^"]*)"`))?.[1];
function alternates(html) {
  return [...html.matchAll(/<link\b[^>]*>/g)]
    .map((m) => m[0])
    .filter((t) => attr(t, "rel") === "alternate" && attr(t, "hreflang"))
    .map((t) => ({ lang: attr(t, "hreflang"), href: attr(t, "href") }));
}

const files = pages(dist);
const urlPath = (file) => "/" + relative(dist, file).split(sep).join("/").replace(/index\.html$/, "");
const byPath = new Map(files.map((f) => [urlPath(f), readFileSync(f, "utf8")]));
const errors = [];
let checked = 0;

for (const [path, html] of byPath) {
  if (path === "/") continue; // the redirect to /de/
  const alts = alternates(html);
  const fail = (msg) => errors.push(`${path}: ${msg}`);
  if (alts.length === 0) {
    fail("no hreflang alternates");
    continue;
  }
  checked += 1;
  const langs = alts.map((a) => a.lang);
  if (new Set(langs).size !== langs.length) fail("a language is listed twice");
  if (!langs.includes("x-default")) fail("no x-default alternate");
  const targets = new Map();
  for (const { lang, href } of alts) {
    let url;
    try {
      url = new URL(href);
    } catch {
      fail(`${lang}: href is not an absolute URL (${href})`);
      continue;
    }
    if (!byPath.has(url.pathname)) fail(`${lang}: ${url.pathname} is not a built page`);
    targets.set(lang, url.pathname);
  }
  if (![...targets.values()].includes(path)) fail("does not list itself");
  const own = path.split("/")[1];
  if (targets.get(own) !== path) fail(`the ${own} alternate is not this page`);
  for (const [lang, target] of targets) {
    const back = byPath.get(target) && alternates(byPath.get(target)).some((a) => a.href && new URL(a.href).pathname === path);
    if (byPath.has(target) && !back) fail(`${lang}: ${target} does not list this page back`);
  }
}

if (errors.length) {
  console.error(`hreflang: ${errors.length} problem(s)\n` + errors.join("\n"));
  process.exit(1);
}
console.log(`hreflang: ${checked} pages checked, all alternates exist, are reciprocal and include x-default.`);
