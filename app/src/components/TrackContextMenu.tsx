import { Menu } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { TbClipboard, TbEdit, TbExternalLink, TbFile, TbPlayerPlay, TbPlayerTrackNext, TbPlus, TbX } from 'react-icons/tb';

interface TrackContextMenuProps {
	/** the track is a url rather than a local file: the file items become browser ones */
	isUrl?: boolean;
	onEditMetadata?: () => void;
	onPlay?: () => void;
	onPlayNext?: () => void;
	onAddToQueue?: () => void;
	onRemove?: () => void;
	/** reveals the file in the OS file manager, or opens the url in the browser when `isUrl` */
	onShowFile?: () => void;
	onCopyUris?: () => void;
}

export default function TrackContextMenu({
	isUrl = false,
	onEditMetadata,
	onPlay,
	onPlayNext,
	onAddToQueue,
	onRemove,
	onShowFile,
	onCopyUris
}: TrackContextMenuProps) {
	const { t } = useTranslation();
	return (
		<Menu.Dropdown>
			{onPlay && (
				<Menu.Item
					leftSection={<TbPlayerPlay size={16} />}
					onClick={() => onPlay()}
				>
					{t('Play')}
				</Menu.Item>
			)}
			{onPlayNext && (
				<Menu.Item
					leftSection={<TbPlayerTrackNext size={16} />}
					onClick={() => onPlayNext()}
				>
					{t('Play Next')}
				</Menu.Item>
			)}
			{onAddToQueue && (
				<Menu.Item
					leftSection={<TbPlus size={16} />}
					onClick={() => onAddToQueue()}
				>
					{t('Add to Queue')}
				</Menu.Item>
			)}
			{onEditMetadata && <Menu.Item
				leftSection={<TbEdit size={16} />}
				onClick={() => onEditMetadata()}
			>
				{t('Edit Metadata')}
			</Menu.Item>}
			{onShowFile && (
				<Menu.Item
					leftSection={isUrl ? <TbExternalLink size={16} /> : <TbFile size={16} />}
					onClick={() => onShowFile()}
				>
					{isUrl ? t('Open in Browser') : t('Show File Location')}
				</Menu.Item>
			)}
			{onCopyUris && (
				<Menu.Item
					leftSection={<TbClipboard size={16} />}
					onClick={() => onCopyUris()}
				>
					{isUrl ? t('Copy URL') : t('Copy URIs')}
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
						{t('Remove')}
					</Menu.Item>
				</>
			)}
		</Menu.Dropdown>
	);
}
