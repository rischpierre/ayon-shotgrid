import React, {useCallback, useEffect, useMemo, useState} from 'react';
import useEvent from '@/hooks/useEvent';
import {useProject} from '@/context/ProjectContext.jsx';
import {getChanges} from '@/api';
import usePublish from '@/features/usePublish.js';

export default function PublishModal() {
    const [open, setOpen] = useState(false);
    const [changes, setChanges] = useState(null); // {moves, assignments}
    const {projectId} = useProject();
    const {publish, submitting, error} = usePublish();

    const loadChanges = useCallback(async () => {
        if (!projectId) return;
        try {
            const data = await getChanges(projectId);
            setChanges(data || {moves: {}, assignments: {}});
        } catch (e) {
            console.error('Failed to load changes', e);
            setChanges({moves: {}, assignments: {}});
        }
    }, [projectId]);

    const onOpen = useCallback(() => {
        setOpen(true);
    }, []);

    useEvent('open-publish', onOpen);

    useEffect(() => {
        if (open) loadChanges();
    }, [open, loadChanges]);

    const hasChanges = !!(changes && ((changes.moves && Object.keys(changes.moves).length) || (changes.assignments && Object.keys(changes.assignments).length)));
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
                                    Move {m.shot_name || m.shot_id} → {String(m.to_week)}/{String(m.to_day)} ({m.to_date})
                                </div>
                            )) : null}
                            {/* assignments is a nested structure; show summary counts */}
                            {changes.assignments && (
                                <div className="change-item">
                                    Assignments: {Object.keys(changes.assignments).length} entities with changes
                                </div>
                            )}
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
