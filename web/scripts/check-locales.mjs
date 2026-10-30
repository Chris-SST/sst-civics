// Fails if any locale file misses or adds keys compared with en-GB.json,
// or changes the {{placeholders}} of a string. Plain Node, no dependencies.
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dir = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "locales");
const BASE = "en-GB.json";

function flatten(value, prefix = "", out = new Map()) {
  if (Array.isArray(value)) {
    out.set(`${prefix}[]`, value.length);
    value.forEach((v, i) => flatten(v, `${prefix}[${i}]`, out));
  } else if (value && typeof value === "object") {
    for (const [k, v] of Object.entries(value)) flatten(v, prefix ? `${prefix}.${k}` : k, out);
  } else {
    out.set(prefix, value);
  }
  return out;
}

const load = (f) => flatten(JSON.parse(readFileSync(join(dir, f), "utf8")));
const placeholders = (s) => (typeof s === "string" ? (s.match(/\{\{\s*\w+\s*\}\}/g) ?? []).sort().join("|") : "");

const base = load(BASE);
let failed = false;

for (const file of readdirSync(dir).filter((f) => f.endsWith(".json") && f !== BASE).sort()) {
  const other = load(file);
  const problems = [];
  for (const k of base.keys()) if (!other.has(k)) problems.push(`missing: ${k}`);
  for (const k of other.keys()) if (!base.has(k)) problems.push(`extra: ${k}`);
  for (const [k, v] of base) {
    if (other.has(k) && placeholders(v) !== placeholders(other.get(k))) problems.push(`placeholders differ: ${k}`);
  }
  if (problems.length) {
    failed = true;
    console.error(`${file}: ${problems.length} problem(s)`);
    problems.forEach((p) => console.error(`  ${p}`));
  } else {
    console.log(`${file}: ok (${other.size} entries)`);
  }
}

if (failed) process.exit(1);
