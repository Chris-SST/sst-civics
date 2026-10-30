// Writes the PWA icons into public/icons: icon.svg plus icon-192.png, icon-512.png and
// icon-maskable-512.png, in the brand violet with the speech-bubble mark. Plain Node, no
// dependencies (the PNG is rasterised here and deflated with node:zlib).
import { deflateSync } from "node:zlib";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "icons");
mkdirSync(out, { recursive: true });

const VIOLET = [0x5b, 0x4b, 0xdb];
const YELLOW = [0xff, 0xd2, 0x3f];
const INK = [0x1b, 0x17, 0x40];
const hex = (c) => "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("");

// Layout in a 512 space. "any" icons have rounded corners; the maskable one is full bleed with a
// smaller tile so the launcher's mask never crops the mark.
const layouts = {
  any: { bgRadius: 112, tile: 300 },
  maskable: { bgRadius: 0, tile: 216 },
};

function geometry({ tile }) {
  const cx = 256, cy = 256, k = tile / 38;
  const m = (x, y) => [cx + (x - 12) * k, cy + (y - 10) * k]; // mark space (24 x 20) to icon space
  const bubble = [m(4, 3), m(16, 3)];
  for (let i = 0; i <= 12; i++) {
    const a = -Math.PI / 2 + (Math.PI * i) / 12; // right end: half circle, centre (16,7), radius 4
    bubble.push(m(16 + 4 * Math.cos(a), 7 + 4 * Math.sin(a)));
  }
  bubble.push(m(8, 11), m(4, 15));
  return { tile, k, cx, cy, bubble, dot: { c: m(19, 14), r: 4 * k }, tileR: tile * (12 / 38) };
}

function svg(name) {
  const l = layouts[name], g = geometry(l), t = g.tile, x0 = 256 - t / 2;
  const pts = g.bubble.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ");
  return `<rect width="512" height="512" rx="${l.bgRadius}" fill="${hex(VIOLET)}"/>
  <rect x="${x0}" y="${x0}" width="${t}" height="${t}" rx="${g.tileR.toFixed(1)}" fill="${hex(YELLOW)}"/>
  <polygon points="${pts}" fill="${hex(INK)}"/>
  <circle cx="${g.dot.c[0].toFixed(1)}" cy="${g.dot.c[1].toFixed(1)}" r="${g.dot.r.toFixed(1)}" fill="${hex(VIOLET)}"/>`;
}

writeFileSync(
  join(out, "icon.svg"),
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Viapunt">\n  ${svg("any")}\n</svg>\n`,
);

function inPoly(poly, x, y) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function inRound(x, y, x0, y0, w, h, r) {
  if (x < x0 || y < y0 || x > x0 + w || y > y0 + h) return false;
  const dx = Math.max(x0 + r - x, 0, x - (x0 + w - r)), dy = Math.max(y0 + r - y, 0, y - (y0 + h - r));
  return dx * dx + dy * dy <= r * r;
}

function shade(name, x, y) {
  const l = layouts[name], g = geometry(l), x0 = 256 - g.tile / 2;
  if (!inRound(x, y, 0, 0, 512, 512, l.bgRadius)) return null;
  const dx = x - g.dot.c[0], dy = y - g.dot.c[1];
  if (dx * dx + dy * dy <= g.dot.r * g.dot.r) return VIOLET;
  if (inPoly(g.bubble, x, y)) return INK;
  if (inRound(x, y, x0, x0, g.tile, g.tile, g.tileR)) return YELLOW;
  return VIOLET;
}

const crcTable = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

function png(name, size) {
  const S = 4; // 4 x 4 supersampling
  const rows = [];
  for (let py = 0; py < size; py++) {
    const row = Buffer.alloc(1 + size * 4);
    for (let px = 0; px < size; px++) {
      let r = 0, g = 0, b = 0, a = 0;
      for (let sy = 0; sy < S; sy++)
        for (let sx = 0; sx < S; sx++) {
          const c = shade(name, ((px + (sx + 0.5) / S) * 512) / size, ((py + (sy + 0.5) / S) * 512) / size);
          if (c) { r += c[0]; g += c[1]; b += c[2]; a++; }
        }
      const o = 1 + px * 4;
      if (a) { row[o] = r / a; row[o + 1] = g / a; row[o + 2] = b / a; }
      row[o + 3] = Math.round((255 * a) / (S * S));
    }
    rows.push(row);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; ihdr[9] = 6; // 8-bit RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(Buffer.concat(rows), { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

writeFileSync(join(out, "icon-192.png"), png("any", 192));
writeFileSync(join(out, "icon-512.png"), png("any", 512));
writeFileSync(join(out, "icon-maskable-512.png"), png("maskable", 512));
console.log("icons written to", out);
