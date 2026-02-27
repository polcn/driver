import fs from "node:fs";
import path from "node:path";

const distDir = path.resolve("dist");
const indexPath = path.join(distDir, "index.html");
const assetsDir = path.join(distDir, "assets");

if (!fs.existsSync(indexPath)) {
  throw new Error("Missing dist/index.html. Run the frontend build first.");
}

if (!fs.existsSync(assetsDir)) {
  throw new Error("Missing dist/assets. Build output is incomplete.");
}

const indexHtml = fs.readFileSync(indexPath, "utf8");
if (!indexHtml.includes('<div id="root"></div>')) {
  throw new Error("dist/index.html is missing the React root container.");
}

const assetFiles = fs.readdirSync(assetsDir);
const hasJsBundle = assetFiles.some((file) => file.endsWith(".js"));
const hasCssBundle = assetFiles.some((file) => file.endsWith(".css"));

if (!hasJsBundle || !hasCssBundle) {
  throw new Error("Expected both JS and CSS assets in dist/assets.");
}

console.log("frontend smoke check passed");
