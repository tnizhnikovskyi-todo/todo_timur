import { defineConfig } from "vite";

// снимок данных лежит в ../prototype — разрешаем dev-серверу читать каталог warehouse3d
// режим `single` (npm run build:single, W-23): один бандл без ленивых чанков, ресурсы (data.json) — data: URL; tools/build-single.mjs кладёт всё в один HTML
export default defineConfig(({ mode }) => {
  const single = mode === "single";
  return {
    base: "./",
    server: { fs: { allow: [".."] } },
    build: {
      chunkSizeWarningLimit: 900,
      ...(single ? { outDir: "dist-single", emptyOutDir: true, assetsInlineLimit: 100 * 1024 * 1024, cssCodeSplit: false, modulePreload: false, rolldownOptions: { output: { codeSplitting: false } } } : {}),
    },
  };
});
