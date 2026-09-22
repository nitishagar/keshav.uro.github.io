/**
 * Workers Static Assets entry (see wrangler.jsonc `main`).
 *
 * The full implementation lives in ./_worker.js (which doubles as the
 * Cloudflare Pages Functions entry — Pages never serves underscore-prefixed
 * worker files, while Workers bundles this shim at deploy time). Single
 * default export only: workerd boot-crashes on named exports.
 */
export { default } from "./_worker.js";
