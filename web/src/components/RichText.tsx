import { useMemo } from "react";
import DOMPurify from "dompurify";
import katex from "katex";
import { marked } from "marked";
import "katex/dist/katex.min.css";

/** Renders tutor messages: Markdown with LaTeX maths. Maths is rendered with KaTeX before
 * Markdown, so underscores and asterisks inside formulae survive; the result is sanitised. */

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

export default function RichText({ text, className }: { text: string; className?: string }) {
  const html = useMemo(() => toHtml(text), [text]);
  return <div className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
