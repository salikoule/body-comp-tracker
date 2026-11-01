"""Turn a photographed scan report into readable strips for the AI reader."""

import anvil.js
import anvil.media

STRIP_WIDTH = 2048
MAX_STRIPS = 24

_SOURCE = """
async function prepare(url, type, name, stripWidth, maxStrips) {
  const blob = await (await fetch(url)).blob();
  const pages = [];
  if (type === 'application/pdf' || /\\.pdf$/i.test(name || '')) {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const text = new TextDecoder('latin1').decode(bytes);
    let at = 0;
    while ((at = text.indexOf('/DCTDecode', at)) !== -1) {
      let start = text.indexOf('stream', at);
      if (start < 0) break;
      start += 6;
      if (text[start] === '\\r') start++;
      if (text[start] === '\\n') start++;
      const end = text.indexOf('endstream', start);
      if (end < 0) break;
      pages.push(new Blob([bytes.subarray(start, end)], {type: 'image/jpeg'}));
      at = end;
    }
  } else if ((type || '').indexOf('image/') === 0) {
    pages.push(blob);
  }
  const strips = [];
  for (const page of pages) {
    let bitmap;
    try { bitmap = await createImageBitmap(page, {imageOrientation: 'from-image'}); } catch (e) { continue; }
    const w = bitmap.width, h = bitmap.height;
    const outW = Math.min(w, stripWidth), scale = outW / w;
    const stripH = Math.round(w * 0.5), step = Math.round(stripH * 0.85);
    for (let y = 0; y < h && strips.length < maxStrips; y += step) {
      const sh = Math.min(stripH, h - y);
      const canvas = document.createElement('canvas');
      canvas.width = outW;
      canvas.height = Math.max(1, Math.round(sh * scale));
      canvas.getContext('2d').drawImage(bitmap, 0, y, w, sh, 0, 0, canvas.width, canvas.height);
      strips.push(canvas.toDataURL('image/jpeg', 0.85));
      if (y + sh >= h) break;
    }
  }
  return strips;
}
return prepare;
"""

_prepare = None


def strips_for(media):
    """Data-URL JPEG strips of every photographed page, or [] when the file should be read as-is."""
    global _prepare
    if media is None:
        return []
    if _prepare is None:
        _prepare = anvil.js.window.Function(_SOURCE)()
    try:
        with anvil.media.TempUrl(media) as url:
            strips = _prepare(url, media.content_type or "", getattr(media, "name", "") or "", STRIP_WIDTH, MAX_STRIPS)
        return list(strips or [])
    except Exception:
        return []
