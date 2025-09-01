# Gemini SRT Translator

This web-based tool provides a user-friendly interface to translate subtitle files (`.srt`) using Google's Gemini AI. It's designed to handle batch translations, match subtitles with corresponding video files, and even fetch movie or TV show information from The Movie Database (TMDB).

## Features

- **File Upload**: Upload multiple video and subtitle files simultaneously.
- **Automatic Matching**: Intelligently pairs subtitle files with their corresponding video files.
- **Batch Translation**: Translate multiple subtitle files at once with a single click.
- **TMDB Integration**: Fetch metadata and posters for movies and TV shows.
- **Real-time Console**: Monitor the translation process with live logging in the browser.
- **Configurable**: Easily change the Gemini model and target language via a `config.json` file.
- **Download Translated Files**: Download the newly translated `.srt` files directly from the UI.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/VenimK/gemini-srt-translator-web]
    cd gemini-srt-translator-web
    ```

2.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    # On Windows, use: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create a `.env` file:**
    Create a file named `.env` in the root of the project and add your Gemini API key:
    ```
    GEMINI_API_KEY="your_gemini_api_key_here"
    ```

5.  **(Optional) Configure TMDB:**
    To enable the TMDB feature, add your TMDB API key to the `.env` file:
    ```
    TMDB_API_KEY="your_tmdb_api_key_here"
    ```

## How to Use

1.  **Run the application:**
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000
    ```

2.  **Open your browser:**
    Navigate to `http://127.0.0.1:8000`.

3.  **Upload Files**:
    Click "Choose Files" to select your video and `.srt` files. The application will automatically match them.

4.  **Translate**:
    Select the files you wish to translate using the checkboxes and click the "TRANSLATE" button.

5.  **Download**:
    Once the translation is complete, a download button will appear next to each translated file.

## Configuration

You can customize the translation language and the Gemini model by editing the `config.json` file:

```json
{
  "language_code": "en",
  "model": "gemini-2.5-flash",
  "tmdb_api_key": ""
}
```

- `language_code`: The target language for the translation (e.g., "es" for Spanish, "fr" for French).
- `model`: The Gemini model to use for translation.
- `tmdb_api_key`: Your TMDB API key. It's recommended to set this via the `.env` file, but it can be placed here as a fallback.
