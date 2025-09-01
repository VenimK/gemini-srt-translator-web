import requests
import re
import logging

class TMDBHelper:
    def __init__(self, api_key, language_code="en-US", logger=logging.getLogger(__name__)):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.language_code = language_code
        self.logger = logger

    def _log(self, message, level=logging.INFO):
        self.logger.log(level, message)

    def _extract_season_episode(self, filename):
        # Regex for SXXEXX, sXXeXX, XXxYY, etc.
        patterns = [
            r"[Ss](\d{1,2})[Ee](\d{1,2})",
            r"(\d{1,2})[xX](\d{1,2})",
            r"season[._\s]?(\d{1,2})[._\s]?episode[._\s]?(\d{1,2})",
            r"(\d{1,2})[._\s]?episode[._\s]?(\d{1,2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return int(match.group(1)), int(match.group(2))
        return None, None

    def _extract_series_title_from_filename(self, filename):
        # Try to find patterns like "Series Name - SXXEXX" or "Series Name.SXXEXX"
        match = re.search(r'^(.*?)[._\s-][Ss]\d{1,2}[Ee]\d{1,2}', filename, re.IGNORECASE)
        if match:
            # Clean the extracted series name
            series_title = match.group(1)
            # Remove common tags that might be at the end of the series title
            series_title = re.sub(r'\\b(1080p|720p|480p|2160p|4k|uhd|web-dl|webrip|bluray|dvdrip|hdrip|hdtv|x264|x265|h264|h265|aac|ac3|dts|remux|repack|proper|internal|limited|extended|uncut)\\b', '', series_title, flags=re.IGNORECASE)
            series_title = re.sub(r'[\\(\\]\\d{4}[\\)\\]]', '', series_title) # Remove year
            series_title = re.sub(r'[._-]', ' ', series_title) # Replace separators
            series_title = re.sub(r'\\s+', ' ', series_title).strip() # Collapse spaces
            return series_title
        
        # If no SXXEXX pattern, try to clean the whole filename as a fallback
        return self._clean_filename(filename)

    def _clean_filename(self, filename):
        # Remove extension
        cleaned = re.sub(r'\.[^.]+$', '', filename)
        # Replace separators with spaces
        cleaned = re.sub(r'[._-]', ' ', cleaned)
        # Remove common tags like resolution, source, codecs, etc.
        cleaned = re.sub(r'\b(1080p|720p|480p|2160p|4k|uhd|web-dl|webrip|bluray|dvdrip|hdrip|hdtv|x264|x265|h264|h265|aac|ac3|dts|remux|repack|proper|internal|limited|extended|uncut)\b', '', cleaned, flags=re.IGNORECASE)
        # Remove year in parentheses or brackets
        cleaned = re.sub(r'[\(\[]\d{4}[\)\]]', '', cleaned)
        # Remove season/episode info
        cleaned = re.sub(r'[Ss]\d{1,2}[Ee]\d{1,2}', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\d{1,2}[xX]\d{1,2}', '', cleaned, flags=re.IGNORECASE)
        # Collapse multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _extract_media_info(self, filename):
        year_match = re.search(r'\b((19|20)\d{2})\b', filename)
        year = int(year_match.group(1)) if year_match else None
        title = self._clean_filename(filename)
        if year:
            # Remove the year from the title string if it's still there
            title = title.replace(str(year), '').strip()
        return title, year

    def search_movie(self, query, year=None):
        params = {'api_key': self.api_key, 'query': query, 'language': self.language_code}
        if year:
            params['year'] = year
        response = requests.get(f"{self.base_url}/search/movie", params=params)
        response.raise_for_status()
        return response.json().get('results', [])

    def search_tv(self, query, year=None):
        params = {'api_key': self.api_key, 'query': query, 'language': self.language_code}
        if year:
            params['first_air_date_year'] = year
        response = requests.get(f"{self.base_url}/search/tv", params=params)
        response.raise_for_status()
        return response.json().get('results', [])

    def get_tv_episode_details(self, tv_id, season_number, episode_number):
        params = {'api_key': self.api_key, 'language': self.language_code}
        url = f"{self.base_url}/tv/{tv_id}/season/{season_number}/episode/{episode_number}"
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_media_info_from_filename(self, filename, is_tv_series, manual_series_title=None):
        self._log(f"Getting media info for filename: {filename}, is_tv_series: {is_tv_series}")

        if is_tv_series:
            season, episode = self._extract_season_episode(filename)
            if season is None or episode is None:
                raise ValueError("Could not extract season and episode from filename.")

            query_title = manual_series_title or self._extract_series_title_from_filename(filename)
            self._log(f"Searching for TV series: '{query_title}'")
            
            series_results = self.search_tv(query_title)
            if not series_results:
                raise ValueError(f"TV series '{query_title}' not found.")
            
            best_match = series_results[0]
            series_id = best_match['id']
            
            self._log(f"Found series: {best_match['name']} (ID: {series_id}). Fetching details for S{season:02d}E{episode:02d}.")
            
            try:
                episode_details = self.get_tv_episode_details(series_id, season, episode)
                return {
                    'title': best_match.get('name', ''),
                    'year': best_match.get('first_air_date', '')[:4], 
                    'overview': best_match.get('overview', ''),
                    'episode_title': episode_details.get('name', ''),
                    'episode_overview': episode_details.get('overview', ''),
                    'poster_path': episode_details.get('still_path') or best_match.get('poster_path', '')
                }
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    raise ValueError(f"Episode S{season:02d}E{episode:02d} not found for series '{best_match['name']}'.")
                else:
                    raise

        else: # It's a movie
            query_title, year = self._extract_media_info(filename)
            self._log(f"Searching for movie: '{query_title}' (Year: {year})")

            movie_results = self.search_movie(query_title, year=year)
            if not movie_results:
                # Try again without the year if no results
                if year:
                    self._log(f"No results for '{query_title}' with year {year}. Retrying without year.")
                    movie_results = self.search_movie(query_title)
            
            if not movie_results:
                raise ValueError(f"Movie '{query_title}' not found.")

            best_match = movie_results[0]
            self._log(f"Found movie: {best_match['title']}")

            return {
                'title': best_match.get('title', ''),
                'year': best_match.get('release_date', '')[:4],
                'overview': best_match.get('overview', ''),
                'episode_title': None,
                'episode_overview': None,
                'poster_path': best_match.get('poster_path', '')
            }
