import os
import json
import logging
import time
import hashlib
from pathlib import Path
from typing import Dict, Optional, Callable

from google import genai
from google.genai.types import Content, Part

class Translator:
    _instance = None
    _initialized = False
    _cache_file = Path(".translation_cache.json")
    _cache = {}
    last_request_time = 0
    min_request_interval = 6.1  # 10 requests per minute
    
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
        
        # Store generation config
        self.generation_config = {
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 4000,
        }
        
        # Safety settings
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
        
        # Get API key with clear error message
        api_key = os.getenv("GEMINI_API_KEY") or self.config.get("api_key") or self.config.get("gemini_api_key")
        if not api_key:
            error_msg = "No API key found. Please set GEMINI_API_KEY environment variable or provide in config.json"
            logging.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            # Initialize the client with the API key
            logging.info(f"Initializing Gemini client with API key (first 8 chars): {api_key[:8]}...")
            self.client = genai.Client(api_key=api_key)
            
            # Get model name with fallback
            self.model_name = self.config.get("model", "gemini-2.5-flash")
            logging.info(f"Using model: {self.model_name}")
            
            # Test the connection
            self._test_connection()
            
            self._initialized = True
            logging.info("Translator initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize translator: {str(e)}"
            logging.error(error_msg)
            if "quota" in str(e).lower():
                error_msg += "\n\nYou've exceeded your daily quota for the Gemini API."
                error_msg += "\n1. Wait 24 hours for the quota to reset"
                error_msg += "\n2. Upgrade your Google Cloud billing plan"
                error_msg += "\n3. Use a different API key with available quota"
            raise RuntimeError(error_msg) from e
    
    def _test_connection(self):
        """Test the connection to the Gemini API"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[{"role": "user", "parts": [{"text": "Test connection"}]}],
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            
            if not response.candidates or not response.candidates[0].content.parts:
                raise ValueError("Empty response from model")
                
            return True
            
        except Exception as e:
            logging.error(f"Connection test failed: {e}")
            raise
    
    def _rate_limit(self):
        """Ensure we don't exceed the rate limit of 10 requests per minute"""
        now = time.time()
        time_since_last = now - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logging.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def _translate_text(self, text: str) -> str:
        """Translate a single piece of text with rate limiting"""
        self._rate_limit()
        
        try:
            # Format the request
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[{
                    "role": "user",
                    "parts": [{"text": f"Translate this to {self.config.get('target_language', 'English')}: {text}"}]
                }],
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            
            # Extract the response
            if not response.candidates or not response.candidates[0].content.parts:
                raise ValueError("Empty response from model")
                
            translated_text = response.candidates[0].content.parts[0].text.strip()
            return translated_text
            
        except Exception as e:
            logging.error(f"Translation error: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logging.error(f"API Error response: {e.response.text}")
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
    
    def _get_cache_key(self, text: str) -> str:
        key_data = {
            'text': text,
            'model': self.model_name,
            'target_lang': self.config.get('target_language', 'en')
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    async def translate_subtitle(self, subtitle_path: Path, output_path: Path, 
                              progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
        """
        Translate subtitle file using Gemini API
        """
        try:
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split into subtitle blocks
            blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
            total_blocks = len(blocks)
            translated_blocks = []
            
            for i, block in enumerate(blocks):
                if progress_callback:
                    progress_callback(i + 1, total_blocks)
                
                # Split block into lines
                lines = block.split('\n')
                if len(lines) < 2:  # Skip invalid blocks
                    translated_blocks.append(block)
                    continue
                
                # Extract index and timestamp
                index = lines[0]
                timestamp = lines[1]
                text = '\n'.join(lines[2:]) if len(lines) > 2 else ''
                
                if not text.strip():
                    translated_blocks.append(block)
                    continue
                
                # Check cache first
                cache_key = self._get_cache_key(text)
                if cache_key in self._cache:
                    translated_text = self._cache[cache_key]
                else:
                    # Translate the text
                    translated_text = await self._translate_text(text)
                    self._cache[cache_key] = translated_text
                    self._save_cache()
                
                # Rebuild the block
                translated_block = f"{index}\n{timestamp}\n{translated_text}"
                translated_blocks.append(translated_block)
            
            # Write the translated subtitles
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(translated_blocks))
            
            if progress_callback:
                progress_callback(total_blocks, total_blocks)
                
            return output_path
            
        except Exception as e:
            logging.error(f"Error in translate_subtitle: {str(e)}")
            raise
    
    @classmethod
    def clear_cache(cls):
        """Clear the translation cache."""
        cls._cache = {}
        try:
            if cls._cache_file.exists():
                cls._cache_file.unlink()
        except Exception as e:
            logging.error(f"Failed to clear cache file: {e}")
    
    @classmethod
    def get_models(cls):
        """Return a list of supported model names."""
        return ["gemini-pro", "gemini-1.5-flash", "gemini-2.5-flash"]
    
    def __del__(self):
        # Save cache on cleanup
        self._save_cache()