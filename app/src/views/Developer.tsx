import { Accordion, Button, Stack, Text, Alert, Code, ScrollArea } from '@mantine/core';
import { useContext, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { TbAlertCircle, TbCheck } from 'react-icons/tb';
import { PlayerStateContext } from '../common/contexts';
import { fmtError } from '../common/utils';

export default function Developer() {
	const playerState = useContext(PlayerStateContext);
	const [isChecking, setIsChecking] = useState(false);
	const [healthStatus, setHealthStatus] = useState<boolean | null>(null);
	const [error, setError] = useState<string | null>(null);

	const checkHealth = async () => {
		setIsChecking(true);
		setError(null);
		try {
			const isRunning = await invoke<boolean>('api_is_running');
			setHealthStatus(isRunning);
		} catch (err) {
			setError(fmtError(err));
			setHealthStatus(null);
		} finally {
			setIsChecking(false);
		}
	};

	return (
		/* hosted in the settings modal, so the player-state dump scrolls inside a
		   bounded area instead of growing the modal past the window */
		<ScrollArea.Autosize mah={400} miw={480}>
			<Accordion defaultValue='player-state' variant='separated'>
				<Accordion.Item value='api'>
					<Accordion.Control><Text fw={500}>API Information</Text></Accordion.Control>
					<Accordion.Panel>
						<Text size='sm' c='dimmed'>Backend URL: http://localhost:?</Text>
					</Accordion.Panel>
				</Accordion.Item>

				<Accordion.Item value='player-state'>
					<Accordion.Control><Text fw={500}>Player State</Text></Accordion.Control>
					<Accordion.Panel>
						{playerState ? (
							<Code block>
								{JSON.stringify(playerState, null, 2)}
							</Code>
						) : (
							<Text c='dimmed'>No player state available</Text>
						)}
					</Accordion.Panel>
				</Accordion.Item>
			</Accordion>
		</ScrollArea.Autosize>
	);
}
