import React from 'react';
import {useProject} from '@/context/ProjectContext.jsx';
import {useMode} from '@/context/ModeContext.jsx';
import {EntityType} from '@/constants';

export default function Header() {
    const {projects, projectId, setProjectId, loading} = useProject();
    const {mode, setMode} = useMode();
    const projectList = Array.isArray(projects) ? projects : [];

    return (
        <header>
            <strong>Whiteboard</strong>
            <div style={{display: 'flex', alignItems: 'center', gap: 8}}>
                <label htmlFor="projectSelect" style={{fontSize: 12, color: '#c7cbe0'}}>Project</label>
                <select
                    id="projectSelect"
                    value={projectId || ''}
                    disabled={loading || !projectList.length}
                    onChange={e => setProjectId(e.target.value)}
                    style={{
                        background: '#0f1330',
                        color: '#e7e9ef',
                        border: '1px solid #2a2f58',
                        borderRadius: 6,
                        padding: '6px 8px'
                    }}
                >
                    {projectList.length === 0 ? (
                        <option>Loading…</option>
                    ) : projectList.map(p => (
                        <option key={p.id} value={String(p.id)}>{p.name}</option>
                    ))}
                </select>
            </div>
            <div className="mode-tabs">
                <button
                    data-mode="shots"
                    className={mode === EntityType.Shot ? 'active' : ''}
                    onClick={() => setMode(EntityType.Shot)}
                >
                    Shots
                </button>
                <button
                    data-mode="assets"
                    className={mode === EntityType.Asset ? 'active' : ''}
                    onClick={() => setMode(EntityType.Asset)}
                >
                    Assets
                </button>
            </div>
            <div style={{marginLeft: 'auto'}}>
                <button id="publishBtn" className="btn primary"
                        onClick={() => window.dispatchEvent(new CustomEvent('open-publish'))}>Publish…
                </button>
            </div>
        </header>
    );
}
