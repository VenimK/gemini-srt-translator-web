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
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "type": "log",
            "level": record.levelname.lower(),
            "message": record.getMessage()
        }
        # For progress updates, the message is already a JSON string
        if record.levelname == "PROGRESS":
            try:
                return record.getMessage()
            except json.JSONDecodeError:
                pass # Fallback to standard logging
        
        return json.dumps(log_data)

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
        self.setFormatter(JsonFormatter())

    def emit(self, record):
        log_entry = self.format(record)
        self.broadcaster.add_log(log_entry)

# Add a custom log level for progress
logging.PROGRESS = 25
logging.addLevelName(logging.PROGRESS, "PROGRESS")

# Configure root logger for terminal output
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[logging.StreamHandler()])

# Get the root logger and add our custom handler for the web UI
root_logger = logging.getLogger()
root_logger.addHandler(AppLogHandler(broadcaster))

# --- End Logging Setup ---

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

config_manager = ConfigManager(config_file="config.json")
translator = Translator(config_manager.config)

UPLOAD_DIR = Path("temp_uploads")
TRANSLATED_DIR = Path("translated_subtitles")
UPLOAD_DIR.mkdir(exist_ok=True)
TRANSLATED_DIR.mkdir(exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open(os.path.join("static", "index.html"), "r") as f:
        return f.read()

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
    translator._initialize(config_manager.config)
    logging.info("Configuration updated.")
    return {"message": "Configuration updated successfully"}

@app.get("/models/")
async def get_models():
    models = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ]
    return JSONResponse(content=models)

@app.post("/translate/")
async def translate_files_endpoint(selected_files: list[dict]):
    num_files = len(selected_files)
    logging.info(f"Received translation request for {num_files} files. Starting batch translation...")
    language_code = config_manager.get("language_code", "en")
    
    translated_results = []
    for i, file_pair in enumerate(selected_files):
        subtitle_path_str = file_pair.get('subtitle')
        if not subtitle_path_str:
            continue

        subtitle_path = Path(subtitle_path_str)
        output_dir = TRANSLATED_DIR
        output_dir.mkdir(exist_ok=True)
        output_filename = f"{subtitle_path.stem}.{language_code}{subtitle_path.suffix}"
        output_path = output_dir / output_filename
        
        progress_data = {
            "type": "progress",
            "message": f"Starting translation for: {subtitle_path.name} ({i + 1}/{num_files})",
            "current": i + 1,
            "total": num_files,
            "filename": subtitle_path.name
        }
        logging.log(logging.PROGRESS, json.dumps(progress_data))

        def progress_callback(current_chunk, total_chunks):
            progress_data = {
                "type": "translation_progress",
                "current_file": i + 1,
                "total_files": num_files,
                "filename": subtitle_path.name,
                "current_chunk": current_chunk,
                "total_chunks": total_chunks
            }
            logging.log(logging.PROGRESS, json.dumps(progress_data))

        try:
            translated_path = await translator.translate_subtitle(subtitle_path, output_path, progress_callback=progress_callback)
            if translated_path:
                logging.info(f"Successfully translated: {subtitle_path.name} ({i + 1}/{num_files})")
                translated_results.append({
                    "original_subtitle": subtitle_path_str,
                    "translated_subtitle": str(translated_path),
                    "status": "Success"
                })
            else:
                error_message = f"Translation returned no path for: {subtitle_path.name} ({i + 1}/{num_files})."
                logging.warning(error_message)
                translated_results.append({
                    "original_subtitle": subtitle_path_str,
                    "status": "Failed",
                    "error": error_message
                })
        except Exception as e:
            logging.error(f"Translation failed for {subtitle_path.name} ({i + 1}/{num_files}): {e}")
            translated_results.append({
                "original_subtitle": subtitle_path_str,
                "status": "Failed",
                "error": str(e)
            })
            
    logging.info(f"Batch translation completed for {num_files} files.")
    return JSONResponse(content=translated_results)

@app.get("/tmdb/info")
async def get_tmdb_info(filename: str, series_title: str = None):
    tmdb_api_key = config_manager.get("tmdb_api_key")
    language_code = config_manager.get("language_code", "en-US")
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
                yield f"data: {log_entry}\n\n"
        finally:
            broadcaster.unsubscribe(q)
    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = TRANSLATED_DIR / filename
    if not file_path.exists():
        file_path = UPLOAD_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found at {file_path.absolute()}")
    return FileResponse(path=file_path, media_type='application/octet-stream', filename=filename)

@app.post("/clear_cache")
async def clear_cache_endpoint():
    Translator.clear_cache()
    logging.info("Translation cache cleared.")
    return JSONResponse(content={"status": "success", "message": "Translation cache cleared."})