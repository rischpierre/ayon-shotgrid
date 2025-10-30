import React, {createContext, useContext, useMemo, useState} from 'react';
import {EntityType} from '@/constants';

const ModeContext = createContext(null);

export function ModeProvider({children}) {
    const [mode, setMode] = useState(EntityType.Shot);
    const value = useMemo(() => ({mode, setMode}), [mode]);
    return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export function useMode() {
    const ctx = useContext(ModeContext);
    if (!ctx) throw new Error('useMode must be used within ModeProvider');
    return ctx;
}
