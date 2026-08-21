import { expect } from 'chai';
import { formatTrackPlace } from '../../src/common/format.ts';

// the daemon sends both values as raw tag strings (or null when the tag is absent)
describe('formatTrackPlace', () => {
	it('hides a track place with no number and no total', () => {
		expect(formatTrackPlace(null, null)).to.equal(null);
		expect(formatTrackPlace('', null)).to.equal(null);
		expect(formatTrackPlace('   ', '')).to.equal(null);
	});

	it('hides the only track of a single track album', () => {
		expect(formatTrackPlace('1', '1')).to.equal(null);
		expect(formatTrackPlace('01', '01')).to.equal(null);
	});

	it('keeps #1 when the total is unknown, so album openers stay marked', () => {
		expect(formatTrackPlace('1', null)).to.equal('#1');
		expect(formatTrackPlace('1', '')).to.equal('#1');
	});

	it('shows the number over the total', () => {
		expect(formatTrackPlace('1', '12')).to.equal('#1 / 12');
		expect(formatTrackPlace('4', '11')).to.equal('#4 / 11');
	});

	it('strips leading zeros from both values', () => {
		expect(formatTrackPlace('06', '06')).to.equal('#6 / 6');
		expect(formatTrackPlace('06', '012')).to.equal('#6 / 12');
		expect(formatTrackPlace('009', null)).to.equal('#9');
	});

	it('trims surrounding whitespace', () => {
		expect(formatTrackPlace(' 7 ', ' 12 ')).to.equal('#7 / 12');
	});

	it('marks an unknown number against a known total', () => {
		expect(formatTrackPlace(null, '12')).to.equal('#? / 12');
		expect(formatTrackPlace('', '06')).to.equal('#? / 6');
		// still worth showing at a total of 1: the number itself is unknown
		expect(formatTrackPlace(null, '1')).to.equal('#? / 1');
	});

	it('passes through non numeric tag values', () => {
		expect(formatTrackPlace('A1', null)).to.equal('#A1');
	});
});
