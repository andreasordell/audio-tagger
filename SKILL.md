---
name: audio-tagger
description: Tag audio files (MP3, FLAC, OGG, M4A, WAV, WMA) with artist and title metadata extracted from filenames. Use when the user wants to add ID3 tags, Vorbis comments, or other audio metadata based on filename patterns like "Artist - Title.mp3".
---

# Audio Tagger

Tag audio files with artist/title metadata parsed from filenames.

## Supported Formats

- **MP3** → ID3v2 tags
- **FLAC** → Vorbis comments  
- **OGG** → Vorbis comments
- **M4A/MP4** → iTunes-style tags
- **WAV** → ID3 tags
- **WMA** → ASF tags

## Quick Start

```bash
# Install dependency
pip install mutagen --break-system-packages

# Tag single file (default pattern: "{artist} - {title}")
python scripts/tag_audio.py "Pink Floyd - Comfortably Numb.mp3"

# Tag directory
python scripts/tag_audio.py ./music/

# Preview without changes
python scripts/tag_audio.py ./music/ --dry-run

# Process subdirectories
python scripts/tag_audio.py ./music/ --recursive
```

## Filename Patterns

Default: `{artist} - {title}` matches "Artist - Song Title.mp3"

Custom patterns:
```bash
--pattern "{title} - {artist}"      # "Song Title - Artist.mp3"
--pattern "{artist} -- {title}"     # "Artist -- Song Title.mp3"  
--pattern "{artist}_{title}"        # "Artist_Song Title.mp3"
```

## Workflow

1. **Analyze filenames** to determine the pattern
2. **Run with --dry-run** to verify parsing
3. **Execute** the actual tagging

## Direct Tagging (Without Script)

For simple cases, use mutagen directly:

```python
from mutagen.easyid3 import EasyID3

audio = EasyID3("song.mp3")
audio['artist'] = 'Artist Name'
audio['title'] = 'Song Title'
audio.save()
```

## Common Issues

- **No ID3 header**: Script creates one automatically
- **Encoding issues**: Uses UTF-8 (ID3v2.4)
- **Pattern mismatch**: Check separator characters match exactly
