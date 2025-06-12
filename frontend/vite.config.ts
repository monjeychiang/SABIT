import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueJsx(),
    AutoImport({
      imports: ['vue', 'vue-router', 'pinia'],
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5175,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
        secure: false,
        timeout: 60000,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('代理错误', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('代理请求', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('代理响应', proxyRes.statusCode, req.url);
          });
          proxy.on('close', () => {
            console.log('代理连接已关闭，正在尝试重新连接...');
          });
        }
      }
    },
    hmr: {
      clientPort: 5175,
      overlay: true,
      timeout: 10000,
      protocol: 'ws',
      host: 'localhost'
    }
  },
  base: './',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    assetsInlineLimit: 4096
  }
})
