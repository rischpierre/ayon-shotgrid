import React, {useEffect, useMemo, useRef} from 'react';

export default function ContextMenu({openAt, items = [], onClose}) {
    const ref = useRef(null);
    const style = useMemo(() => ({display: openAt ? 'block' : 'none'}), [openAt]);

    useEffect(() => {
        if (!openAt) return;
        const el = ref.current;
        if (el) {
            const x = Math.max(8, Math.min(window.innerWidth - 220, openAt.x));
            const y = Math.max(8, Math.min(window.innerHeight - 80, openAt.y));
            el.style.left = `${x}px`;
            el.style.top = `${y}px`;
        }
    }, [openAt]);

    useEffect(() => {
        if (!openAt) return;
        const onDoc = (e) => {
            if (ref.current && !ref.current.contains(e.target)) onClose?.();
        };
        document.addEventListener('mousedown', onDoc);
        return () => document.removeEventListener('mousedown', onDoc);
    }, [openAt, onClose]);

    return (
        <div className="context-menu" ref={ref} style={style} aria-hidden={!openAt}>
            {items.map((it, i) => (
                <div key={i} className="item" onClick={() => {
                    it.onClick?.();
                    onClose?.();
                }}>
                    {it.label}
                </div>
            ))}
        </div>
    );
}
