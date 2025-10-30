import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.jsx';
import {ProjectProvider} from './context/ProjectContext.jsx';
import {ModeProvider} from './context/ModeContext.jsx';

const rootEl = document.getElementById('root');
const root = createRoot(rootEl);

root.render(
    <React.StrictMode>
        <ProjectProvider>
            <ModeProvider>
                <App/>
            </ModeProvider>
        </ProjectProvider>
    </React.StrictMode>
);
