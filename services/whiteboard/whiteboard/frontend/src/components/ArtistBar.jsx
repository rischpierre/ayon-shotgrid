import React, {useCallback} from 'react';

export default function ArtistBar({artists = []}) {
    const onDragStart = useCallback((a) => (e) => {
        const payload = {type: 'artist', artist_id: a.id, artist_is_group: !!a.is_group};
        e.dataTransfer.setData('application/x-wb', JSON.stringify(payload));
        // Add a generic text flavor for better cross-browser support
        try {
            e.dataTransfer.setData('text/plain', 'wb');
        } catch {
        }
        e.dataTransfer.effectAllowed = 'copyMove';
    }, []);

    return (<div style={{display: 'flex', gap: 8, padding: '8px 0', overflowX: 'auto', alignItems: 'center'}}>
            {artists.length === 0 ? (
                <div style={{color: '#9aa3b2'}}>No artists found for this project.</div>) : (artists.map(a => (
                    <div key={`${a.is_group ? 'g' : 'u'}-${a.id}`} className="artist" title={a.name} draggable
                         onDragStart={onDragStart(a)}>
                        <img src={a.thumb_url} alt={a.name}/>
                    </div>)))}
        </div>);
}
