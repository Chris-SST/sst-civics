import type { APIRoute } from "astro";

export const GET: APIRoute = ({ site }) => {
  const url = site ?? new URL("https://staging.viapunt.ch");
  const base = url.toString().replace(/\/$/, "");
  const body = url.hostname.includes("staging")
    ? "User-agent: *\nDisallow: /\n"
    : `User-agent: *\nAllow: /\n\nSitemap: ${base}/sitemap-index.xml\n`;
  return new Response(body, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
};
