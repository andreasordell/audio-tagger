---
name: audio-tagger
description: Tag audio files (MP3, FLAC, OGG, M4A, WAV, WMA) with metadata from filenames or Discogs. Extracts artist/title from filename patterns, optionally enriches with year, genre, style, and label from Discogs (finds earliest release for accurate year). Use when user wants to add ID3 tags or audio metadata.
---

# Audio Tagger

Tag audio files with metadata parsed from filenames, optionally enriched via Discogs.

## Supported Formats

- **MP3** → ID3v2 (TPE1, TIT2, TDRC, TCON, TPUB)
- **FLAC/OGG** → Vorbis comments  
- **M4A/MP4** → iTunes-style tags
- **WAV** → ID3 tags
- **WMA** → ASF tags

## Quick Start

```bash
pip install mutagen requests --break-system-packages

# Basic: artist/title from filename
python scripts/tag_audio.py ./music/

# With Discogs metadata (year, genre, label)
python scripts/tag_audio.py ./music/ --discogs

# Preview first
python scripts/tag_audio.py ./music/ --discogs --dry-run
```

## Discogs Integration

Fetches from Discogs API to find **earliest release** (accurate year), plus genre, style, and label.

```bash
# Standalone lookup
python scripts/discogs_lookup.py "Pink Floyd" "Comfortably Numb"

# JSON output for scripting
python scripts/discogs_lookup.py "Pink Floyd" "Comfortably Numb" --json
```

**API token** (optional, higher rate limits):
```bash
export DISCOGS_TOKEN=your_token_here
# or
python scripts/tag_audio.py ./music/ --discogs --discogs-token YOUR_TOKEN
```

## Filename Patterns

Default: `{artist} - {title}`

```bash
--pattern "{title} - {artist}"      # Title first
--pattern "{artist} -- {title}"     # Double dash
--pattern "{artist}_{title}"        # Underscore
```

## Workflow

1. **Analyze** filenames → determine pattern
2. **Dry-run** → verify parsing and Discogs matches
3. **Execute** → apply tags

## Tags Written

| Field | MP3 (ID3) | FLAC/OGG | M4A |
|-------|-----------|----------|-----|
| Artist | TPE1 | artist | ©ART |
| Title | TIT2 | title | ©nam |
| Year | TDRC | date | ©day |
| Genre | TCON | genre | ©gen |
| Label | TPUB | label | — |
