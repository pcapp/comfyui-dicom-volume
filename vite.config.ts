import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: "web", emptyOutDir: true,
    lib: { entry: "frontend/extension.ts", formats: ["es"], fileName: () => "viewer.js" },
    rollupOptions: {
      external: [/^\.\.\/\.\.\/scripts\//],
      output: { banner: "/*! Includes Lucide (ISC); see THIRD_PARTY_NOTICES.md in the extension repository. */" },
    },
  },
});
