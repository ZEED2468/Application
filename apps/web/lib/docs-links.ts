/** Open a generated PDF in Google Docs viewer (read-only). */
export function toGoogleDocsViewerUrl(pdfUrl: string | null | undefined): string | null {
  if (!pdfUrl) return null;
  return `https://docs.google.com/viewer?url=${encodeURIComponent(pdfUrl)}`;
}

export function jdPreview(text: string | null | undefined, max = 100): string | null {
  if (!text?.trim()) return null;
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max).trim()}…`;
}
