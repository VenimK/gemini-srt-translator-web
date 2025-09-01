import re
from pathlib import Path
import google.generativeai as genai
import logging
import subprocess
import time

class Translator:
    def __init__(self, config):
        self.config = config
        gemini_api_key = self.config.get("gemini_api_key")
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel(self.config.get("model"))
        else:
            logging.error("Gemini API Key not provided. Translation will fail.")
            self.model = None

    def translate_subtitle(self, subtitle_path, output_path, progress_callback=None):
        start_time = time.time()
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

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            for line in iter(process.stdout.readline, ''):
                logging.info(line.strip())
                if progress_callback:
                    # Simple progress reporting, can be improved if gst provides better output
                    progress_callback(line.strip())
            
            process.wait()

            if process.returncode == 0:
                end_time = time.time()
                logging.info(f"Translation for {subtitle_path.name} completed in {end_time - start_time:.2f} seconds.")
                return str(output_path)
            else:
                error_output = process.stdout.read() if process.stdout else ""
                logging.error(f"Error translating {subtitle_path.name}. Exit code: {process.returncode}. Output: {error_output}")
                raise RuntimeError(f"Translation failed for {subtitle_path.name}. Check logs for details.")

        except FileNotFoundError:
            logging.error("The 'gst' command was not found. Make sure gemini-srt-translator is installed and in your PATH.")
            raise RuntimeError("The 'gst' command is not available.")
        except Exception as e:
            logging.error(f"An error occurred during translation: {e}")
            raise