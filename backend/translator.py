import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Callable, List
import google.generativeai as genai
from google.generativeai import types
import asyncio

class Translator:
    _instance = None
    _initialized = False
    _cache_file = Path(".translation_cache.json")
    _cache = {}
    
    def __new__(cls, config: Dict):
        if cls._instance is None:
            cls._instance = super(Translator, cls).__new__(cls)
            cls._instance._initialize(config)
        return cls._instance
    
    def _initialize(self, config: Dict):
        if self._initialized:
            return
            
        self.config = config
        self._load_cache()
        
        # Initialize the Google AI client
        api_key = os.getenv("GEMINI_API_KEY") or self.config.get("api_key")
        if not api_key:
            raise ValueError("No API key provided. Set GEMINI_API_KEY environment variable or provide in config.")
            
        genai.configure(api_key=api_key)
        self.model_name = self.config.get("model", "gemini-2.5-pro")
        self.model = genai.GenerativeModel(self.model_name)
        
        # Configure generation parameters
        self.generation_config = {
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
        self._initialized = True
        logging.info(f"Initialized translator with model: {self.model_name}")
    
    def _load_cache(self):
        if self._cache_file.exists():
            try:
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                logging.info(f"Loaded {len(self._cache)} translations from cache")
            except Exception as e:
                logging.error(f"Failed to load cache: {e}")
                self._cache = {}
    
    def _save_cache(self):
        try:
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Failed to save cache: {e}")
    
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
            'model': self.model_name,
            'language': self.config.get('language'),
            'language_code': self.config.get('language_code')
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    async def _translate_with_retry(self, text: str, max_retries: int = 3) -> str:
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
        
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Create a prompt for translation
                prompt = (
                    f"Translate the following text to {self.config.get('language', 'English')}. "
                    "Keep the timing and formatting exactly the same, only translate the text. "
                    f"Here's the text to translate:\n\n{text}"
                )
                
                # Generate the response
                response = await self.model.generate_content_async(
                    contents=[{"role": "user", "parts": [{"text": prompt}]}],
                    generation_config=types.GenerationConfig(**self.generation_config)
                )
                
                translated = response.text.strip()
                
                # Cache the result
                self._cache[cache_key] = translated
                self._save_cache()
                
                return translated
                
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                if any(x in error_msg for x in ["429", "quota", "rate limit"]):
                    # Exponential backoff with jitter
                    retry_after = min(5 * (2 ** attempt) + random.uniform(0, 1), 60)  # Cap at 60 seconds
                    logging.warning(f"Rate limited. Attempt {attempt + 1}/{max_retries}. Retrying in {retry_after:.1f} seconds...")
                    await asyncio.sleep(retry_after)
                    continue
                logging.error(f"Translation error: {e}")
                raise
        
        # If we get here, all retries failed
        logging.error(f"Failed to translate after {max_retries} attempts")
        raise last_exception or Exception("Translation failed")
    
    async def translate_subtitle(self, subtitle_path: Path, output_path: Path, 
                              progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
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
                    translated_text = await self._translate_with_retry(text)
                    
                    # Rebuild the block
                    translated_block = f"{header}\n{translated_text}"
                    translated_blocks.append(translated_block)

                    # Add a small delay to avoid hitting rate limits
                    await asyncio.sleep(1)
                    
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