const weeksEl = document.getElementById('weeks');
let sequenceFilter = localStorage.getItem('wb_sequence_filter') || 'ALL';
const artistBar = document.getElementById('artistBar');
const modeButtons = document.querySelectorAll('.mode-tabs button');
const projectSelect = document.getElementById('projectSelect');
// No filters: On hold and Omitted are shown as dedicated boards

const dayOrder = ['mon','tue','wed','thu','fri'];
const dayTitle = { mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri' };
const weekOrder = ['w0','w1','w2','w3'];
const weekTitle = { w0: 'Current week', w1: 'Next week', w2: '3rd week', w3: '4th week' };

// Task configuration (loaded dynamically per project)
let TASKS_BY_KIND = { shots: ['lighting','tracking','animation','layout'], assets: ['modeling','surfacing','rigging','lookdev'] };

function hashColor(str) {
    // Simple deterministic HSL color from string
    let h = 0;
    for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
    const hue = h % 360;
    return `hsl(${hue}, 70%, 45%)`;
}
function colorForTask(taskName) { return hashColor(String(taskName || 'task')); }

// Task picker elements/state
const taskPicker = document.getElementById('taskPicker');
const taskOptions = document.getElementById('taskOptions');
const taskPickerHeader = document.getElementById('taskPickerHeader');
let pendingAssign = null; // { artistId, shotId }

// Context menu elements/state for unassign
const contextMenu = document.getElementById('contextMenu');
const ctxUnassign = document.getElementById('ctxUnassign');
let ctxData = null; // { artistId, shotId, task }

function showContextMenu(x, y, data) {
    ctxData = data;
    contextMenu.style.left = Math.max(8, Math.min(window.innerWidth - 180, x)) + 'px';
    contextMenu.style.top = Math.max(8, Math.min(window.innerHeight - 60, y)) + 'px';
    contextMenu.style.display = 'block';
    contextMenu.setAttribute('aria-hidden', 'false');
}
function hideContextMenu() {
    contextMenu.style.display = 'none';
    contextMenu.setAttribute('aria-hidden', 'true');
    ctxData = null;
}
ctxUnassign.addEventListener('click', async () => {
    if (!ctxData) return;
    const { artistId, shotId, task } = ctxData;
    hideContextMenu();
    try {
        const resp = await fetch(`/api/unassign${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ artist_id: artistId, shot_id: shotId, task })
        });
        if (resp.ok) await loadMode(currentMode);
    } catch {}
});
document.addEventListener('mousedown', (e) => {
    if (contextMenu.style.display !== 'block') return;
    if (!contextMenu.contains(e.target)) hideContextMenu();
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideContextMenu(); });

function buildTaskOptions() {
    taskOptions.innerHTML = '';
    const list = TASKS_BY_KIND['shots'] || [];
    for (const tRaw of list) {
        const t = String(tRaw);
        const opt = document.createElement('div');
        opt.className = 'task-option';
        opt.dataset.task = t;
        const label = t.length ? (t[0].toUpperCase()+t.slice(1)) : t;
        opt.innerHTML = `<div class="task-swatch" style="background:${colorForTask(t)}"></div><div class="task-label">${label}</div>`;
        opt.addEventListener('click', async () => {
            if (!pendingAssign) return;
            const { artistId, shotId } = pendingAssign;
            hideTaskPicker();
            const resp = await fetch(`/api/assign${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ artist_id: artistId, shot_id: shotId, task: t })
            });
            if (resp.ok) await loadMode(currentMode);
        });
        taskOptions.appendChild(opt);
    }
}

function showTaskPicker(x, y, artistId, shotId) {
    pendingAssign = { artistId, shotId };
    taskPicker.style.left = Math.max(8, Math.min(window.innerWidth - 256, x + 8)) + 'px';
    taskPicker.style.top = Math.max(8, Math.min(window.innerHeight - 200, y + 8)) + 'px';
    taskPicker.style.display = 'block';
    taskPicker.setAttribute('aria-hidden', 'false');
}
function hideTaskPicker() {
    taskPicker.style.display = 'none';
    taskPicker.setAttribute('aria-hidden', 'true');
    pendingAssign = null;
}

// Draggable header for picker
(() => {
    let dragging = false; let dx = 0, dy = 0;
    taskPickerHeader.addEventListener('mousedown', (e) => {
        dragging = true; const rect = taskPicker.getBoundingClientRect();
        dx = e.clientX - rect.left; dy = e.clientY - rect.top;
        e.preventDefault();
    });
    window.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        taskPicker.style.left = Math.max(0, Math.min(window.innerWidth - taskPicker.offsetWidth, e.clientX - dx)) + 'px';
        taskPicker.style.top = Math.max(0, Math.min(window.innerHeight - taskPicker.offsetHeight, e.clientY - dy)) + 'px';
    });
    window.addEventListener('mouseup', () => dragging = false);
})();

// Dismiss on outside click or Escape
document.addEventListener('mousedown', (e) => {
    if (taskPicker.style.display !== 'block') return;
    if (!taskPicker.contains(e.target)) hideTaskPicker();
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideTaskPicker(); });

buildTaskOptions();

let currentMode = 'shots';

modeButtons.forEach(b => b.addEventListener('click', () => {
    modeButtons.forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    currentMode = b.dataset.mode;
    loadMode(currentMode);
}));

async function loadMode(mode) {
    // Fetch each week's snapshot
    const snaps = await Promise.all(weekOrder.map(async w => {
        const params = new URLSearchParams();
        if (window.currentProjectId) params.set('project_id', window.currentProjectId);
        const res = await fetch(`/api/week/${w}?${params.toString()}`);
        if (!res.ok) throw new Error('Failed to load week ' + w);
        return res.json();
    }));

    // Clear container
    weeksEl.innerHTML = '';

    // Render artists from first snapshot
    renderArtists(snaps[0]?.artists ?? []);

    // Render No due date board (only in shots mode and if provided)
    const w0 = snaps.find(s => s.week === 'w0');
    // Cache annotations map from w0
    window.annotationsMap = (w0 && w0.annotations) ? w0.annotations : {};
    if (mode === 'shots' && w0 && Array.isArray(w0.no_due_date) && w0.no_due_date.length) {
        renderNoDueDate(w0);
    }

    // Build per-week, per-day items aggregation for the chosen mode
    const byWeek = {};
    const assignments = {};
    for (const snap of snaps) {
        const weekMap = {};
        for (const day of dayOrder) {
            const itemsForDay = [];
            const boardsForDay = snap.boards[day] || [];
            for (const b of boardsForDay) {
                if (b.kind !== mode) continue;
                const arr = snap.board_items[b.id] || [];
                itemsForDay.push(...arr);
            }
            weekMap[day] = itemsForDay;
        }
        byWeek[snap.week] = weekMap;
        if (mode === 'shots') Object.assign(assignments, snap.assignments || {});
    }

    renderWeeks({ kind: mode, by_week: byWeek, assignments });

    // After weeks, render On hold and Omitted sections (shots mode only)
    if (mode === 'shots' && w0) {
        renderHoldOmit(w0);
    }
}

function renderArtists(artists) {
    artistBar.innerHTML = '';
    for (const a of artists) {
        const el = document.createElement('div');
        el.className = 'artist';
        el.draggable = true;
        el.dataset.artistId = a.id;
        el.innerHTML = `<img src="${a.thumb_url}" alt="${a.name}" title="${a.name}" />`;
        el.addEventListener('dragstart', e => {
            e.dataTransfer.setData('application/artist-id', a.id);
            e.dataTransfer.effectAllowed = 'copy';
        });
        artistBar.appendChild(el);
    }
    cacheArtists(artists);
}

function renderNoDueDate(w0snap) {
    const section = document.createElement('section');
    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.alignItems = 'center';
    header.style.gap = '12px';

    // Sequence filter combobox (left side)
    const seqWrap = document.createElement('div');
    const label = document.createElement('label');
    label.style.fontSize = '12px';
    label.style.color = '#c7cbe0';
    label.style.marginRight = '6px';
    label.textContent = 'Sequence';
    const select = document.createElement('select');
    select.style.background = '#0f1330';
    select.style.color = '#e7e9ef';
    select.style.border = '1px solid #2a2f58';
    select.style.borderRadius = '6px';
    select.style.padding = '6px 8px';

    const seqs = Array.isArray(w0snap.sequences) ? w0snap.sequences : [];
    const allOpt = document.createElement('option');
    allOpt.value = 'ALL';
    allOpt.textContent = 'All sequences';
    select.appendChild(allOpt);
    for (const s of seqs) {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s;
        select.appendChild(opt);
    }
    if (!sequenceFilter || (sequenceFilter !== 'ALL' && !seqs.includes(sequenceFilter))) {
        sequenceFilter = 'ALL';
    }
    select.value = sequenceFilter || 'ALL';
    select.addEventListener('change', () => {
        sequenceFilter = select.value || 'ALL';
        localStorage.setItem('wb_sequence_filter', sequenceFilter);
        // Reload to re-render both no-date and weeks with current filter
        loadMode(currentMode);
    });
    seqWrap.appendChild(label);
    seqWrap.appendChild(select);

    const h = document.createElement('h2');
    h.textContent = 'No due date';

    // Place filter left, then title
    header.appendChild(seqWrap);
    header.appendChild(h);

    section.appendChild(header);

    const grid = document.createElement('div');
    grid.className = 'boards';
    section.appendChild(grid);

    // Single board that spans the full width
    const wrap = document.createElement('div');
    wrap.className = 'board';
    wrap.style.gridColumn = '1 / -1';
    wrap.innerHTML = `<h3>Shots</h3><div class="list"></div>`;
    const list = wrap.querySelector('.list');

    // Make the list a responsive grid spanning the page width
    list.style.display = 'grid';
    list.style.gridTemplateColumns = 'repeat(auto-fill, minmax(300px, 1fr))';
    list.style.gap = '8px';
    list.style.maxHeight = 'unset';
    list.style.overflowY = 'visible';
    list.style.alignItems = 'start';

    const items = w0snap.no_due_date || [];
    const filtered = items.filter(it => sequenceFilter === 'ALL' || (it.sequence || '') === sequenceFilter);

    for (const it of filtered) {
        const card = document.createElement('div');
        card.className = 'card';
        card.dataset.itemId = it.id;
        card.dataset.kind = 'shots';
        card.draggable = true;
        card.addEventListener('dragstart', e => {
            e.dataTransfer.setData('application/item-id', JSON.stringify({ item_id: it.id, kind: 'shots' }));
            e.dataTransfer.effectAllowed = 'move';
        });
        const seqBadge = it.sequence ? `<div class="badge">${it.sequence}</div>` : '';
        card.innerHTML = `
            <div class="thumb"><img src="${it.thumb_url}" alt="thumb" /></div>
            <div>
                <div class="title">${it.name} ${seqBadge}</div>
                <div class="assignees" data-shot-assignees="${it.id}"></div>
            </div>
        `;
        list.appendChild(card);
    }

    grid.appendChild(wrap);

    // Insert at top of weeks container
    const prev = document.getElementById('noDueSection');
    if (prev && prev.parentElement) prev.parentElement.removeChild(prev);
    section.id = 'noDueSection';
    weeksEl.prepend(section);
}

function renderWeeks(snapshot) {
    // weeksEl is managed by loadMode (which may have injected No due date section)
    const today = new Date();
    const dow = today.getDay(); // Sun=0..Sat=6
    const dayMap = {1:'mon',2:'tue',3:'wed',4:'thu',5:'fri'};
    const currentDayKey = dayMap[dow] || null;
    // Calculate current Monday
    const monday = new Date(today);
    const offset = (today.getDay() + 6) % 7; // Mon=0
    monday.setDate(today.getDate() - offset);

    for (const wk of weekOrder) {
        const section = document.createElement('section');
        const h = document.createElement('h2');
        h.textContent = weekTitle[wk];
        section.appendChild(h);
        const grid = document.createElement('div');
        grid.className = 'boards';
        section.appendChild(grid);

        for (const day of dayOrder) {
            const wrap = document.createElement('div');
            wrap.className = 'board';
            if (wk === 'w0' && currentDayKey && currentDayKey === day) {
                wrap.classList.add('current-day');
            }
            wrap.dataset.day = day;
            wrap.dataset.week = wk;
            wrap.dataset.kind = snapshot.kind;
            // Compute calendar date for header
            const weekIdx = parseInt(wk.slice(1), 10) || 0;
            const dayIdx = {mon:0,tue:1,wed:2,thu:3,fri:4}[day];
            const d = new Date(monday);
            d.setDate(monday.getDate() + weekIdx*7 + dayIdx);
            const dayNum = d.getDate();
            const annKey = `${wk}/${day}`;
            const annObj = (window.annotationsMap && window.annotationsMap[annKey]) ? window.annotationsMap[annKey] : null;
            wrap.innerHTML = `<h3>${dayTitle[day]} ${dayNum}</h3>
                <div class="list"></div>`;
            const h3 = wrap.querySelector('h3');
            // Make header flex to place annotation on the right side
            h3.style.display = 'flex';
            h3.style.alignItems = 'center';
            h3.style.justifyContent = 'space-between';
            // If annotation exists and has text, render it on the right
            if (annObj && typeof annObj === 'object' && annObj.text && String(annObj.text).trim().length) {
                const annSpan = document.createElement('span');
                const rawText = String(annObj.text);
                const truncated = rawText.length > 30 ? rawText.slice(0, 30) + '…' : rawText;
                annSpan.textContent = truncated;
                annSpan.style.color = annObj.color || '#c7cbe0';
                annSpan.style.fontSize = '12px';
                annSpan.style.marginLeft = '12px';
                annSpan.style.opacity = '0.95';
                annSpan.title = rawText;
                annSpan.style.cursor = 'pointer';
                annSpan.addEventListener('click', async () => {
                    const curText = String((window.annotationsMap && window.annotationsMap[annKey] && window.annotationsMap[annKey].text) || '');
                    const curColor = String((window.annotationsMap && window.annotationsMap[annKey] && window.annotationsMap[annKey].color) || '#c7cbe0');
                    const newText = window.prompt('Annotation text', curText);
                    if (newText === null) return;
                    const newColor = window.prompt('Font color (hex, e.g., #ffcc00)', curColor) || curColor;
                    try {
                        const resp = await fetch(`/api/annotations${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ week: wk, day, text: newText, color: newColor })
                        });
                        if (resp.ok) {
                            window.annotationsMap = (await resp.json()).annotations || window.annotationsMap;
                            await loadMode(currentMode);
                        }
                    } catch {}
                });
                h3.appendChild(annSpan);
            } else {
                // No widget when there is no annotation; allow creating by double‑clicking the header
                h3.style.cursor = 'default';
                h3.addEventListener('dblclick', async () => {
                    const newText = window.prompt('Add annotation text');
                    if (newText === null) return;
                    const newColor = window.prompt('Font color (hex, e.g., #ffcc00)', '#c7cbe0') || '#c7cbe0';
                    try {
                        const resp = await fetch(`/api/annotations${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ week: wk, day, text: newText, color: newColor })
                        });
                        if (resp.ok) {
                            window.annotationsMap = (await resp.json()).annotations || window.annotationsMap;
                            await loadMode(currentMode);
                        }
                    } catch {}
                });
            }
            const list = wrap.querySelector('.list');

            const items = (snapshot.by_week[wk] || {})[day] || [];
            for (const it of items) {
                const card = document.createElement('div');
                card.className = 'card';
                card.dataset.itemId = it.id;
                card.dataset.kind = snapshot.kind;
                card.draggable = true;
                card.addEventListener('dragstart', e => {
                    e.dataTransfer.setData('application/item-id', JSON.stringify({ item_id: it.id, kind: snapshot.kind }));
                    e.dataTransfer.effectAllowed = 'move';
                });
                card.innerHTML = `
                    <div class="thumb"><img src="${it.thumb_url}" alt="thumb" /></div>
                    <div>
                        <div class="title">${it.name}</div>
                        <div class="assignees" data-shot-assignees="${it.id}"></div>
                    </div>
                `;
                window._itemNameCache = window._itemNameCache || {};
                window._itemNameCache[it.id] = it.name;
                if (snapshot.kind === 'shots') {
                    const holder = card.querySelector('.assignees');
                    const assigned = snapshot.assignments[it.id] || [];
                    for (const a of assigned) {
                        const artist = (window._artistsCache || []).find(x => x.id === a.artist_id);
                        if (!artist) continue;
                        const av = document.createElement('div');
                        av.className = 'assignee';
                        av.style.borderColor = colorForTask(a.task);
                        av.dataset.artistId = a.artist_id;
                        av.dataset.task = a.task;
                        av.dataset.shotId = it.id;
                        av.title = `${artist.name} — ${a.task} (right‑click to unassign)`;
                        av.innerHTML = `<img src="${artist.thumb_url}" alt="${artist.name}" />`;
                        av.addEventListener('contextmenu', (e) => {
                            e.preventDefault();
                            showContextMenu(e.clientX, e.clientY, { artistId: a.artist_id, shotId: it.id, task: a.task });
                        });
                        holder.appendChild(av);
                    }
                }
                list.appendChild(card);
            }

            // Drag and drop: allow assigning artists to shots and moving items across days/weeks
            list.addEventListener('dragover', e => {
                const types = e.dataTransfer?.types || [];
                const isArtist = types.includes('application/artist-id');
                const isItem = types.includes('application/item-id');
                if ((isArtist && snapshot.kind === 'shots') || isItem) {
                    e.preventDefault();
                }
            });

            list.addEventListener('dragenter', e => {
                const types = e.dataTransfer?.types || [];
                const isArtist = types.includes('application/artist-id');
                const isItem = types.includes('application/item-id');
                const ok = (isArtist && snapshot.kind === 'shots') || isItem;
                wrap.classList.toggle('drop-ok', ok);
                wrap.classList.toggle('drop-bad', !ok && (isArtist || isItem));
            });
            list.addEventListener('dragleave', () => {
                wrap.classList.remove('drop-ok','drop-bad');
            });

            list.addEventListener('drop', async e => {
                wrap.classList.remove('drop-ok','drop-bad');

                // Card move between weeks/days (shots or assets)
                const movePayload = e.dataTransfer.getData('application/item-id');
                if (movePayload) {
                    try {
                        const data = JSON.parse(movePayload);
                        const resp = await fetch(`/api/move_week_day${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ item_id: data.item_id, kind: data.kind, to_week: wk, to_day: day })
                        });
                        if (resp.ok) {
                            await loadMode(currentMode);
                            return;
                        }
                    } catch {}
                }

                // Assigning artists to shots (only in shots mode)
                if (snapshot.kind !== 'shots') return; // forbid assigning to assets
                const artistId = e.dataTransfer.getData('application/artist-id');
                if (!artistId) return;
                // Assign onto nearest shot card under cursor (or the first card if none)
                const card = document.elementFromPoint(e.clientX, e.clientY)?.closest('.card');
                const shotCard = card && card.dataset.kind === 'shots' ? card : list.querySelector('.card');
                if (!shotCard) return;
                const shotId = shotCard.dataset.itemId;
                // Instead of assigning immediately, open task picker
                showTaskPicker(e.clientX, e.clientY, artistId, shotId);
            });

            grid.appendChild(wrap);
        }

        weeksEl.appendChild(section);
    }
}

// Cache artists for quick lookup while rendering assigned avatars
function cacheArtists(artists) {
    window._artistsCache = artists;
}

// Tasks for current project
async function loadTasks() {
    const pid = window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : '';
    try {
        const res = await fetch(`/api/tasks${pid}`);
        if (res.ok) {
            const data = await res.json();
            if (data && typeof data === 'object') {
                TASKS_BY_KIND = {
                    shots: Array.isArray(data.shots) && data.shots.length ? data.shots : TASKS_BY_KIND.shots,
                    assets: Array.isArray(data.assets) && data.assets.length ? data.assets : TASKS_BY_KIND.assets,
                };
            }
        }
    } catch {}
    buildTaskOptions();
}

// Project dropdown + URL sync
async function loadProjects() {
    try {
        const res = await fetch('/api/projects');
        const list = res.ok ? await res.json() : [];
        projectSelect.innerHTML = '';
        const urlParams = new URLSearchParams(location.search);
        const urlPid = urlParams.get('project');
        const active = list.filter(p => !p.archived);
        const saved = localStorage.getItem('selectedProjectId');
        let toSelect = '';
        if (urlPid && list.find(p => String(p.id) === String(urlPid))) {
            toSelect = urlPid;
        } else if (saved && list.find(p => String(p.id) === String(saved))) {
            toSelect = saved;
        } else {
            toSelect = (active[0]?.id ?? (list[0]?.id ?? ''));
        }
        for (const p of list) {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name + (p.archived ? ' (archived)' : '');
            if (String(p.id) === String(toSelect)) opt.selected = true;
            projectSelect.appendChild(opt);
        }
        window.currentProjectId = String(toSelect || '');
        // Ensure URL reflects the current project
        const newParams = new URLSearchParams(location.search);
        if (window.currentProjectId) newParams.set('project', window.currentProjectId); else newParams.delete('project');
        const newUrl = `${location.pathname}?${newParams.toString()}`;
        window.history.replaceState({}, '', newUrl);

        projectSelect.addEventListener('change', async () => {
            window.currentProjectId = String(projectSelect.value);
            localStorage.setItem('selectedProjectId', window.currentProjectId);
            const params = new URLSearchParams(location.search);
            if (window.currentProjectId) params.set('project', window.currentProjectId); else params.delete('project');
            window.history.replaceState({}, '', `${location.pathname}?${params.toString()}`);
            await loadTasks();
            loadMode(currentMode);
        });
    } catch (e) {
        projectSelect.innerHTML = '<option>Error loading projects</option>';
    }
}

// Publish modal logic
const publishBtn = document.getElementById('publishBtn');
const publishModal = document.getElementById('publishModal');
const changesContainer = document.getElementById('changesContainer');
const closePublish = document.getElementById('closePublish');
const cancelPublish = document.getElementById('cancelPublish');
const confirmPublish = document.getElementById('confirmPublish');

function showPublishModal() {
    publishModal.style.display = 'flex';
    publishModal.setAttribute('aria-hidden', 'false');
}
function hidePublishModal() {
    publishModal.style.display = 'none';
    publishModal.setAttribute('aria-hidden', 'true');
}

function renderChangesList(data) {
    const moves = Array.isArray(data.moves) ? data.moves : [];
    const assigns = data.assignments || {};
    const parts = [];
    if (!moves.length && (!assigns || !Object.keys(assigns).length)) {
        changesContainer.innerHTML = '<div style="color:#9aa3b2;">No changes pending.</div>';
        return;
    }
    parts.push('<div class="changes-list">');
    if (moves.length) {
        parts.push('<div style="font-weight:600; margin:6px 0;">Reschedules</div>');
        for (const m of moves) {
            const nm = (window._itemNameCache && window._itemNameCache[m.shot_id]) || m.shot_name || m.shot_id;
            parts.push(`<div class="change-item">${nm}: ${m.from_date ? `from ${m.from_date} ` : ''}→ ${m.to_date} (${weekTitle[m.to_week]} ${dayTitle[m.to_day]})</div>`);
        }
    }
    const aShotIds = Object.keys(assigns || {});
    if (aShotIds.length) {
        parts.push('<div style="font-weight:600; margin:6px 0;">Assignments</div>');
        for (const sid of aShotIds) {
            const nm = (window._itemNameCache && window._itemNameCache[sid]) || `Shot ${sid}`;
            const list = assigns[sid] || [];
            for (const a of list) {
                const artist = (window._artistsCache || []).find(x => String(x.id) === String(a.artist_id));
                const aname = artist ? artist.name : `Artist ${a.artist_id}`;
                parts.push(`<div class="change-item">${nm}: ${aname} → ${a.task}</div>`);
            }
        }
    }
    parts.push('</div>');
    changesContainer.innerHTML = parts.join('');
}

async function openPublish() {
    try {
        const pid = window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : '';
        const res = await fetch(`/api/changes${pid}`);
        const data = res.ok ? await res.json() : { moves: [], assignments: {} };
        renderChangesList(data);
        showPublishModal();
    } catch (e) {
        changesContainer.innerHTML = '<div style="color:#ff6b6b;">Failed to load changes.</div>';
        showPublishModal();
    }
}

publishBtn.addEventListener('click', openPublish);
closePublish.addEventListener('click', hidePublishModal);
cancelPublish.addEventListener('click', hidePublishModal);

confirmPublish.addEventListener('click', async () => {
    confirmPublish.disabled = true;
    confirmPublish.textContent = 'Publishing…';
    try {
        const pid = window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : '';
        const res = await fetch(`/api/publish${pid}`, { method: 'POST' });
        if (res.ok) {
            hidePublishModal();
            await loadMode(currentMode);
        } else {
            changesContainer.innerHTML = '<div style="color:#ff6b6b;">Publish failed.</div>';
        }
    } catch (e) {
        changesContainer.innerHTML = '<div style="color:#ff6b6b;">Publish error.</div>';
    } finally {
        confirmPublish.disabled = false;
        confirmPublish.textContent = 'Publish';
    }
});

// Initial load
(async () => {
    await loadProjects();
    await loadTasks();
    loadMode(currentMode);
})();


function renderHoldOmit(w0snap) {
    // Remove previous section if exists
    const prev = document.getElementById('holdOmitSection');
    if (prev && prev.parentElement) prev.parentElement.removeChild(prev);

    // Helper to create a week-like section with 5 day columns
    function makeWeekLikeSection(title, items) {
        const section = document.createElement('section');
        const h2 = document.createElement('h2');
        h2.textContent = title;
        section.appendChild(h2);
        const grid = document.createElement('div');
        grid.className = 'boards';
        section.appendChild(grid);

        // Prepare five columns (Mon..Fri)
        const cols = {};
        for (const day of dayOrder) {
            const wrap = document.createElement('div');
            wrap.className = 'board';
            wrap.innerHTML = `<h3>${dayTitle[day]}</h3><div class="list"></div>`;
            const h3 = wrap.querySelector('h3');
            // Flex header for consistency with week boards
            h3.style.display = 'flex';
            h3.style.alignItems = 'center';
            h3.style.justifyContent = 'space-between';
            const list = wrap.querySelector('.list');
            cols[day] = list;
            grid.appendChild(wrap);

            // Accept drops (UI-only)
            list.addEventListener('dragover', e => {
                const types = e.dataTransfer?.types || [];
                if (types.includes('application/item-id')) { e.preventDefault(); list.classList.add('drop-ok'); }
            });
            list.addEventListener('dragleave', () => list.classList.remove('drop-ok'));
            list.addEventListener('drop', e => {
                list.classList.remove('drop-ok');
                const data = e.dataTransfer.getData('application/item-id');
                try {
                    const { item_id } = JSON.parse(data || '{}');
                    if (!item_id) return;
                    const card = document.querySelector(`.card[data-item-id="${CSS.escape(item_id)}"]`);
                    if (card) list.appendChild(card);
                } catch {}
            });
        }

        // Distribute items round-robin into the five columns
        const arr = Array.isArray(items) ? items : [];
        for (let i = 0; i < arr.length; i++) {
            const it = arr[i];
            const day = dayOrder[i % dayOrder.length];
            const list = cols[day];
            const card = document.createElement('div');
            card.className = 'card';
            card.dataset.itemId = it.id;
            card.dataset.kind = 'shots';
            card.draggable = true;
            card.addEventListener('dragstart', e => {
                e.dataTransfer.setData('application/item-id', JSON.stringify({ item_id: it.id, kind: 'shots' }));
                e.dataTransfer.effectAllowed = 'move';
            });
            const seqBadge = it.sequence ? `<div class="badge">${it.sequence}</div>` : '';
            card.innerHTML = `
                <div class="thumb"><img src="${it.thumb_url}" alt="thumb" /></div>
                <div>
                    <div class="title">${it.name} ${seqBadge}</div>
                    <div class="assignees" data-shot-assignees="${it.id}"></div>
                </div>
            `;
            list.appendChild(card);
        }
        return section;
    }

    const hasHold = Array.isArray(w0snap.on_hold) && w0snap.on_hold.length;
    const hasOmit = Array.isArray(w0snap.omitted) && w0snap.omitted.length;
    if (!hasHold && !hasOmit) return;

    const container = document.createElement('section');
    container.id = 'holdOmitSection';

    if (hasHold) container.appendChild(makeWeekLikeSection('On hold', w0snap.on_hold));
    if (hasOmit) container.appendChild(makeWeekLikeSection('Omitted', w0snap.omitted));

    weeksEl.appendChild(container);
}
