"""Text out of a procurement document: PDF, DOCX, DOC (Word 97-2003), XLSX, XLS, and ZIP.

API audit, 30 Sep 2026 (Victor approved "Part A"): the files attached to EU procurement
procedures are stored as text in procurement_documents. The binary is not kept.

extract(data, filename) -> list[Extracted]. One element for an ordinary file; for a ZIP,
one element per file inside it (nested ZIPs are opened one level down). Every element says
how its text was obtained in `source`:
  extracted:<format>        text found
  no-text:<reason>          read, but nothing to extract (e.g. a scanned PDF has no text
                            layer; no OCR is attempted, so this is stated, not guessed)
  unsupported:<format>      a format this module does not read
"""
from __future__ import annotations

import io
import re
import struct
import zipfile
from dataclasses import dataclass

MAX_BYTES = 60 * 1024 * 1024          # larger files are not read
MAX_CHARS = 2_000_000                 # a whole document, capped only against runaways
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class Extracted:
    name: str          # file name (for a ZIP member: its path inside the archive)
    fmt: str           # pdf, docx, doc, xlsx, xls, txt, ...
    text: str | None
    source: str
    inner: bool = False  # True for a file that came out of a ZIP
    size: int | None = None  # bytes read


def _fmt(name: str) -> str:
    m = re.search(r"\.([A-Za-z0-9]{2,5})$", name or "")
    return m.group(1).lower() if m else ""


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    text = _CTRL.sub(" ", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:MAX_CHARS] or None


# --------------------------------------------------------------------------- #
# Formats
# --------------------------------------------------------------------------- #
def _pdf(data: bytes) -> tuple[str | None, str]:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                return None, "no-text:encrypted"
        pages = [p.extract_text() or "" for p in reader.pages]
    except Exception as exc:  # noqa: BLE001 - a broken PDF must not stop a batch
        return None, f"no-text:unreadable-pdf:{type(exc).__name__}"
    text = _clean("\n\n".join(pages))
    if not text or len(text) < 20 * max(1, len(pages)) // 4:
        return None, "no-text:no-text-layer"   # scanned: no OCR
    return text, "extracted:pdf"


def _docx(data: bytes) -> tuple[str | None, str]:
    import docx
    try:
        d = docx.Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        return None, f"no-text:unreadable-docx:{type(exc).__name__}"
    parts = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            parts.append("\t".join(c.text for c in row.cells))
    text = _clean("\n".join(parts))
    return (text, "extracted:docx") if text else (None, "no-text:empty")


def _doc(data: bytes) -> tuple[str | None, str]:
    """Word 97-2003 binary: read the text through the piece table (the Clx in the table
    stream), which is how Word itself locates the characters. Fields keep their result,
    drop their code; cell and row marks become tabs and new lines."""
    import olefile
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        return None, f"no-text:not-ole:{type(exc).__name__}"
    try:
        if not ole.exists("WordDocument"):
            return None, "no-text:no-worddocument-stream"
        wd = ole.openstream("WordDocument").read()
        flags = struct.unpack_from("<H", wd, 0x000A)[0]
        table_name = "1Table" if flags & 0x0200 else "0Table"
        if not ole.exists(table_name):
            return None, "no-text:no-table-stream"
        table = ole.openstream(table_name).read()
        fc_clx, lcb_clx = struct.unpack_from("<II", wd, 0x01A2)
        clx = table[fc_clx:fc_clx + lcb_clx]
        i = 0
        while i < len(clx) and clx[i] == 0x01:            # skip Prc entries
            i += 3 + struct.unpack_from("<H", clx, i + 1)[0]
        if i >= len(clx) or clx[i] != 0x02:
            return None, "no-text:no-piece-table"
        lcb = struct.unpack_from("<I", clx, i + 1)[0]
        plc = clx[i + 5:i + 5 + lcb]
        n = (len(plc) - 4) // 12
        cps = struct.unpack_from(f"<{n + 1}I", plc, 0)
        out = []
        for k in range(n):
            fc = struct.unpack_from("<I", plc, 4 * (n + 1) + 8 * k + 2)[0]
            count = cps[k + 1] - cps[k]
            if fc & 0x40000000:                               # compressed: 1 byte per char
                start = (fc & ~0x40000000) // 2
                out.append(wd[start:start + count].decode("cp1252", errors="replace"))
            else:                                             # UTF-16LE
                out.append(wd[fc:fc + 2 * count].decode("utf-16-le", errors="replace"))
        raw = "".join(out)
    except Exception as exc:  # noqa: BLE001
        return None, f"no-text:unreadable-doc:{type(exc).__name__}"
    finally:
        ole.close()
    raw = re.sub(r"\x13[^\x13\x14\x15]*\x14", "", raw)       # field code, keep its result
    raw = re.sub(r"\x13[^\x13\x14\x15]*\x15", "", raw)       # field with no result
    raw = raw.replace("\x15", "").replace("\x07", "\t").replace("\x0b", "\n").replace("\x0c", "\n")
    text = _clean(raw)
    return (text, "extracted:doc") if text else (None, "no-text:empty")


def _xlsx(data: bytes) -> tuple[str | None, str]:
    import openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        return None, f"no-text:unreadable-xlsx:{type(exc).__name__}"
    lines = []
    for ws in wb.worksheets:
        lines.append(f"## {ws.title}")
        for row in ws.iter_rows(values_only=True):
            cells = ["" if v is None else str(v) for v in row]
            if any(c.strip() for c in cells):
                lines.append("\t".join(cells).rstrip())
    text = _clean("\n".join(lines))
    return (text, "extracted:xlsx") if text else (None, "no-text:empty")


def _xls(data: bytes) -> tuple[str | None, str]:
    import xlrd
    try:
        wb = xlrd.open_workbook(file_contents=data)
    except Exception as exc:  # noqa: BLE001
        return None, f"no-text:unreadable-xls:{type(exc).__name__}"
    lines = []
    for sh in wb.sheets():
        lines.append(f"## {sh.name}")
        for r in range(sh.nrows):
            cells = [str(v) if v not in ("", None) else "" for v in sh.row_values(r)]
            if any(c.strip() for c in cells):
                lines.append("\t".join(cells).rstrip())
    text = _clean("\n".join(lines))
    return (text, "extracted:xls") if text else (None, "no-text:empty")


def _txt(data: bytes) -> tuple[str | None, str]:
    for enc in ("utf-8", "cp1252"):
        try:
            return _clean(data.decode(enc)), "extracted:txt"
        except UnicodeDecodeError:
            continue
    return None, "no-text:undecodable"


_READERS = {"pdf": _pdf, "docx": _docx, "doc": _doc, "xlsx": _xlsx, "xlsm": _xlsx,
            "xls": _xls, "txt": _txt, "csv": _txt}


# Inside a ZIP, keep what a bidder would open; drop what only a program reads. Measured on
# Cedefop, 30 Sep 2026: one archive of unpacked Europass ODT templates gave 4,093 members
# (Pictures/*.png, META-INF/manifest.xml, *.mustache, layout-cache) and Windows folders
# carried Thumbs.db. A drawing, a photo or a sample XML file in a tender dossier stays.
_PACKAGE_DIRS = {"META-INF", "Pictures", "Thumbnails", "_rels", "Configurations2"}
_PACKAGE_FILES = {"mimetype", "manifest.rdf", "[Content_Types].xml", "settings.xml", "styles.xml",
                  "meta.xml", "content.xml", "layout-cache"}
_SYSTEM_FILES = {"thumbs.db", ".ds_store", "desktop.ini"}


def _is_document_member(name: str) -> bool:
    parts = name.split("/")
    base = parts[0] if len(parts) == 1 else parts[-1]
    if parts[0] == "__MACOSX" or base.startswith(".") or base.lower() in _SYSTEM_FILES:
        return False
    if any(p in _PACKAGE_DIRS for p in parts[:-1]) or base in _PACKAGE_FILES:
        return False
    return not base.endswith(".mustache")


def _sniff(data: bytes, fmt: str) -> str:
    """Trust the bytes over the name: some publishers serve a legacy .doc under .docx."""
    if data[:4] == b"%PDF":
        return "pdf"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":      # OLE2: .doc or .xls
        # A Word or Excel file saved in the old format under a new name is read as what it
        # is; any other OLE file (.ppt, .msg, Thumbs.db) keeps its own name (unsupported).
        return {"docx": "doc", "docm": "doc", "dot": "doc", "xlsx": "xls",
                "xlsm": "xls"}.get(fmt, fmt or "doc")
    if data[:2] == b"PK" and fmt not in ("docx", "xlsx", "xlsm"):
        return "zip"
    return fmt


def extract(data: bytes, filename: str, *, _depth: int = 0) -> list[Extracted]:
    fmt = _sniff(data, _fmt(filename))
    if len(data) > MAX_BYTES:
        return [Extracted(filename, fmt, None, "no-text:too-large", size=len(data))]
    if fmt == "zip":
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            return [Extracted(filename, "zip", None, "no-text:bad-zip")]
        out: list[Extracted] = []
        for info in zf.infolist():
            name = info.filename
            if info.is_dir() or not _is_document_member(name):
                continue
            inner = zf.read(info)
            if _depth >= 1 and _sniff(inner, _fmt(name)) == "zip":
                out.append(Extracted(name, "zip", None, "no-text:nested-zip", inner=True, size=len(inner)))
                continue
            for e in extract(inner, name, _depth=_depth + 1):
                e.inner = True
                out.append(e)
        return out or [Extracted(filename, "zip", None, "no-text:no-documents-in-zip",
                                 size=len(data))]
    reader = _READERS.get(fmt)
    if reader is None:
        return [Extracted(filename, fmt, None, f"unsupported:{fmt or 'unknown'}", size=len(data))]
    text, source = reader(data)
    return [Extracted(filename, fmt, text, source, size=len(data))]


def to_html(text: str | None) -> str | None:
    """Paragraphs from blank-line breaks; the text escaped."""
    if not text:
        return None
    import html
    return "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>"
                   for p in re.split(r"\n{2,}", text) if p.strip())
