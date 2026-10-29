import { useMemo } from "react";
import DOMPurify from "dompurify";
import katex from "katex";
import { marked } from "marked";
import "katex/dist/katex.min.css";
import Figure from "./Figure";

/** Renders tutor messages and question texts: Markdown with LaTeX maths, plus figures. Maths is
 * rendered with KaTeX before Markdown, so underscores and asterisks inside formulae survive; the
 * HTML is sanitised. Fenced ```figure blocks are cut out first and drawn as SVG in place. */

const PLACEHOLDER = (i: number) => `\u0000MATH${i}\u0000`;

function renderMaths(src: string): { text: string; blocks: string[] } {
  const blocks: string[] = [];
  const keep = (tex: string, display: boolean) => {
    let html: string;
    try {
      html = katex.renderToString(tex, { displayMode: display, throwOnError: false, output: "html" });
    } catch {
      html = `<code>${tex}</code>`;
    }
    blocks.push(html);
    return PLACEHOLDER(blocks.length - 1);
  };
  let text = src.replace(/\\\[([\s\S]+?)\\\]/g, (_m, tex) => keep(tex, true));
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_m, tex) => keep(tex, true));
  text = text.replace(/\\\(([\s\S]+?)\\\)/g, (_m, tex) => keep(tex, false));
  // Single-dollar inline maths, only when it looks like maths (no spaces right inside).
  text = text.replace(/(^|[^\\$])\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\d)/g, (_m, pre, tex) => pre + keep(tex, false));
  return { text, blocks };
}

export function toHtml(source: string): string {
  const { text, blocks } = renderMaths(source);
  let html = marked.parse(text, { async: false, gfm: true, breaks: true }) as string;
  html = html.replace(/\u0000MATH(\d+)\u0000/g, (_m, i) => blocks[Number(i)] ?? "");
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true, mathMl: true },
    ADD_ATTR: ["aria-hidden", "style"],
  });
}

type Segment = { kind: "html"; html: string } | { kind: "figure"; source: string; pending: boolean };

const FIGURE_RE = /```figure[^\n]*\n([\s\S]*?)```/g;
const OPEN_FIGURE_RE = /```figure[^\n]*(?:\n[\s\S]*)?$/;

/** Splits the source around fenced figure blocks. An unterminated block (while the reply is
 * still streaming) becomes a pending placeholder. */
export function toSegments(source: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  FIGURE_RE.lastIndex = 0;
  while ((m = FIGURE_RE.exec(source)) !== null) {
    const before = source.slice(last, m.index);
    if (before.trim()) out.push({ kind: "html", html: toHtml(before) });
    out.push({ kind: "figure", source: m[1].trim(), pending: false });
    last = m.index + m[0].length;
  }
  let rest = source.slice(last);
  const open = OPEN_FIGURE_RE.exec(rest);
  if (open && !rest.slice(open.index + 3).includes("```")) {
    const before = rest.slice(0, open.index);
    if (before.trim()) out.push({ kind: "html", html: toHtml(before) });
    out.push({ kind: "figure", source: "", pending: true });
    rest = "";
  }
  if (rest.trim() || out.length === 0) out.push({ kind: "html", html: toHtml(rest) });
  return out;
}

export default function RichText({ text, className }: { text: string; className?: string }) {
  const segments = useMemo(() => toSegments(text), [text]);
  if (segments.length === 1 && segments[0].kind === "html") {
    return <div className={className} dangerouslySetInnerHTML={{ __html: segments[0].html }} />;
  }
  return (
    <div className={className}>
      {segments.map((s, i) =>
        s.kind === "html" ? (
          <div key={i} dangerouslySetInnerHTML={{ __html: s.html }} />
        ) : (
          <Figure key={i} source={s.source} pending={s.pending} />
        ),
      )}
    </div>
  );
}
