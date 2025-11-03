import React, {useEffect, useMemo, useRef, useState} from 'react';

export default function TaskPicker({tasks = [], openAt = null, title = 'Choose task', onPick, onClose}) {
    const [visible, setVisible] = useState(false);
    const ref = useRef(null);

    useEffect(() => {
        if (openAt) {
            setVisible(true);
            const el = ref.current;
            if (el) {
                const x = Math.max(8, Math.min(window.innerWidth - 260, openAt.x));
                const y = Math.max(8, Math.min(window.innerHeight - 200, openAt.y));
                el.style.left = `${x}px`;
                el.style.top = `${y}px`;
            }
        } else {
            setVisible(false);
        }
    }, [openAt]);

    useEffect(() => {
        if (!visible) return;
        const onDoc = (e) => {
            if (ref.current && !ref.current.contains(e.target)) {
                setVisible(false);
                onClose?.();
            }
        };
        document.addEventListener('mousedown', onDoc);
        return () => document.removeEventListener('mousedown', onDoc);
    }, [visible, onClose]);

    const style = useMemo(() => ({display: visible ? 'block' : 'none'}), [visible]);

    return (
        <div className="task-picker" ref={ref} style={style} aria-hidden={!visible}>
            <header>{title}</header>
            <div className="options">
                {tasks.length === 0 ? (
                    <div style={{color: '#9aa3b2'}}>No tasks available.</div>
                ) : tasks.map(task => (
                    <div key={task.id || task} className="task-option" onClick={() => {
                        onPick?.(task);
                        setVisible(false);
                        onClose?.();
                    }}>
                        <span className="task-swatch" style={{background: task.color}}/>
                        <span className="task-label">{task.content}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
