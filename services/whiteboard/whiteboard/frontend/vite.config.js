import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  // publicDir defaults to 'public' when omitted
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    fs: { allow: [path.resolve(__dirname)] },
    proxy: {
      // Proxy API calls to FastAPI during development to avoid CORS and HTML fallbacks
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // Emit assets into backend static dir so FastAPI can serve them in production
    outDir: path.resolve(__dirname, '..', 'backend', 'whiteboard', 'static'),
    emptyOutDir: false,
    // no rollupOptions.input needed when index.html is at project root
  },
});