import time
import sqlite3
from datetime import datetime, timedelta

from modules.db import DatabaseConnection


class MockConcertScraper:
    def __init__(self, location='New York'):
        self.location = location

    def _normalize_artist_name(self, name):
        """Normalize artist name for better matching"""
        return name.lower().replace('the ', '').strip()

    def get_artists_from_db(self):
        """Get unique artists from file_metadata and url_metadata tables"""
        artists = set()
        with DatabaseConnection() as conn:
            # Get artists from file metadata
            file_artists = conn.execute('SELECT DISTINCT artist FROM file_metadata WHERE artist IS NOT NULL AND artist != ""').fetchall()
            for row in file_artists:
                artist = row[0]
                if artist and isinstance(artist, str):
                    artists.update(self._normalize_artist_name(a.strip()) for a in artist.split(','))

            # Get artists from URL metadata
            url_artists = conn.execute('SELECT DISTINCT artist FROM url_metadata WHERE artist IS NOT NULL AND artist != ""').fetchall()
            for row in url_artists:
                artist = row[0]
                if artist and isinstance(artist, str):
                    artists.update(self._normalize_artist_name(a.strip()) for a in artist.split(','))
        return artists

    def get_artist_counts(self):
        """Get count of each artist from file_metadata and url_metadata tables"""
        artist_counts = {}
        with DatabaseConnection() as conn:
            def process_artists(table):
                artists = conn.execute(f'SELECT artist FROM {table} WHERE artist IS NOT NULL AND artist != ""').fetchall()
                for row in artists:
                    artist_field = row[0]
                    if artist_field and isinstance(artist_field, str):
                        for a in artist_field.split(','):
                            normalized = self._normalize_artist_name(a.strip())
                            artist_counts[normalized] = artist_counts.get(normalized, 0) + 1

            process_artists('file_metadata')
            process_artists('url_metadata')
        return artist_counts

    def search_artist_events(self, artist_name):
        """Mock method for searching events by artist - returns empty list for future webscraping implementation"""
        return []

    def cache_events(self, events):
        """Cache events to database"""
        with DatabaseConnection() as conn:
            for event in events:
                try:
                    conn.execute('''
                        INSERT OR REPLACE INTO concert_events
                        (artist, event_name, venue, city, state, country, date, url, last_checked)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        event['artist'], event['event_name'], event['venue'],
                        event['city'], event['state'], event['country'],
                        event['date'], event['url'], event['last_checked']
                    ))
                except sqlite3.Error as e:
                    print(f"Error caching event: {e}")

            conn.commit()

    def get_cached_events(self, max_age_days=7):
        """Get cached events, filter by age"""
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)

        with DatabaseConnection() as conn:
            rows = conn.execute('''
                SELECT * FROM concert_events
                WHERE last_checked > ?
                ORDER BY date ASC
            ''', (cutoff_time,)).fetchall()

        return [dict(row) for row in rows]

    def update_artist_events(self, artist_name):
        """Update events for a single artist"""
        events = self.search_artist_events(artist_name)
        if events:
            self.cache_events(events)
        return len(events)

    def update_all_artists_events(self, max_batches=None):
        """Update events for all artists in database"""
        artists = list(self.get_artists_from_db())
        if not artists:
            return 0

        # Sort by last checked, prioritize unchecked artists
        unchecked_artists = []
        checked_artists = []
        cutoff_time = time.time() - (7 * 24 * 60 * 60)  # 7 days ago

        with DatabaseConnection() as conn:
            for artist in artists:
                # Check if we have recent events for this artist
                recent_count = conn.execute('''
                    SELECT COUNT(*) FROM concert_events
                    WHERE artist = ? AND last_checked > ?
                ''', (artist, cutoff_time)).fetchone()[0]

                if recent_count == 0:
                    unchecked_artists.append(artist)
                else:
                    checked_artists.append(artist)

        # Process unchecked first, then checked
        artists_to_process = unchecked_artists + checked_artists

        total_events = 0
        batch_size = 10  # Process 10 artists per batch
        batches_processed = 0

        for i in range(0, len(artists_to_process), batch_size):
            if max_batches and batches_processed >= max_batches:
                break

            batch = artists_to_process[i:i+batch_size]
            print(f"Processing batch {batches_processed + 1}: {len(batch)} artists")

            for artist in batch:
                events_count = self.update_artist_events(artist)
                total_events += events_count
                print(f"  {artist}: {events_count} events")

            batches_processed += 1

        return total_events

    def get_events_for_ui(self, user_location=None, max_distance_km=100):
        """Get events suitable for UI display, sorted by distance/date"""
        events = self.get_cached_events()

        if not events:
            return []

        # For now, simple date-based sorting
        # Future enhancement: calculate distance from user_location
        events.sort(key=lambda e: datetime.strptime(e['date'], '%Y-%m-%d'))

        # Filter events within 3 months
        three_months_later = datetime.now() + timedelta(days=90)
        recent_events = []
        for event in events:
            event_date = datetime.strptime(event['date'], '%Y-%m-%d')
            if event_date >= datetime.now() and event_date <= three_months_later:
                recent_events.append(event)

        return recent_events
