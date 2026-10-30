// Prints the four Lighthouse scores per page from .lighthouseci/lhr-*.json (median performance run).
import { readdirSync, readFileSync } from "node:fs";

const dir = ".lighthouseci";
const runs = readdirSync(dir)
  .filter((f) => /^lhr-.*\.json$/.test(f))
  .map((f) => JSON.parse(readFileSync(`${dir}/${f}`, "utf8")));
const pages = new Map();
for (const r of runs) pages.set(r.finalDisplayedUrl ?? r.finalUrl, [...(pages.get(r.finalDisplayedUrl ?? r.finalUrl) ?? []), r]);
const score = (r, k) => Math.round((r.categories[k]?.score ?? 0) * 100);
console.log("page".padEnd(52) + "perf  a11y  best  seo");
for (const [url, list] of pages) {
  list.sort((a, b) => score(a, "performance") - score(b, "performance"));
  const r = list[Math.floor(list.length / 2)];
  const row = ["performance", "accessibility", "best-practices", "seo"].map((k) => String(score(r, k)).padEnd(6));
  console.log(new URL(url).pathname.padEnd(52) + row.join(""));
}
