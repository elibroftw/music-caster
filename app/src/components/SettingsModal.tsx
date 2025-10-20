import { Box, Checkbox, Modal, Stack, TextInput } from '@mantine/core';

interface SettingsModalProps {
	opened: boolean;
	onClose: () => void;
}

export default function SettingsModal({ opened, onClose }: SettingsModalProps) {
	return (
		<Modal
			opened={opened}
			onClose={onClose}
			title="Settings"
			size="xl"
			centered
		>
			<Box style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
				<Stack gap="md">
					<Checkbox label="Auto update" defaultChecked />
					<Checkbox label="Notifications" defaultChecked />
					<Checkbox label="Folder context menu" defaultChecked />
					<Checkbox label="Remember last folder" />
					<TextInput label="System Audio Delay" defaultValue="0" />
					<Checkbox label="Reversed play next" />
					<Checkbox label="Populate queue on startup" />
					<Checkbox label="Smart queue" defaultChecked />
					<Checkbox label="Save window positions" defaultChecked />
					<Checkbox label="Left-side music controls" />
					<Checkbox label="Show album art" defaultChecked />
					<Checkbox label="Use cover.* for album art" defaultChecked />
					<TextInput label="Track Format" defaultValue="&artist - &title" />
				</Stack>

				<Stack gap="md">
					<Checkbox label="Discord presence" />
					<Checkbox label="Run on startup" />
					<Checkbox label="Scan folders" />
					<Checkbox label="Exit app on GUI close" />
					<Checkbox label="Show track number" />
					<Checkbox label="Vertical GUI" />
					<Checkbox label="Mini mode on top" />
					<Checkbox label="Show index in queue" />
					<Checkbox label="Always queue library" />
					<Checkbox label="Persistent queue" defaultChecked />
					<TextInput label="On battery resolution" defaultValue="" />
					<TextInput label="Plugged in resolution" defaultValue="" />
					<Checkbox label="Experimental features" />
				</Stack>
			</Box>
		</Modal>
	);
}
