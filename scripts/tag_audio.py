#!/usr/bin/env python3
"""
Tag audio files with artist and title extracted from filename.

Supports: MP3 (ID3), FLAC, OGG, M4A/MP4, WMA, WAV
Requires: pip install mutagen

Usage:
    python tag_audio.py <file_or_directory> [--pattern PATTERN] [--dry-run] [--recursive]

Patterns use {artist} and {title} placeholders:
    "{artist} - {title}"     (default)
    "{title} - {artist}"
    "{artist} -- {title}"
    "{artist}_{title}"
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import mutagen
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3, TIT2, TPE1, ID3NoHeaderError
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    from mutagen.mp4 import MP4
    from mutagen.asf import ASF
    from mutagen.wave import WAVE
except ImportError:
    print("Error: mutagen not installed. Run: pip install mutagen")
    sys.exit(1)

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


def tag_mp3(filepath: Path, artist: str, title: str) -> None:
    """Tag MP3 file with ID3v2."""
    try:
        audio = ID3(filepath)
    except ID3NoHeaderError:
        audio = ID3()
    
    audio['TPE1'] = TPE1(encoding=3, text=artist)
    audio['TIT2'] = TIT2(encoding=3, text=title)
    audio.save(filepath)


def tag_flac(filepath: Path, artist: str, title: str) -> None:
    """Tag FLAC file with Vorbis comments."""
    audio = FLAC(filepath)
    audio['artist'] = artist
    audio['title'] = title
    audio.save()


def tag_ogg(filepath: Path, artist: str, title: str) -> None:
    """Tag OGG file with Vorbis comments."""
    audio = OggVorbis(filepath)
    audio['artist'] = artist
    audio['title'] = title
    audio.save()


def tag_m4a(filepath: Path, artist: str, title: str) -> None:
    """Tag M4A/MP4 file."""
    audio = MP4(filepath)
    audio['\xa9ART'] = [artist]
    audio['\xa9nam'] = [title]
    audio.save()


def tag_wma(filepath: Path, artist: str, title: str) -> None:
    """Tag WMA file."""
    audio = ASF(filepath)
    audio['Author'] = [artist]
    audio['Title'] = [title]
    audio.save()


def tag_wav(filepath: Path, artist: str, title: str) -> None:
    """Tag WAV file with ID3."""
    audio = WAVE(filepath)
    if audio.tags is None:
        audio.add_tags()
    audio.tags['TPE1'] = TPE1(encoding=3, text=artist)
    audio.tags['TIT2'] = TIT2(encoding=3, text=title)
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


def tag_file(filepath: Path, pattern: str, dry_run: bool = False) -> tuple[bool, str]:
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
    
    if dry_run:
        return True, f"Would tag: artist='{artist}', title='{title}'"
    
    try:
        TAGGERS[ext](filepath, artist, title)
        return True, f"Tagged: artist='{artist}', title='{title}'"
    except Exception as e:
        return False, f"Error: {e}"


def process_path(path: Path, pattern: str, dry_run: bool, recursive: bool) -> dict:
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
        success, msg = tag_file(filepath, pattern, dry_run)
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
        '''
    )
    parser.add_argument('path', type=Path, help='File or directory to process')
    parser.add_argument('--pattern', '-p', default='{artist} - {title}',
                        help='Filename pattern (default: "{artist} - {title}")')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('--recursive', '-r', action='store_true',
                        help='Process directories recursively')
    
    args = parser.parse_args()
    
    if not args.path.exists():
        print(f"Error: Path not found: {args.path}")
        sys.exit(1)
    
    if args.dry_run:
        print("=== DRY RUN (no changes will be made) ===\n")
    
    stats = process_path(args.path, args.pattern, args.dry_run, args.recursive)
    
    print(f"\nSummary: {stats['success']} tagged, {stats['failed']} failed, {stats['skipped']} skipped")
    
    sys.exit(0 if stats['failed'] == 0 else 1)


if __name__ == '__main__':
    main()
