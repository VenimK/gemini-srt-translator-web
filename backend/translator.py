import os
import json
import logging
import time
import hashlib
from pathlib import Path
from typing import Dict, Optional, Callable
import asyncio
import re # Import re

import google.generativeai as genai


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
        # Only set _initialized to True after successful initialization
        # This allows re-initialization if the first attempt failed or config changed
        
        old_api_key = self.config.get("gemini_api_key") if hasattr(self, 'config') else None
        old_model_name = self.config.get("model") if hasattr(self, 'config') else None

        self.config = config # Always update the config
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
            # Do not raise ValueError here if it's a re-initialization and key is still missing
            # Instead, set model to None and let translation attempts fail gracefully
            self.model = None
            self._initialized = False
            return
        
        # Only re-configure genai and re-create model if API key or model name has changed
        new_model_name = self.config.get("model", "gemini-1.5-flash-latest")
        if api_key != old_api_key or new_model_name != old_model_name or self.model is None:
            try:
                # Initialize the client with the API key
                logging.info(f"Initializing Gemini client with API key (first 8 chars): {api_key[:8]}...")
                genai.configure(api_key=api_key)
                
                # Get model name with fallback
                self.model_name = new_model_name
                logging.info(f"Using model: {self.model_name}")

                self.model = genai.GenerativeModel(
                    model_name=self.model_name,
                    safety_settings=self.safety_settings,
                    generation_config=self.generation_config
                )
                
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
                self.model = None # Ensure model is None on failure
                self._initialized = False
                # Do not re-raise here, let the calling code handle the uninitialized state
        else:
            logging.info("Translator already initialized with current config. No re-initialization needed.")
            self._initialized = True # Ensure it's marked as initialized if no change
    
    def _test_connection(self):
        """Test the connection to the Gemini API"""
        try:
            response = self.model.generate_content("Test connection")
            
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
            response = await self.model.generate_content_async(
                f"Translate this to {self.config.get('target_language', 'English')}: {text}"
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
        logging.info(f"Translator.translate_subtitle called for {subtitle_path.name}")
        try:
            language = self.config.get("language", "English")
            model_name = self.config.get("model", "gemini-1.5-flash")
            gemini_api_key = self.config.get("gemini_api_key", "")

            if not gemini_api_key:
                raise ValueError("Gemini API key is not set.")

            # Using the gemini-srt-translator CLI tool
            cmd = [
                "gst", "translate",
                "-i", str(subtitle_path),
                "-o", str(output_path),
                "-l", language,
                "--model", model_name,
                "-k", gemini_api_key
            ]

            logging.info(f"Executing command: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            # Read stdout and stderr concurrently
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                log_message = line.strip()
                logging.info(f"GST Output: {log_message}")
                if progress_callback:
                    # Attempt to parse progress from gst output if available
                    # This is a placeholder; actual parsing depends on gst's output format
                    match = re.search(r'Progress: (\\d+)% (\\d+)/(\\d+)', log_message)
                    if match:
                        percentage = int(match.group(1))
                        current = int(match.group(2))
                        total = int(match.group(3))
                        progress_callback(current, total) # Pass current and total blocks
                    else:
                        # If no specific progress, just pass a generic update
                        progress_callback(0, 1) # Indicate some activity
            
            await process.wait()

            if process.returncode == 0:
                logging.info(f"GST command completed successfully for {subtitle_path.name}.")
                return output_path
            else:
                error_output = await process.stdout.read() # Read any remaining output
                logging.error(f"Error translating {subtitle_path.name}. Exit code: {process.returncode}. Output: {error_output}")
                raise RuntimeError(f"Translation failed for {subtitle_path.name}. Check logs for details.")

        except FileNotFoundError:
            logging.error("The 'gst' command was not found. Make sure gemini-srt-translator is installed and in your PATH.")
            raise RuntimeError("The 'gst' command is not available.")
        except Exception as e:
            logging.error(f"An error occurred during translation: {e}")
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
    
    
    
    def __del__(self):
        # Save cache on cleanup
        self._save_cache()