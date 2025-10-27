const weeksEl = document.getElementById('weeks');
let sequenceFilter = localStorage.getItem('wb_sequence_filter') || 'ALL';
let assetTypeFilter = localStorage.getItem('wb_asset_type_filter') || 'ALL';
const artistBar = document.getElementById('artistBar');
const modeButtons = document.querySelectorAll('.mode-tabs button');
const projectSelect = document.getElementById('projectSelect');
// No filters: On hold and Omitted are shown as dedicated boards

const dayOrder = ['mon','tue','wed','thu','fri'];
const dayTitle = { mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri' };
const weekOrder = ['w0','w1','w2','w3'];
const weekTitle = { w0: 'Current week', w1: 'Next week', w2: '3rd week', w3: '4th week' };

const EntityType = Object.freeze({
  Shot: 'Shot',
  Asset: 'Asset',
});

// Task configuration (loaded dynamically per project)
let TASKS_PER_ENTITY_TYPE = { shots: ['lighting','tracking','animation','layout'], assets: ['modeling','surfacing','rigging','lookdev'] };

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

class PendingAssign {
    constructor(artist_id, artist_is_group, entity_id, entity_type) {
        this.artist_id = String(artist_id);
        this.artist_is_group = artist_is_group;
        this.entity_id = String(entity_id);
        this.entity_type = entity_type;
    }
}
let pendingAssign = /** @type {PendingAssign|null} */ (null);

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
    const { artistId, artist_is_group, shotId, task } = ctxData;
    hideContextMenu();
    try {
        const resp = await fetch(`/api/unassign${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ artist_id: artistId, artist_is_group: artist_is_group,shot_id: shotId, task: task })
        });
        if (resp.ok) await loadMode(currentMode);
    } catch {}
});

// Day header context menu for annotations
const dayMenu = document.getElementById('dayMenu');
const dayAddEdit = document.getElementById('dayAddEdit');
const dayRemove = document.getElementById('dayRemove');
const dayColor = document.getElementById('dayColor');
const dayColorSub = document.getElementById('dayColorSub');
let dayCtx = null; // { week, day }
const DAY_COLORS = ['#ff6b6b', '#f1c40f', '#2ecc71', '#3498db', '#c7cbe0'];

function buildDayColorSubmenu(curColor) {
    dayColorSub.innerHTML = '';
    DAY_COLORS.forEach(col => {
        const opt = document.createElement('div');
        opt.className = 'item';
        opt.style.display = 'flex';
        opt.style.alignItems = 'center';
        opt.style.gap = '8px';
        opt.innerHTML = `<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:${col};border:2px solid rgba(255,255,255,0.3);"></span><span style="color:#e7e9ef;">${col.toUpperCase()}</span>`;
        opt.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (!dayCtx) return;
            const { week, day } = dayCtx;
            hideDayMenu();
            const key = `${week}/${day}`;
            const cur = (window.annotationsMap && window.annotationsMap[key]) || { text: '' };
            try {
                const resp = await fetch(`/api/annotations${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ week, day, text: cur.text || '', color: col })
                });
                if (resp.ok) {
                    window.annotationsMap = (await resp.json()).annotations || window.annotationsMap;
                    await loadMode(currentMode);
                }
            } catch {}
        });
        dayColorSub.appendChild(opt);
    });
}

function showDayMenu(x, y, data) {
    dayCtx = data; // {week, day}
    // Position main menu
    dayMenu.style.left = Math.max(8, Math.min(window.innerWidth - 220, x)) + 'px';
    dayMenu.style.top = Math.max(8, Math.min(window.innerHeight - 180, y)) + 'px';
    dayMenu.style.display = 'block';
    dayMenu.setAttribute('aria-hidden', 'false');
    // Prepare color submenu content and hide initially
    const key = `${data.week}/${data.day}`;
    const cur = (window.annotationsMap && window.annotationsMap[key]) || { color: '#c7cbe0' };
    buildDayColorSubmenu(cur.color);
    dayColorSub.style.display = 'none';
}
function hideDayMenu() {
    dayMenu.style.display = 'none';
    dayMenu.setAttribute('aria-hidden', 'true');
    dayColorSub.style.display = 'none';
    dayCtx = null;
}

document.addEventListener('mousedown', (e) => {
    if (contextMenu.style.display === 'block' && !contextMenu.contains(e.target)) hideContextMenu();
    if (dayMenu.style.display === 'block' && !dayMenu.contains(e.target)) hideDayMenu();
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { hideContextMenu(); hideDayMenu(); } });

dayAddEdit.addEventListener('click', async () => {
    if (!dayCtx) return;
    const { week, day } = dayCtx;
    const key = `${week}/${day}`;
    const cur = (window.annotationsMap && window.annotationsMap[key]) || { text: '', color: '#c7cbe0' };
    hideDayMenu();
    const newText = window.prompt('Annotation text', cur.text || '');
    if (newText === null) return;
    try {
        const resp = await fetch(`/api/annotations${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ week, day, text: newText, color: cur.color || '#c7cbe0' })
        });
        if (resp.ok) {
            window.annotationsMap = (await resp.json()).annotations || window.annotationsMap;
            await loadMode(currentMode);
        }
    } catch {}
});

dayRemove.addEventListener('click', async () => {
    if (!dayCtx) return;
    const { week, day } = dayCtx;
    hideDayMenu();
    try {
        const resp = await fetch(`/api/annotations${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ week, day, text: '' })
        });
        if (resp.ok) {
            window.annotationsMap = (await resp.json()).annotations || window.annotationsMap;
            await loadMode(currentMode);
        }
    } catch {}
});

dayColor.addEventListener('mouseenter', () => {
    // Show submenu aligned to parent
    const rect = dayMenu.getBoundingClientRect();
    dayColorSub.style.left = (rect.width - 2) + 'px';
    dayColorSub.style.top = '0px';
    dayColorSub.style.display = 'block';
});
dayColor.addEventListener('mouseleave', () => {
    // Hide submenu when moving off entire menu unless entering submenu
    // Slight delay not necessary; submenu stays if hovered
});
dayMenu.addEventListener('mouseleave', () => {
    // Hide submenu when leaving menu entirely
    dayColorSub.style.display = 'none';
});

function buildTaskOptions(taskListOverride, entity_type) {
    taskOptions.innerHTML = '';
    const defaultList = (TASKS_PER_ENTITY_TYPE[entity_type] || TASKS_PER_ENTITY_TYPE[EntityType.Shot] || []);
    const list = Array.isArray(taskListOverride) && taskListOverride.length ? taskListOverride : defaultList;
    for (const tRaw of list) {
        const t = String(tRaw);
        const opt = document.createElement('div');
        opt.className = 'task-option';
        opt.dataset.task = t;
        const label = t.length ? (t[0].toUpperCase()+t.slice(1)) : t;
        opt.innerHTML = `<div class="task-swatch" style="background:${colorForTask(t)}"></div><div class="task-label">${label}</div>`;
        opt.addEventListener('click', async () => {
            if (!pendingAssign) return;
            const pending_assign = pendingAssign; // capture before hiding (hideTaskPicker clears it)
            const body = {
                artist_id: pending_assign.artist_id,
                artist_is_group: pending_assign.artist_is_group,
                entity_id: pending_assign.entity_id,
                entity_type: pending_assign.entity_type,
                task: t
            }

            hideTaskPicker();
            const resp = await fetch(`/api/assign${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (resp.ok) await loadMode(currentMode);
        });
        taskOptions.appendChild(opt);
    }
}

function showTaskPicker(x, y, artistId, artistIsGroup, shotId, entity_type) {
    pendingAssign = { artist_id: artistId, artist_is_group: artistIsGroup,  entity_id: shotId, entity_type: entity_type};

    const perShot = (entity_type === EntityType.Shot && window.tasksPerShot && window.tasksPerShot[shotId]) ? window.tasksPerShot[shotId] : null;
    buildTaskOptions(perShot, entity_type);
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

// Determine initial mode from URL (?entity_type=shots|assets)
(function initModeFromUrl(){
    const params = new URLSearchParams(location.search);
    const et = (params.get('entity_type') || '').toLowerCase();
    let initial = (et === EntityType.Asset) ? EntityType.Asset : EntityType.Shot;
    // Highlight the proper tab
    modeButtons.forEach(x => x.classList.toggle('active', x.dataset.mode === initial));
    window.currentMode = initial;
})();
let currentMode = window.currentMode || EntityType.Shot;

modeButtons.forEach(b => b.addEventListener('click', () => {
    modeButtons.forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    currentMode = b.dataset.mode;
    const params = new URLSearchParams(location.search);
    params.set('entity_type', currentMode);
    window.history.replaceState({}, '', `${location.pathname}?${params.toString()}`);
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
    // Cache annotations map from w0, but don't clobber recent local edits if server hasn't caught up yet
    const serverAnn = (w0 && w0.annotations) ? w0.annotations : {};
    if (serverAnn && Object.keys(serverAnn).length) {
        // Merge, giving precedence to locally-updated entries to reflect immediate changes
        window.annotationsMap = Object.assign({}, serverAnn, window.annotationsMap || {});
    } else {
        window.annotationsMap = window.annotationsMap || {};
    }
    // Expose per-shot tasks map for task picker
    window.tasksPerShot = (w0 && w0.tasks_per_shot) ? w0.tasks_per_shot : {};
    if (mode === EntityType.Shot && w0 && Array.isArray(w0.no_due_date) && w0.no_due_date.length) {
        renderNoDueDate(w0);
    }
    if (mode === EntityType.Asset && w0 && Array.isArray(w0.assets_no_due_date) && w0.assets_no_due_date.length) {
        renderNoDueDateAssets(w0);
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
                if (b.entity_type !== mode) continue;
                const arr = snap.board_items[b.id] || [];
                itemsForDay.push(...arr);
            }
            weekMap[day] = itemsForDay;
        }
        byWeek[snap.week] = weekMap;
        if (mode === EntityType.Shot) Object.assign(assignments, snap.assignments || {});
    }

    renderWeeks({ entity_type: mode, by_week: byWeek, assignments });

    // After weeks, render On hold and Omitted sections (shots mode only)
    if (mode === EntityType.Shot && w0) {
        renderHoldOmit(w0);
    }
}

function renderArtists(artists) {
    artistBar.innerHTML = '';
    for (const artist of artists) {
        const el = document.createElement('div');
        el.className = 'artist';
        el.draggable = true;
        el.dataset.artistId = artist.id;
        el.dataset.artistIsGroup = artist.is_group;
        el.innerHTML = `<img src="${artist.thumb_url}" alt="${artist.name}" title="${artist.name}" />`;
        el.addEventListener('dragstart', e => {
            e.dataTransfer.setData('application/artist-id', artist.id);
            e.dataTransfer.setData('application/artist-is-gropu', artist.is_group);
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
        card.dataset.entity_type = EntityType.Shot;
        card.draggable = true;
        card.addEventListener('dragstart', e => {
            e.dataTransfer.setData('application/item-id', JSON.stringify({ item_id: it.id, entity_type: EntityType.Shot}));
            e.dataTransfer.effectAllowed = 'move';
        });
        const seqBadge = it.sequence ? `<div class=\"badge\">${it.sequence}</div>` : '';
        card.innerHTML = `
            <div class=\"thumb\"><img src=\"${it.thumb_url}\" alt=\"thumb\" /></div>
            <div>
                <div class=\"title\">${it.name} ${seqBadge}</div>
                <div class=\"assignees\" data-shot-assignees=\"${it.id}\"></div>
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

function renderNoDueDateAssets(w0snap) {
    const section = document.createElement('section');
    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.alignItems = 'center';
    header.style.gap = '12px';

    // Type filter combobox (left side)
    const typeWrap = document.createElement('div');
    const label = document.createElement('label');
    label.style.fontSize = '12px';
    label.style.color = '#c7cbe0';
    label.style.marginRight = '6px';
    label.textContent = 'Type';
    const select = document.createElement('select');
    select.style.background = '#0f1330';
    select.style.color = '#e7e9ef';
    select.style.border = '1px solid #2a2f58';
    select.style.borderRadius = '6px';
    select.style.padding = '6px 8px';

    const types = Array.isArray(w0snap.asset_types) ? w0snap.asset_types : [];
    const allOpt = document.createElement('option');
    allOpt.value = 'ALL';
    allOpt.textContent = 'All types';
    select.appendChild(allOpt);
    for (const t of types) {
        const opt = document.createElement('option');
        opt.value = t;
        opt.textContent = t;
        select.appendChild(opt);
    }
    if (!assetTypeFilter || (assetTypeFilter !== 'ALL' && !types.includes(assetTypeFilter))) {
        assetTypeFilter = 'ALL';
    }
    select.value = assetTypeFilter || 'ALL';
    select.addEventListener('change', () => {
        assetTypeFilter = select.value || 'ALL';
        localStorage.setItem('wb_asset_type_filter', assetTypeFilter);
        // Reload to re-render both no-date and weeks with current filter
        loadMode(currentMode);
    });
    typeWrap.appendChild(label);
    typeWrap.appendChild(select);

    const h = document.createElement('h2');
    h.textContent = 'No due date';

    // Place filter left, then title
    header.appendChild(typeWrap);
    header.appendChild(h);

    section.appendChild(header);

    const grid = document.createElement('div');
    grid.className = 'boards';
    section.appendChild(grid);

    // Single board spanning full width
    const wrap = document.createElement('div');
    wrap.className = 'board';
    wrap.style.gridColumn = '1 / -1';
    wrap.innerHTML = `<h3>Assets</h3><div class=\"list\"></div>`;
    const list = wrap.querySelector('.list');

    list.style.display = 'grid';
    list.style.gridTemplateColumns = 'repeat(auto-fill, minmax(300px, 1fr))';
    list.style.gap = '8px';
    list.style.maxHeight = 'unset';
    list.style.overflowY = 'visible';
    list.style.alignItems = 'start';

    const items = w0snap.assets_no_due_date || [];
    const filtered = items.filter(it => assetTypeFilter === 'ALL' || (it.sequence || '') === assetTypeFilter);

    for (const it of filtered) {
        const card = document.createElement('div');
        card.className = 'card';
        card.dataset.itemId = it.id;
        card.dataset.entity_type = EntityType.Asset;
        card.draggable = true;
        card.addEventListener('dragstart', e => {
            e.dataTransfer.setData('application/item-id', JSON.stringify({ item_id: it.id, entity_type: EntityType.Asset }));
            e.dataTransfer.effectAllowed = 'move';
        });
        const typeBadge = it.sequence ? `<div class=\"badge\">${it.sequence}</div>` : '';
        card.innerHTML = `
            <div class=\"thumb\"><img src=\"${it.thumb_url}\" alt=\"thumb\" /></div>
            <div>
                <div class=\"title\">${it.name} ${typeBadge}</div>
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
            wrap.dataset.entity_type = snapshot.entity_type;
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
                // Optional: click to quickly edit text
                annSpan.addEventListener('click', async () => {
                    const curText = String((window.annotationsMap && window.annotationsMap[annKey] && window.annotationsMap[annKey].text) || '');
                    const curColor = String((window.annotationsMap && window.annotationsMap[annKey] && window.annotationsMap[annKey].color) || '#c7cbe0');
                    const newText = window.prompt('Annotation text', curText);
                    if (newText === null) return;
                    try {
                        const resp = await fetch(`/api/annotations${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ week: wk, day, text: newText, color: curColor })
                        });
                        if (resp.ok) {
                            window.annotationsMap = (await resp.json()).annotations || window.annotationsMap;
                            await loadMode(currentMode);
                        }
                    } catch {}
                });
                h3.appendChild(annSpan);
            }
            // Right-click on day header opens annotation menu
            h3.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                showDayMenu(e.clientX, e.clientY, { week: wk, day });
            });
            const list = wrap.querySelector('.list');

            const items = (snapshot.by_week[wk] || {})[day] || [];
            for (const it of items) {
                const card = document.createElement('div');
                card.className = 'card';
                card.dataset.itemId = it.id;
                card.dataset.entity_type = snapshot.entity_type;
                card.draggable = true;
                card.addEventListener('dragstart', e => {
                    e.dataTransfer.setData('application/item-id', JSON.stringify({ item_id: it.id, entity_type: snapshot.entity_type }));
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
                const holder = card.querySelector('.assignees');
                const assigned = snapshot.assignments[it.id] || [];
                for (const assignment of assigned) {
                    const artist = (window._artistsCache || []).find(x => x.id === assignment.artist_id);
                    if (!artist) continue;
                    const div = document.createElement('div');
                    div.className = 'assignee';
                    div.style.borderColor = colorForTask(assignment.task);
                    div.dataset.artistId = assignment.artist_id;
                    div.dataset.artistIsGroup = assignment.artist_is_group;
                    div.dataset.task = assignment.task;
                    div.dataset.shotId = it.id;
                    div.title = `${artist.name} — ${assignment.task} (right‑click to unassign)`;
                    div.innerHTML = `<img src="${artist.thumb_url}" alt="${artist.name}" />`;
                    div.addEventListener('contextmenu', (e) => {
                        e.preventDefault();
                        showContextMenu(e.clientX, e.clientY, {artistId: assignment.artist_id, artist_is_group: assignment.artist_is_group, shotId: it.id, task: assignment.task });
                    });
                    holder.appendChild(div);
                }
                list.appendChild(card);
            }

            // Drag and drop: allow assigning artists to shots and moving items across days/weeks
            list.addEventListener('dragover', e => {
                const types = e.dataTransfer?.types || [];
                const isArtist = types.includes('application/artist-id');
                const isItem = types.includes('application/item-id');
                if (isArtist || isItem) {
                    e.preventDefault();
                }
            });

            list.addEventListener('dragenter', e => {
                const types = e.dataTransfer?.types || [];
                const isArtist = types.includes('application/artist-id');
                const isItem = types.includes('application/item-id');
                const ok = (isArtist || isItem);
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
                        const body = {
                            item_id: data.item_id,
                            entity_type: snapshot.entity_type,
                            to_week: wk,
                            to_day: day
                        }
                        console.log(body)
                        const resp = await fetch(`/api/move_item${window.currentProjectId ? `?project_id=${encodeURIComponent(window.currentProjectId)}` : ''}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(body)
                        });
                        if (resp.ok) {
                            await loadMode(currentMode);
                            return;
                        }
                    } catch {}
                }

                // Assigning artists to shots or assets
                const artistId = e.dataTransfer.getData('application/artist-id');
                const artistIsGroup = e.dataTransfer.getData('application/artist-is-group');
                if (!artistId) return;
                // Assign onto nearest card of current entity_type under cursor (or the first card if none)
                const card = document.elementFromPoint(e.clientX, e.clientY)?.closest('.card');
                const targetCard = card && card.dataset.entity_type === snapshot.entity_type ? card : list.querySelector('.card');
                if (!targetCard) return;
                const itemId = targetCard.dataset.itemId;
                // Instead of assigning immediately, open task picker
                showTaskPicker(e.clientX, e.clientY, artistId, artistIsGroup, itemId, snapshot.entity_type);
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
                TASKS_PER_ENTITY_TYPE = {
                    shots: Array.isArray(data.shots) && data.shots.length ? data.shots : TASKS_PER_ENTITY_TYPE.shots,
                    assets: Array.isArray(data.assets) && data.assets.length ? data.assets : TASKS_PER_ENTITY_TYPE.assets,
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
            card.dataset.entity_type = EntityType.Shot;
            card.draggable = true;
            card.addEventListener('dragstart', e => {
                e.dataTransfer.setData('application/item-id', JSON.stringify({ item_id: it.id, entity_type: EntityType.Shot }));
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
