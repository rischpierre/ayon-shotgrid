import { useEffect, useRef } from 'react';
import { msUntilNextLocalMidnight } from '@/utils/time.js';

// Calls onRollover right after local midnight and reschedules itself
export default function useMidnightRollover(onRollover) {
  const timerRef = useRef(null);

  useEffect(() => {
    if (typeof onRollover !== 'function') return;

    const schedule = () => {
      const delay = msUntilNextLocalMidnight();
      const safeDelay = delay > 0 ? delay : 10_000; // 10s fallback
      timerRef.current = window.setTimeout(() => {
        try {
          onRollover();
        } finally {
          schedule(); // schedule next rollover
        }
      }, safeDelay);
    };

    schedule();
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [onRollover]);
}
