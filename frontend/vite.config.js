import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true,
    host: true, // Allow external access (0.0.0.0)
    cors: true, // Enable CORS for all origins (for Firebase Auth popup)
    allowedHosts: [
      'trading.almalikiy.net',
      'backend-trading.almalikiy.net',
      'localhost',
      '.localhost',
      '0.0.0.0'
    ],
    // Optionally, you can add proxy config here if backend is on a different port
  },
});
