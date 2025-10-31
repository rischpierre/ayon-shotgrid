import React from 'react';
import Header from './components/Header.jsx';
import ContentShell from './components/ContentShell.jsx';
import PublishModal from './components/PublishModal.jsx';

export default function App() {
    return (
        <div className="app-root">
            <Header/>
            <main style={{padding: '0 12px'}}>
                <ContentShell/>
            </main>
            <PublishModal/>
            <footer style={{padding: '8px 12px', color: '#9aa3b2'}}>Drag artist thumbnails onto shot cards to assign.
                Drag any card to another day to reschedule. Assignments only allowed for shots.
            </footer>
        </div>
    );
}
