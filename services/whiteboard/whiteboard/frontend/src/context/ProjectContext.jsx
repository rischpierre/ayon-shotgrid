import React, {createContext, useContext, useEffect, useMemo, useState} from 'react';
import {listProjects} from '@/api';

const ProjectContext = createContext(null);

function updateQueryParam(name, value) {
    const url = new URL(window.location.href);
    const params = url.searchParams;
    if (value === null || value === undefined || value === '') {
        params.delete(name);
    } else {
        params.set(name, String(value));
    }
    // Only replace if changed
    const next = `${url.pathname}?${params.toString()}${url.hash}`;
    if (next !== window.location.pathname + window.location.search + window.location.hash) {
        window.history.replaceState(null, '', next);
    }
}

export function ProjectProvider({children}) {
    const [projects, setProjects] = useState([]);
    const [projectId, setProjectId] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;

        async function run() {
            setLoading(true);
            setError(null);
            try {
                const data = await listProjects();
                if (!cancelled) {
                    setProjects(data || []);
                    // Determine initial selection priority:
                    // 1) URL ?project=... if present and valid
                    // 2) localStorage wb_project_id if still valid
                    // 3) default to first project
                    const urlParams = new URLSearchParams(window.location.search);
                    const fromUrl = urlParams.get('project');
                    const hasUrl = fromUrl && data.find(p => String(p.id) === String(fromUrl));
                    const prev = localStorage.getItem('wb_project_id');
                    const hasPrev = prev && data.find(p => String(p.id) === String(prev));
                    const initial = hasUrl ? String(fromUrl) : (hasPrev ? String(prev) : (data[0]?.id ?? null));
                    setProjectId(initial ? String(initial) : null);
                }
            } catch (e) {
                if (!cancelled) setError(e);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        run();
        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        if (projectId) {
            localStorage.setItem('wb_project_id', String(projectId));
            // Expose for any legacy helpers that might peek
            window.currentProjectId = String(projectId);
            // Sync to URL
            updateQueryParam('project', String(projectId));
        }
    }, [projectId]);

    const value = useMemo(() => ({
        projects,
        projectId,
        setProjectId,
        loading,
        error,
    }), [projects, projectId, loading, error]);

    return (
        <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
    );
}

export function useProject() {
    const ctx = useContext(ProjectContext);
    if (!ctx) throw new Error('useProject must be used within ProjectProvider');
    return ctx;
}
