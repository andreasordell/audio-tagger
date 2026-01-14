#!/usr/bin/env python3
"""
Tag audio files with artist and title extracted from filename.
Optionally enrich with Discogs metadata (year, genre, style, label).

Supports: MP3 (ID3), FLAC, OGG, M4A/MP4, WMA, WAV
Requires: pip install mutagen requests

Usage:
    python tag_audio.py <file_or_directory> [--pattern PATTERN] [--dry-run] [--recursive]
    python tag_audio.py <file_or_directory> --discogs  # Fetch from Discogs

Patterns use {artist} and {title} placeholders:
    "{artist} - {title}"     (default)
    "{title} - {artist}"
    "{artist} -- {title}"
    "{artist}_{title}"
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

try:
    import mutagen
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3, TIT2, TPE1, TDRC, TCON, TPUB, ID3NoHeaderError
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    from mutagen.mp4 import MP4
    from mutagen.asf import ASF
    from mutagen.wave import WAVE
except ImportError:
    print("Error: mutagen not installed. Run: pip install mutagen")
    sys.exit(1)

# Optional Discogs support
try:
    from discogs_lookup import find_earliest_release, DiscogsResult
    DISCOGS_AVAILABLE = True
except ImportError:
    DISCOGS_AVAILABLE = False

SUPPORTED_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.m4a', '.mp4', '.wma', '.wav'}


def parse_filename(filename: str, pattern: str) -> dict[str, str] | None:
    """
    Parse artist and title from filename using pattern.
    Returns dict with 'artist' and 'title' keys, or None if no match.
    """
    # Remove extension
    stem = Path(filename).stem
    
    # Escape regex special chars in pattern, then replace placeholders
    escaped = re.escape(pattern)
    regex = escaped.replace(r'\{artist\}', r'(?P<artist>.+?)').replace(r'\{title\}', r'(?P<title>.+)')
    
    match = re.match(f'^{regex}$', stem, re.IGNORECASE)
    if match:
        return {
            'artist': match.group('artist').strip(),
            'title': match.group('title').strip()
        }
    return None


def tag_mp3(filepath: Path, artist: str, title: str, year: int = None, 
            genre: str = None, label: str = None) -> None:
    """Tag MP3 file with ID3v2."""
    try:
        audio = ID3(filepath)
    except ID3NoHeaderError:
        audio = ID3()
    
    audio['TPE1'] = TPE1(encoding=3, text=artist)
    audio['TIT2'] = TIT2(encoding=3, text=title)
    if year:
        audio['TDRC'] = TDRC(encoding=3, text=str(year))
    if genre:
        audio['TCON'] = TCON(encoding=3, text=genre)
    if label:
        audio['TPUB'] = TPUB(encoding=3, text=label)
    audio.save(filepath)


def tag_flac(filepath: Path, artist: str, title: str, year: int = None,
             genre: str = None, label: str = None) -> None:
    """Tag FLAC file with Vorbis comments."""
    audio = FLAC(filepath)
    audio['artist'] = artist
    audio['title'] = title
    if year:
        audio['date'] = str(year)
    if genre:
        audio['genre'] = genre
    if label:
        audio['label'] = label
    audio.save()


def tag_ogg(filepath: Path, artist: str, title: str, year: int = None,
            genre: str = None, label: str = None) -> None:
    """Tag OGG file with Vorbis comments."""
    audio = OggVorbis(filepath)
    audio['artist'] = artist
    audio['title'] = title
    if year:
        audio['date'] = str(year)
    if genre:
        audio['genre'] = genre
    if label:
        audio['label'] = label
    audio.save()


def tag_m4a(filepath: Path, artist: str, title: str, year: int = None,
            genre: str = None, label: str = None) -> None:
    """Tag M4A/MP4 file."""
    audio = MP4(filepath)
    audio['\xa9ART'] = [artist]
    audio['\xa9nam'] = [title]
    if year:
        audio['\xa9day'] = [str(year)]
    if genre:
        audio['\xa9gen'] = [genre]
    # Note: MP4 doesn't have a standard label field
    audio.save()


def tag_wma(filepath: Path, artist: str, title: str, year: int = None,
            genre: str = None, label: str = None) -> None:
    """Tag WMA file."""
    audio = ASF(filepath)
    audio['Author'] = [artist]
    audio['Title'] = [title]
    if year:
        audio['WM/Year'] = [str(year)]
    if genre:
        audio['WM/Genre'] = [genre]
    if label:
        audio['WM/Publisher'] = [label]
    audio.save()


def tag_wav(filepath: Path, artist: str, title: str, year: int = None,
            genre: str = None, label: str = None) -> None:
    """Tag WAV file with ID3."""
    audio = WAVE(filepath)
    if audio.tags is None:
        audio.add_tags()
    audio.tags['TPE1'] = TPE1(encoding=3, text=artist)
    audio.tags['TIT2'] = TIT2(encoding=3, text=title)
    if year:
        audio.tags['TDRC'] = TDRC(encoding=3, text=str(year))
    if genre:
        audio.tags['TCON'] = TCON(encoding=3, text=genre)
    if label:
        audio.tags['TPUB'] = TPUB(encoding=3, text=label)
    audio.save()


TAGGERS = {
    '.mp3': tag_mp3,
    '.flac': tag_flac,
    '.ogg': tag_ogg,
    '.m4a': tag_m4a,
    '.mp4': tag_m4a,
    '.wma': tag_wma,
    '.wav': tag_wav,
}


def tag_file(filepath: Path, pattern: str, dry_run: bool = False,
             use_discogs: bool = False, discogs_token: str = None) -> tuple[bool, str]:
    """
    Tag a single audio file.
    Returns (success, message).
    """
    ext = filepath.suffix.lower()
    
    if ext not in SUPPORTED_EXTENSIONS:
        return False, f"Unsupported format: {ext}"
    
    parsed = parse_filename(filepath.name, pattern)
    if not parsed:
        return False, f"Filename doesn't match pattern '{pattern}'"
    
    artist, title = parsed['artist'], parsed['title']
    year, genre, label = None, None, None
    discogs_info = ""
    
    # Fetch from Discogs if requested
    if use_discogs:
        if not DISCOGS_AVAILABLE:
            return False, "Discogs lookup not available (check discogs_lookup.py)"
        
        try:
            result = find_earliest_release(artist, title, token=discogs_token)
            if result:
                year = result.year
                # Combine genres and styles for richer genre tag
                all_genres = result.genres + result.styles
                genre = ", ".join(all_genres[:3]) if all_genres else None  # Limit to 3
                label = result.label
                discogs_info = f" [Discogs: {year}, {genre or 'N/A'}, {label or 'N/A'}]"
            else:
                discogs_info = " [Discogs: not found]"
        except Exception as e:
            discogs_info = f" [Discogs error: {e}]"
    
    if dry_run:
        return True, f"Would tag: artist='{artist}', title='{title}'{discogs_info}"
    
    try:
        TAGGERS[ext](filepath, artist, title, year=year, genre=genre, label=label)
        return True, f"Tagged: artist='{artist}', title='{title}'{discogs_info}"
    except Exception as e:
        return False, f"Error: {e}"


def process_path(path: Path, pattern: str, dry_run: bool, recursive: bool,
                 use_discogs: bool = False, discogs_token: str = None) -> dict:
    """
    Process a file or directory.
    Returns stats dict with 'success', 'failed', 'skipped' counts.
    """
    stats = {'success': 0, 'failed': 0, 'skipped': 0, 'details': []}
    
    if path.is_file():
        files = [path]
    else:
        glob_pattern = '**/*' if recursive else '*'
        files = [f for f in path.glob(glob_pattern) if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
    
    for filepath in sorted(files):
        success, msg = tag_file(filepath, pattern, dry_run, use_discogs, discogs_token)
        detail = {'file': str(filepath), 'success': success, 'message': msg}
        stats['details'].append(detail)
        
        if success:
            stats['success'] += 1
            print(f"✓ {filepath.name}: {msg}")
        else:
            if 'Unsupported' in msg or "doesn't match" in msg:
                stats['skipped'] += 1
                print(f"⊘ {filepath.name}: {msg}")
            else:
                stats['failed'] += 1
                print(f"✗ {filepath.name}: {msg}")
        
        # Rate limiting for Discogs
        if use_discogs and not dry_run:
            time.sleep(1)
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Tag audio files with artist/title from filename',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  tag_audio.py "Pink Floyd - Comfortably Numb.mp3"
  tag_audio.py ./music --pattern "{artist} - {title}"
  tag_audio.py ./music --pattern "{title} by {artist}" --dry-run
  tag_audio.py ./music --recursive
  tag_audio.py ./music --discogs  # Fetch year/genre/label from Discogs
        '''
    )
    parser.add_argument('path', type=Path, help='File or directory to process')
    parser.add_argument('--pattern', '-p', default='{artist} - {title}',
                        help='Filename pattern (default: "{artist} - {title}")')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('--recursive', '-r', action='store_true',
                        help='Process directories recursively')
    parser.add_argument('--discogs', '-d', action='store_true',
                        help='Fetch metadata from Discogs (year, genre, label)')
    parser.add_argument('--discogs-token', 
                        help='Discogs API token (or set DISCOGS_TOKEN env var)')
    
    args = parser.parse_args()
    
    if not args.path.exists():
        print(f"Error: Path not found: {args.path}")
        sys.exit(1)
    
    if args.discogs and not DISCOGS_AVAILABLE:
        print("Error: Discogs lookup requires discogs_lookup.py in same directory")
        sys.exit(1)
    
    if args.dry_run:
        print("=== DRY RUN (no changes will be made) ===\n")
    
    if args.discogs:
        print("=== Fetching metadata from Discogs (earliest release) ===\n")
    
    token = args.discogs_token or os.environ.get('DISCOGS_TOKEN')
    stats = process_path(args.path, args.pattern, args.dry_run, args.recursive,
                         args.discogs, token)
    
    print(f"\nSummary: {stats['success']} tagged, {stats['failed']} failed, {stats['skipped']} skipped")
    
    sys.exit(0 if stats['failed'] == 0 else 1)


if __name__ == '__main__':
    main()
