import { Menu } from '@mantine/core';
import { Track } from 'common/commands';
import { TbClipboard, TbCopy, TbEdit, TbFile, TbPlayerPlay, TbPlayerTrackNext, TbPlus, TbX } from 'react-icons/tb';

interface TrackContextMenuProps {
	onEditMetadata: () => void;
	onPlayNext?: () => void;
	onAddToQueue?: () => void;
	onRemove?: () => void;
	onShowFile?: () => void;
	onDuplicate?: () => void;
	onCopyUris?: () => void;
}

export default function TrackContextMenu({
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
			<Menu.Item
				leftSection={<TbPlayerPlay size={16} />}
			>
				Play
			</Menu.Item>
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
			<Menu.Item
				leftSection={<TbEdit size={16} />}
				onClick={() => onEditMetadata()}
			>
				Edit Metadata
			</Menu.Item>
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
			{onDuplicate && (
				<Menu.Item
					leftSection={<TbCopy size={16} />}
					onClick={() => onDuplicate()}
				>
					Duplicate
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
