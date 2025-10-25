import { Menu } from '@mantine/core';
import { TbPlayerTrackNext, TbPlus, TbX, TbCopy, TbFile, TbEdit, TbClipboard } from 'react-icons/tb';

interface Track {
	artist: string;
	album: string;
	title: string;
	track: string;
	length: string;
	bpm: string;
	bitrate: string;
}

interface TrackContextMenuProps {
	track: Track;
	onEditMetadata: (track: Track) => void;
	onPlayNext?: (track: Track) => void;
	onAddToQueue?: (track: Track) => void;
	onRemove?: (track: Track) => void;
	onShowFile?: (track: Track) => void;
	onDuplicate?: (track: Track) => void;
	onCopyUris?: (track: Track) => void;
}

export default function TrackContextMenu({
	track,
	onEditMetadata,
	onPlayNext,
	onAddToQueue,
	onRemove,
	onShowFile,
	onDuplicate,
	onCopyUris
}: TrackContextMenuProps) {
	return (
		<Menu.Dropdown>
			{onPlayNext && (
				<Menu.Item
					leftSection={<TbPlayerTrackNext size={16} />}
					onClick={() => onPlayNext(track)}
				>
					Play Next
				</Menu.Item>
			)}
			{onAddToQueue && (
				<Menu.Item
					leftSection={<TbPlus size={16} />}
					onClick={() => onAddToQueue(track)}
				>
					Add to Queue
				</Menu.Item>
			)}
			<Menu.Item
				leftSection={<TbEdit size={16} />}
				onClick={() => onEditMetadata(track)}
			>
				Edit Metadata
			</Menu.Item>
			{onShowFile && (
				<Menu.Item
					leftSection={<TbFile size={16} />}
					onClick={() => onShowFile(track)}
				>
					Show File Location
				</Menu.Item>
			)}
			{onCopyUris && (
				<Menu.Item
					leftSection={<TbClipboard size={16} />}
					onClick={() => onCopyUris(track)}
				>
					Copy URIs
				</Menu.Item>
			)}
			{onDuplicate && (
				<Menu.Item
					leftSection={<TbCopy size={16} />}
					onClick={() => onDuplicate(track)}
				>
					Duplicate
				</Menu.Item>
			)}
			{onRemove && (
				<>
					<Menu.Divider />
					<Menu.Item
						leftSection={<TbX size={16} />}
						onClick={() => onRemove(track)}
						color="red"
					>
						Remove
					</Menu.Item>
				</>
			)}
		</Menu.Dropdown>
	);
}
