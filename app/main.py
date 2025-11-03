from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
from defusedxml import ElementTree as defused_et
import xml.dom.minidom
import xml.etree.ElementTree as ET
import xmltodict
import re

# ---------------------------------------------------
#  APP CONFIG
# ---------------------------------------------------
app = FastAPI(title="XML Beauty")

# mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# configure templates directory (used for root page)
templates = Jinja2Templates(directory="app/templates")

# ---------------------------------------------------
#  ROUTES
# ---------------------------------------------------

# Root route opens the XML formatter page
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("xml_tool.html", {"request": request, "now": datetime.utcnow()})

# Small demo route (keep or remove as you like)
@app.get("/api/time")
def api_time():
    return JSONResponse({"utc": datetime.utcnow().isoformat()})

@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request, "now": datetime.utcnow()})

# ---------------------------------------------------
#  XML FORMATTER ENDPOINTS
# ---------------------------------------------------
MAX_XML_BYTES = 1_000_000  # 1 MB limit


def _read_uploaded_file(upload: UploadFile):
    """Helper to read uploaded file content as text (utf-8 fallback to latin1)."""
    contents = None
    if upload and getattr(upload, "filename", None):
        data = None
        # NOTE: caller must await .read() ; this helper expects bytes passed in instead.
        return None
    return None


def _extract_error_line(msg: str):
    """Try to extract a line number from parser error text."""
    if not msg:
        return None
    m = re.search(r'line\s+(\d+)', msg, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


@app.post("/xml/format")
async def xml_format(
    request: Request,
    xml_text: str = Form(None),
    xml_file: UploadFile = File(None),
    indent_spaces: int = Form(4)
):
    """
    Validate and pretty-print XML.
    Returns JSON:
      - success: { "pretty": "<formatted xml>" }
      - error:   { "error": "message", "line": <line number optional> }
    """
    raw = ""
    # pick source
    if xml_file and getattr(xml_file, "filename", None):
        contents = await xml_file.read()
        if len(contents) > MAX_XML_BYTES:
            return JSONResponse({"error": f"File too large ({len(contents)} bytes). Max {MAX_XML_BYTES} bytes."}, status_code=400)
        try:
            raw = contents.decode("utf-8")
        except Exception:
            raw = contents.decode("latin-1", errors="ignore")
    elif xml_text is not None:
        raw = xml_text
        if len(raw.encode("utf-8")) > MAX_XML_BYTES:
            return JSONResponse({"error": f"Text too large ({len(raw.encode('utf-8'))} bytes). Max {MAX_XML_BYTES} bytes."}, status_code=400)
    else:
        return JSONResponse({"error": "No XML provided. Paste XML or upload an .xml file."}, status_code=400)

    raw_stripped = raw.strip()
    if not raw_stripped:
        return JSONResponse({"error": "Empty XML content."}, status_code=400)

    # Validate using defusedxml
    try:
        defused_et.fromstring(raw_stripped.encode("utf-8"))
    except Exception as e:
        msg = str(e)
        line = _extract_error_line(msg)
        return JSONResponse({"error": f"XML parse error: {msg}", "line": line}, status_code=400)

    # Beautify using minidom with chosen indent
    try:
        dom = xml.dom.minidom.parseString(raw_stripped.encode("utf-8"))
        indent = int(indent_spaces) if int(indent_spaces) in (2, 3, 4) else int(4)
        pretty = dom.toprettyxml(indent=" " * indent)
        pretty = "\n".join([line for line in pretty.splitlines() if line.strip() != ""])
    except Exception as e:
        # If pretty-print fails, return a parse error (should be rare because we validated above)
        msg = str(e)
        return JSONResponse({"error": f"Failed to pretty-print XML: {msg}"}, status_code=400)

    return JSONResponse({"pretty": pretty})


@app.post("/xml/minify")
async def xml_minify(
    request: Request,
    xml_text: str = Form(None),
    xml_file: UploadFile = File(None)
):
    """
    Return compact/minified XML (no extra whitespace).
    JSON: { "pretty": "<minified-xml>" } or error object.
    """
    raw = ""
    if xml_file and getattr(xml_file, "filename", None):
        contents = await xml_file.read()
        if len(contents) > MAX_XML_BYTES:
            return JSONResponse({"error": f"File too large ({len(contents)} bytes). Max {MAX_XML_BYTES} bytes."}, status_code=400)
        try:
            raw = contents.decode("utf-8")
        except Exception:
            raw = contents.decode("latin-1", errors="ignore")
    elif xml_text is not None:
        raw = xml_text
        if len(raw.encode("utf-8")) > MAX_XML_BYTES:
            return JSONResponse({"error": f"Text too large ({len(raw.encode('utf-8'))} bytes). Max {MAX_XML_BYTES} bytes."}, status_code=400)
    else:
        return JSONResponse({"error": "No XML provided."}, status_code=400)

    raw = raw.strip()
    if not raw:
        return JSONResponse({"error": "Empty XML content."}, status_code=400)

    # validate
    try:
        defused_et.fromstring(raw.encode("utf-8"))
    except Exception as e:
        line = _extract_error_line(str(e))
        return JSONResponse({"error": f"XML parse error: {str(e)}", "line": line}, status_code=400)

    # minify using ElementTree tostring (compact)
    try:
        tree = ET.fromstring(raw)
        compact = ET.tostring(tree, encoding="utf-8").decode("utf-8")
    except Exception as e:
        return JSONResponse({"error": f"XML minify error: {str(e)}"}, status_code=400)

    return JSONResponse({"pretty": compact})


@app.post("/xml/convert")
async def xml_convert(
    request: Request,
    xml_text: str = Form(None),
    xml_file: UploadFile = File(None)
):
    """
    Convert XML to JSON (structure).
    Returns JSON representation or error.
    """
    raw = ""
    if xml_file and getattr(xml_file, "filename", None):
        contents = await xml_file.read()
        if len(contents) > MAX_XML_BYTES:
            return JSONResponse({"error": f"File too large ({len(contents)} bytes). Max {MAX_XML_BYTES} bytes."}, status_code=400)
        try:
            raw = contents.decode("utf-8")
        except Exception:
            raw = contents.decode("latin-1", errors="ignore")
    elif xml_text is not None:
        raw = xml_text
        if len(raw.encode("utf-8")) > MAX_XML_BYTES:
            return JSONResponse({"error": f"Text too large ({len(raw.encode('utf-8'))} bytes). Max {MAX_XML_BYTES} bytes."}, status_code=400)
    else:
        return JSONResponse({"error": "No XML provided."}, status_code=400)

    raw = raw.strip()
    if not raw:
        return JSONResponse({"error": "Empty XML content."}, status_code=400)

    # validate then convert
    try:
        defused_et.fromstring(raw.encode("utf-8"))
    except Exception as e:
        line = _extract_error_line(str(e))
        return JSONResponse({"error": f"XML parse error: {str(e)}", "line": line}, status_code=400)

    try:
        parsed = xmltodict.parse(raw)
    except Exception as e:
        return JSONResponse({"error": f"XML->JSON parse error: {str(e)}"}, status_code=400)

    # xmltodict returns an OrderedDict — JSONResponse will serialize it
    return JSONResponse(parsed)
