import { useEffect, useRef } from 'react';

/**
 * Scrolls the bottom sentinel into view whenever `deps` change.
 * Returns a ref to attach to the sentinel element.
 */
export function useAutoScroll(deps: unknown[]) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return bottomRef;
}
