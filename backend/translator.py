import re
import json
import hashlib
import logging
import time
import subprocess
from pathlib import Path
from functools import lru_cache
from typing import Optional, Callable, Dict, Any
import google.generativeai as genai

class Translator:
    _instance = None
    _cache_file = Path(".translation_cache.json")
    _cache: Dict[str, str] = {}
    
    def __new__(cls, config):
        if cls._instance is None:
            cls._instance = super(Translator, cls).__new__(cls)
            cls._instance._initialize(config)
            cls._load_cache()
        return cls._instance
    
    def _initialize(self, config):
        self.config = config
        gemini_api_key = self.config.get("gemini_api_key")
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel(self.config.get("model", "gemini-1.5-flash"))
        else:
            logging.warning("Gemini API Key not provided. Translation will fail.")
            self.model = None
    
    @classmethod
    def _load_cache(cls):
        try:
            if cls._cache_file.exists():
                with open(cls._cache_file, 'r') as f:
                    cls._cache = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load translation cache: {e}")
    
    @classmethod
    def _save_cache(cls):
        try:
            with open(cls._cache_file, 'w') as f:
                json.dump(cls._cache, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save translation cache: {e}")
    
    @classmethod
    def clear_cache(cls):
        """Clear the translation cache."""
        cls._cache = {}
        try:
            if cls._cache_file.exists():
                cls._cache_file.unlink()
        except Exception as e:
            logging.error(f"Failed to clear cache file: {e}")
    
    def _get_cache_key(self, text: str) -> str:
        """Generate a cache key based on text and current config."""
        key_data = {
            'text': text,
            'model': self.config.get('model'),
            'language': self.config.get('language'),
            'language_code': self.config.get('language_code')
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    def translate_text(self, text: str) -> str:
        """Translate a single text with caching."""
        if not text.strip():
            return text
            
        cache_key = self._get_cache_key(text)
        
        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # If not in cache, translate
        if not self.model:
            raise ValueError("Model not initialized. Check your API key.")
            
        try:
            response = self.model.generate_content(f"Translate the following text to {self.config.get('language', 'English')}: {text}")
            translated = response.text
            
            # Cache the result
            self._cache[cache_key] = translated
            self._save_cache()
            
            return translated
        except Exception as e:
            logging.error(f"Translation error: {e}")
            raise
    
    def translate_subtitle(self, subtitle_path: Path, output_path: Path, 
                         progress_callback: Optional[Callable[[int, int], None]] = None) -> None:
        """
        Translate an SRT file with progress tracking.
        
        Args:
            subtitle_path: Path to the source SRT file
            output_path: Path to save the translated SRT file
            progress_callback: Callback function that takes (current, total) as arguments
        """
        start_time = time.time()
        
        try:
            # Count total lines first for progress tracking
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                total_lines = sum(1 for _ in f)
            
            translated_lines = []
            current_line = 0
            
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split into subtitle blocks
            blocks = re.split(r'\n\n', content.strip())
            
            for i, block in enumerate(blocks):
                if not block.strip():
                    continue
                    
                # Parse the block (simple SRT parser)
                lines = block.split('\n')
                if len(lines) < 3:  # At least number, timestamp, and text
                    continue
                    
                # Keep the number and timestamp
                header = '\n'.join(lines[:2])
                text = '\n'.join(lines[2:])
                
                # Translate the text
                translated_text = self.translate_text(text)
                
                # Rebuild the block
                translated_block = f"{header}\n{translated_text}"
                translated_lines.append(translated_block)
                
                # Update progress
                current_line += len(lines) + 1  # +1 for the empty line between blocks
                if progress_callback:
                    progress = int((current_line / total_lines) * 100)
                    progress_callback(progress, 100)
            
            # Write the translated file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(translated_lines))
            
            logging.info(f"Translation completed in {time.time() - start_time:.2f} seconds")
            
        except Exception as e:
            logging.error(f"Error in translate_subtitle: {e}")
            raise
    
    @classmethod
    def get_models(cls):
        """Return a list of supported model names."""
        return ["gemini-pro", "gemini-1.5-flash", "gemini-2.5-flash"]
    
    def __del__(self):
        # Save cache on cleanup
        self._save_cache()