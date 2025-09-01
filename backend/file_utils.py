import os
from pathlib import Path

def classify_file_type(file_path):
    """Classifies file as video, text (subtitle), or other."""
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm']
    text_extensions = ['.srt', '.ass', '.ssa', '.vtt', '.sub']

    ext = Path(file_path).suffix.lower()
    if ext in video_extensions:
        return 'video'
    elif ext in text_extensions:
        return 'text'
    return 'other'

def find_video_matches(subtitle_files, video_files):
    """Find matching video files for subtitle files."""
    matches = []
    subtitle_files = [Path(f) for f in subtitle_files]
    video_files = [Path(f) for f in video_files]

    video_stems = {v.stem.lower(): v for v in video_files}

    for subtitle_file in subtitle_files:
        subtitle_stem = subtitle_file.stem.lower()
        matched_video = None

        # Direct match
        if subtitle_stem in video_stems:
            matched_video = video_stems.pop(subtitle_stem)
        else:
            # Fuzzy match based on common prefix
            best_match_video = None
            highest_score = 0
            for video_stem, video_path in video_stems.items():
                # A simple similarity score
                score = len(os.path.commonprefix([subtitle_stem, video_stem]))
                if score > highest_score:
                    highest_score = score
                    best_match_video = video_path
            
            # Threshold for a confident match
            if best_match_video and highest_score / len(subtitle_stem) > 0.7:
                matched_video = best_match_video
                # Remove from pool to avoid matching it again
                video_stems.pop(best_match_video.stem.lower())

        status = "Matched" if matched_video else "No match"
        matches.append({
            'subtitle': str(subtitle_file),
            'video': str(matched_video) if matched_video else None,
            'status': status
        })

    # Add remaining video files that didn't get matched
    for video_path in video_stems.values():
        matches.append({
            'subtitle': None,
            'video': str(video_path),
            'status': "No subtitles"
        })

    return matches