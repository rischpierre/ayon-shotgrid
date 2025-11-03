import { useEffect } from 'react';

// Refresh when the page becomes visible or the window gains focus
export default function useVisibilityRefresh(onVisible) {
  useEffect(() => {
    if (typeof onVisible !== 'function') return;

    const handler = () => {
      if (document.visibilityState === 'visible') {
        onVisible();
      }
    };

    document.addEventListener('visibilitychange', handler);
    window.addEventListener('focus', handler);

    return () => {
      document.removeEventListener('visibilitychange', handler);
      window.removeEventListener('focus', handler);
    };
  }, [onVisible]);
}
