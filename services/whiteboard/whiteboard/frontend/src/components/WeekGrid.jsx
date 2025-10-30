import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {annotationColors, dayMap, dayOrder, dayTitle, weekOrder, EntityType} from '@/constants';
import {useMode} from '@/context/ModeContext.jsx';
import Card from './Card.jsx';


export default function WeekGrid({snapshot, onDropArtist, onMoveItem, onSetAnnotation, onRemoveDueDate, onUnassign}) {
    const {week, days, boards, board_items, annotations, artists, assignments} = snapshot || {};
    const parents = snapshot?.parents || [];
    const {mode} = useMode();

    const today = new Date();
    const weekday = today.getDay(); // 0=Sun..6=Sat
    const isCurrentWeek = week === weekOrder[0];
    const currentDayKey = useMemo(() => {
        return dayMap[weekday] || null;
    }, [weekday]);

    const mondayOfWeek = useMemo(() => {
        // compute Monday date for this snapshot week (w0..w3)
        const now = new Date();
        const dayIdx = now.getDay();
        const diffToMon = ((dayIdx + 6) % 7); // Mon=1 -> 0, Sun=0 -> 6
        const mon = new Date(now);
        mon.setDate(now.getDate() - diffToMon);
        const offsetWeeks = typeof week === 'string' && week.startsWith('w') ? parseInt(week.slice(1) || '0', 10) : 0;
        mon.setDate(mon.getDate() + (offsetWeeks * 7));
        mon.setHours(0, 0, 0, 0);
        return mon;
    }, [week]);

    const columns = useMemo(() => {
        // Ensure we respect backend lowercase day order if provided
        const order = days && days.length ? days : dayOrder;
        return order.map((day, idx) => {
            const labelDate = new Date(mondayOfWeek);
            labelDate.setDate(mondayOfWeek.getDate() + idx);
            const dayNum = labelDate.getDate();
            const title = `${dayTitle[day] || day}, ${dayNum}`;
            return {
                key: day,
                title,
                boards: (boards?.[day] || []).filter(b => b.entity_type === mode),
            };
        });
    }, [days, boards, mode, mondayOfWeek]);

    // Build a quick lookup for artist details
    const artistById = useMemo(() => {
        const map = {};
        (artists || []).forEach(a => {
            map[a.id] = a;
        });
        return map;
    }, [artists]);

    // Header annotation menu state
    const [headerMenu, setHeaderMenu] = useState({open: false, x: 0, y: 0, day: null});
    const closeHeaderMenu = useCallback(() => setHeaderMenu(m => (m.open ? {...m, open: false} : m)), []);
    const [colorSubOpen, setColorSubOpen] = useState(false);

    useEffect(() => {
        if (!headerMenu.open) return;
        const onDown = (e) => closeHeaderMenu();
        const onEsc = (e) => {
            if (e.key === 'Escape') closeHeaderMenu();
        };
        window.addEventListener('mousedown', onDown);
        window.addEventListener('keydown', onEsc);
        return () => {
            window.removeEventListener('mousedown', onDown);
            window.removeEventListener('keydown', onEsc);
        };
    }, [headerMenu.open, closeHeaderMenu]);

    const doAddAnnotation = useCallback(() => {
        if (!headerMenu.day) return;
        const key = `${week}/${headerMenu.day}`;
        const existing = annotations && annotations[key];
        const text = window.prompt('Annotation text:', existing?.text || '');
        if (text === null) return;
        const color = existing?.color || annotationColors[0];
        onSetAnnotation?.({week, day: headerMenu.day, text, color});
        closeHeaderMenu();
    }, [annotations, headerMenu.day, onSetAnnotation, week, closeHeaderMenu]);

    const doRemoveAnnotation = useCallback(() => {
        if (!headerMenu.day) return;
        onSetAnnotation?.({week, day: headerMenu.day, text: '', color: ''});
        closeHeaderMenu();
    }, [headerMenu.day, onSetAnnotation, week, closeHeaderMenu]);

    const doSetColor = useCallback((color) => {
        if (!headerMenu.day) return;
        const key = `${week}/${headerMenu.day}`;
        const existing = annotations && annotations[key];
        const text = (existing?.text || '').toString();
        onSetAnnotation?.({week, day: headerMenu.day, text, color});
        closeHeaderMenu();
    }, [annotations, headerMenu.day, onSetAnnotation, week, closeHeaderMenu]);

    const handleColDragOver = (e) => {
        // Be permissive: in dragover, browsers often don't expose payload. Use types to allow drop.
        const types = Array.from(e.dataTransfer?.types || []);
        if (types.includes('application/x-wb') || types.includes('text/plain')) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        }
    };

    // Items per board (no weekday asset-type filtering)
    const filteredItemsForBoard = useCallback((boardId) => {
        const items = board_items?.[boardId] || [];
        return items;
    }, [board_items]);

    return (
        <div className="boards">
            {columns.map(col => (
                <div key={col.key}
                     className={`board${isCurrentWeek && currentDayKey === col.key ? ' current-day' : ''}`}>
                    <h3 onContextMenu={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setColorSubOpen(false);
                        setHeaderMenu({open: true, x: e.clientX, y: e.clientY, day: col.key});
                    }} title="Right-click for annotation actions">
                        <span>{col.title}</span>
                        {/* annotation dot if any */}
                        {annotations && annotations[`${week}/${col.key}`] && (
                            <span style={{display: 'inline-flex', alignItems: 'center', gap: 6}}>
                <span style={{
                    width: 14,
                    height: 14,
                    borderRadius: 7,
                    background: annotations[`${week}/${col.key}`].color || '#c7cbe0',
                    border: '2px solid rgba(255,255,255,0.3)'
                }}/>
                <em style={{
                    color: '#9aa3b2',
                    fontStyle: 'normal',
                    fontSize: 12
                }}>{annotations[`${week}/${col.key}`].text}</em>
              </span>
                        )}
                    </h3>
                    <div
                        className="list"
                        onDragOver={handleColDragOver}
                        onDrop={(e) => {
                            try {
                                const data = e.dataTransfer.getData('application/x-wb');
                                if (data) {
                                    const p = JSON.parse(data);
                                    if (p && p.type === 'item') {
                                        const to_index = col.boards.reduce((acc, b) => acc + (board_items?.[b.id]?.length || 0), 0);
                                        onMoveItem?.({
                                            item_id: p.item_id,
                                            entity_type: p.entity_type,
                                            to_week: week,
                                            to_day: col.key,
                                            to_index
                                        });
                                    }
                                }
                            } catch {
                            }
                        }}
                    >
                        {col.boards.map(board => (
                            <React.Fragment key={board.id}>
                                {filteredItemsForBoard(board.id).map(item => {
                                    const raw = (assignments && assignments[mode][item.id]) || [];
                                    const enriched = raw.map(a => ({
                                        ...a,
                                        thumb_url: artistById[a.artist_id]?.thumb_url,
                                        name: artistById[a.artist_id]?.name,
                                    }));
                                    return (
                                        <Card key={`${board.id}-${item.id}`} item={item} onDropArtist={onDropArtist}
                                              assignees={enriched} onRemoveDueDate={onRemoveDueDate}
                                              onUnassign={onUnassign}/>
                                    );
                                })}
                            </React.Fragment>
                        ))}
                    </div>
                </div>
            ))}
            {headerMenu.open && (
                <div style={{
                    position: 'fixed',
                    left: headerMenu.x,
                    top: headerMenu.y,
                    zIndex: 1000,
                    background: '#1f2937',
                    color: 'white',
                    border: '1px solid #374151',
                    borderRadius: 6,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                    minWidth: 200,
                    padding: 4
                }} onMouseDown={(e) => e.stopPropagation()}>
                    <div role="menuitem" tabIndex={0} style={{padding: '8px 12px', cursor: 'pointer', borderRadius: 4}}
                         onClick={doAddAnnotation} onKeyDown={(e) => {
                        if (e.key === 'Enter') doAddAnnotation();
                    }}>
                        Add annotation
                    </div>
                    <div role="menuitem" tabIndex={0} style={{padding: '8px 12px', cursor: 'pointer', borderRadius: 4}}
                         onClick={doRemoveAnnotation} onKeyDown={(e) => {
                        if (e.key === 'Enter') doRemoveAnnotation();
                    }}>
                        Remove annotation
                    </div>
                    <div style={{position: 'relative'}}
                         onMouseEnter={() => setColorSubOpen(true)}
                         onMouseLeave={() => setColorSubOpen(false)}>
                        <div role="menuitem" tabIndex={0} style={{
                            padding: '8px 12px',
                            cursor: 'pointer',
                            borderRadius: 4,
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                        }}>
                            <span>Set Color</span>
                            <span style={{opacity: 0.7}}>▶</span>
                        </div>
                        {colorSubOpen && (
                            <div style={{
                                position: 'absolute',
                                left: '100%',
                                top: 0,
                                marginLeft: 6,
                                background: '#111827',
                                border: '1px solid #374151',
                                borderRadius: 6,
                                boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                                padding: 4,
                                minWidth: 160,
                                zIndex: 1001
                            }} onMouseDown={(e) => e.stopPropagation()}>
                                {annotationColors.map((clr) => (
                                    <div key={clr} role="menuitem" tabIndex={0}
                                         style={{
                                             padding: '8px 12px',
                                             cursor: 'pointer',
                                             borderRadius: 4,
                                             display: 'flex',
                                             alignItems: 'center',
                                             gap: 8
                                         }}
                                         onClick={() => doSetColor(clr)} onKeyDown={(e) => {
                                        if (e.key === 'Enter') doSetColor(clr);
                                    }}>
                                        <span style={{
                                            width: 14,
                                            height: 14,
                                            borderRadius: 3,
                                            background: clr,
                                            display: 'inline-block',
                                            border: '1px solid rgba(255,255,255,0.2)'
                                        }}/>
                                        <span>{clr}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
