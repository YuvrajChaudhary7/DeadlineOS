const taskUser = signedInUser();
let taskRows = [];
let taskFilter = 'all';
let taskPage = 1;
let taskProjects = [];
const taskProjectFilter = new URLSearchParams(location.search).get('project');
const taskForm = document.querySelector('#task-form');
const quickForm = document.querySelector('#quick-capture-form');
const quickInput = document.querySelector('#quick-capture-input');
const quickHint = document.querySelector('#quick-capture-hint');

if (taskUser?.role !== 'student') {
  showMessage('Personal task lists are available for student accounts.');
  taskForm?.classList.add('hidden');
  quickForm?.classList.add('hidden');
}

async function loadProjects() {
  if (taskUser?.role !== 'student') return;
  try {
    taskProjects = await api('/projects');
    const select = document.querySelector('#task-project');
    select.replaceChildren(new Option('No project', ''));
    const quickSelect = document.querySelector('#quick-project');
    quickSelect.replaceChildren(new Option('No project', ''));
    taskProjects.forEach(project => { select.add(new Option(project.name, String(project.id))); quickSelect.add(new Option(project.name, String(project.id))); });
    if (taskProjectFilter && taskProjects.some(project => String(project.id) === taskProjectFilter)) select.value = taskProjectFilter;
  } catch (error) { showMessage(error.message); }
}

async function createTask(data) {
  try {
    await api('/personal-tasks', { method: 'POST', body: JSON.stringify(data) });
    taskForm.reset();
    showMessage('Task added to your list.', 'success');
    await Promise.all([loadTasks(), loadTaskStats()]);
  } catch (error) { showMessage(error.message); }
}

taskForm?.addEventListener('submit', async event => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(taskForm));
  data.due_at = new Date(data.due_at).toISOString();
  data.project_id = data.project_id ? Number(data.project_id) : null;
  await createTask(data);
});

function parseQuickCapture(raw) {
  let text = raw.trim();
  const priorityMatch = text.match(/#(low|medium|high)\b|\b(low|medium|high)\s+priority\b/i);
  const priority = (priorityMatch?.[1] || priorityMatch?.[2] || 'medium').toLowerCase();
  if (priorityMatch) text = text.replace(priorityMatch[0], ' ');

  const due = new Date();
  let hasDate = false;
  const isoMatch = text.match(/\b(20\d{2})-(\d{2})-(\d{2})\b/);
  const relativeMatch = text.match(/\bin\s+(\d{1,3})\s+days?\b/i);
  const weekdayNames = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
  const weekdayMatch = text.match(/\b(?:next\s+)?(sunday|monday|tuesday|wednesday|thursday|friday|saturday)\b/i);
  if (isoMatch) {
    due.setFullYear(Number(isoMatch[1]), Number(isoMatch[2]) - 1, Number(isoMatch[3]));
    if (due.getFullYear() !== Number(isoMatch[1]) || due.getMonth() !== Number(isoMatch[2]) - 1 || due.getDate() !== Number(isoMatch[3])) throw new Error('That calendar date is not valid.');
    hasDate = true; text = text.replace(isoMatch[0], ' ');
  } else if (relativeMatch) {
    due.setDate(due.getDate() + Number(relativeMatch[1])); hasDate = true; text = text.replace(relativeMatch[0], ' ');
  } else if (/\btomorrow\b/i.test(text)) {
    due.setDate(due.getDate() + 1); hasDate = true; text = text.replace(/\btomorrow\b/i, ' ');
  } else if (/\btoday\b/i.test(text)) {
    hasDate = true; text = text.replace(/\btoday\b/i, ' ');
  } else if (weekdayMatch) {
    const target = weekdayNames.indexOf(weekdayMatch[1].toLowerCase());
    let offset = (target - due.getDay() + 7) % 7;
    if (offset === 0 || /^next\s/i.test(weekdayMatch[0])) offset = offset || 7;
    due.setDate(due.getDate() + offset); hasDate = true; text = text.replace(weekdayMatch[0], ' ');
  }

  const timeMatch = text.match(/\b(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/i)
    || text.match(/\b(?:at\s*)?([01]?\d|2[0-3]):([0-5]\d)\b/i);
  if (timeMatch) {
    let hour = Number(timeMatch[1]); const minute = Number(timeMatch[2] || 0);
    if (timeMatch[3]) { const suffix = timeMatch[3].toLowerCase(); hour = hour % 12 + (suffix === 'pm' ? 12 : 0); }
    due.setHours(hour, minute, 0, 0); text = text.replace(timeMatch[0], ' ');
  } else {
    due.setHours(17, 0, 0, 0);
    if (!hasDate) due.setDate(due.getDate() + 1);
  }

  const title = text.replace(/\b(?:at|by)\b/gi, ' ').replace(/\s+/g, ' ').trim();
  if (!title || title.length > 160) throw new Error('Enter a task title of 1–160 characters.');
  return { title, due_at: due.toISOString(), priority, recurrence: 'none', description: '' };
}

quickForm?.addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const data = parseQuickCapture(quickInput.value);
    data.project_id = document.querySelector('#quick-project').value ? Number(document.querySelector('#quick-project').value) : null;
    await api('/personal-tasks', { method: 'POST', body: JSON.stringify(data) });
    quickInput.value = '';
    quickHint.textContent = `Added “${data.title}” for ${new Date(data.due_at).toLocaleString()} · ${data.priority} priority.`;
    quickHint.classList.remove('quick-capture-error');
    showMessage('Quick task captured.', 'success');
    await Promise.all([loadTasks(), loadTaskStats()]);
  } catch (error) {
    quickHint.textContent = error.message;
    quickHint.classList.add('quick-capture-error');
  }
});

async function loadTasks() {
  if (taskUser?.role !== 'student') return;
  try {
    const archived = taskFilter === 'archive';
    taskRows = await api(`/personal-tasks?archived=${archived}&page=${taskPage}&per_page=25`);
    renderTasks();
  } catch (error) { showMessage(error.message); }
}

async function loadTaskStats() {
  try {
    const data = await api('/dashboard');
    document.querySelector('#task-streak').textContent = data.streak.current;
    document.querySelector('#task-best-streak').textContent = data.streak.best;
    document.querySelector('#task-open-count').textContent = data.summary.open;
  } catch (error) { showMessage(error.message); }
}

function renderTasks() {
  const host = document.querySelector('#task-list');
  const rows = taskRows.filter(task => (taskFilter === 'archive' || taskFilter === 'all' || (taskFilter === 'todo' ? !task.is_complete : task.is_complete))
    && (!taskProjectFilter || String(task.project_id) === taskProjectFilter));
  renderPagination(host, taskRows, page => { taskPage = page; loadTasks(); });
  document.querySelector('#task-section-title').textContent = taskFilter === 'archive' ? 'Archived history' : taskFilter === 'complete' ? 'Completed tasks' : 'My checklist';
  if (!rows.length) {
    const empty = document.createElement('div'); empty.className = 'empty-state';
    const title = document.createElement('h3'); title.textContent = taskFilter === 'archive' ? 'No archived items' : taskFilter === 'complete' ? 'Nothing completed yet' : 'Your list is clear';
    const description = document.createElement('p'); description.textContent = taskFilter === 'archive' ? 'Archive finished work to keep a history here.' : 'Add a project or personal deadline above to make a plan.';
    empty.append(title, description); host.replaceChildren(empty); return;
  }
  host.replaceChildren(...rows.map(task => {
    const card = document.createElement('article'); card.className = `task-card ${task.is_complete ? 'task-complete' : ''}`;
    const head = document.createElement('div'); head.className = 'card-topline';
    const priority = document.createElement('span'); priority.className = `priority priority-${task.priority}`;
    priority.textContent = `${task.priority} priority${task.recurrence !== 'none' ? ` · ${task.recurrence}` : ''}`;
    const due = document.createElement('span');
    due.className = `status ${!task.is_complete && new Date(task.due_at) < new Date() ? 'status-late' : task.is_complete ? 'status-done' : 'status-open'}`;
    due.textContent = task.is_complete ? 'Complete' : new Date(task.due_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    head.append(priority, due);
    const title = document.createElement('h3'); title.textContent = task.title; if (task.is_complete) title.classList.add('strikethrough');
    const desc = document.createElement('p'); desc.textContent = task.description || 'Personal project deadline';
    const project = taskProjects.find(item => item.id === task.project_id);
    const meta = document.createElement('div'); meta.className = 'deadline-meta';
    meta.textContent = `Due ${new Date(task.due_at).toLocaleString()}${project ? ` · ${project.name}` : ''}`;
    const risk = document.createElement('div'); risk.className = `risk-chip risk-${task.risk?.label?.replace(' ', '-') || 'on-track'}`;
    risk.textContent = `Risk ${task.risk?.score ?? 0}/100 · ${task.risk?.label || 'on track'}`;
    const riskReasons = document.createElement('small'); riskReasons.className = 'risk-reasons';
    riskReasons.textContent = task.risk?.reasons?.join(' · ') || 'No immediate risk factors';

    const subtasks = document.createElement('div'); subtasks.className = 'subtask-list';
    for (const sub of task.subtasks || []) {
      const label = document.createElement('label'); label.className = 'subtask-row';
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = sub.is_complete;
      checkbox.onchange = async () => { try { await api(`/personal-tasks/${task.id}/subtasks/${sub.id}`, { method: 'PATCH', body: JSON.stringify({ is_complete: checkbox.checked }) }); await loadTasks(); } catch (error) { showMessage(error.message); } };
      const text = document.createElement('span'); text.textContent = sub.title; if (sub.is_complete) text.className = 'strikethrough';
      label.append(checkbox, text); subtasks.append(label);
    }
    const subtaskForm = document.createElement('form'); subtaskForm.className = 'subtask-add';
    const subtaskInput = document.createElement('input'); subtaskInput.placeholder = 'Add a step'; subtaskInput.maxLength = 160; subtaskInput.required = true;
    const subtaskButton = document.createElement('button'); subtaskButton.className = 'button button-small'; subtaskButton.textContent = 'Add step';
    subtaskForm.append(subtaskInput, subtaskButton);
    subtaskForm.onsubmit = async event => { event.preventDefault(); subtaskButton.disabled = true; try { await api(`/personal-tasks/${task.id}/subtasks`, { method: 'POST', body: JSON.stringify({ title: subtaskInput.value }) }); await loadTasks(); } catch (error) { showMessage(error.message); subtaskButton.disabled = false; } };

    const actions = document.createElement('div'); actions.className = 'task-actions';
    if (!task.is_archived) {
      const toggle = document.createElement('button'); toggle.className = 'button button-small'; toggle.textContent = task.is_complete ? 'Mark to do' : 'Mark complete';
      toggle.onclick = async () => { toggle.disabled = true; try { const result = await api(`/personal-tasks/${task.id}`, { method: 'PATCH', body: JSON.stringify({ is_complete: !task.is_complete }) }); if (result.next_task_id) showMessage('Completed. The next recurring task has been added.', 'success'); await Promise.all([loadTasks(), loadTaskStats()]); } catch (error) { showMessage(error.message); toggle.disabled = false; } };
      actions.append(toggle);
    }
    const archive = document.createElement('button'); archive.className = 'button button-quiet button-small'; archive.textContent = task.is_archived ? 'Restore' : 'Archive';
    archive.onclick = async () => { try { await api(`/personal-tasks/${task.id}`, { method: 'PATCH', body: JSON.stringify({ is_archived: !task.is_archived }) }); showMessage(task.is_archived ? 'Task restored.' : 'Task moved to archive.', 'success'); await loadTasks(); } catch (error) { showMessage(error.message); } };
    actions.append(archive);
    const remove = document.createElement('button'); remove.className = 'button button-quiet button-small'; remove.textContent = 'Delete';
    remove.onclick = async () => { if (!confirm(`Permanently delete “${task.title}”?`)) return; try { await api(`/personal-tasks/${task.id}`, { method: 'DELETE' }); showMessage('Task deleted.', 'success'); await Promise.all([loadTasks(), loadTaskStats()]); } catch (error) { showMessage(error.message); } };
    actions.append(remove);
    card.append(head, title, desc, meta, risk, riskReasons);
    if (!task.is_archived) card.append(subtasks, subtaskForm);
    card.append(actions);
    return card;
  }));
}

document.querySelectorAll('.filter').forEach(button => button.addEventListener('click', async () => {
  taskFilter = button.dataset.filter;
  taskPage = 1;
  document.querySelectorAll('.filter').forEach(filter => { const active = filter === button; filter.classList.toggle('active', active); filter.setAttribute('aria-pressed', String(active)); });
  await loadTasks();
}));

loadProjects().then(() => Promise.all([loadTasks(), loadTaskStats()]));
