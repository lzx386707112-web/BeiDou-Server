import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import AutoImport from 'unplugin-auto-import/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
import Components from 'unplugin-vue-components/vite';
import { defineConfig } from 'vite';
import vueDevTools from 'vite-plugin-vue-devtools';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: '../src/main/resources/static',
    assetsDir: 'assets',
    emptyOutDir: true,
    // 确保生成的文件名不包含hash，便于Spring Boot处理
    // rollupOptions: {
    //   output: {
    //     chunkFileNames: 'js/[name].js',
    //     entryFileNames: 'js/[name].js',
    //     assetFileNames: 'assets/[name].[ext]',
    //   },
    // },
  },
});
