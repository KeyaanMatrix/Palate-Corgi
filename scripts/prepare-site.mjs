import { access, copyFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const root = process.cwd();
const source = resolve(root, "web");
const output = resolve(root, "public");

await mkdir(output, { recursive: true });
await copyFile(resolve(source, "index.html"), resolve(output, "submission.html"));
await copyFile(
  resolve(source, "palate-social-v2.png"),
  resolve(output, "palate-social-v2.png"),
);

try {
  await access(resolve(source, "demo.mp4"));
  await copyFile(resolve(source, "demo.mp4"), resolve(output, "demo.mp4"));
} catch {
  // The real phone capture is an explicit credential-gated submission seam.
}
