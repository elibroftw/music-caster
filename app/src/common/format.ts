// pure formatting helpers. keep this module free of react/browser/tauri imports so
// the unit tests under app/test/unit can import it straight from node

export function formatTime(seconds: number): string {
	const hours = Math.floor(seconds / 3600);
	const minutes = Math.floor((seconds % 3600) / 60);
	const secs = Math.floor(seconds % 60);

	if (hours > 0) {
		return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
	}
	return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Renders a queue row's track place. The daemon serves the raw tracknumber tag values,
 * so blanks and zero padded numbers reach us as-is.
 * @returns `#X`, `#X / Y`, or null when the track place says nothing useful
 */
export function formatTrackPlace(number: string | null, total: string | null): string | null {
	const clean = (value: string | null) => {
		const trimmed = (value ?? '').trim().replace(/^0+(?=\d)/, '');
		return trimmed === '' ? null : trimmed;
	};
	const trackTotal = clean(total);
	// an untagged number is only worth a row when the album's total is known
	const trackNumber = clean(number) ?? (trackTotal === null ? null : '?');
	if (trackNumber === null) return null;
	// track 1 of 1 says nothing, but `#1` with an unknown total still marks album openers
	if (trackNumber === '1' && trackTotal === '1') return null;
	return trackTotal === null ? `#${trackNumber}` : `#${trackNumber} / ${trackTotal}`;
}
