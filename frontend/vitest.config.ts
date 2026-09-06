import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  test: {
    // Node by default; the render test opts into jsdom with a docblock.
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
