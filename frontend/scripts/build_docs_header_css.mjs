/**
 * Generate api/docs/_assets/app_header.css from the real app header styles.
 *
 * The API docs pages are static HTML served straight from public/. They do not
 * load the React bundle, so they cannot use src/components/shared/header.css
 * directly, and that file also depends on ~20 CSS variables declared in
 * src/styles/globals.css.
 *
 * This script emits ONE self-contained stylesheet: the variables the header
 * actually references, followed by header.css verbatim. Re-run it whenever the
 * app header changes so the docs header does not drift from the product:
 *
 *     node scripts/build_docs_header_css.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const HEADER = resolve(here, "../src/components/shared/header.css");
const GLOBALS = resolve(here, "../src/styles/globals.css");
const OUT = resolve(here, "../public/api/docs/_assets/app_header.css");

const header = readFileSync(HEADER, "utf8");
const globals = readFileSync(GLOBALS, "utf8");

// every variable the header references
const referenced = new Set(
  [...header.matchAll(/var\((--[a-z0-9-]+)/g)].map((m) => m[1]),
);

// pull their declarations out of the globals :root block
const rootBlock = globals.match(/:root\s*\{([\s\S]*?)\n\}/);
if (!rootBlock) throw new Error("no :root block found in globals.css");

const declarations = [];
for (const [, name, value] of rootBlock[1].matchAll(
  /(--[a-z0-9-]+)\s*:\s*([^;]+);/g,
)) {
  if (referenced.has(name)) declarations.push(`  ${name}: ${value.trim()};`);
}

// resolve one level of indirection: a variable whose value references another
for (const decl of [...declarations]) {
  for (const [, inner] of decl.matchAll(/var\((--[a-z0-9-]+)/g)) {
    if (declarations.some((d) => d.trim().startsWith(inner + ":"))) continue;
    const m = rootBlock[1].match(
      new RegExp(`(${inner})\\s*:\\s*([^;]+);`),
    );
    if (m) declarations.push(`  ${m[1]}: ${m[2].trim()};`);
  }
}

const missing = [...referenced].filter(
  (v) => !declarations.some((d) => d.trim().startsWith(v + ":")) &&
         !header.includes(`${v}:`),
);

const out = `/* GENERATED FILE - do not edit by hand.
 *
 * Built from src/components/shared/header.css by scripts/build_docs_header_css.mjs
 * so the static API docs carry the SAME header as the product. Re-run that
 * script after changing the app header, or the two will drift.
 *
 * Contains: the ${declarations.length} design tokens the header references,
 * then header.css verbatim.
 */
:root {
${declarations.sort().join("\n")}
}

${header}
`;

writeFileSync(OUT, out, "utf8");
console.log(`[OK] wrote ${OUT}`);
console.log(`     ${declarations.length} tokens inlined, header.css ${header.split("\n").length} lines`);
if (missing.length) {
  console.log(`[WARN] variables referenced but not resolved: ${missing.join(", ")}`);
}
