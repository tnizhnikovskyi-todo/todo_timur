import { defineConfig } from "vite";

// снимок данных лежит в ../prototype — разрешаем dev-серверу читать каталог warehouse3d
export default defineConfig({
  base: "./",
  server: { fs: { allow: [".."] } },
  build: { chunkSizeWarningLimit: 900 },
});
