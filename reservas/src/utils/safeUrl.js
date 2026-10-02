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
