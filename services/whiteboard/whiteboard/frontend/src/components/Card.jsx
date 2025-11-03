import React, {useCallback, useMemo, useState, useEffect} from 'react';
import {colorForTask} from '@/utils';
import {EntityType} from '@/constants';

export default function Card({item, onDropArtist, assignees = [], onRemoveDueDate, onUnassign}) {
    const isShot = useMemo(() => item?.entity_type === EntityType.Shot, [item]);

    const onDragStart = useCallback((e) => {
        const payload = {type: 'item', item_id: item.id, entity_type: item.entity_type};
        e.dataTransfer.setData('application/x-wb', JSON.stringify(payload));
        // Some browsers require a text flavor to enable dropping
        try {
            e.dataTransfer.setData('text/plain', 'wb');
        } catch {
        }
        e.dataTransfer.effectAllowed = 'move';
    }, [item]);

    const onDragOver = useCallback((e) => {
        // Allow drop of artists onto cards. Avoid reading data in dragover (often empty in Chrome/Edge)
        const types = Array.from(e.dataTransfer?.types || []);
        if (types.includes('application/x-wb')) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
        }
    }, []);

    const onDrop = useCallback((e) => {
        try {
            const data = e.dataTransfer.getData('application/x-wb');
            if (data) {
                const p = JSON.parse(data);
                if (p && p.type === 'artist') {
                    onDropArtist?.({
                        artist_id: p.artist_id,
                        artist_is_group: p.artist_is_group,
                        entity_id: item.id,
                        entity_type: item.entity_type
                    }, {x: e.clientX, y: e.clientY});
                }
            }
        } catch {
        }
    }, [item, onDropArtist]);

    const avatarSize = 16;
    const avatarRadius = Math.round(avatarSize / 2);

    // Context menu state
    const [menu, setMenu] = useState({open: false, x: 0, y: 0});
    const [assigneeMenu, setAssigneeMenu] = useState({open: false, x: 0, y: 0, assignee: null});

    const openMenu = useCallback((x, y) => {
        setMenu({open: true, x, y});
    }, []);

    const closeMenu = useCallback(() => setMenu(m => (m.open ? {...m, open: false} : m)), []);

    const handleContext = useCallback((e) => {
        e.preventDefault();
        openMenu(e.clientX, e.clientY);
    }, [openMenu]);

    useEffect(() => {
        if (!menu.open) return;
        const onGlobalClick = (e) => {
            // close on outside click
            closeMenu();
        };
        const onEsc = (e) => {
            if (e.key === 'Escape') closeMenu();
        };
        window.addEventListener('mousedown', onGlobalClick);
        window.addEventListener('keydown', onEsc);
        return () => {
            window.removeEventListener('mousedown', onGlobalClick);
            window.removeEventListener('keydown', onEsc);
        };
    }, [menu.open, closeMenu]);

    const doUnschedule = useCallback(() => {
        onRemoveDueDate?.({item_id: item.id, entity_type: item.entity_type});
        closeMenu();
    }, [item, onRemoveDueDate, closeMenu]);

    // Assignee context menu behavior
    useEffect(() => {
        if (!assigneeMenu.open) return;
        const onGlobalClick = () => setAssigneeMenu(m => (m.open ? {...m, open: false, assignee: null} : m));
        const onEsc = (e) => { if (e.key === 'Escape') onGlobalClick(); };
        window.addEventListener('mousedown', onGlobalClick);
        window.addEventListener('keydown', onEsc);
        return () => {
            window.removeEventListener('mousedown', onGlobalClick);
            window.removeEventListener('keydown', onEsc);
        };
    }, [assigneeMenu.open]);

    const doUnassign = useCallback(() => {
        const a = assigneeMenu.assignee;
        if (!a) return;
        onUnassign?.({
            artist_id: a.artist_id,
            artist_is_group: !!a.artist_is_group,
            entity_id: item.id,
            entity_type: item.entity_type,
            task_name: a.task_name,
            task_id: a.task_id,
        });
        setAssigneeMenu(m => ({...m, open: false, assignee: null}));
    }, [assigneeMenu.assignee, item, onUnassign]);

    return (
        <div className={`card${isShot ? ' card-shot' : ' card-asset'}`} draggable onDragStart={onDragStart}
             onDragOver={onDragOver} onDrop={onDrop} onContextMenu={handleContext} title={item.parent || ''}>
            <div className="thumb"><img src={item.thumb_url} alt="thumb"/></div>
            <div className="title">{item.name}</div>
            {assignees?.length > 0 ? (
                <div className="assignees"
                     style={{display: 'flex', gap: 4, alignItems: 'center', justifyContent: 'flex-end'}}>
                    {assignees.map((assignee, idx) => {
                        const clr = assignee.color || colorForTask(assignee.task_name);
                        const onAvatarClick = (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setAssigneeMenu({open: true, x: e.clientX, y: e.clientY, assignee});
                        };
                        return (
                            <img
                                key={`${assignee.artist_id}-${assignee.task_id || assignee.task_name || idx}`}
                                src={assignee.thumb_url}
                                alt={assignee.name || ''}
                                title={`${assignee.name || 'Artist'}${assignee.task_name ? ' • ' + assignee.task_name : ''}`}
                                onClick={onAvatarClick}
                                onContextMenu={onAvatarClick}
                                style={{
                                    width: avatarSize,
                                    height: avatarSize,
                                    borderRadius: avatarRadius,
                                    objectFit: 'cover',
                                    border: `2px solid ${clr}`,
                                    boxShadow: `0 0 0 2px rgba(0,0,0,0.4)`,
                                    cursor: 'pointer',
                                }}
                            />
                        );
                    })}
                </div>
            ) : (
                <div/>
            )}
            {menu.open && (
                <div style={{
                    position: 'fixed',
                    left: menu.x,
                    top: menu.y,
                    zIndex: 1000,
                    background: '#1f2937',
                    color: 'white',
                    border: '1px solid #374151',
                    borderRadius: 6,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                    minWidth: 160,
                    padding: 4
                }} onMouseDown={(e) => e.stopPropagation()}>
                    <div role="menuitem" tabIndex={0} style={{padding: '8px 12px', cursor: 'pointer', borderRadius: 4}}
                         onClick={doUnschedule} onKeyDown={(e) => {
                        if (e.key === 'Enter') doUnschedule();
                    }}>
                        Unschedule
                    </div>
                </div>
            )}
            {assigneeMenu.open && (
                <div style={{
                    position: 'fixed',
                    left: assigneeMenu.x,
                    top: assigneeMenu.y,
                    zIndex: 1000,
                    background: '#1f2937',
                    color: 'white',
                    border: '1px solid #374151',
                    borderRadius: 6,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                    minWidth: 160,
                    padding: 4
                }} onMouseDown={(e) => e.stopPropagation()}>
                    <div role="menuitem" tabIndex={0} style={{padding: '8px 12px', cursor: 'pointer', borderRadius: 4}}
                         onClick={doUnassign} onKeyDown={(e) => { if (e.key === 'Enter') doUnassign(); }}>
                        Unassign
                    </div>
                </div>
            )}
        </div>
    );
}
