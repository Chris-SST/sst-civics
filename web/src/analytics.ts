/** Cookie-free visitor statistics (self-hosted Umami, D-062). Active only when the build sets
 * VITE_UMAMI_WEBSITE_ID (production) and the browser does not send Do Not Track. Umami counts
 * page views itself, including route changes; `track` adds the funnel steps (free practice
 * started and finished, sign-up, checkout opened, help chat used). No personal data is sent:
 * event data is limited to the canton, the product key or a score. */

declare global {
  interface Window {
    umami?: { track: (name: string, data?: Record<string, string | number>) => void };
  }
}

export function startAnalytics(): void {
  const id = import.meta.env.VITE_UMAMI_WEBSITE_ID as string | undefined;
  if (!id || navigator.doNotTrack === "1") return;
  const script = document.createElement("script");
  script.defer = true;
  script.src = "/stats/script.js";
  script.dataset.websiteId = id;
  script.dataset.hostUrl = "/stats";
  script.dataset.doNotTrack = "true";
  document.head.append(script);
}

export function track(name: string, data?: Record<string, string | number>): void {
  try {
    window.umami?.track(name, data);
  } catch {
    /* statistics must never break the app */
  }
}
