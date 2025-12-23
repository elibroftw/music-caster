import { Menu } from '@mantine/core';
import { Track } from 'common/commands';
import { TbClipboard, TbCopy, TbEdit, TbFile, TbPlayerPlay, TbPlayerTrackNext, TbPlus, TbX } from 'react-icons/tb';

interface TrackContextMenuProps {
	onEditMetadata?: () => void;
	onPlay?: () => void;
	onPlayNext?: () => void;
	onAddToQueue?: () => void;
	onRemove?: () => void;
	onShowFile?: () => void;
	onCopyUris?: () => void;
}

export default function TrackContextMenu({
	onEditMetadata,
	onPlay,
	onPlayNext,
	onAddToQueue,
	onRemove,
	onShowFile,
	onCopyUris
}: TrackContextMenuProps) {
	return (
		<Menu.Dropdown>
			{onPlay && (
				<Menu.Item
					leftSection={<TbPlayerPlay size={16} />}
					onClick={() => onPlay()}
				>
					Play
				</Menu.Item>
			)}
			{onPlayNext && (
				<Menu.Item
					leftSection={<TbPlayerTrackNext size={16} />}
					onClick={() => onPlayNext()}
				>
					Play Next
				</Menu.Item>
			)}
			{onAddToQueue && (
				<Menu.Item
					leftSection={<TbPlus size={16} />}
					onClick={() => onAddToQueue()}
				>
					Add to Queue
				</Menu.Item>
			)}
			{onEditMetadata && <Menu.Item
				leftSection={<TbEdit size={16} />}
				onClick={() => onEditMetadata()}
			>
				Edit Metadata
			</Menu.Item>}
			{onShowFile && (
				<Menu.Item
					leftSection={<TbFile size={16} />}
					onClick={() => onShowFile()}
				>
					Show File Location
				</Menu.Item>
			)}
			{onCopyUris && (
				<Menu.Item
					leftSection={<TbClipboard size={16} />}
					onClick={() => onCopyUris()}
				>
					Copy URIs
				</Menu.Item>
			)}
			{onRemove && (
				<>
					<Menu.Divider />
					<Menu.Item
						leftSection={<TbX size={16} />}
						onClick={() => onRemove()}
						color='red'
					>
						Remove
					</Menu.Item>
				</>
			)}
		</Menu.Dropdown>
	);
}
