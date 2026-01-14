#!/usr/bin/env python3
"""
Lookup audio metadata from Discogs API.

Finds the earliest release for accurate year, plus genre, style, and label.

Requires: pip install requests
Optional: Set DISCOGS_TOKEN environment variable for higher rate limits

Usage:
    python discogs_lookup.py "Pink Floyd" "Comfortably Numb"
    python discogs_lookup.py "Pink Floyd" "Comfortably Numb" --json
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from urllib.parse import quote

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)

DISCOGS_API = "https://api.discogs.com"
USER_AGENT = "AudioTaggerSkill/1.0"


@dataclass
class DiscogsResult:
    artist: str
    title: str
    year: int | None
    genres: list[str]
    styles: list[str]
    label: str | None
    release_id: int
    release_url: str
    format: str | None
    country: str | None


def search_discogs(artist: str, title: str, token: str | None = None) -> list[dict]:
    """Search Discogs for releases matching artist and title."""
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Discogs token={token}"
    
    # Search for track title by artist
    query = f"{artist} {title}"
    url = f"{DISCOGS_API}/database/search"
    params = {
        "q": query,
        "type": "release",
        "per_page": 50,  # Get more results to find earliest
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    
    return response.json().get("results", [])


def get_release_details(release_id: int, token: str | None = None) -> dict:
    """Get full release details including tracklist."""
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Discogs token={token}"
    
    url = f"{DISCOGS_API}/releases/{release_id}"
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    return response.json()


def track_on_release(release_details: dict, title: str) -> bool:
    """Check if the track appears on this release."""
    title_lower = title.lower()
    for track in release_details.get("tracklist", []):
        track_title = track.get("title", "").lower()
        # Fuzzy match: check if title is contained or vice versa
        if title_lower in track_title or track_title in title_lower:
            return True
    return False


def find_earliest_release(
    artist: str, 
    title: str, 
    token: str | None = None,
    verify_tracklist: bool = True
) -> DiscogsResult | None:
    """
    Find the earliest release containing this track.
    
    Args:
        artist: Artist name
        title: Track title
        token: Discogs API token (optional, for higher rate limits)
        verify_tracklist: If True, verify track appears in tracklist (slower but more accurate)
    
    Returns:
        DiscogsResult with earliest release info, or None if not found
    """
    results = search_discogs(artist, title, token)
    
    if not results:
        return None
    
    # Filter and sort by year
    candidates = []
    for r in results:
        year = r.get("year")
        if year and isinstance(year, int) and year > 1900:
            candidates.append(r)
    
    # Sort by year ascending (earliest first)
    candidates.sort(key=lambda x: x.get("year", 9999))
    
    # Find earliest release that actually contains the track
    for candidate in candidates:
        release_id = candidate.get("id")
        
        if verify_tracklist and release_id:
            try:
                details = get_release_details(release_id, token)
                time.sleep(0.5)  # Rate limiting
                
                if not track_on_release(details, title):
                    continue
                
                # Found a verified match
                return DiscogsResult(
                    artist=artist,
                    title=title,
                    year=candidate.get("year"),
                    genres=details.get("genres", []),
                    styles=details.get("styles", []),
                    label=details.get("labels", [{}])[0].get("name") if details.get("labels") else None,
                    release_id=release_id,
                    release_url=f"https://www.discogs.com/release/{release_id}",
                    format=candidate.get("format", [""])[0] if candidate.get("format") else None,
                    country=candidate.get("country"),
                )
            except Exception:
                continue
        else:
            # Skip verification, use search result directly
            return DiscogsResult(
                artist=artist,
                title=title,
                year=candidate.get("year"),
                genres=candidate.get("genre", []),
                styles=candidate.get("style", []),
                label=candidate.get("label", [""])[0] if candidate.get("label") else None,
                release_id=release_id,
                release_url=f"https://www.discogs.com/release/{release_id}",
                format=candidate.get("format", [""])[0] if candidate.get("format") else None,
                country=candidate.get("country"),
            )
    
    # Fallback: return first result without verification
    if candidates:
        c = candidates[0]
        return DiscogsResult(
            artist=artist,
            title=title,
            year=c.get("year"),
            genres=c.get("genre", []),
            styles=c.get("style", []),
            label=c.get("label", [""])[0] if c.get("label") else None,
            release_id=c.get("id"),
            release_url=f"https://www.discogs.com/release/{c.get('id')}",
            format=c.get("format", [""])[0] if c.get("format") else None,
            country=c.get("country"),
        )
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Lookup track metadata from Discogs (finds earliest release)"
    )
    parser.add_argument("artist", help="Artist name")
    parser.add_argument("title", help="Track title")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-verify", action="store_true", 
                        help="Skip tracklist verification (faster but less accurate)")
    parser.add_argument("--token", help="Discogs API token (or set DISCOGS_TOKEN env var)")
    
    args = parser.parse_args()
    
    token = args.token or os.environ.get("DISCOGS_TOKEN")
    
    result = find_earliest_release(
        args.artist, 
        args.title, 
        token=token,
        verify_tracklist=not args.no_verify
    )
    
    if not result:
        print(f"No results found for '{args.artist} - {args.title}'", file=sys.stderr)
        sys.exit(1)
    
    if args.json:
        print(json.dumps({
            "artist": result.artist,
            "title": result.title,
            "year": result.year,
            "genres": result.genres,
            "styles": result.styles,
            "label": result.label,
            "format": result.format,
            "country": result.country,
            "release_id": result.release_id,
            "release_url": result.release_url,
        }, indent=2))
    else:
        print(f"Artist:  {result.artist}")
        print(f"Title:   {result.title}")
        print(f"Year:    {result.year}")
        print(f"Genre:   {', '.join(result.genres) if result.genres else 'N/A'}")
        print(f"Style:   {', '.join(result.styles) if result.styles else 'N/A'}")
        print(f"Label:   {result.label or 'N/A'}")
        print(f"Format:  {result.format or 'N/A'}")
        print(f"Country: {result.country or 'N/A'}")
        print(f"Discogs: {result.release_url}")


if __name__ == "__main__":
    main()
