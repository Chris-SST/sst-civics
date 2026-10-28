import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["brand/*.png", "fonts/*.woff2", "icons/*.svg"],
      manifest: {
        name: "SST Virtual Tutor",
        short_name: "SST Tutor",
        description: "AI tutor for IB, IGCSE, A Level and Swiss school science and maths, by Swiss Science Tutors.",
        lang: "en-GB",
        start_url: "/",
        display: "standalone",
        background_color: "#f9f9f9",
        theme_color: "#84b796",
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
