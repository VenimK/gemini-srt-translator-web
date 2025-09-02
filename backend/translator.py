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
    
    def _translate_with_retry(self, text: str, max_retries: int = 3) -> str:
        """
        Translate text with retry logic for rate limits.
        
        Args:
            text: Text to translate
            max_retries: Maximum number of retry attempts
            
        Returns:
            Translated text
            
        Raises:
            Exception: If all retry attempts are exhausted
        """
        import time
        import random
        from google.api_core.exceptions import ResourceExhausted
        
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.model:
            raise ValueError("Model not initialized. Check your API key.")
            
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    f"Translate the following text to {self.config.get('language', 'English')}: {text}"
                )
                translated = response.text
                
                # Cache the result
                self._cache[cache_key] = translated
                self._save_cache()
                
                return translated
                
            except Exception as e:
                last_exception = e
                if "429" in str(e) or "quota" in str(e).lower() or "rate limit" in str(e).lower():
                    # Extract retry delay from error message if available, otherwise use exponential backoff
                    retry_after = 5 * (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                    logging.warning(f"Rate limited. Attempt {attempt + 1}/{max_retries}. Retrying in {retry_after:.1f} seconds...")
                    time.sleep(retry_after)
                    continue
                raise
        
        # If we get here, all retries failed
        logging.error(f"Failed to translate after {max_retries} attempts")
        raise last_exception or Exception("Translation failed")

    def translate_text(self, text: str) -> str:
        """Translate a single text with caching."""
        if not text.strip():
            return text
            
        return self._translate_with_retry(text)
    
    def translate_subtitle(self, subtitle_path: Path, output_path: Path, progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
        """
        Translate a subtitle file using the configured model with progress tracking.
        
        Args:
            subtitle_path: Path to the source SRT file
            output_path: Path to save the translated SRT file
            progress_callback: Optional callback function that takes (current, total) as arguments
            
        Returns:
            Path to the translated subtitle file
        """
        try:
            # Count total blocks first for progress tracking
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split into subtitle blocks (handles both Windows and Unix line endings)
            blocks = [b.strip() for b in content.replace('\r\n', '\n').split('\n\n') if b.strip()]
            total_blocks = len(blocks)
            
            translated_blocks = []
            
            for i, block in enumerate(blocks):
                try:
                    # Update progress
                    if progress_callback:
                        progress_callback(i + 1, total_blocks)
                    
                    # Skip empty blocks
                    if not block.strip():
                        translated_blocks.append('')
                        continue
                        
                    # Parse the block (simple SRT parser)
                    lines = [l for l in block.split('\n') if l.strip()]
                    if len(lines) < 2:  # At least number and timestamp
                        translated_blocks.append(block)
                        continue
                        
                    # Keep the number and timestamp
                    header = '\n'.join(lines[:2])
                    text = '\n'.join(lines[2:])
                    
                    # Translate the text with retry logic
                    translated_text = self._translate_with_retry(text)
                    
                    # Rebuild the block
                    translated_block = f"{header}\n{translated_text}"
                    translated_blocks.append(translated_block)
                    
                except Exception as e:
                    logging.error(f"Error translating block {i + 1}: {str(e)}")
                    # Keep the original block if translation fails
                    translated_blocks.append(block)
            
            # Write the translated file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(translated_blocks))
            
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