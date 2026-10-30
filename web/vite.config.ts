import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["fonts/*.woff2", "icons/*.svg"],
      manifest: {
        name: "Viapunt",
        short_name: "Viapunt",
        description: "Understand the Swiss naturalisation test in your own language, then practise it in German.",
        lang: "en-GB",
        start_url: "/",
        display: "standalone",
        background_color: "#f4f1ff",
        theme_color: "#5b4bdb",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
          { src: "/icons/icon.svg", sizes: "any", type: "image/svg+xml" },
        ],
      },
      workbox: {
        // Never cache API responses: account and billing state must be live.
        navigateFallbackDenylist: [/^\/api\//],
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: false },
    },
  },
  build: { sourcemap: false },
});
