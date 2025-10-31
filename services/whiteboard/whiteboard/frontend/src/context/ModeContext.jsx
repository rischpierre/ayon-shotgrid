import React, {createContext, useContext, useMemo, useState, useEffect} from 'react';
import {EntityType} from '@/constants';

const ModeContext = createContext(null);

function updateQueryParam(name, value) {
    const url = new URL(window.location.href);
    const params = url.searchParams;
    if (value === null || value === undefined || value === '') {
        params.delete(name);
    } else {
        params.set(name, String(value));
    }
    const next = `${url.pathname}?${params.toString()}${url.hash}`;
    if (next !== window.location.pathname + window.location.search + window.location.hash) {
        window.history.replaceState(null, '', next);
    }
}

export function ModeProvider({children}) {
    const [mode, setMode] = useState(() => {
        try {
            const params = new URLSearchParams(window.location.search);
            const fromUrl = params.get('entity_type');
            if (fromUrl === EntityType.Shot || fromUrl === EntityType.Asset) return fromUrl;
        } catch (e) {
            // ignore
        }
        return EntityType.Shot;
    });

    useEffect(() => {
        if (mode) updateQueryParam('entity_type', mode);
    }, [mode]);

    const value = useMemo(() => ({mode, setMode}), [mode]);
    return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export function useMode() {
    const ctx = useContext(ModeContext);
    if (!ctx) throw new Error('useMode must be used within ModeProvider');
    return ctx;
}
