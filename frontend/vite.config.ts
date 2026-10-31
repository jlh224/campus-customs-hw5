import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The desk runs at http://localhost:5173 (the origin the backend allows).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, open: !process.env.NO_OPEN },
});
