// The five plugins below used to be hidden inside @lovable.dev/vite-tanstack-config.
// They are declared here because that package also chose nitro's *cloudflare*
// preset, which is wrong for KLAW: the Node SSR tier has to sit next to the
// FastAPI process, not on a Workers runtime.
//
// One behaviour is deliberately NOT carried over. The Lovable plugin ran
// `loadEnv(mode, cwd, "VITE_")` and `define`-injected every VITE_* variable into
// the server bundle as well as the client one. Plain Vite exposes VITE_* to the
// client only. Server-side code reads process.env, so an operator can no longer
// leak a backend key into public JavaScript merely by prefixing it VITE_.
import { defineConfig } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { nitro } from "nitro/vite";

export default defineConfig({
  // Vite 8 tự phân giải `paths` của tsconfig, nên không cần vite-tsconfig-paths.
  resolve: { tsconfigPaths: true },
  plugins: [
    tailwindcss(),
    nitro({ preset: "node-server" }),
    // Redirect TanStack Start's bundled server entry to src/server.ts, our SSR
    // error wrapper. nitro builds from this.
    tanstackStart({ server: { entry: "server" } }),
    viteReact(),
  ],
});
