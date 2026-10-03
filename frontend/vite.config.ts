import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // разрешаем любой Host — удобно при проверке через туннель (cloudflared/ngrok)
    allowedHosts: true,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
