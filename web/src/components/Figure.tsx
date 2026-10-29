import { useId } from "react";
import { useTranslation } from "react-i18next";

/** Draws the figures the tutor emits in fenced ```figure blocks (prompts/figures/v1.md) as
 * hand-written SVG. Unknown types and invalid specs show a visible fallback. */

const C = {
  green: "#84b796",
  greenDark: "#63866f",
  charcoal: "#373b3c",
  blue: "#3a8dca",
  gold: "#c9a24e",
  text: "#3f332d",
  grid: "#e7e6e6",
  axis: "#8a8a8a",
};
const SERIES = [C.green, C.blue, C.gold, C.charcoal, C.greenDark];
const W = 520;
const H = 340;
const FONT = 'font-family: "Rethink Sans", Arial, Helvetica, sans-serif; font-size: 12px;';

// --- Safe expression evaluator -----------------------------------------------------------------

type Tok =
  | { t: "num"; v: number }
  | { t: "id"; v: string }
  | { t: "op"; v: string }
  | { t: "lp" }
  | { t: "rp" }
  | { t: "comma" };

type Fn = (x: number) => number;

const FUNCS: Record<string, (a: number) => number> = {
  sin: Math.sin,
  cos: Math.cos,
  tan: Math.tan,
  asin: Math.asin,
  acos: Math.acos,
  atan: Math.atan,
  exp: Math.exp,
  ln: Math.log,
  log: Math.log10,
  sqrt: Math.sqrt,
  abs: Math.abs,
};
const CONSTS: Record<string, number> = { pi: Math.PI, e: Math.E };

function tokenize(src: string): Tok[] {
  const s = src.replace(/−/g, "-").replace(/×/g, "*").replace(/÷/g, "/").replace(/\*\*/g, "^");
  const out: Tok[] = [];
  let i = 0;
  while (i < s.length) {
    const ch = s[i];
    if (/\s/.test(ch)) {
      i++;
      continue;
    }
    if (/[0-9.]/.test(ch)) {
      const m = /^(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?/.exec(s.slice(i));
      if (!m) throw new Error("number");
      out.push({ t: "num", v: Number(m[0]) });
      i += m[0].length;
      continue;
    }
    if (/[a-zA-Z_]/.test(ch)) {
      const m = /^[a-zA-Z_][a-zA-Z0-9_]*/.exec(s.slice(i));
      if (!m) throw new Error("identifier");
      out.push({ t: "id", v: m[0] });
      i += m[0].length;
      continue;
    }
    if ("+-*/^".includes(ch)) out.push({ t: "op", v: ch });
    else if (ch === "(") out.push({ t: "lp" });
    else if (ch === ")") out.push({ t: "rp" });
    else if (ch === ",") out.push({ t: "comma" });
    else throw new Error(`unexpected ${ch}`);
    i++;
  }
  return out;
}

/** Recursive descent: expr > term > unary > power > atom. Implicit multiplication such as
 * `2x` or `3(x+1)` is accepted. Returns a closure in x; never uses eval. */
export function compileExpression(src: string): Fn {
  const toks = tokenize(src);
  let p = 0;
  const peek = () => toks[p];
  const next = () => toks[p++];

  function expr(): Fn {
    let left = term();
    for (;;) {
      const t = peek();
      if (t && t.t === "op" && (t.v === "+" || t.v === "-")) {
        next();
        const right = term();
        const l = left;
        left = t.v === "+" ? (x) => l(x) + right(x) : (x) => l(x) - right(x);
      } else return left;
    }
  }
  function startsAtom(t: Tok | undefined): boolean {
    return !!t && (t.t === "num" || t.t === "id" || t.t === "lp");
  }
  function term(): Fn {
    let left = unary();
    for (;;) {
      const t = peek();
      if (t && t.t === "op" && (t.v === "*" || t.v === "/")) {
        next();
        const right = unary();
        const l = left;
        left = t.v === "*" ? (x) => l(x) * right(x) : (x) => l(x) / right(x);
      } else if (startsAtom(t) && t.t !== "num") {
        // implicit multiplication: 2x, 2(x+1), x(x-1)
        const right = unary();
        const l = left;
        left = (x) => l(x) * right(x);
      } else return left;
    }
  }
  function unary(): Fn {
    const t = peek();
    if (t && t.t === "op" && t.v === "-") {
      next();
      const inner = unary();
      return (x) => -inner(x);
    }
    if (t && t.t === "op" && t.v === "+") {
      next();
      return unary();
    }
    return power();
  }
  function power(): Fn {
    const base = atom();
    const t = peek();
    if (t && t.t === "op" && t.v === "^") {
      next();
      const exponent = unary(); // right-associative, allows x^-1
      return (x) => Math.pow(base(x), exponent(x));
    }
    return base;
  }
  function atom(): Fn {
    const t = next();
    if (!t) throw new Error("unexpected end");
    if (t.t === "num") {
      const v = t.v;
      return () => v;
    }
    if (t.t === "lp") {
      const inner = expr();
      const close = next();
      if (!close || close.t !== "rp") throw new Error("expected )");
      return inner;
    }
    if (t.t === "id") {
      const name = t.v.toLowerCase();
      if (peek()?.t === "lp") {
        const f = FUNCS[name];
        if (!f) throw new Error(`unknown function ${name}`);
        next();
        const arg = expr();
        const close = next();
        if (!close || close.t !== "rp") throw new Error("expected )");
        return (x) => f(arg(x));
      }
      if (name === "x") return (x) => x;
      if (name in CONSTS) {
        const v = CONSTS[name];
        return () => v;
      }
      if (name in FUNCS) {
        // sin x without brackets: applies to the next factor
        const f = FUNCS[name];
        const arg = unary();
        return (x) => f(arg(x));
      }
      throw new Error(`unknown identifier ${name}`);
    }
    throw new Error("unexpected token");
  }
  const fn = expr();
  if (p !== toks.length) throw new Error("trailing input");
  return fn;
}

// --- Helpers ----------------------------------------------------------------------------------

const num = (v: unknown, fallback: number): number =>
  typeof v === "number" && Number.isFinite(v) ? v : fallback;
const str = (v: unknown, fallback = ""): string => (typeof v === "string" ? v : fallback);
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const obj = (v: unknown): Record<string, unknown> =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};

function niceStep(range: number, target = 6): number {
  if (!(range > 0)) return 1;
  const raw = range / target;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const r = raw / mag;
  const m = r < 1.5 ? 1 : r < 3.5 ? 2 : r < 7.5 ? 5 : 10;
  return m * mag;
}
function ticks(min: number, max: number, step: number): number[] {
  const out: number[] = [];
  const start = Math.ceil(min / step - 1e-9) * step;
  for (let v = start; v <= max + 1e-9 && out.length < 60; v += step) out.push(Math.round(v * 1e9) / 1e9);
  return out;
}
const fmt = (v: number): string => {
  const a = Math.abs(v);
  if (a >= 1e5 || (a > 0 && a < 1e-3)) return v.toExponential(1).replace("e+", "e");
  return String(Math.round(v * 1000) / 1000);
};

interface Frame {
  xmin: number;
  xmax: number;
  ymin: number;
  ymax: number;
  left: number;
  right: number;
  top: number;
  bottom: number;
  X: (x: number) => number;
  Y: (y: number) => number;
}

function makeFrame(xmin: number, xmax: number, ymin: number, ymax: number, pad = { l: 44, r: 16, t: 16, b: 36 }): Frame {
  if (!(xmax > xmin)) xmax = xmin + 1;
  if (!(ymax > ymin)) ymax = ymin + 1;
  const left = pad.l;
  const right = W - pad.r;
  const top = pad.t;
  const bottom = H - pad.b;
  return {
    xmin,
    xmax,
    ymin,
    ymax,
    left,
    right,
    top,
    bottom,
    X: (x) => left + ((x - xmin) / (xmax - xmin)) * (right - left),
    Y: (y) => bottom - ((y - ymin) / (ymax - ymin)) * (bottom - top),
  };
}

/** Axes through the origin when it is visible, otherwise along the edges; grid optional. */
function Axes({ f, xLabel, yLabel, grid }: { f: Frame; xLabel?: string; yLabel?: string; grid?: boolean }) {
  const xs = ticks(f.xmin, f.xmax, niceStep(f.xmax - f.xmin));
  const ys = ticks(f.ymin, f.ymax, niceStep(f.ymax - f.ymin));
  const x0 = f.xmin <= 0 && f.xmax >= 0 ? f.X(0) : f.left;
  const y0 = f.ymin <= 0 && f.ymax >= 0 ? f.Y(0) : f.bottom;
  const labelSide = x0 > f.left + 30 ? -6 : 6;
  return (
    <g>
      {grid &&
        xs.map((v) => <line key={`gx${v}`} x1={f.X(v)} x2={f.X(v)} y1={f.top} y2={f.bottom} stroke={C.grid} />)}
      {grid &&
        ys.map((v) => <line key={`gy${v}`} x1={f.left} x2={f.right} y1={f.Y(v)} y2={f.Y(v)} stroke={C.grid} />)}
      <line x1={f.left} x2={f.right} y1={y0} y2={y0} stroke={C.axis} strokeWidth={1.2} />
      <line x1={x0} x2={x0} y1={f.top} y2={f.bottom} stroke={C.axis} strokeWidth={1.2} />
      {xs.map((v) => (
        <g key={`tx${v}`}>
          <line x1={f.X(v)} x2={f.X(v)} y1={y0 - 3} y2={y0 + 3} stroke={C.axis} />
          {v !== 0 || x0 === f.left ? (
            <text x={f.X(v)} y={y0 + 15} textAnchor="middle" fill={C.axis}>
              {fmt(v)}
            </text>
          ) : null}
        </g>
      ))}
      {ys.map((v) => (
        <g key={`ty${v}`}>
          <line x1={x0 - 3} x2={x0 + 3} y1={f.Y(v)} y2={f.Y(v)} stroke={C.axis} />
          {v !== 0 || y0 === f.bottom ? (
            <text
              x={x0 + labelSide}
              y={f.Y(v) + 4}
              textAnchor={labelSide < 0 ? "end" : "start"}
              fill={C.axis}
            >
              {fmt(v)}
            </text>
          ) : null}
        </g>
      ))}
      {xLabel && (
        <text x={f.right} y={y0 - 6} textAnchor="end" fill={C.text} fontStyle="italic">
          {xLabel}
        </text>
      )}
      {yLabel && (
        <text x={x0 + 8} y={f.top + 10} fill={C.text} fontStyle="italic">
          {yLabel}
        </text>
      )}
    </g>
  );
}

function Svg({ children, height = H, label }: { children: React.ReactNode; height?: number; label: string }) {
  return (
    <svg
      viewBox={`0 0 ${W} ${height}`}
      role="img"
      aria-label={label}
      style={{ width: "100%", height: "auto", maxWidth: W, display: "block" }}
    >
      <style>{`text { ${FONT} }`}</style>
      {children}
    </svg>
  );
}

function ArrowDefs({ id, colours }: { id: string; colours: string[] }) {
  return (
    <defs>
      {Array.from(new Set(colours)).map((c) => (
        <marker
          key={c}
          id={`${id}-${c.slice(1)}`}
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill={c} />
        </marker>
      ))}
    </defs>
  );
}
const markerUrl = (id: string, c: string) => `url(#${id}-${c.slice(1)})`;

// --- Figure types -------------------------------------------------------------------------------

function FunctionGraph({ spec, label }: { spec: Record<string, unknown>; label: string }) {
  const xs = obj(spec.x);
  const ys = obj(spec.y);
  const xmin = num(xs.min, -5);
  const xmax = num(xs.max, 5);
  const fns = arr(spec.functions).map(obj);
  const compiled = fns.map((f) => {
    try {
      return compileExpression(str(f.expr));
    } catch {
      return null;
    }
  });
  // Sample 200 points; auto-range y if not given.
  const N = 200;
  const samples = compiled.map((fn) => {
    const pts: (number | null)[][] = [];
    for (let i = 0; i <= N; i++) {
      const x = xmin + ((xmax - xmin) * i) / N;
      let y: number | null = null;
      if (fn) {
        try {
          const v = fn(x);
          y = Number.isFinite(v) ? v : null;
        } catch {
          y = null;
        }
      }
      pts.push([x, y]);
    }
    return pts;
  });
  let ymin = num(ys.min, NaN);
  let ymax = num(ys.max, NaN);
  if (!Number.isFinite(ymin) || !Number.isFinite(ymax)) {
    const all = samples.flat().map((p) => p[1]).filter((v): v is number => v !== null);
    const lo = all.length ? Math.min(...all) : -5;
    const hi = all.length ? Math.max(...all) : 5;
    const pad = (hi - lo || 2) * 0.1;
    if (!Number.isFinite(ymin)) ymin = Math.min(lo - pad, 0);
    if (!Number.isFinite(ymax)) ymax = Math.max(hi + pad, 0);
  }
  const f = makeFrame(xmin, xmax, ymin, ymax);
  const range = ymax - ymin;
  const paths = samples.map((pts) => {
    let d = "";
    let prev: number | null = null;
    pts.forEach(([x, y]) => {
      if (x === null || y === null) {
        prev = null;
        return;
      }
      const clipped = y > ymax + range || y < ymin - range;
      const jump = prev !== null && Math.abs(y - prev) > range;
      if (prev === null || jump || clipped) {
        d += clipped ? "" : `M${f.X(x).toFixed(1)} ${f.Y(y).toFixed(1)}`;
        prev = clipped ? null : y;
        return;
      }
      d += `L${f.X(x).toFixed(1)} ${f.Y(y).toFixed(1)}`;
      prev = y;
    });
    return d;
  });
  const clipId = useId().replace(/:/g, "");
  const legend = fns.map((fn) => str(fn.label)).filter(Boolean);
  const extra = legend.length ? 18 * Math.ceil(legend.length / 2) : 0;
  return (
    <Svg label={label} height={H + extra}>
      <defs>
        <clipPath id={clipId}>
          <rect x={f.left} y={f.top} width={f.right - f.left} height={f.bottom - f.top} />
        </clipPath>
      </defs>
      <Axes f={f} xLabel={str(xs.label, "x")} yLabel={str(ys.label, "y")} grid />
      <g clipPath={`url(#${clipId})`}>
        {paths.map((d, i) => (
          <path key={i} d={d} fill="none" stroke={SERIES[i % SERIES.length]} strokeWidth={2.2} strokeLinejoin="round" />
        ))}
        {arr(spec.lines).map((l, i) => {
          const ln = obj(l);
          const dash = ln.dashed === false ? undefined : "6 5";
          if (ln.kind === "vertical")
            return (
              <line key={i} x1={f.X(num(ln.x, 0))} x2={f.X(num(ln.x, 0))} y1={f.top} y2={f.bottom} stroke={C.charcoal} strokeDasharray={dash} />
            );
          return (
            <line key={i} x1={f.left} x2={f.right} y1={f.Y(num(ln.y, 0))} y2={f.Y(num(ln.y, 0))} stroke={C.charcoal} strokeDasharray={dash} />
          );
        })}
      </g>
      {arr(spec.lines).map((l, i) => {
        const ln = obj(l);
        if (!ln.label) return null;
        return ln.kind === "vertical" ? (
          <text key={i} x={f.X(num(ln.x, 0)) + 4} y={f.top + 12} fill={C.charcoal}>
            {str(ln.label)}
          </text>
        ) : (
          <text key={i} x={f.right - 4} y={f.Y(num(ln.y, 0)) - 4} textAnchor="end" fill={C.charcoal}>
            {str(ln.label)}
          </text>
        );
      })}
      {arr(spec.points).map((p, i) => {
        const pt = obj(p);
        const px = f.X(num(pt.x, 0));
        const py = f.Y(num(pt.y, 0));
        return (
          <g key={i}>
            <circle cx={px} cy={py} r={4.5} fill={C.charcoal} stroke="#fff" strokeWidth={1.5} />
            {pt.label ? (
              <text x={px + 7} y={py - 7} fill={C.text} fontWeight={600}>
                {str(pt.label)}
              </text>
            ) : null}
          </g>
        );
      })}
      {legend.map((text, i) => (
        <g key={i} transform={`translate(${f.left + (i % 2) * 240}, ${H + 4 + Math.floor(i / 2) * 18})`}>
          <line x1={0} x2={22} y1={0} y2={0} stroke={SERIES[i % SERIES.length]} strokeWidth={2.5} />
          <text x={28} y={4} fill={C.text}>
            {text}
          </text>
        </g>
      ))}
    </Svg>
  );
}

function NumberLine({ spec, label }: { spec: Record<string, unknown>; label: string }) {
  const min = num(spec.min, -5);
  const max = num(spec.max, 5);
  const step = num(spec.step, niceStep(max - min, 10));
  const height = 110;
  const y = 60;
  const pad = 28;
  const X = (v: number) => pad + ((v - min) / (max - min || 1)) * (W - 2 * pad);
  const tk = ticks(min, max, step);
  const intervals = arr(spec.intervals).map(obj);
  const points = arr(spec.points).map(obj);
  return (
    <Svg label={label} height={height}>
      {intervals.map((iv, i) => {
        const a = num(iv.from, min);
        const b = num(iv.to, max);
        const xa = X(Math.max(a, min));
        const xb = X(Math.min(b, max));
        return (
          <g key={i}>
            <line x1={xa} x2={xb} y1={y} y2={y} stroke={C.green} strokeWidth={8} strokeOpacity={0.55} />
            {a >= min && (
              <circle cx={xa} cy={y} r={5.5} fill={iv.open_from ? "#fff" : C.greenDark} stroke={C.greenDark} strokeWidth={2} />
            )}
            {b <= max && (
              <circle cx={xb} cy={y} r={5.5} fill={iv.open_to ? "#fff" : C.greenDark} stroke={C.greenDark} strokeWidth={2} />
            )}
            {iv.label ? (
              <text x={(xa + xb) / 2} y={y - 18} textAnchor="middle" fill={C.greenDark} fontWeight={600}>
                {str(iv.label)}
              </text>
            ) : null}
          </g>
        );
      })}
      <line x1={pad - 10} x2={W - pad + 10} y1={y} y2={y} stroke={C.charcoal} strokeWidth={1.5} />
      <path d={`M${W - pad + 10} ${y} l-7 -4 v8 z`} fill={C.charcoal} />
      <path d={`M${pad - 10} ${y} l7 -4 v8 z`} fill={C.charcoal} />
      {tk.map((v) => (
        <g key={v}>
          <line x1={X(v)} x2={X(v)} y1={y - 6} y2={y + 6} stroke={C.charcoal} />
          <text x={X(v)} y={y + 24} textAnchor="middle" fill={C.axis}>
            {fmt(v)}
          </text>
        </g>
      ))}
      {points.map((p, i) => {
        const v = num(p.x, 0);
        return (
          <g key={i}>
            <circle cx={X(v)} cy={y} r={6} fill={p.filled === false ? "#fff" : C.blue} stroke={C.blue} strokeWidth={2.2} />
            {p.label ? (
              <text x={X(v)} y={y - 14} textAnchor="middle" fill={C.text} fontWeight={600}>
                {str(p.label)}
              </text>
            ) : null}
          </g>
        );
      })}
    </Svg>
  );
}

function Triangle({ spec, label }: { spec: Record<string, unknown>; label: string }) {
  const names = arr(spec.vertices).map((v) => str(v)).slice(0, 3);
  while (names.length < 3) names.push(["A", "B", "C"][names.length]);
  const right = str(spec.right_angle_at);
  const ri = names.indexOf(right);
  let pos: [number, number][];
  if (ri >= 0) {
    // the right angle sits at the bottom-left corner, the next vertex to the right, the last above
    const corner: [number, number] = [90, 280];
    const along: [number, number] = [450, 280];
    const up: [number, number] = [90, 60];
    pos = [corner, corner, corner];
    pos[ri] = corner;
    pos[(ri + 1) % 3] = along;
    pos[(ri + 2) % 3] = up;
  } else {
    pos = [
      [70, 280],
      [460, 280],
      [310, 60],
    ];
  }
  const cx = (pos[0][0] + pos[1][0] + pos[2][0]) / 3;
  const cy = (pos[0][1] + pos[1][1] + pos[2][1]) / 3;
  const outward = (x: number, y: number, d: number): [number, number] => {
    const dx = x - cx;
    const dy = y - cy;
    const len = Math.hypot(dx, dy) || 1;
    return [x + (dx / len) * d, y + (dy / len) * d];
  };
  const sides = arr(spec.sides).map(obj);
  const angles = arr(spec.angles).map(obj);
  const idx = (name: unknown) => names.indexOf(str(name));
  return (
    <Svg label={label}>
      <polygon points={pos.map((p) => p.join(",")).join(" ")} fill={C.green} fillOpacity={0.12} stroke={C.charcoal} strokeWidth={2} strokeLinejoin="round" />
      {ri >= 0 &&
        (() => {
          const [px, py] = pos[ri];
          const [ax, ay] = pos[(ri + 1) % 3];
          const [bx, by] = pos[(ri + 2) % 3];
          const s = 18;
          const ua = [(ax - px) / Math.hypot(ax - px, ay - py), (ay - py) / Math.hypot(ax - px, ay - py)];
          const ub = [(bx - px) / Math.hypot(bx - px, by - py), (by - py) / Math.hypot(bx - px, by - py)];
          const d = `M${px + ua[0] * s} ${py + ua[1] * s} L${px + (ua[0] + ub[0]) * s} ${py + (ua[1] + ub[1]) * s} L${px + ub[0] * s} ${py + ub[1] * s}`;
          return <path d={d} fill="none" stroke={C.charcoal} strokeWidth={1.5} />;
        })()}
      {angles.map((a, i) => {
        const k = idx(a.at);
        if (k < 0) return null;
        const [px, py] = pos[k];
        const [ox, oy] = pos[(k + 1) % 3];
        const [qx, qy] = pos[(k + 2) % 3];
        const a1 = Math.atan2(oy - py, ox - px);
        const a2 = Math.atan2(qy - py, qx - px);
        const r = 30;
        let sweep = a2 - a1;
        while (sweep <= -Math.PI) sweep += 2 * Math.PI;
        while (sweep > Math.PI) sweep -= 2 * Math.PI;
        const large = Math.abs(sweep) > Math.PI ? 1 : 0;
        const flag = sweep > 0 ? 1 : 0;
        const d = `M${px + r * Math.cos(a1)} ${py + r * Math.sin(a1)} A${r} ${r} 0 ${large} ${flag} ${px + r * Math.cos(a2)} ${py + r * Math.sin(a2)}`;
        const mid = a1 + sweep / 2;
        return (
          <g key={i}>
            {k !== ri && <path d={d} fill="none" stroke={C.blue} strokeWidth={1.5} />}
            <text x={px + 46 * Math.cos(mid)} y={py + 46 * Math.sin(mid) + 4} textAnchor="middle" fill={C.blue} fontWeight={600}>
              {str(a.label)}
            </text>
          </g>
        );
      })}
      {sides.map((s, i) => {
        const pair = arr(s.between).map(idx);
        if (pair.length < 2 || pair[0] < 0 || pair[1] < 0) return null;
        const mx = (pos[pair[0]][0] + pos[pair[1]][0]) / 2;
        const my = (pos[pair[0]][1] + pos[pair[1]][1]) / 2;
        const [lx, ly] = outward(mx, my, 22);
        return (
          <text key={i} x={lx} y={ly + 4} textAnchor="middle" fill={C.text} fontWeight={600}>
            {str(s.label)}
          </text>
        );
      })}
      {names.map((n, i) => {
        const [lx, ly] = outward(pos[i][0], pos[i][1], 20);
        return (
          <text key={n} x={lx} y={ly + 5} textAnchor="middle" fill={C.text} fontWeight={700} fontSize={14}>
            {n}
          </text>
        );
      })}
    </Svg>
  );
}

function Vectors({ spec, label }: { spec: Record<string, unknown>; label: string }) {
  const id = useId().replace(/:/g, "");
  const xs = obj(spec.x);
  const ys = obj(spec.y);
  const vecs = arr(spec.vectors).map(obj);
  const pts = vecs.flatMap((v) => [arr(v.from).map((n) => num(n, 0)), arr(v.to).map((n) => num(n, 0))]);
  const auto = (k: 0 | 1, lo: boolean) => {
    const vals = pts.map((p) => p[k] ?? 0);
    if (!vals.length) return lo ? -1 : 5;
    return lo ? Math.min(...vals, 0) - 1 : Math.max(...vals, 0) + 1;
  };
  const f = makeFrame(num(xs.min, auto(0, true)), num(xs.max, auto(0, false)), num(ys.min, auto(1, true)), num(ys.max, auto(1, false)));
  const colours = vecs.map((_, i) => SERIES[i % SERIES.length]);
  return (
    <Svg label={label}>
      <ArrowDefs id={id} colours={colours} />
      <Axes f={f} grid={spec.grid !== false} xLabel={str(xs.label)} yLabel={str(ys.label)} />
      {vecs.map((v, i) => {
        const from = arr(v.from).map((n) => num(n, 0));
        const to = arr(v.to).map((n) => num(n, 0));
        const x1 = f.X(from[0] ?? 0);
        const y1 = f.Y(from[1] ?? 0);
        const x2 = f.X(to[0] ?? 0);
        const y2 = f.Y(to[1] ?? 0);
        const c = colours[i];
        const mx = (x1 + x2) / 2;
        const my = (y1 + y2) / 2;
        const dx = x2 - x1;
        const dy = y2 - y1;
        const len = Math.hypot(dx, dy) || 1;
        return (
          <g key={i}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={c} strokeWidth={2.5} strokeDasharray={v.dashed ? "7 5" : undefined} markerEnd={markerUrl(id, c)} />
            {v.label ? (
              <text x={mx - (dy / len) * 12} y={my + (dx / len) * 12 + 4} textAnchor="middle" fill={c} fontWeight={700} fontSize={14}>
                {str(v.label)}
              </text>
            ) : null}
          </g>
        );
      })}
    </Svg>
  );
}

function FreeBody({ spec, label }: { spec: Record<string, unknown>; label: string }) {
  const id = useId().replace(/:/g, "");
  const theta = Math.max(0, Math.min(60, num(spec.incline_deg, 0)));
  const rad = (theta * Math.PI) / 180;
  const cx = W / 2 - 20;
  const cy = theta ? 190 : 200;
  const size = 64;
  const forces = arr(spec.forces).map(obj);
  const L = 95;
  const toAngle = (fo: Record<string, unknown>): number => {
    const d = fo.direction;
    const along = str(fo.along);
    const named: Record<string, number> = { right: 0, up: 90, left: 180, down: 270 };
    let deg = typeof d === "number" ? d : (named[str(d)] ?? 90);
    if (theta && along === "surface") deg = str(d) === "left" || str(d) === "down" ? 180 + theta : theta;
    if (theta && along === "normal") deg = str(d) === "down" ? 270 + theta : 90 + theta;
    return (deg * Math.PI) / 180;
  };
  // incline: surface rising to the right through the block's base
  const half = size / 2;
  const base: [number, number] = [cx + half * Math.sin(rad), cy + half * Math.cos(rad)]; // foot of the block on the surface
  const run = 230;
  const surf = {
    x1: base[0] - run * Math.cos(rad),
    y1: base[1] + run * Math.sin(rad),
    x2: base[0] + run * Math.cos(rad),
    y2: base[1] - run * Math.sin(rad),
  };
  return (
    <Svg label={label}>
      <ArrowDefs id={id} colours={[C.blue]} />
      {theta ? (
        <g>
          <polygon points={`${surf.x1},${surf.y1} ${surf.x2},${surf.y2} ${surf.x2},${surf.y1}`} fill={C.green} fillOpacity={0.15} stroke={C.charcoal} strokeWidth={1.5} />
          <path d={`M${surf.x1 + 70} ${surf.y1} A70 70 0 0 0 ${surf.x1 + 70 * Math.cos(rad)} ${surf.y1 - 70 * Math.sin(rad)}`} fill="none" stroke={C.axis} />
          <text x={surf.x1 + 84} y={surf.y1 - 10} fill={C.text}>
            {`${theta}°`}
          </text>
        </g>
      ) : (
        <line x1={cx - 200} x2={cx + 200} y1={cy + half} y2={cy + half} stroke={C.charcoal} strokeWidth={1.5} />
      )}
      <g transform={`rotate(${-theta} ${cx} ${cy})`}>
        <rect x={cx - half} y={cy - half} width={size} height={size} rx={4} fill="#fff" stroke={C.charcoal} strokeWidth={2} />
      </g>
      {str(spec.body) && str(spec.body) !== "block" ? (
        <text x={cx} y={cy + 4} textAnchor="middle" fill={C.text}>
          {str(spec.body)}
        </text>
      ) : null}
      <circle cx={cx} cy={cy} r={3} fill={C.charcoal} />
      {forces.map((fo, i) => {
        const a = toAngle(fo);
        const x2 = cx + L * Math.cos(a);
        const y2 = cy - L * Math.sin(a);
        const lx = cx + (L + 16) * Math.cos(a);
        const ly = cy - (L + 16) * Math.sin(a);
        return (
          <g key={i}>
            <line x1={cx} y1={cy} x2={x2} y2={y2} stroke={C.blue} strokeWidth={2.5} markerEnd={markerUrl(id, C.blue)} />
            <text x={lx} y={ly + 4} textAnchor={Math.cos(a) < -0.3 ? "end" : Math.cos(a) > 0.3 ? "start" : "middle"} fill={C.blue} fontWeight={700} fontSize={14}>
              {str(fo.label)}
            </text>
          </g>
        );
      })}
    </Svg>
  );
}

function BarChart({ spec, label }: { spec: Record<string, unknown>; label: string }) {
  const cats = arr(spec.categories).map((c) => str(c));
  const vals = arr(spec.values).map((v) => num(v, 0));
  const n = Math.max(cats.length, vals.length);
  const hi = Math.max(0, ...vals);
  const lo = Math.min(0, ...vals);
  const step = niceStep(hi - lo || 1, 5);
  const ymax = Math.ceil(hi / step) * step || step;
  const ymin = Math.floor(lo / step) * step;
  const f = makeFrame(0, n, ymin, ymax, { l: 48, r: 16, t: 16, b: 40 });
  const bw = ((f.right - f.left) / Math.max(n, 1)) * 0.6;
  const ys = ticks(ymin, ymax, step);
  return (
    <Svg label={label}>
      {ys.map((v) => (
        <g key={v}>
          <line x1={f.left} x2={f.right} y1={f.Y(v)} y2={f.Y(v)} stroke={C.grid} />
          <text x={f.left - 6} y={f.Y(v) + 4} textAnchor="end" fill={C.axis}>
            {fmt(v)}
          </text>
        </g>
      ))}
      <line x1={f.left} x2={f.right} y1={f.Y(0)} y2={f.Y(0)} stroke={C.axis} strokeWidth={1.2} />
      <line x1={f.left} x2={f.left} y1={f.top} y2={f.bottom} stroke={C.axis} strokeWidth={1.2} />
      {Array.from({ length: n }).map((_, i) => {
        const v = vals[i] ?? 0;
        const x = f.X(i + 0.5) - bw / 2;
        const y = f.Y(Math.max(v, 0));
        const h = Math.abs(f.Y(v) - f.Y(0));
        return (
          <g key={i}>
            <rect x={x} y={y} width={bw} height={h} fill={C.green} rx={3} />
            <text x={x + bw / 2} y={v >= 0 ? y - 5 : y + h + 13} textAnchor="middle" fill={C.text}>
              {fmt(v)}
            </text>
            <text x={x + bw / 2} y={f.bottom + 16} textAnchor="middle" fill={C.text}>
              {cats[i] ?? ""}
            </text>
          </g>
        );
      })}
      {str(spec.y_label) && (
        <text x={f.left + 6} y={f.top + 10} fill={C.text} fontStyle="italic">
          {str(spec.y_label)}
        </text>
      )}
      {str(spec.x_label) && (
        <text x={f.right} y={f.bottom + 32} textAnchor="end" fill={C.text} fontStyle="italic">
          {str(spec.x_label)}
        </text>
      )}
    </Svg>
  );
}

function Scatter({ spec, label }: { spec: Record<string, unknown>; label: string }) {
  const pts = arr(spec.points)
    .map((p) => (Array.isArray(p) ? [num(p[0], NaN), num(p[1], NaN)] : [num(obj(p).x, NaN), num(obj(p).y, NaN)]))
    .filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
  const xsv = pts.map((p) => p[0]);
  const ysv = pts.map((p) => p[1]);
  const pad = (lo: number, hi: number) => (hi - lo || 2) * 0.12;
  const xlo = xsv.length ? Math.min(...xsv) : 0;
  const xhi = xsv.length ? Math.max(...xsv) : 10;
  const ylo = ysv.length ? Math.min(...ysv) : 0;
  const yhi = ysv.length ? Math.max(...ysv) : 10;
  const xs = obj(spec.x);
  const ys = obj(spec.y);
  const f = makeFrame(
    num(xs.min, Math.min(0, xlo - pad(xlo, xhi))),
    num(xs.max, xhi + pad(xlo, xhi)),
    num(ys.min, Math.min(0, ylo - pad(ylo, yhi))),
    num(ys.max, yhi + pad(ylo, yhi)),
  );
  const line = obj(spec.line);
  const hasLine = typeof line.m === "number" && typeof line.c === "number";
  const m = num(line.m, 0);
  const c = num(line.c, 0);
  const clamp = (x: number) => ({ x, y: m * x + c });
  const p1 = clamp(f.xmin);
  const p2 = clamp(f.xmax);
  return (
    <Svg label={label}>
      <Axes f={f} grid xLabel={str(spec.x_label, str(xs.label))} yLabel={str(spec.y_label, str(ys.label))} />
      {hasLine && (
        <g>
          <line x1={f.X(p1.x)} y1={f.Y(p1.y)} x2={f.X(p2.x)} y2={f.Y(p2.y)} stroke={C.blue} strokeWidth={2} />
          {line.label ? (
            <text x={f.right - 6} y={Math.max(f.top + 12, Math.min(f.bottom - 6, f.Y(p2.y) - 8))} textAnchor="end" fill={C.blue} fontWeight={600}>
              {str(line.label)}
            </text>
          ) : null}
        </g>
      )}
      {pts.map((p, i) => (
        <circle key={i} cx={f.X(p[0])} cy={f.Y(p[1])} r={4.5} fill={C.greenDark} stroke="#fff" strokeWidth={1.5} />
      ))}
    </Svg>
  );
}

function EnergyLevels({ spec, label }: { spec: Record<string, unknown>; label: string }) {
  const id = useId().replace(/:/g, "");
  const levels = arr(spec.levels).map(obj);
  const energies = levels.map((l) => num(l.energy, 0));
  const unit = str(spec.unit);
  const lo = Math.min(...energies, 0);
  const hi = Math.max(...energies, 0);
  const top = 30;
  const bottom = H - 30;
  const Y = (e: number) => bottom - ((e - lo) / (hi - lo || 1)) * (bottom - top);
  const x1 = 130;
  const x2 = 390;
  const n = levels.length;
  const resolve = (v: unknown): number => {
    const k = num(v, NaN);
    if (!Number.isFinite(k)) return -1;
    if (Number.isInteger(k) && k >= 1 && k <= n) return k - 1;
    if (Number.isInteger(k) && k >= 0 && k < n) return k;
    const byEnergy = energies.indexOf(k);
    return byEnergy;
  };
  const transitions = arr(spec.transitions).map(obj);
  return (
    <Svg label={label}>
      <ArrowDefs id={id} colours={[C.blue, C.gold]} />
      {levels.map((l, i) => {
        const y = Y(energies[i]);
        return (
          <g key={i}>
            <line x1={x1} x2={x2} y1={y} y2={y} stroke={C.charcoal} strokeWidth={2} />
            <text x={x1 - 10} y={y + 4} textAnchor="end" fill={C.text} fontWeight={600}>
              {str(l.label)}
            </text>
            <text x={x2 + 10} y={y + 4} fill={C.axis}>
              {`${fmt(energies[i])}${unit ? ` ${unit}` : ""}`}
            </text>
          </g>
        );
      })}
      {transitions.map((tr, i) => {
        const a = resolve(tr.from);
        const b = resolve(tr.to);
        if (a < 0 || b < 0) return null;
        const x = x1 + 50 + (i * 60) % (x2 - x1 - 80);
        const ya = Y(energies[a]);
        const yb = Y(energies[b]);
        const colour = energies[b] < energies[a] ? C.blue : C.gold;
        return (
          <g key={i}>
            <line x1={x} y1={ya} x2={x} y2={yb + (yb > ya ? -2 : 2)} stroke={colour} strokeWidth={2} markerEnd={markerUrl(id, colour)} />
            {tr.label ? (
              <text x={x + 8} y={(ya + yb) / 2 + 4} fill={colour}>
                {str(tr.label)}
              </text>
            ) : null}
          </g>
        );
      })}
    </Svg>
  );
}

// --- Entry point ------------------------------------------------------------------------------

const RENDERERS: Record<string, (p: { spec: Record<string, unknown>; label: string }) => React.ReactElement> = {
  function_graph: FunctionGraph,
  number_line: NumberLine,
  triangle: Triangle,
  vectors: Vectors,
  free_body: FreeBody,
  bar_chart: BarChart,
  scatter: Scatter,
  energy_levels: EnergyLevels,
};

export function parseFigure(source: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(source);
    const spec = obj(parsed);
    return typeof spec.type === "string" && spec.type in RENDERERS ? spec : null;
  } catch {
    return null;
  }
}

export default function Figure({ source, pending }: { source: string; pending?: boolean }) {
  const { t } = useTranslation();
  if (pending) {
    return (
      <div className="figure figure-pending muted small" aria-busy="true">
        {t("figure.pending")}
      </div>
    );
  }
  const spec = parseFigure(source);
  const Renderer = spec ? RENDERERS[String(spec.type)] : null;
  if (!spec || !Renderer) {
    return (
      <div className="figure figure-failed small" role="note">
        {t("figure.failed")}
      </div>
    );
  }
  const label = t(`figure.types.${String(spec.type)}`, { defaultValue: String(spec.type) });
  try {
    return (
      <figure className="figure">
        <Renderer spec={spec} label={label} />
      </figure>
    );
  } catch {
    return (
      <div className="figure figure-failed small" role="note">
        {t("figure.failed")}
      </div>
    );
  }
}
