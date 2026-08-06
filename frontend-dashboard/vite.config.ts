import { defineConfig } from "@lovable.dev/vite-tanstack-config";

const isVercelBuild = process.env.VERCEL === "1";

export default defineConfig({
  nitro: {
    preset: isVercelBuild ? "vercel" : "node-server",
  },

  tanstackStart: {
    // Preserve ECADIN's SSR error wrapper as the server entry.
    server: { entry: "server" },
  },
});
