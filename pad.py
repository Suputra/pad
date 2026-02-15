# /// script
# dependencies = ["fastapi", "uvicorn", "websockets", "python-multipart"]
# ///
"""Ultralight collaborative pad - run with: uv run pad.py"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import uvicorn
import os

app = FastAPI()
content = ""
clients: list[WebSocket] = []
MEDIA_DIR = Path(__file__).parent / "media"
MEDIA_DIR.mkdir(exist_ok=True)

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
        body { height: 100vh; background: #1a1a1a; display: flex; font-family: 'Inter', system-ui, -apple-system, sans-serif; }
        .sidebar {
            width: 200px; background: #0d0d0d; border-right: 1px solid #333;
            display: flex; flex-direction: column; flex-shrink: 0;
        }
        .sidebar-header {
            padding: 12px; border-bottom: 1px solid #333; display: flex;
            align-items: center; justify-content: space-between;
        }
        .sidebar-header h3 { color: #888; font-size: 12px; font-weight: normal; text-transform: uppercase; }
        .sidebar input[type="file"] { display: none; }
        .btn {
            background: #333; color: #e0e0e0; border: none; padding: 4px 8px;
            border-radius: 4px; cursor: pointer; font-size: 11px;
        }
        .btn:hover { background: #444; }
        .file-list { flex: 1; overflow-y: auto; padding: 8px; }
        .file-item {
            display: flex; align-items: center; gap: 6px; padding: 6px 8px;
            border-radius: 4px; color: #aaa; text-decoration: none; font-size: 12px;
            word-break: break-all;
        }
        .file-item:hover { background: #252525; color: #fff; }
        .file-item .delete {
            margin-left: auto; color: #666; cursor: pointer; font-size: 14px;
            opacity: 0; transition: opacity 0.1s;
        }
        .file-item:hover .delete { opacity: 1; }
        .file-item .delete:hover { color: #f66; }
        .main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
        .container { flex: 1; display: flex; flex-direction: column; padding: 12px; gap: 12px; min-height: 0; }
        textarea {
            flex: 1; width: 100%; background: #0d0d0d; color: #e0e0e0;
            border: 1px solid #333; border-radius: 4px; padding: 12px;
            font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
            font-size: 13px; resize: none; line-height: 1.5;
        }
        textarea:focus { outline: none; border-color: #555; }
        #preview {
            background: #0d0d0d; border: 1px solid #333; border-radius: 4px;
            padding: 12px; font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
            font-size: 13px; color: #e0e0e0; line-height: 1.5;
            white-space: pre-wrap; word-break: break-all; max-height: 35vh; overflow-y: auto;
        }
        #preview:empty { display: none; }
        #preview a { color: #6bf; }
        #preview a:hover { text-decoration: underline; }
        #preview code { background: #252525; padding: 2px 5px; border-radius: 3px; }
        #preview pre { background: #252525; padding: 8px; border-radius: 4px; overflow-x: auto; }
        #preview pre code { background: none; padding: 0; }
        #preview strong { color: #fff; }
        #preview em { color: #ccc; }
        #preview h1, #preview h2, #preview h3 { color: #fff; margin: 8px 0 4px; }
        #preview ul, #preview ol { margin-left: 20px; }
        .drop-overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.8);
            display: none; align-items: center; justify-content: center;
            color: #6bf; font-size: 24px; z-index: 100;
        }
        .drop-overlay.active { display: flex; }
        @media (max-width: 600px) {
            .sidebar { width: 150px; }
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-header">
            <h3>Files</h3>
            <button class="btn" onclick="document.getElementById('file-input').click()">+ Upload</button>
            <input type="file" id="file-input" multiple>
        </div>
        <div class="file-list" id="files"></div>
    </div>
    <div class="main">
        <div class="container">
            <textarea id="pad" placeholder="paste anything here..."></textarea>
            <div id="preview"></div>
        </div>
    </div>
    <div class="drop-overlay" id="drop-overlay">Drop files to upload</div>
    <script>
        const pad = document.getElementById('pad');
        const preview = document.getElementById('preview');
        const filesDiv = document.getElementById('files');
        const fileInput = document.getElementById('file-input');
        const dropOverlay = document.getElementById('drop-overlay');
        const ws = new WebSocket(`ws://${location.host}/ws`);
        let isRemoteUpdate = false;

        function renderPreview(text) {
            if (!text.trim()) { preview.innerHTML = ''; return; }

            // Escape HTML
            let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

            // Markdown-ish rendering
            // Code blocks first (```...```)
            html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
            // Inline code
            html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
            // Bold
            html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            // Italic
            html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
            // Headers
            html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
            html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
            html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

            // Links: [text](url)
            html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

            // Auto-link URLs (http://, https://, or bare domains/paths)
            // Match: http(s)://... OR word.word/... OR word/word...
            html = html.replace(
                /(?<!["'=])(https?:\/\/[^\s<]+|(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:\/[^\s<]*)?|(?<![.\w])(?:[a-zA-Z0-9-]+\/)+[a-zA-Z0-9-]+(?:\/[^\s<]*)?)/g,
                (match) => {
                    // Skip if already inside an anchor tag
                    const href = match.startsWith('http') ? match : 'http://' + match;
                    return `<a href="${href}" target="_blank">${match}</a>`;
                }
            );

            preview.innerHTML = html;
        }

        ws.onmessage = (e) => {
            const pos = pad.selectionStart;
            isRemoteUpdate = true;
            pad.value = e.data;
            pad.selectionStart = pad.selectionEnd = pos;
            isRemoteUpdate = false;
            renderPreview(e.data);
        };

        pad.oninput = () => {
            if (!isRemoteUpdate) ws.send(pad.value);
            renderPreview(pad.value);
        };

        ws.onclose = () => setTimeout(() => location.reload(), 1000);

        // File handling
        async function loadFiles() {
            const res = await fetch('/files');
            const files = await res.json();
            filesDiv.innerHTML = files.length ? files.map(f => {
                const ext = f.split('.').pop().toLowerCase();
                const previewable = ['txt','html','htm','pdf','png','jpg','jpeg','gif','svg','webp','mp4','webm','mp3','wav'].includes(ext);
                return `<a class="file-item" href="/${encodeURIComponent(f)}" ${previewable ? 'target="_blank"' : 'download'}>
                    ${f}
                    <span class="delete" onclick="deleteFile(event, '${f}')">&times;</span>
                </a>`;
            }).join('') : '<div style="color:#555;font-size:11px;padding:8px;">No files yet</div>';
        }

        async function uploadFiles(fileList) {
            console.log('Uploading', fileList.length, 'files');
            for (const file of fileList) {
                console.log('Uploading:', file.name);
                const form = new FormData();
                form.append('file', file);
                try {
                    const res = await fetch('/upload', { method: 'POST', body: form });
                    const data = await res.json();
                    console.log('Upload result:', data);
                } catch (e) {
                    console.error('Upload failed:', e);
                }
            }
            loadFiles();
        }

        async function deleteFile(e, name) {
            e.preventDefault();
            e.stopPropagation();
            if (confirm(`Delete ${name}?`)) {
                await fetch(`/delete/${encodeURIComponent(name)}`, { method: 'POST' });
                loadFiles();
            }
        }

        fileInput.onchange = (e) => {
            console.log('File input changed, files:', fileInput.files.length);
            if (fileInput.files.length > 0) {
                uploadFiles(fileInput.files);
            }
            fileInput.value = '';
        };

        // Drag and drop
        let dragCounter = 0;
        document.addEventListener('dragenter', (e) => {
            e.preventDefault();
            dragCounter++;
            dropOverlay.classList.add('active');
        });
        document.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dragCounter--;
            if (dragCounter === 0) dropOverlay.classList.remove('active');
        });
        document.addEventListener('dragover', (e) => e.preventDefault());
        document.addEventListener('drop', (e) => {
            e.preventDefault();
            dragCounter = 0;
            dropOverlay.classList.remove('active');
            console.log('Drop event, files:', e.dataTransfer.files.length);
            if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
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
            for client in clients:
                if client != ws:
                    await client.send_text(content)
    except WebSocketDisconnect:
        clients.remove(ws)

@app.get("/files")
async def list_files():
    return JSONResponse(sorted([f.name for f in MEDIA_DIR.iterdir() if f.is_file()]))

@app.post("/delete/{filename}")
async def delete_file(filename: str):
    path = (MEDIA_DIR / filename).resolve()
    if path.parent == MEDIA_DIR.resolve() and path.exists() and path.is_file():
        path.unlink()
        return JSONResponse({"ok": True})
    return JSONResponse({"error": "not found"}, status_code=404)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Sanitize filename
    safe_name = Path(file.filename).name
    path = MEDIA_DIR / safe_name
    with open(path, "wb") as f:
        f.write(await file.read())
    os.chmod(path, 0o644)  # Ensure nginx can read
    return JSONResponse({"ok": True, "name": safe_name})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
