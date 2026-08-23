-- adds the genre column. a plain ALTER TABLE ADD COLUMN would fail with "duplicate
-- column name" on databases that already have it (the daemon briefly added it with an
-- idempotent ALTER, and an edit of migration 3 shipped for a short window), and sqlite
-- has no ADD COLUMN IF NOT EXISTS, so rebuild the table to the target schema instead.
-- genre values are not carried over; the daemon repopulates them on its next library index.
CREATE TABLE file_metadata_new (
	file_path TEXT PRIMARY KEY NOT NULL,
	title TEXT,
	artist TEXT,
	album TEXT,
	genre TEXT,
	length INTEGER UNSIGNED,
	explicit BOOLEAN DEFAULT 0 NOT NULL CHECK (explicit IN (0, 1)),
	track_number INTEGER UNSIGNED DEFAULT 1 NOT NULL,
	sort_key TEXT DEFAULT file_path NOT NULL,
	time_modified REAL
);
INSERT INTO file_metadata_new (file_path, title, artist, album, length, explicit, track_number, sort_key, time_modified)
	SELECT file_path, title, artist, album, length, explicit, track_number, sort_key, time_modified FROM file_metadata;
DROP TABLE file_metadata;
ALTER TABLE file_metadata_new RENAME TO file_metadata;
