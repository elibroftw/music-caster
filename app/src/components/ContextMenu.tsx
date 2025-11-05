import { Button, Menu } from '@mantine/core';
import { useWindowEvent } from '@mantine/hooks';
import { Dispatch, PropsWithChildren, SetStateAction, useEffect, useState } from 'react';

interface ContextMenuTrigger<T> {
	item: T,
	x: number,
	y: number
}

/**
 * Use this hook in conjunction with the ContextMenu component
 * const [contextMenuTrigger, setContextMenuTrigger] = useContextMenu<number>();
 * onContextMenu={e => {
 * 	e.preventDefault();
 *	setContextMenuTrigger({
 *  item: index,
 *  x: e.clientX,
 *  y: e.clientY,
 * });
 * }}
 * <ContextMenu trigger={contextMenuTrigger} offsetLeft={70} offsetTop={-75}><Dropdown></ContextMenu>
 */
export function useContextMenu<T>(): [ContextMenuTrigger<T> | null, Dispatch<SetStateAction<ContextMenuTrigger<T> | null>>] {
	const [menuTrigger, setMenuTrigger] = useState<ContextMenuTrigger<T> | null>(null);
	useEffect(() => {
		const handler = () => setMenuTrigger(null);
		window.addEventListener('scroll', handler, true);
		return () => {
			window.removeEventListener('scroll', handler);
		}
	}, []);
	useWindowEvent('click', () => setMenuTrigger(null));
	useWindowEvent('contextmenu', event => {
		if (event.clientX !== menuTrigger?.x || event.clientY !== menuTrigger.y) {
			setMenuTrigger(null);
		}
	});
	return [menuTrigger, setMenuTrigger];
}

interface ContextMenuProps<T> extends PropsWithChildren {
	offsetLeft?: number;
	offsetTop?: number;
	trigger: ContextMenuTrigger<T> | null;
}

/// use the useContextMenu hook to set the trigger
export function ContextMenu<T>({ trigger, children, offsetLeft = 0, offsetTop = 0 }: ContextMenuProps<T>) {
	return (
		<Menu opened={trigger !== null} key={JSON.stringify(trigger)}>
			<Menu.Target>
				<Button unstyled
					style={{
						position: 'absolute',
						width: 0,
						height: 0,
						padding: 0,
						border: 0,
						left: (trigger?.x ?? 0) + offsetLeft,
						top: (trigger?.y ?? 0) + offsetTop,
					}} />
			</Menu.Target>
			{children}
		</Menu>
	);
}
