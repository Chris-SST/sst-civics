// Lighthouse CI for the guide site: the built site (dist/) served by `astro preview`, the
// default mobile profile (phone emulation, throttled). Run: npm run build && npm run lighthouse
// LHCI_RUNS sets the runs per page (the median counts); CI=true adds --no-sandbox.
const port = 4322;
module.exports = {
  ci: {
    collect: {
      startServerCommand: `npx astro preview --port ${port} --host 127.0.0.1`,
      startServerReadyPattern: "astro",
      url: [`http://127.0.0.1:${port}/de/`, `http://127.0.0.1:${port}/de/grundkenntnistest/`, `http://127.0.0.1:${port}/de/faq/`],
      numberOfRuns: Number(process.env.LHCI_RUNS ?? 3),
      settings: {
        formFactor: "mobile",
        screenEmulation: { mobile: true, width: 412, height: 823, deviceScaleFactor: 1.75, disabled: false },
        chromeFlags: process.env.CI ? "--no-sandbox --headless=new" : "--headless=new",
        onlyCategories: ["performance", "accessibility", "best-practices", "seo"],
      },
    },
    assert: {
      assertions: {
        "categories:performance": ["error", { minScore: 0.9, aggregationMethod: "median-run" }],
        "categories:accessibility": ["error", { minScore: 0.9, aggregationMethod: "median-run" }],
        "categories:best-practices": ["error", { minScore: 0.9, aggregationMethod: "median-run" }],
        "categories:seo": ["error", { minScore: 0.9, aggregationMethod: "median-run" }],
      },
    },
    upload: { target: "filesystem", outputDir: ".lighthouseci" },
  },
};
