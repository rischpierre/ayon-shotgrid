import {useCallback, useState} from 'react';
import {publishChanges} from '@/api';
import {useProject} from '@/context/ProjectContext.jsx';

export default function usePublish() {
    const {projectId} = useProject();
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);

    const publish = useCallback(async () => {
        if (!projectId) return {ok: false};
        setSubmitting(true);
        setError(null);
        try {
            const res = await publishChanges({}, projectId);
            return res;
        } catch (e) {
            setError(e);
            return {ok: false, error: e};
        } finally {
            setSubmitting(false);
        }
    }, [projectId]);

    return {publish, submitting, error};
}
