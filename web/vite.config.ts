import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: `npm run dev` (cổng 5173) chuyển /api sang uvicorn ở cổng 8000.
// Build: `npm run build` -> web/dist, FastAPI tự phục vụ thư mục này nếu có.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
});
