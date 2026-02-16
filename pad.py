# /// script
# dependencies = ["fastapi", "uvicorn", "websockets", "python-multipart"]
# ///
"""Ultralight collaborative pad - run with: uv run pad.py"""

from fastapi import Body, FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import uvicorn

MEDIA_DIR = Path(__file__).parent / "media"
MEDIA_DIR.mkdir(exist_ok=True)

app = FastAPI()
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

content = ""
clients: list[WebSocket] = []


def sanitize_media_filename(name: str) -> str:
    return Path(name).name.strip()


HTML = r"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>pad</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect x='15' y='10' width='70' height='80' rx='8' fill='%23333'/><rect x='25' y='25' width='40' height='6' rx='2' fill='%236bf'/><rect x='25' y='40' width='50' height='6' rx='2' fill='%23666'/><rect x='25' y='55' width='35' height='6' rx='2' fill='%23666'/></svg>">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=JetBrains+Mono:wght@400&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            height: 100vh;
            background: #111;
            color: #e0e0e0;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            overflow: hidden;
        }
        .layout {
            height: 100%;
            display: flex;
            min-height: 0;
        }
        .sidebar {
            width: 220px;
            background: #0a0a0a;
            border-right: 1px solid #222;
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
            min-height: 0;
        }
        .sidebar-header {
            padding: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 6px;
            flex-shrink: 0;
        }
        .sidebar input[type="file"] { display: none; }
        .btn {
            background: none;
            color: #666;
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            white-space: nowrap;
        }
        .btn:hover { background: #222; color: #aaa; }
        .file-list {
            flex: 1;
            overflow-y: auto;
            padding: 0 8px 8px;
            min-height: 0;
        }
        .file-item {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 5px 8px;
            border-radius: 4px;
            color: #888;
            text-decoration: none;
            font-size: 12px;
        }
        .file-name {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            word-break: break-all;
        }
        .file-item:hover { background: #1a1a1a; color: #ccc; }
        .file-item .delete {
            margin-left: auto;
            color: #666;
            cursor: pointer;
            font-size: 12px;
            opacity: 0;
            transition: opacity 0.1s;
        }
        .file-item:hover .delete { opacity: 1; }
        .file-item .delete:hover { color: #f66; }
        .main {
            flex: 1;
            display: flex;
            flex-direction: column;
            min-width: 0;
            min-height: 0;
            position: relative;
        }
        .editor-shell {
            flex: 1;
            min-height: 0;
            overflow: hidden;
            position: relative;
        }
        #pad,
        #rendered {
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            padding: 16px 20px;
            font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
            font-size: 13px;
            line-height: 1.6;
        }
        #pad {
            background: transparent;
            color: #e0e0e0;
            border: none;
            resize: none;
        }
        #pad:focus { outline: none; }
        #rendered {
            display: none;
            color: #e0e0e0;
            overflow-y: auto;
            word-break: break-word;
            cursor: text;
        }
        #rendered.empty {
            color: #555;
        }
        .editor-shell.render-mode #pad {
            display: none;
        }
        .editor-shell.render-mode #rendered {
            display: block;
        }
        #rendered a { color: #6bf; }
        #rendered a:hover { text-decoration: underline; }
        #rendered code { background: #1a1a1a; padding: 2px 5px; border-radius: 3px; }
        #rendered pre { background: #1a1a1a; padding: 8px; border-radius: 4px; overflow-x: auto; }
        #rendered pre code { background: none; padding: 0; }
        #rendered strong { color: #fff; }
        #rendered em { color: #ccc; }
        #rendered h1, #rendered h2, #rendered h3 { color: #fff; margin: 12px 0 4px; }
        #rendered h1:first-child, #rendered h2:first-child, #rendered h3:first-child { margin-top: 0; }
        #rendered ul, #rendered ol { margin-left: 20px; }
        #rendered p { margin: 6px 0; }
        #rendered blockquote { border-left: 3px solid #333; padding-left: 12px; color: #999; margin: 8px 0; }
        #rendered table { border-collapse: collapse; margin: 8px 0; }
        #rendered th, #rendered td { border: 1px solid #333; padding: 4px 8px; font-size: 12px; }
        #rendered th { background: #1a1a1a; }
        #rendered hr { border: none; border-top: 1px solid #333; margin: 12px 0; }
        #rendered img { max-width: 100%; border-radius: 4px; }
        .btn.active { color: #6bf; }
        .drop-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.8);
            display: none;
            align-items: center;
            justify-content: center;
            color: #6bf;
            font-size: 24px;
            z-index: 100;
        }
        .drop-overlay.active { display: flex; }
        @media (max-width: 850px) {
            .layout {
                flex-direction: column;
            }
            .sidebar {
                width: 100%;
                max-height: 40vh;
                border-right: none;
                border-bottom: 1px solid #222;
            }
        }
    </style>
</head>
<body>
    <div class="layout">
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <button class="btn" id="upload-btn">+ upload</button>
                <button class="btn" id="save-as">save as</button>
                <button class="btn" id="toggle-mode" title="Ctrl+E">rendered</button>
                <input type="file" id="file-input" multiple>
            </div>
            <div class="file-list" id="files"></div>
        </div>
        <div class="main">
            <div class="editor-shell edit-mode" id="editor-shell">
                <textarea id="pad" placeholder="start typing..."></textarea>
                <div id="rendered" title="Click to edit"></div>
            </div>
        </div>
    </div>
    <div class="drop-overlay" id="drop-overlay">Drop files to upload</div>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>
        const pad = document.getElementById('pad');
        const rendered = document.getElementById('rendered');
        const editorShell = document.getElementById('editor-shell');
        const toggleModeBtn = document.getElementById('toggle-mode');
        const saveAsBtn = document.getElementById('save-as');
        const filesDiv = document.getElementById('files');
        const fileInput = document.getElementById('file-input');
        const uploadBtn = document.getElementById('upload-btn');
        const dropOverlay = document.getElementById('drop-overlay');
        const wsProtocol = location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${wsProtocol}://${location.host}/ws`);

        let isRemoteUpdate = false;
        let currentMode = 'edit';

        marked.setOptions({ breaks: true, gfm: true });

        function renderMarkdown(text) {
            if (!text.trim()) {
                rendered.classList.add('empty');
                rendered.textContent = 'Nothing here yet';
                return;
            }
            rendered.classList.remove('empty');
            rendered.innerHTML = marked.parse(text);
            rendered.querySelectorAll('a').forEach(a => {
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
            });
            // Make checkboxes clickable and toggle source markdown
            rendered.querySelectorAll('input[type="checkbox"]').forEach((cb, i) => {
                cb.disabled = false;
                cb.addEventListener('click', () => {
                    let idx = 0;
                    const src = pad.value.replace(/^([\s>]*- )\[([ xX])\]/gm, (match, prefix, check) => {
                        if (idx++ === i) {
                            const toggled = (check === ' ') ? 'x' : ' ';
                            return `${prefix}[${toggled}]`;
                        }
                        return match;
                    });
                    pad.value = src;
                    if (ws.readyState === WebSocket.OPEN) ws.send(pad.value);
                    renderMarkdown(pad.value);
                });
            });
        }

        function setMode(mode) {
            currentMode = mode;
            const renderMode = mode === 'render';
            editorShell.classList.toggle('render-mode', renderMode);
            editorShell.classList.toggle('edit-mode', !renderMode);
            toggleModeBtn.classList.toggle('active', renderMode);
            if (renderMode) {
                renderMarkdown(pad.value);
                rendered.scrollTop = pad.scrollTop;
            } else {
                pad.focus();
            }
        }

        ws.onmessage = (event) => {
            const cursorPos = pad.selectionStart;
            isRemoteUpdate = true;
            pad.value = event.data;
            const nextPos = Math.min(cursorPos, pad.value.length);
            pad.selectionStart = nextPos;
            pad.selectionEnd = nextPos;
            if (currentMode === 'render') renderMarkdown(pad.value);
            isRemoteUpdate = false;
        };

        ws.onclose = () => setTimeout(() => location.reload(), 1000);

        pad.addEventListener('input', () => {
            if (!isRemoteUpdate && ws.readyState === WebSocket.OPEN) {
                ws.send(pad.value);
            }
        });

        pad.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                setMode('render');
                event.preventDefault();
            }
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'e') {
                setMode(currentMode === 'edit' ? 'render' : 'edit');
                event.preventDefault();
            }
        });

        toggleModeBtn.addEventListener('click', () => {
            setMode(currentMode === 'edit' ? 'render' : 'edit');
        });

        rendered.addEventListener('click', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'A') return;
            setMode('edit');
        });

        async function saveAsFile() {
            const filenameInput = prompt('Save as:', 'note.txt');
            if (filenameInput === null) return;

            const filename = filenameInput.trim();
            if (!filename) {
                alert('File name cannot be empty.');
                return;
            }

            try {
                const res = await fetch('/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename, content: pad.value }),
                });
                const data = await res.json();
                if (!res.ok || !data.ok) {
                    alert(data.error || 'Save failed.');
                    return;
                }
                loadFiles();
            } catch {
                alert('Save failed.');
            }
        }

        saveAsBtn.addEventListener('click', saveAsFile);

        async function loadFiles() {
            const res = await fetch('/files');
            const files = await res.json();

            filesDiv.innerHTML = '';
            if (!files.length) {
                const empty = document.createElement('div');
                empty.style.color = '#555';
                empty.style.fontSize = '11px';
                empty.style.padding = '8px';
                empty.textContent = 'No files yet';
                filesDiv.appendChild(empty);
                return;
            }

            files.forEach((name) => {
                const link = document.createElement('a');
                link.className = 'file-item';
                link.href = `/media/${encodeURIComponent(name)}`;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';

                const label = document.createElement('span');
                label.className = 'file-name';
                label.textContent = name;

                const deleteBtn = document.createElement('span');
                deleteBtn.className = 'delete';
                deleteBtn.textContent = 'x';
                deleteBtn.title = 'Delete file';
                deleteBtn.addEventListener('click', (event) => deleteFile(event, name));

                link.appendChild(label);
                link.appendChild(deleteBtn);
                filesDiv.appendChild(link);
            });
        }

        async function uploadFiles(fileList) {
            for (const file of fileList) {
                const form = new FormData();
                form.append('file', file);
                await fetch('/upload', { method: 'POST', body: form });
            }
            loadFiles();
        }

        async function deleteFile(event, name) {
            event.preventDefault();
            event.stopPropagation();
            if (!confirm(`Delete ${name}?`)) return;
            await fetch(`/delete/${encodeURIComponent(name)}`, { method: 'POST' });
            loadFiles();
        }

        uploadBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) uploadFiles(fileInput.files);
            fileInput.value = '';
        });

        let dragCounter = 0;
        document.addEventListener('dragenter', (event) => {
            event.preventDefault();
            dragCounter += 1;
            dropOverlay.classList.add('active');
        });
        document.addEventListener('dragleave', (event) => {
            event.preventDefault();
            dragCounter -= 1;
            if (dragCounter <= 0) dropOverlay.classList.remove('active');
        });
        document.addEventListener('dragover', (event) => event.preventDefault());
        document.addEventListener('drop', (event) => {
            event.preventDefault();
            dragCounter = 0;
            dropOverlay.classList.remove('active');
            if (event.dataTransfer.files.length) uploadFiles(event.dataTransfer.files);
        });

        loadFiles();
    </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def get():
    return HTML


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global content
    await ws.accept()
    clients.append(ws)
    await ws.send_text(content)

    try:
        while True:
            content = await ws.receive_text()
            stale_clients: list[WebSocket] = []
            for client in clients:
                if client == ws:
                    continue
                try:
                    await client.send_text(content)
                except Exception:
                    stale_clients.append(client)

            for stale in stale_clients:
                if stale in clients:
                    clients.remove(stale)
    except WebSocketDisconnect:
        if ws in clients:
            clients.remove(ws)


@app.get("/files")
async def list_files():
    return JSONResponse(sorted([f.name for f in MEDIA_DIR.iterdir() if f.is_file()]))


@app.post("/save")
async def save_text_file(payload: dict = Body(...)):
    filename = sanitize_media_filename(str(payload.get("filename", "")))
    if not filename:
        return JSONResponse({"error": "filename required"}, status_code=400)
    if not filename.lower().endswith(".txt"):
        filename = f"{filename}.txt"

    path = (MEDIA_DIR / filename).resolve()
    if path.parent != MEDIA_DIR.resolve():
        return JSONResponse({"error": "invalid filename"}, status_code=400)

    text = str(payload.get("content", ""))
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o644)
    return JSONResponse({"ok": True, "name": filename})


@app.post("/delete/{filename}")
async def delete_file(filename: str):
    path = (MEDIA_DIR / filename).resolve()
    if path.parent == MEDIA_DIR.resolve() and path.exists() and path.is_file():
        path.unlink()
        return JSONResponse({"ok": True})
    return JSONResponse({"error": "not found"}, status_code=404)


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    safe_name = sanitize_media_filename(file.filename or "")
    if not safe_name:
        return JSONResponse({"error": "filename required"}, status_code=400)

    path = MEDIA_DIR / safe_name
    with open(path, "wb") as f:
        f.write(await file.read())
    os.chmod(path, 0o644)
    return JSONResponse({"ok": True, "name": safe_name})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
