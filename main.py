from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path
import shutil
import json
import asyncio
import logging
import threading
from collections import deque
from typing import Deque

from backend.file_utils import classify_file_type, find_video_matches
from backend.config_manager import ConfigManager
from backend.translator import Translator
from backend.tmdb_helper import TMDBHelper

# --- Logging Setup ---
class LogBroadcaster:
    def __init__(self):
        self._lock = threading.Lock()
        self.clients: list[asyncio.Queue] = []
        self.history: Deque[str] = deque(maxlen=100)

    def add_log(self, log_entry: str):
        with self._lock:
            self.history.append(log_entry)
            for q in self.clients:
                try:
                    q.put_nowait(log_entry)
                except asyncio.QueueFull:
                    pass

    async def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=200)
        with self._lock:
            for log in self.history:
                q.put_nowait(log)
            self.clients.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        with self._lock:
            try:
                self.clients.remove(q)
            except ValueError:
                pass

broadcaster = LogBroadcaster()

class AppLogHandler(logging.Handler):
    def __init__(self, broadcaster: LogBroadcaster):
        super().__init__()
        self.broadcaster = broadcaster

    def emit(self, record):
        log_entry = self.format(record)
        self.broadcaster.add_log(log_entry)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[logging.StreamHandler()])

queue_handler = AppLogHandler(broadcaster)
queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logging.getLogger().addHandler(queue_handler)
# --- End Logging Setup ---

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

config_manager = ConfigManager(config_file="config.json")

api_key = config_manager.get('gemini_api_key')
model = config_manager.get('model')
if api_key:
    logging.info(f"Using Gemini API Key: {api_key[:5]}...{api_key[-5:]}")
if model:
    logging.info(f"Using Model: {model}")

UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

import asyncio
from fastapi import WebSocket
from typing import Dict, Set
from pathlib import Path
import json
from backend.translator import Translator

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.tasks:
            self.tasks[client_id].cancel()
            del self.tasks[client_id]

    async def send_progress(self, client_id: str, progress: int, total: int):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json({
                    "type": "progress",
                    "progress": progress,
                    "total": total
                })
            except Exception as e:
                logging.error(f"Error sending progress to {client_id}: {e}")
                self.disconnect(client_id)

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page."""
    try:
        with open(os.path.join("static", "index.html"), 'r') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error loading index.html: {e}")
        return "<html><body><h1>Error loading page</h1></body></html>"

@app.post("/upload_files/")
async def upload_files(files: list[UploadFile] = File(...)):
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)
    UPLOAD_DIR.mkdir(exist_ok=True)

    uploaded_files_info = []
    for file in files:
        file_path = UPLOAD_DIR / file.filename
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_files_info.append({"filename": file.filename, "path": str(file_path)})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error uploading {file.filename}: {e}")
    
    found_files = {'video': [], 'text': [], 'other': []}
    for info in uploaded_files_info:
        file_path = Path(info['path'])
        file_type = classify_file_type(file_path)
        found_files[file_type].append(str(file_path))

    matches = find_video_matches(found_files['text'], found_files['video'])
    return JSONResponse(content=matches)

@app.get("/config/")
async def get_config():
    return JSONResponse(content=config_manager.config)

@app.post("/config/")
async def update_config(new_config: dict):
    config_manager.update(new_config)
    config_manager.save_config()
    logging.info("Configuration updated.")
    return {"message": "Configuration updated successfully"}

@app.get("/models/")
async def get_models():
    # In a real application, you might get this from the Gemini API
    # For now, we'll use a static list of common models.
    models = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ]
    return JSONResponse(content=models)

@app.post("/translate")
async def translate_files_endpoint(request: dict):
    """
    Handle file translation with progress tracking.
    Expected request format:
    {
        "files": [{"path": "path/to/file.srt", "name": "file.srt"}],
        "client_id": "unique_client_id"
    }
    """
    try:
        files = request.get("files", [])
        client_id = request.get("client_id")
        
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        results = []
        translator = Translator(config_manager.get_config())
        
        for file_info in files:
            file_path = Path(file_info["path"])
            output_path = UPLOAD_DIR / f"translated_{file_path.name}"
            
            # Progress callback
            async def progress_callback(current: int, total: int):
                if client_id:
                    await manager.send_progress(client_id, current, total)
            
            try:
                # Wrap sync callback in async
                def sync_progress(current: int, total: int):
                    asyncio.create_task(progress_callback(current, total))
                
                translator.translate_subtitle(
                    file_path, 
                    output_path,
                    progress_callback=sync_progress
                )
                
                results.append({
                    "original": file_info["name"],
                    "translated": output_path.name,
                    "status": "completed"
                })
                
            except Exception as e:
                logging.error(f"Error translating {file_path}: {e}")
                results.append({
                    "original": file_info["name"],
                    "error": str(e),
                    "status": "failed"
                })
        
        return {"status": "completed", "results": results}
        
    except Exception as e:
        logging.error(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clear_cache")
async def clear_cache():
    """Clear the translation cache."""
    try:
        Translator.clear_cache()
        return {"status": "success", "message": "Translation cache cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle any incoming messages if needed
    except Exception as e:
        logging.error(f"WebSocket error for {client_id}: {e}")
    finally:
        manager.disconnect(client_id)

@app.get("/tmdb/info")
async def get_tmdb_info(filename: str, series_title: str = None):
    tmdb_api_key = config_manager.get("tmdb_api_key")
    language_code = config_manager.get("language_code", "en-US") # Default to en-US if not found
    if not tmdb_api_key:
        raise HTTPException(status_code=400, detail="TMDB API key not configured.")

    tmdb_helper = TMDBHelper(tmdb_api_key, language_code=language_code)
    try:
        season, episode = tmdb_helper._extract_season_episode(filename)
        is_tv_series = season is not None and episode is not None

        info = tmdb_helper.get_media_info_from_filename(filename, is_tv_series, series_title)
        return JSONResponse(content=info)
    except Exception as e:
        logging.error(f"TMDB info fetch failed for {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs/stream/")
async def stream_logs():
    q = await broadcaster.subscribe()
    async def log_generator():
        try:
            while True:
                log_entry = await q.get()
                yield f"data: {json.dumps(log_entry)}\n\n"
        finally:
            broadcaster.unsubscribe(q)
    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = UPLOAD_DIR / filename
    logging.info(f"Download request for filename: {filename}")
    logging.info(f"Checking for file at path: {file_path.absolute()}")
    logging.info(f"Does file exist? {file_path.exists()}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found at {file_path.absolute()}")
    return FileResponse(path=file_path, media_type='application/octet-stream', filename=filename)
