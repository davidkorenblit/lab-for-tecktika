import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // In dev there is no Azure Static Web Apps host, so both /api and /.auth are
  // proxied to whatever backend the developer is pointing at.
  const apiTarget = env.VITE_DEV_API_PROXY || 'http://localhost:7071';

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { '@': path.resolve(__dirname, './src') },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        '/.auth': { target: apiTarget, changeOrigin: true },
      },
    },
  };
});
