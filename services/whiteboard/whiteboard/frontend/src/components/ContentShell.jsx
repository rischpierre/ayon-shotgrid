import React, {useCallback, useMemo, useState} from 'react';
import ArtistBar from './ArtistBar.jsx';
import useMultiWeekData from '@/features/useMultiWeekData.js';
import MultiWeekGrid from './MultiWeekGrid.jsx';
import Card from './Card.jsx';
import TaskPicker from './TaskPicker.jsx';
import {useProject} from '@/context/ProjectContext.jsx';
import {useMode} from '@/context/ModeContext.jsx';
import {assign, moveItem, setAnnotations, removeDueDate, unassign} from '@/api';
import {EntityType, weekOrder} from '@/constants';

export default function ContentShell() {
    const {weeks, loading, error, tasksMap, reload} = useMultiWeekData();
    const {projectId} = useProject();
    const {mode} = useMode();

    const [taskAt, setTaskAt] = useState(null); // {x,y}
    const [pending, setPending] = useState(null); // { artist_id, artist_is_group, entity_id }

    const allArtists = useMemo(() => {
        // Prefer w0 artists; fallback to first available
        const order = ['w0', 'w1', 'w2', 'w3'];
        for (const wk of order) {
            const a = weeks?.[wk]?.artists;
            if (Array.isArray(a) && a.length) return a;
        }
        return [];
    }, [weeks]);

    // Quickly look up artist details (thumb, name) by id
    const artistById = useMemo(() => {
        const map = {};
        (allArtists || []).forEach(a => {
            map[a.id] = a;
        });
        return map;
    }, [allArtists]);

    // Merge assignments across loaded weeks so top/bottom boards can show avatars too
    const assignmentsAll = useMemo(() => {
        const out = {};
        for (const wk of ['w0', 'w1', 'w2', 'w3']) {
            const a = weeks?.[wk]?.assignments;
            if (a && typeof a === 'object') {
                for (const [eid, list] of Object.entries(a)) {
                    const id = Number(eid);
                    if (!out[id]) out[id] = [];
                    // concatenate; duplicates will be de-duped visually via key
                    out[id] = out[id].concat(list || []);
                }
            }
        }
        return out;
    }, [weeks]);

    const getAssignees = useCallback((entityId) => {
        const raw = assignmentsAll?.[entityId] || [];
        return raw.map(a => ({
            ...a,
            thumb_url: artistById[a.artist_id]?.thumb_url,
            name: artistById[a.artist_id]?.name,
        }));
    }, [assignmentsAll, artistById]);

    const onDropArtist = useCallback((payload, point) => {
        // Only allow assignments to shots
        const {entity_type} = payload;
        setPending({
            artist_id: payload.artist_id,
            artist_is_group: payload.artist_is_group,
            entity_id: payload.entity_id,
            entity_type: entity_type,
        });
        setTaskAt(point);
    }, []);

    const taskOptions = useMemo(() => {
        if (!pending || !tasksMap) return [];
        const list = tasksMap[mode]?.[pending.entity_id] || [];
        // Normalize to {id, name}
        return (Array.isArray(list) ? list : []).map(t => ({id: t.id, content: t.content}));
    }, [pending, tasksMap]);

    const onPickTask = useCallback(async (task) => {
        if (!pending || !projectId) return;
        try {
            const body = {
                artist_id: pending.artist_id,
                artist_is_group: pending.artist_is_group,
                entity_id: pending.entity_id,
                entity_type: pending.entity_type,
                task_name: task.content,
                task_id: task.id,
            };
            await assign(body, projectId);
            setTaskAt(null);
            setPending(null);
            await reload();
        } catch (e) {
            console.error('Assign failed', e);
            setTaskAt(null);
            setPending(null);
        }
    }, [pending, projectId, reload]);

    const aggregate = useCallback((picker) => {
        const out = [];
        const seen = new Set();
        for (const wk of ['w0', 'w1', 'w2', 'w3']) {
            const arr = picker(weeks?.[wk]);
            if (Array.isArray(arr)) {
                for (const item of arr) {
                    if (!item) continue;
                    // Filter by current mode
                    if (mode === EntityType.Shot && item.entity_type !== EntityType.Shot) continue;
                    if (mode === EntityType.Asset && item.entity_type !== EntityType.Asset) continue;
                    if (!seen.has(item.id)) {
                        seen.add(item.id);
                        out.push(item);
                    }
                }
            }
        }
        return out;
    }, [weeks, mode]);

    const noDue = useMemo(() => aggregate(s => (s?.no_due_date || [])), [aggregate, mode]);
    const onHold = useMemo(() => aggregate(s => s?.on_hold || []), [aggregate]);
    const omitted = useMemo(() => aggregate(s => s?.omitted || []), [aggregate]);

    const onRemoveDueDateDirect = useCallback(async ({item_id, entity_type}) => {
        if (!projectId) return;
        try {
            await removeDueDate({item_id, entity_type}, projectId);
            await reload();
        } catch (e) {
            console.error('Remove due date failed', e);
        }
    }, [projectId, reload]);

    // Filter options based on current mode and loaded data
    const parentOptions = useMemo(() => {
        const set = new Set();
        for (const week of weekOrder) {
            const week_snapshot = weeks?.[week];
            if (!week_snapshot) continue;
            // parents already provided as sorted list per snapshot (sequences for shots, asset types for assets)
            (week_snapshot.parents[mode] || []).forEach(p => set.add(p));
        }
        return Array.from(set).sort((a, b) => String(a).localeCompare(String(b)));
    }, [weeks, mode]);

    const [filterParent, setFilterParent] = useState('');

    const filteredNoDue = useMemo(() => {
        if (!filterParent) return noDue;
        return noDue.filter(it => it.parent === filterParent);
    }, [noDue, filterParent]);

    return (
        <>
            <div className="artist-bar" id="artistBar">
                <ArtistBar artists={allArtists}/>
            </div>
            <section id="weeks">
                {loading && <div style={{color: '#9aa3b2', padding: '8px 0'}}>Loading…</div>}
                {error &&
                    <div style={{color: '#ff6b6b', padding: '8px 0'}}>Error: {String(error.message || error)}</div>}
                {/* Full-width No Due Date above */}
                <div style={{padding: '12px 16px'}}>
                    <div className="board">
                        <h3 style={{display: 'flex', alignItems: 'center', justifyContent: 'flex-start', gap: 12}}>
                            <div style={{display: 'flex', alignItems: 'center', gap: 8}}>
                                <>
                                    <label htmlFor="parentFilterNoDue"
                                           style={{color: '#c7cbe0', fontSize: 13}}>Filter:</label>
                                    <select id="parentFilterNoDue" value={filterParent}
                                            onChange={(e) => setFilterParent(e.target.value)} style={{
                                        background: '#1b2042',
                                        color: '#e7e9ef',
                                        border: '1px solid #2a2f58',
                                        borderRadius: 6,
                                        padding: '6px 8px'
                                    }}>
                                        <option value="">{mode === EntityType.Asset ? 'All Asset Types' : 'All Sequences'}</option>
                                        {parentOptions.map(opt => (
                                            <option key={opt} value={opt}>{opt}</option>
                                        ))}
                                    </select>
                                </>
                            </div>
                            <span>No Due Date</span>
                        </h3>
                        <div className="list" style={{display: 'flex', flexWrap: 'wrap', gap: 8, flexDirection: 'row'}}>
                            {filteredNoDue.map(item => (
                                <Card key={`no-${item.id}`} item={item} onDropArtist={onDropArtist}
                                      assignees={getAssignees(item.id)} onRemoveDueDate={onRemoveDueDateDirect}
                                      onUnassign={async (payload) => { await unassign(payload, projectId); await reload(); }}
                                      />
                            ))}
                        </div>
                    </div>
                </div>

                {/* Four week sections with Mon–Fri day boards */}
                <MultiWeekGrid
                    weeks={weeks}
                    onDropArtist={onDropArtist}
                    onUnassign={async (payload) => {
                        if (!projectId) return;
                        try {
                            await unassign(payload, projectId);
                            await reload();
                        } catch (e) {
                            console.error('Unassign failed', e);
                        }
                    }}
                    onMoveItem={async (payload) => {
                        if (!projectId) return;
                        try {
                            await moveItem(payload, projectId);
                            await reload();
                        } catch (e) {
                            console.error('Move failed', e);
                        }
                    }}
                    onSetAnnotation={async ({week, day, text, color}) => {
                        if (!projectId) return;
                        try {
                            await setAnnotations({week, day, text, color}, projectId);
                            await reload();
                        } catch (e) {
                            console.error('Set annotation failed', e);
                        }
                    }}
                    onRemoveDueDate={async ({item_id, entity_type}) => {
                        if (!projectId) return;
                        try {
                            await removeDueDate({item_id, entity_type}, projectId);
                            await reload();
                        } catch (e) {
                            console.error('Remove due date failed', e);
                        }
                    }}
                />

                {/* On Hold and Omitted below */}
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, minmax(240px, 1fr))',
                    gap: 12,
                    padding: '12px 16px'
                }}>
                    <div className="board">
                        <h3>On Hold</h3>
                        <div className="list" style={{display: 'flex', flexWrap: 'wrap', gap: 8}}>
                            {onHold.map(item => (
                                <Card key={`hld-${item.id}`} item={item} onDropArtist={onDropArtist}
                                      assignees={getAssignees(item.id)} onRemoveDueDate={onRemoveDueDateDirect}
                                      onUnassign={async (payload) => { await unassign(payload, projectId); await reload(); }}
                                      />
                            ))}
                        </div>
                    </div>
                    <div className="board">
                        <h3>Omitted</h3>
                        <div className="list" style={{display: 'flex', flexWrap: 'wrap', gap: 8}}>
                            {omitted.map(item => (
                                <Card key={`omt-${item.id}`} item={item} onDropArtist={onDropArtist}
                                      assignees={getAssignees(item.id)} onRemoveDueDate={onRemoveDueDateDirect}
                                      onUnassign={async (payload) => { await unassign(payload, projectId); await reload(); }}
                                      />
                            ))}
                        </div>
                    </div>
                </div>
            </section>

            <TaskPicker
                tasks={taskOptions}
                openAt={taskAt}
                title="Assign task"
                onPick={onPickTask}
                onClose={() => {
                    setTaskAt(null);
                    setPending(null);
                }}
            />
        </>
    );
}
