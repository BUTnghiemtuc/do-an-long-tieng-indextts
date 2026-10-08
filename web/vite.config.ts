import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: `npm run dev` (cổng 5300; không dùng 5173 mặc định của Vite) chuyển /api sang uvicorn ở cổng 8000.
// Build: `npm run build` -> web/dist, FastAPI tự phục vụ thư mục này nếu có.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5300,
    strictPort: true, // cổng bận thì báo lỗi, không tự nhảy sang cổng khác
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
  preview: { port: 5300, strictPort: true },
});
