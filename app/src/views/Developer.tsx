import { Button, Paper, Stack, Text, Alert } from '@mantine/core';
import { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { TbAlertCircle, TbCheck } from 'react-icons/tb';

export default function Developer() {
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
			setError(err instanceof Error ? err.message : 'Unknown error');
			setHealthStatus(null);
		} finally {
			setIsChecking(false);
		}
	};

	return (
		<Stack gap="md">
			<Paper shadow="sm" p="md">
				<Stack gap="md">
					<Text size="lg" fw={500}>Music Caster Backend Health Check</Text>

					<Button onClick={checkHealth} loading={isChecking}>
						Check Backend Status
					</Button>

					{healthStatus !== null && (
						<Alert
							icon={healthStatus ? <TbCheck size={20} /> : <TbAlertCircle size={20} />}
							title={healthStatus ? 'Backend is Running' : 'Backend is Not Running'}
							color={healthStatus ? 'green' : 'red'}
						>
							{healthStatus
								? 'The Music Caster backend is running and responding on port 2001.'
								: 'The Music Caster backend is not running or not responding on port 2001.'}
						</Alert>
					)}

					{error && (
						<Alert icon={<TbAlertCircle size={20} />} title="Error" color="red">
							{error}
						</Alert>
					)}
				</Stack>
			</Paper>

			<Paper shadow="sm" p="md">
				<Stack gap="xs">
					<Text size="lg" fw={500}>API Information</Text>
					<Text size="sm" c="dimmed">Backend URL: http://localhost:2001</Text>
					<Text size="sm" c="dimmed">Health endpoint: /running/</Text>
				</Stack>
			</Paper>
		</Stack>
	);
}
