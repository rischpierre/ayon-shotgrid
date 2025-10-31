import React, {useCallback, useEffect, useMemo, useState} from 'react';
import useEvent from '@/hooks/useEvent';
import {useProject} from '@/context/ProjectContext.jsx';
import {getChanges} from '@/api';
import usePublish from '@/features/usePublish.js';

export default function PublishModal() {
    const [open, setOpen] = useState(false);
    const [changes, setChanges] = useState(null); // {moves[], assignments{}, unschedules[], unassigns[]}
    const {projectId} = useProject();
    const {publish, submitting, error} = usePublish();

    const loadChanges = useCallback(async () => {
        if (!projectId) return;
        try {
            const data = await getChanges(projectId);
            setChanges(data || {moves: [], assignments: {}, unschedules: [], unassigns: []});
        } catch (e) {
            console.error('Failed to load changes', e);
            setChanges({moves: [], assignments: {}, unschedules: [], unassigns: []});
        }
    }, [projectId]);

    const onOpen = useCallback(() => {
        setOpen(true);
    }, []);

    useEvent('open-publish', onOpen);

    useEffect(() => {
        if (open) loadChanges();
    }, [open, loadChanges]);

    const hasMoves = !!(changes && Array.isArray(changes.moves) && changes.moves.length > 0);
    const hasAssigns = !!(changes && changes.assignments && Object.keys(changes.assignments).length);
    const hasUnschedules = !!(changes && Array.isArray(changes.unschedules) && changes.unschedules.length > 0);
    const hasUnassigns = !!(changes && Array.isArray(changes.unassigns) && changes.unassigns.length > 0);
    const hasChanges = hasMoves || hasAssigns || hasUnschedules || hasUnassigns;
    const style = useMemo(() => ({display: open ? 'flex' : 'none'}), [open]);

    return (
        <div className="modal" style={style} aria-hidden={!open}>
            <div className="dialog">
                <header style={{padding: '10px 12px', borderBottom: '1px solid #24294d'}}>
                    <h3>Publish changes to ShotGrid</h3>
                    <button className="btn" onClick={() => setOpen(false)}>✕</button>
                </header>
                <div className="body">
                    {!changes ? (
                        <div style={{color: '#9aa3b2'}}>Loading changes…</div>
                    ) : (!hasChanges ? (
                        <div style={{color: '#9aa3b2'}}>No changes pending.</div>
                    ) : (
                        <div className="changes-list">
                            {Array.isArray(changes.moves) ? changes.moves.map((m, i) => (
                                <div key={`m-${i}`} className="change-item">
                                    Move {m.name || `${m.entity_type} ${m.entity_id}`} → {String(m.to_week)}/{String(m.to_day)} ({m.to_date || ''})
                                </div>
                            )) : null}
                            {/* assignments is a nested structure; list each change */}
                            {changes.assignments && Object.entries(changes.assignments).map(([etype, byEntity]) => (
                                Object.entries(byEntity || {}).map(([entityId, tasks]) => (
                                    (Array.isArray(tasks) ? tasks : []).map((t, i) => (
                                        <div key={`a-${etype}-${entityId}-${t.task_id}-${t.artist_id}-${i}`} className="change-item">
                                            Assign {etype} {entityId}: {t.task_name} → {t.artist_is_group ? 'Group' : 'Artist'} {t.artist_id}
                                        </div>
                                    ))
                                ))
                            ))}
                            {/* unschedules: list each unscheduled entity */}
                            {Array.isArray(changes.unschedules) && changes.unschedules.map((u, i) => (
                                <div key={`u-${i}`} className="change-item">
                                    Unschedule {u.entity_type} {u.name || u.entity_id}
                                </div>
                            ))}
                            {/* unassigns: list each removed assignment */}
                            {Array.isArray(changes.unassigns) && changes.unassigns.map((r, i) => (
                                <div key={`r-${i}`} className="change-item">
                                    Unassign {r.entity_type} {r.name || r.entity_id}: {r.task_name} → {r.artist_is_group ? 'Group' : 'Artist'} {r.artist_id}
                                </div>
                            ))}
                        </div>
                    ))}
                    {error && <div style={{color: '#ff6b6b', marginTop: 8}}>Publish
                        error: {String(error.message || error)}</div>}
                </div>
                <footer>
                    <button className="btn" onClick={() => setOpen(false)} disabled={submitting}>Cancel</button>
                    <button className="btn primary" disabled={!hasChanges || submitting} onClick={async () => {
                        const res = await publish();
                        if (res && res.ok !== false) {
                            setOpen(false);
                        }
                    }}>Publish
                    </button>
                </footer>
            </div>
        </div>
    );
}
