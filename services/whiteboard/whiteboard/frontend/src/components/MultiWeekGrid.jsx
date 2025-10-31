import React from 'react';
import WeekGrid from './WeekGrid.jsx';
import {weekOrder, weekTitle} from '@/constants';

export default function MultiWeekGrid({weeks, onDropArtist, onMoveItem, onSetAnnotation, onRemoveDueDate, onUnassign}) {
    return (
        <div className="multi-weeks" style={{display: 'grid', gap: 16, padding: '12px 16px'}}>
            {weekOrder.map(wk => {
                const snapshot = weeks?.[wk];
                if (!snapshot) return (
                    <div key={wk} className="week-section">
                        <h2 style={{margin: '4px 0 8px 0', fontSize: 14, color: '#c7cbe0'}}>{weekTitle[wk] || wk}</h2>
                        <div className="boards" style={{opacity: 0.6, padding: '8px 0'}}>Loading…</div>
                    </div>
                );
                return (
                    <div key={wk} className="week-section">
                        <h2 style={{margin: '4px 0 8px 0', fontSize: 14, color: '#c7cbe0'}}>{weekTitle[wk] || wk}</h2>
                        <WeekGrid snapshot={snapshot} onDropArtist={onDropArtist} onMoveItem={onMoveItem}
                                  onSetAnnotation={onSetAnnotation} onRemoveDueDate={onRemoveDueDate}
                                  onUnassign={onUnassign}/>
                    </div>
                );
            })}
        </div>
    );
}
