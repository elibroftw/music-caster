-- Deliberately nullable with no numeric default: files without tempo metadata should
-- keep BPM unset so the library displays a blank cell rather than an assumed fallback value.
ALTER TABLE file_metadata ADD COLUMN bpm REAL;
