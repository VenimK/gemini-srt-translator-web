import os
import json
import logging
import time
import hashlib
from pathlib import Path
from typing import Dict, Optional, Callable, List, Tuple
import asyncio
import re

import google.generativeai as genai

class SubtitleBlock:
    def __init__(self, index: int, start_time: str, end_time: str, text: str):
        self.index = index
        self.start_time = start_time
        self.end_time = end_time
        self.text = text

    def __str__(self):
        return f"{self.index}\n{self.start_time} --> {self.end_time}\n{self.text}"

class Translator:
    _instance = None
    _initialized = False
    _cache_file = Path(".translation_cache.json")
    _cache = {}
    last_request_time = 0
    min_request_interval = 0.5  # Reduced for concurrent requests

    def __new__(cls, config: Dict):
        if cls._instance is None:
            cls._instance = super(Translator, cls).__new__(cls)
            cls._instance._initialize(config)
        return cls._instance

    def _initialize(self, config: Dict):
        old_api_key = self.config.get("gemini_api_key") if hasattr(self, 'config') else None
        old_model_name = self.config.get("model") if hasattr(self, 'config') else None

        self.config = config
        self._load_cache()

        self.generation_config = {
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 8192,
        }

        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]

        api_key = os.getenv("GEMINI_API_KEY") or self.config.get("gemini_api_key")
        if not api_key:
            logging.error("No API key found.")
            self.model = None
            self._initialized = False
            return

        new_model_name = self.config.get("model", "gemini-1.5-flash-latest")
        if api_key != old_api_key or new_model_name != old_model_name or not hasattr(self, 'model'):
            try:
                logging.info(f"Initializing Gemini client with API key...")
                genai.configure(api_key=api_key)
                self.model_name = new_model_name
                logging.info(f"Using model: {self.model_name}")
                self.model = genai.GenerativeModel(
                    model_name=self.model_name,
                    safety_settings=self.safety_settings,
                    generation_config=self.generation_config
                )
                self._initialized = True
                logging.info("Translator initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize translator: {e}")
                self.model = None
                self._initialized = False
        else:
            logging.info("Translator already initialized.")
            self._initialized = True

    def _parse_srt(self, srt_content: str) -> List[SubtitleBlock]:
        blocks = []
        for block_text in srt_content.strip().split('\n\n'):
            lines = block_text.split('\n')
            if len(lines) >= 3:
                try:
                    index = int(lines[0])
                    time_line = lines[1]
                    start_time, end_time = time_line.split(' --> ')
                    text = '\n'.join(lines[2:])
                    blocks.append(SubtitleBlock(index, start_time, end_time, text))
                except (ValueError, IndexError) as e:
                    logging.warning(f"Could not parse SRT block: {block_text} - Error: {e}")
        return blocks

    def _reconstruct_srt(self, blocks: List[SubtitleBlock]) -> str:
        # Sort blocks by index before reconstructing
        blocks.sort(key=lambda b: b.index if b else 0)
        return '\n\n'.join(str(block) for block in blocks if block)

    async def _translate_batch(self, texts: List[str], target_language: str) -> List[str]:
        # Rate limiting is now handled by the semaphore in the calling function
        input_json = json.dumps({"lines": texts})
        prompt = f"Translate the 'lines' in the following JSON object to {target_language}. Return a JSON object with a single key 'translated_lines' containing an array of the translated strings. The number of translated strings must match the number of input strings.\n\n{input_json}"

        try:
            response = await self.model.generate_content_async(prompt)
            response_text = response.candidates[0].content.parts[0].text
            
            try:
                # Try to find JSON within the response text
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start != -1 and end != -1:
                    json_str = response_text[start:end]
                    translated_data = json.loads(json_str)
                    translated_lines = translated_data["translated_lines"]
                    if len(translated_lines) == len(texts):
                        return translated_lines
            except json.JSONDecodeError as e:
                logging.warning(f"Failed to parse JSON response: {e}")
                logging.warning(f"Problematic JSON string: {json_str}")

            # If anything fails, fall back
            logging.warning("Falling back to individual translation for this batch.")
            return [await self._translate_text(text, target_language) for text in texts]
        except Exception as e:
            logging.error(f"Batch translation error: {e}")
            return [await self._translate_text(text, target_language) for text in texts]

    async def _translate_text(self, text: str, target_language: str) -> str:
        try:
            response = await self.model.generate_content_async(
                f"Translate this to {target_language}: {text}"
            )
            return response.candidates[0].content.parts[0].text.strip()
        except Exception as e:
            logging.error(f"Single translation error: {e}")
            return text

    async def _translate_srt_file_natively(self, subtitle_path: Path, output_path: Path, progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
        logging.info(f"Starting native concurrent translation for {subtitle_path.name}")
        
        with open(subtitle_path, 'r', encoding='utf-8-sig') as f:
            srt_content = f.read()
        
        blocks = self._parse_srt(srt_content)
        if not blocks:
            logging.warning("No subtitle blocks found to translate.")
            return subtitle_path

        target_language = self.config.get("language", "English")
        batch_size = 50  # Increased batch size
        concurrency_limit = 10
        semaphore = asyncio.Semaphore(concurrency_limit)
        
        translated_blocks = [None] * len(blocks)
        tasks = []
        
        processed_count = 0
        total_count = len(blocks)

        async def translate_and_place(batch_blocks, start_index):
            nonlocal processed_count
            async with semaphore:
                texts_to_translate = [block.text for block in batch_blocks]
                translated_texts = await self._translate_batch(texts_to_translate, target_language)
                
                for i, translated_text in enumerate(translated_texts):
                    original_block = batch_blocks[i]
                    original_block.text = translated_text
                    translated_blocks[start_index + i] = original_block
                
                processed_count += len(batch_blocks)
                if progress_callback:
                    progress_callback(processed_count, total_count)

        for i in range(0, len(blocks), batch_size):
            batch = blocks[i:i+batch_size]
            task = translate_and_place(batch, i)
            tasks.append(task)

        await asyncio.gather(*tasks)
        
        final_blocks = [b for b in translated_blocks if b is not None]
        translated_srt_content = self._reconstruct_srt(final_blocks)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated_srt_content)
            
        logging.info(f"Native translation completed for {subtitle_path.name}")
        return output_path

    async def translate_subtitle(self, subtitle_path: Path, output_path: Path, progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
        if not self._initialized:
            raise RuntimeError("Translator is not initialized. Check API key and configuration.")
        try:
            return await self._translate_srt_file_natively(subtitle_path, output_path, progress_callback)
        except Exception as e:
            logging.error(f"An error occurred during native translation: {e}")
            raise

    def _load_cache(self):
        if self._cache_file.exists():
            try:
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                logging.info(f"Loaded {len(self._cache)} translations from cache")
            except Exception as e:
                logging.warning(f"Failed to load cache: {e}")
                self._cache = {}

    def _save_cache(self):
        try:
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning(f"Failed to save cache: {e}")

    @classmethod
    def clear_cache(cls):
        cls._cache = {}
        if hasattr(cls, '_cache_file') and cls._cache_file.exists():
            try:
                cls._cache_file.unlink()
            except Exception as e:
                logging.error(f"Failed to clear cache file: {e}")

    def __del__(self):
        if hasattr(self, '_cache'):
            self._save_cache()