CREATE TABLE IF NOT EXISTS file_metadata (
	file_path TEXT PRIMARY KEY NOT NULL,
	title TEXT,
	artist TEXT,
	album TEXT,
	length INTEGER UNSIGNED,
	explicit BOOLEAN DEFAULT 0 NOT NULL CHECK (explicit IN (0, 1)),
	track_number INTEGER UNSIGNED DEFAULT 1 NOT NULL,
	sort_key TEXT DEFAULT file_path NOT NULL,
	time_modified REAL
);
CREATE TABLE IF NOT EXISTS url_metadata (
	src TEXT PRIMARY KEY NOT NULL,
	title TEXT,
	artist TEXT,
	album TEXT,
	length REAL,
	url TEXT,
	audio_url TEXT,
	ext TEXT,
	album_cover_url TEXT,
	expiry REAL,
	id TEXT,
	type TEXT,
	playlist_url TEXT,
	live BOOLEAN DEFAULT 0 NOT NULL CHECK (live IN (0, 1)),
	timestamps TEXT
);

