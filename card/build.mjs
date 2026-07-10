// build.mjs — esbuild JS-API build script for intex-pool-card.
// Replaces the POSIX-only shell define in package.json scripts.
// Cross-platform: JSON.stringify avoids the shell-quoting fragility of
//   --define:__CARD_VERSION__='"'$npm_package_version'"'
import { build } from "esbuild";
import { readFileSync } from "node:fs";

const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));

await build({
  entryPoints: ["src/intex-pool-card.js"],
  bundle: true,
  minify: true,
  format: "esm",
  target: "es2021",
  // esbuild 0.28 preserves literal newlines/tabs inside Lit's whitespace
  // template strings. Lowering template literals keeps those bytes escaped,
  // so the generated bundle remains clean under `git diff --check`.
  supported: { "template-literal": false },
  define: { __CARD_VERSION__: JSON.stringify(pkg.version) },
  banner: { js: `// intex-pool-card v${pkg.version}` },
  sourcemap: "linked",
  outfile: "../custom_components/intex_pool/frontend/intex-pool-card.js",
});

console.log(`Built intex-pool-card v${pkg.version}`);
