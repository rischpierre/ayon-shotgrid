const withProject = (url, projectId) => {
    const sep = url.includes('?') ? '&' : '?';
    return projectId ? `${url}${sep}project_id=${encodeURIComponent(projectId)}` : url;
};

async function http(method, url, body) {
    const resp = await fetch(url, {
        method,
        headers: body ? {'Content-Type': 'application/json'} : undefined,
        body: body ? JSON.stringify(body) : undefined,
    });
    if (!resp.ok) {
        const text = await resp.text().catch(() => '');
        throw new Error(`${method} ${url} failed: ${resp.status} ${text}`);
    }
    const ct = resp.headers.get('content-type') || '';
    if (ct.includes('application/json')) return resp.json();
    return resp.text();
}

export async function listProjects() {
    return http('GET', '/api/projects');
}

export async function getTasks(projectId) {
    return http('GET', withProject('/api/tasks', projectId));
}

export async function getWeek(week, projectId) {
    return http('GET', withProject(`/api/week/${encodeURIComponent(week)}`, projectId));
}

export async function moveItem(payload, projectId) {
    return http('POST', withProject('/api/move_item', projectId), payload);
}

export async function assign(payload, projectId) {
    return http('POST', withProject('/api/assign', projectId), payload);
}

export async function unassign(payload, projectId) {
    return http('POST', withProject('/api/unassign', projectId), payload);
}

export async function publishChanges(payload, projectId) {
    return http('POST', withProject('/api/publish', projectId), payload);
}

export async function getChanges(projectId) {
    return http('GET', withProject('/api/changes', projectId));
}

export async function setAnnotations(payload, projectId) {
    return http('POST', withProject('/api/annotations', projectId), payload);
}

export async function removeDueDate(payload, projectId) {
    return http('POST', withProject('/api/remove_due_date', projectId), payload);
}
