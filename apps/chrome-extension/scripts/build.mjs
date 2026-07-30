import { cp, mkdir, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { build } from "esbuild";

const projectDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outputDirectory = path.join(projectDirectory, "dist");

await rm(outputDirectory, { recursive: true, force: true });
await mkdir(outputDirectory, { recursive: true });
await cp(path.join(projectDirectory, "static"), outputDirectory, { recursive: true });

await build({
  entryPoints: {
    "audio-worklet": path.join(projectDirectory, "src/audio-worklet.ts"),
    "service-worker": path.join(projectDirectory, "src/service-worker.ts"),
    offscreen: path.join(projectDirectory, "src/offscreen.ts"),
    popup: path.join(projectDirectory, "src/popup.ts"),
  },
  bundle: true,
  entryNames: "[name]",
  format: "esm",
  target: "chrome116",
  outdir: outputDirectory,
  sourcemap: true,
  logLevel: "info",
});
