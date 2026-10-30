import { useMemo } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";

/** Renders tutor messages, question texts and explanations: Markdown, sanitised. */

export function toHtml(source: string): string {
  const html = marked.parse(source, { async: false, gfm: true, breaks: true }) as string;
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}

export default function RichText({ text, className }: { text: string; className?: string }) {
  const html = useMemo(() => toHtml(text), [text]);
  return <div className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
