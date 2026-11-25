// Only plain http(s) links reach href/src; javascript:, data:, relative and credentialed URLs are dropped.
export function safeHttpUrl(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  if (!text || /[\u0000-\u001f\u007f]/.test(text)) return null;
  let url;
  try {
    url = new URL(text);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  if (url.username || url.password) return null;
  return url.href;
}

// Text to show for a link whose href is the normalized URL: the stored text, plus the real destination host
// when the host as written differs from the one the browser will open (IDN/look-alike, percent-encoded or
// full-width characters, case aside), so the text cannot pass for another site.
export function linkText(value, href) {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text || typeof href !== "string") return text;
  let hostname;
  try {
    hostname = new URL(href).hostname;
  } catch {
    return text;
  }
  const written = text
    .replace(/^[a-z][a-z0-9+.-]*:\/\//i, "")
    .split(/[/?#]/)[0]
    .split("@")
    .pop()
    .replace(/:\d*$/, "")
    .toLowerCase();
  return written === hostname ? text : `${text} (destino: ${hostname})`;
}
