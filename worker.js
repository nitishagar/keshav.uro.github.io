/**
 * DIY Markdown-for-Agents edge worker.
 *
 * Serves `text/markdown` variants of the site's HTML pages when the request
 * carries `Accept: text/markdown`, reproducing Cloudflare's Pro
 * Markdown-for-Agents output/header contract on the free plan:
 * YAML frontmatter (title/description/image) + body markdown (content only)
 * + trailing fenced JSON-LD block, with native-equivalent header surgery.
 *
 * Structure: thin platform layer (`fetch`, HTMLRewriter removal pass) over
 * pure functions (Accept parsing, meta/JSON-LD extraction, serializer,
 * header rules) so every rule is unit-exercisable without a Worker runtime.
 */

const MAX_CONVERT_BYTES = 2097152; // native 2 MB origin cap (exact: convertible)
const TOKEN_DIVISOR = 4; // documented heuristic: ~4 chars per token
const CONTENT_SIGNAL_DEFAULT = "ai-train=yes, search=yes, ai-input=yes";
// Headers describing the ORIGINAL body; invalid once the body is replaced.
const DROP_HEADERS = [
  "content-encoding",
  "content-range",
  "transfer-encoding",
  "etag",
  "last-modified",
];
// HTMLRewriter removal selectors: non-content landmarks, embeds, scripts,
// and client-only controls. `header` is listed harmlessly (no <header> exists).
const STRIP_SELECTORS = [
  "nav",
  "footer",
  "header",
  "script",
  "style",
  "iframe",
  "noscript",
  "template",
  "source",
  "button.mobile-menu-toggle",
  "a.skip-link",
  "span.faq-toggle",
];

function acceptsMarkdown(acceptHeader) {
  if (acceptHeader === null || acceptHeader === undefined) return false;
  const entries = String(acceptHeader).split(",");
  for (let raw of entries) {
    const parts = raw.split(";");
    const mediaType = parts[0].trim().toLowerCase();
    if (mediaType !== "text/markdown") continue;
    let q = 1;
    for (let i = 1; i < parts.length; i++) {
      const param = parts[i].trim();
      const m = /^q\s*=\s*([0-9.]+)/i.exec(param);
      if (m) {
        const v = parseFloat(m[1]);
        q = Number.isNaN(v) ? 1 : v;
      }
    }
    // q=0 is an explicit refusal; */* alone never triggers (ignored above).
    if (q > 0) return true;
  }
  return false;
}

/** Minimal entity decoder: 5 named refs + decimal/hex numeric refs, one pass.
 *  Bare `&` (e.g. "Ghaziabad & Noida") has no `;` terminator and survives. */
function decodeEntities(s) {
  const named = {
    amp: "&",
    lt: "<",
    gt: ">",
    quot: '"',
    "#39": "'",
    "#x27": "'",
    "#X27": "'",
  };
  return String(s).replace(
    /&(amp|lt|gt|quot|#39|#x27|#X27|#[0-9]+|#[xX][0-9a-fA-F]+);/g,
    (m, ref) => {
      if (Object.prototype.hasOwnProperty.call(named, ref)) return named[ref];
      if (ref[0] === "#") {
        const hex = ref[1] === "x" || ref[1] === "X";
        const code = parseInt(hex ? ref.slice(2) : ref.slice(1), hex ? 16 : 10);
        if (Number.isFinite(code) && code > 0 && code <= 0x10ffff) {
          try {
            return String.fromCodePoint(code);
          } catch {
            return m;
          }
        }
      }
      return m;
    },
  );
}

/** Tag attribute reader: double/single-quoted or unquoted, any order. */
function attr(tag, name) {
  const m = new RegExp(
    "\\b" + name + '\\s*=\\s*(?:"([^"]*)"|\'([^\']*)\'|([^\\s>]+))',
    "i",
  ).exec(tag);
  if (!m) return null;
  return m[1] !== undefined ? m[1] : m[2] !== undefined ? m[2] : m[3];
}

/** Frontmatter source: meta name= wins over og: regardless of order. */
function extractMeta(html) {
  let title = null;
  let titleOg = null;
  let description = null;
  let descriptionOg = null;
  let image = null;
  const re = /<meta\b([^>]*)>/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    const tag = "<meta " + m[1] + ">";
    const name = attr(tag, "name");
    const prop = attr(tag, "property");
    const content = attr(tag, "content");
    if (content === null || content.trim() === "") continue;
    const value = decodeEntities(content.trim());
    if (name !== null && name.toLowerCase() === "title" && title === null) {
      title = value;
    } else if (
      prop !== null &&
      prop.toLowerCase() === "og:title" &&
      titleOg === null
    ) {
      titleOg = value;
    } else if (
      name !== null &&
      name.toLowerCase() === "description" &&
      description === null
    ) {
      description = value;
    } else if (
      prop !== null &&
      prop.toLowerCase() === "og:description" &&
      descriptionOg === null
    ) {
      descriptionOg = value;
    } else if (
      prop !== null &&
      prop.toLowerCase() === "og:image" &&
      image === null
    ) {
      image = value;
    }
  }
  return {
    title: title !== null ? title : titleOg,
    description: description !== null ? description : descriptionOg,
    image,
  };
}

/** Raw inner texts of every application/ld+json block (order preserved). */
function extractJsonLd(html) {
  const out = [];
  const re =
    /<script\b[^>]*\btype\s*=\s*("|')application\/ld\+json\1[^>]*>([\s\S]*?)<\/script\s*>/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    const raw = m[2].trim();
    if (raw !== "") out.push(raw);
  }
  return out;
}

/** Convertible scope: <main> inner, else <body> inner, else whole document. */
function scopeMain(html) {
  let m = /<main\b[^>]*>([\s\S]*?)<\/main\s*>/i.exec(html);
  if (m) return m[1];
  m = /<body\b[^>]*>([\s\S]*?)<\/body\s*>/i.exec(html);
  if (m) return m[1];
  return html;
}

function stripTags(s) {
  return String(s).replace(/<[^>]+>/g, "");
}

function resolveHref(href, baseUrl) {
  const h = String(href);
  if (h === "" || /^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)/.test(h)) return h;
  try {
    return new URL(h, baseUrl).href;
  } catch {
    return h;
  }
}

/** Block/inline HTML serializer. Input: HTMLRewriter-stripped <main> HTML. */
function htmlToMarkdown(html, baseUrl) {
  let s = String(html);
  // FAQ question buttons -> level-3 headings (toggle spans pre-removed).
  // Trailing \s* swallows the source newline+indent so the question text
  // stays on the heading line (same for h1-h6 opens below).
  s = s.replace(
    /<button\b[^>]*\bclass="[^"]*faq-question[^"]*"[^>]*>\s*/gi,
    "\n\n### ",
  );
  s = s.replace(/<span\b[^>]*\bclass="[^"]*faq-q[^"]*"[^>]*>\s*/gi, "");
  s = s.replace(/<\/button\s*>/gi, "\n\n");
  // Headings keep their level.
  s = s.replace(/<h([1-6])\b[^>]*>\s*/gi, (m, level) => {
    return "\n\n" + "#".repeat(Number(level)) + " ";
  });
  s = s.replace(/<\/h[1-6]\s*>/gi, "\n\n");
  // Images degrade to alt text; missing/empty alt drops the marker (never src).
  s = s.replace(/<img\b[^>]*>/gi, (tag) => {
    const alt = attr(tag, "alt");
    return alt !== null && alt.trim() !== "" ? " " + alt.trim() + " " : " ";
  });
  // Anchors -> [text](href) with absolute resolution.
  s = s.replace(/<a\b([^>]*)>([\s\S]*?)<\/a\s*>/gi, (m, attrs, inner) => {
    const text = stripTags(inner).trim();
    if (text === "") return "";
    return "[" + text + "](" + resolveHref(attr("<a " + attrs + ">", "href") || "", baseUrl) + ")";
  });
  // Lists.
  s = s.replace(/<(ul|ol)\b[^>]*>/gi, "\n\n");
  s = s.replace(/<\/(ul|ol)\s*>/gi, "\n");
  s = s.replace(/<li\b[^>]*>/gi, "\n- ");
  s = s.replace(/<\/li\s*>/gi, "");
  // Block containers.
  s = s.replace(/<(p|div|section|article|main|blockquote)\b[^>]*>/gi, "\n\n");
  s = s.replace(/<\/(p|div|section|article|main|blockquote)\s*>/gi, "");
  s = s.replace(/<br\s*\/?>/gi, "\n");
  // Inline emphasis (controlled markup: balanced pairs only).
  s = s.replace(/<\/?(strong|b)\s*>/gi, "**");
  s = s.replace(/<\/?(em|i)\s*>/gi, "*");
  // Drop anything left, decode, normalize whitespace per line.
  s = s.replace(/<[^>]+>/g, "");
  s = decodeEntities(s);
  s = s
    .split("\n")
    .map((line) => line.replace(/[ \t\u00a0]+/g, " ").trim())
    .join("\n");
  s = s.replace(/\n{3,}/g, "\n\n").trim();
  return s;
}

/** Documented estimate: ceil(chars / 4), deterministic per input. */
function estimateTokens(text) {
  return Math.ceil(String(text).length / TOKEN_DIVISOR);
}

/** Assemble frontmatter + body + single fenced JSON-LD block. */
function buildMarkdown(meta, body, jsonLdRaws) {
  const parts = [];
  const fields = [];
  if (meta.title !== null && meta.title !== undefined && meta.title !== "") {
    fields.push("title: " + JSON.stringify(meta.title));
  }
  if (
    meta.description !== null &&
    meta.description !== undefined &&
    meta.description !== ""
  ) {
    fields.push("description: " + JSON.stringify(meta.description));
  }
  if (meta.image !== null && meta.image !== undefined && meta.image !== "") {
    fields.push("image: " + JSON.stringify(meta.image));
  }
  if (fields.length > 0) {
    parts.push("---\n" + fields.join("\n") + "\n---");
  }
  parts.push(body);
  const valid = [];
  for (const raw of jsonLdRaws) {
    try {
      JSON.parse(raw);
      valid.push(raw);
    } catch {
      // Skip-and-continue: one malformed block never breaks the page.
    }
  }
  if (valid.length > 0) {
    parts.push("```json\n" + valid.join("\n") + "\n```");
  }
  return parts.join("\n\n") + "\n";
}

/** Path gate: extensionless/directory/.html(.htm) convert; assets bypass.
 *  Query is already stripped (URL.pathname); comparison is case-insensitive
 *  so /photo.JPG bypasses exactly like /photo.jpg. */
function convertiblePath(pathname) {
  const seg = String(pathname).split("/").pop() || "";
  const dot = seg.lastIndexOf(".");
  if (dot === -1) return true;
  const ext = seg.slice(dot + 1).toLowerCase();
  return ext === "" || ext === "html" || ext === "htm";
}

/** Merge Accept into Vary without duplicating it across layers. */
function mergeVary(headers) {
  const vals = (headers.get("Vary") || "")
    .split(",")
    .map((v) => v.trim())
    .filter((v) => v !== "");
  if (!vals.some((v) => v.toLowerCase() === "accept")) vals.push("Accept");
  headers.set("Vary", vals.join(", "));
}

export default {
  async fetch(request, env) {
    const upstream = await env.ASSETS.fetch(request);
    // 3xx passthrough: redirects (/_redirects) are never converted.
    if (upstream.status >= 300 && upstream.status < 400) {
      return upstream;
    }
    // Non-read methods passthrough untouched.
    if (request.method !== "GET" && request.method !== "HEAD") {
      return upstream;
    }
    if (!acceptsMarkdown(request.headers.get("Accept"))) {
      return upstream;
    }
    // Content gate: only HTML responses convert (assets bypass by type).
    const contentType = upstream.headers.get("Content-Type") || "";
    if (!contentType.toLowerCase().includes("text/html")) {
      return upstream;
    }
    // Path gate: only extensionless/directory/.html convert.
    if (!convertiblePath(new URL(request.url).pathname)) {
      return upstream;
    }

    let rawBytes = null;
    try {
      rawBytes = new Uint8Array(await upstream.arrayBuffer());
      // Size gate on total bytes: over-cap falls back to the FULL original
      // response (never a truncated markdown body).
      if (rawBytes.byteLength > MAX_CONVERT_BYTES) {
        return new Response(rawBytes, upstream);
      }
      const htmlText = new TextDecoder().decode(rawBytes);
      const meta = extractMeta(htmlText);
      const jsonLd = extractJsonLd(htmlText);
      // Platform removal pass: strip non-content landmarks, then serialize.
      let rewriter = new HTMLRewriter();
      for (const selector of STRIP_SELECTORS) {
        rewriter = rewriter.on(selector, {
          element(e) {
            e.remove();
          },
        });
      }
      const cleaned = await rewriter
        .transform(
          new Response(scopeMain(htmlText), {
            headers: { "Content-Type": "text/html" },
          }),
        )
        .text();
      const baseUrl = request.url;
      const body = htmlToMarkdown(cleaned, baseUrl);
      const markdown = buildMarkdown(meta, body, jsonLd);
      const mdBytes = new TextEncoder().encode(markdown);

      const headers = new Headers(upstream.headers);
      for (const name of DROP_HEADERS) headers.delete(name);
      headers.set("Content-Type", "text/markdown; charset=utf-8");
      headers.set("Content-Length", String(mdBytes.byteLength));
      mergeVary(headers);
      headers.set("x-markdown-tokens", String(estimateTokens(markdown)));
      headers.set("x-original-tokens", String(estimateTokens(htmlText)));
      if (!headers.get("content-signal")) {
        headers.set("content-signal", CONTENT_SIGNAL_DEFAULT);
      }
      // Status preserved (404 arm keeps 404 + noindex); HEAD returns the
      // GET-equivalent headers with an empty body.
      return new Response(request.method === "HEAD" ? null : mdBytes, {
        status: upstream.status,
        statusText: upstream.statusText,
        headers,
      });
    } catch {
      // Fail open: converter failure returns the original bytes when we have
      // them. (ASSETS.fetch itself throwing has no original; it propagates.)
      if (rawBytes !== null) return new Response(rawBytes, upstream);
      throw new Error("markdown conversion failed before bytes were read");
    }
  },
};
