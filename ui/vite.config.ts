import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  const env = loadEnv(mode, process.cwd(), '')
  
  // SSO Gateway URL - all API requests go through SSO
  const ssoGatewayUrl = env.VITE_SSO_SERVICE_URL || 'http://localhost:8000'

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 3000,
      // Note: API calls now use full SSO Gateway URL from environment variables
      // The proxy is kept for backward compatibility but not strictly needed
      proxy: {
        '/api': {
          target: ssoGatewayUrl,
          changeOrigin: true,
        },
        '/health': {
          target: ssoGatewayUrl,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
  }
})

