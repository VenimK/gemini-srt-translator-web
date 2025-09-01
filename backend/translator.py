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
    
    def translate_subtitle(self, subtitle_path: Path, output_path: Path, progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
        """
        Translate a subtitle file using the configured model.
        
        Args:
            subtitle_path: Path to the input subtitle file
            output_path: Path where the translated subtitle will be saved
            progress_callback: Optional callback function that takes (current, total) progress
        
        Returns:
            Path to the translated subtitle file
        """
        try:
            # Read the subtitle file
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split into blocks (assuming each subtitle block is separated by two newlines)
            blocks = content.split('\n\n')
            total_blocks = len(blocks)
            
            translated_blocks = []
            
            for i, block in enumerate(blocks):
                if not block.strip():
                    translated_blocks.append('')
                    continue
                    
                # Report progress
                if progress_callback:
                    progress_callback(i + 1, total_blocks)
                
                # Translate the block
                try:
                    # Check cache first
                    cache_key = self._get_cache_key(block)
                    if cache_key in self._cache:
                        translated_text = self._cache[cache_key]
                    else:
                        # Call the Gemini API for translation
                        response = self.model.generate_content(
                            f"Translate the following subtitle text to {self.config.get('language_name', 'English')}. "
                            "Keep the timing and formatting exactly the same, only translate the text. "
                            f"Here's the text to translate: {block}"
                        )
                        translated_text = response.text
                        
                        # Cache the result
                        self._cache[cache_key] = translated_text
                        self._save_cache()
                    
                    translated_blocks.append(translated_text)
                    
                except Exception as e:
                    logging.error(f"Error translating block {i + 1}: {str(e)}")
                    # Keep the original text if translation fails
                    translated_blocks.append(block)
            
            # Write the translated content to the output file
            translated_content = '\n\n'.join(translated_blocks)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            
            # Final progress update
            if progress_callback:
                progress_callback(total_blocks, total_blocks)
            
            return output_path
            
        except Exception as e:
            logging.error(f"Error in translate_subtitle: {str(e)}")
            raise
    
    @classmethod
    def get_models(cls):
        """Return a list of supported model names."""
        return ["gemini-pro", "gemini-1.5-flash", "gemini-2.5-flash"]
    
    def __del__(self):
        # Save cache on cleanup
        self._save_cache()