import {useEffect, useMemo, useState, useCallback} from 'react';
import {getTasks, getWeek} from '@/api';
import {EntityType} from '@/constants';
import {useProject} from '@/context/ProjectContext.jsx';
import {useMode} from '@/context/ModeContext.jsx';
import {weekOrder} from "@/constants";

export default function useWeekData(initialWeek = weekOrder[0]) {
    const {projectId} = useProject();
    const {mode} = useMode();
    const [week, setWeek] = useState(initialWeek);
    const [data, setData] = useState(null);
    const [tasksMap, setTasksMap] = useState({Shot: {}, Asset: {}});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const load = useCallback(async (targetWeek = week) => {
        if (!projectId) return;
        setLoading(true);
        setError(null);
        try {
            // tasks per entity (used by task picker)
            const tpe = await getTasks(projectId);
            setTasksMap(tpe || {Shot: {}, Asset: {}});
            const wk = await getWeek(targetWeek, projectId);
            setData(wk);
        } catch (e) {
            setError(e);
        } finally {
            setLoading(false);
        }
    }, [projectId, week]);

    useEffect(() => {
        // reload when project or mode changes (mode influences rendering but backend result is same)
        load(week);
    }, [projectId, mode, week, load]);

    const value = useMemo(() => ({
        week,
        setWeek,
        data,
        tasksMap,
        loading,
        error,
        reload: () => load(week),
    }), [week, data, tasksMap, loading, error, load]);

    return value;
}
