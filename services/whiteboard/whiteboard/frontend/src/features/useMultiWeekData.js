import {useCallback, useEffect, useMemo, useState} from 'react';
import {getTasks, getWeek} from '@/api';
import {useProject} from '@/context/ProjectContext.jsx';
import {weekOrder} from "@/constants/index.js";

export default function useMultiWeekData() {
    const {projectId} = useProject();
    const [weeks, setWeeks] = useState({});
    const [tasksMap, setTasksMap] = useState({Shot: {}, Asset: {}});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const load = useCallback(async () => {
        if (!projectId) return;
        setLoading(true);
        setError(null);
        try {
            const [tpe, ...wk] = await Promise.all([
                getTasks(projectId),
                ...weekOrder.map(w => getWeek(w, projectId)),
            ]);
            const map = tpe || {Shot: {}, Asset: {}};
            setTasksMap(map);
            const byKey = {};
            for (let i = 0; i < weekOrder.length; i++) {
                byKey[weekOrder[i]] = wk[i];
            }
            setWeeks(byKey);
        } catch (e) {
            setError(e);
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        load();
    }, [load]);

    const value = useMemo(() => ({
        weeks,
        tasksMap,
        loading,
        error,
        reload: load,
    }), [weeks, tasksMap, loading, error, load]);

    return value;
}
