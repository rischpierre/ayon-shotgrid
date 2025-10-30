import React, {createContext, useContext, useEffect, useMemo, useState} from 'react';
import {listProjects} from '@/api';

const ProjectContext = createContext(null);

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
                    // Keep previous selection if still valid, else default to first
                    const prev = localStorage.getItem('wb_project_id');
                    const initial = (prev && data.find(p => String(p.id) === String(prev))) ? prev : (data[0]?.id ?? null);
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
