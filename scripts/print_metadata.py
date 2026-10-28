"""
Print the metadata Music Caster reads for every audio file in a folder.

Usage: python scripts/print_metadata.py <folder> [--raw] [--recursive]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import mutagen  # noqa: E402
from meta import AUDIO_EXTS  # noqa: E402
from utils import get_metadata  # noqa: E402

FIELDS = ('track_number', 'track_total', 'title', 'artist', 'album', 'sort_key')
# raw tags that influence track ordering
RAW_KEYS = ('tracknumber', 'tracktotal', 'totaltracks', 'discnumber', 'trkn', 'TRCK', 'TPOS')


def audio_files(folder: str, recursive: bool):
    if recursive:
        for root, _, files in os.walk(folder):
            for f in sorted(files):
                yield os.path.join(root, f)
    else:
        for f in sorted(os.listdir(folder)):
            yield os.path.join(folder, f)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('folder')
    parser.add_argument('--raw', action='store_true', help='also print raw ordering-related tags')
    parser.add_argument('--recursive', '-r', action='store_true')
    args = parser.parse_args()

    for path in audio_files(args.folder, args.recursive):
        if os.path.splitext(path)[1].casefold() not in AUDIO_EXTS:
            continue
        print(os.path.basename(path))
        try:
            m = get_metadata(path)
        except Exception as e:  # report and keep going so one bad file doesn't hide the rest
            print(f'  ERROR: {e!r}\n')
            continue
        for field in FIELDS:
            print(f'  {field:<13} {m.get(field)!r}')
        if args.raw:
            tags = mutagen.File(path) or {}
            for key in RAW_KEYS:
                with_case = next((k for k in tags.keys() if k.casefold() == key.casefold()), None)
                if with_case is not None:
                    print(f'  raw:{with_case:<9} {tags[with_case]!r}')
        print()


if __name__ == '__main__':
    main()
