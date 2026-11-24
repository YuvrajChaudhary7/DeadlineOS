let projectView = 'active';
let projectPage = 1;
const projectUser = signedInUser();

if (projectUser?.role !== 'student') {
  document.querySelector('#project-form').classList.add('hidden');
  showMessage('Project workspaces are available for student accounts.');
}

async function loadProjects() {
  if (projectUser?.role !== 'student') return;
  const host = document.querySelector('#project-list');
  try {
    const [projects, deadlines] = await Promise.all([api(`/projects?archived=${projectView === 'archive'}&page=${projectPage}&per_page=25`), api('/deadlines')]);
    renderPagination(host, projects, page => { projectPage = page; loadProjects(); });
    if (!projects.length) {
      const empty = document.createElement('div'); empty.className = 'empty-state';
      const heading = document.createElement('h3'); heading.textContent = projectView === 'archive' ? 'No archived projects' : 'No project workspaces yet';
      const description = document.createElement('p'); description.textContent = projectView === 'archive' ? 'Archived workspaces stay here until you restore them.' : 'Create a workspace, then add tasks, files and course deadlines.';
      empty.append(heading, description);
      host.replaceChildren(empty); return;
    }
    host.replaceChildren(...projects.map(project => renderProject(project, deadlines)));
  } catch (error) { showMessage(error.message); }
}

function renderProject(project, deadlines) {
  const card = document.createElement('article'); card.className = 'project-card';
  card.style.setProperty('--project-color', project.color);
  const header = document.createElement('div'); header.className = 'project-header';
  const titleWrap = document.createElement('div');
  const title = document.createElement('h2'); title.textContent = project.name;
  const description = document.createElement('p'); description.textContent = project.description || 'No description provided.';
  titleWrap.append(title, description);
  const count = document.createElement('span'); count.className = 'soft-badge'; count.textContent = `${project.completed_count}/${project.task_count} tasks done`;
  header.append(titleWrap, count);

  const linkForm = document.createElement('form'); linkForm.className = 'project-deadline-link';
  const select = document.createElement('select'); select.setAttribute('aria-label', `Choose a course deadline for ${project.name}`);
  const linkedIds = new Set(project.deadlines.map(item => item.id));
  select.add(new Option(linkedIds.size === deadlines.length ? 'No unlinked course deadlines' : 'Link a course deadline', ''));
  deadlines.filter(item => !linkedIds.has(item.id)).forEach(item => select.add(new Option(`${item.course_code} · ${item.title}`, String(item.id))));
  const linkButton = document.createElement('button'); linkButton.className = 'button button-small'; linkButton.textContent = 'Link deadline'; linkButton.disabled = projectView === 'archive' || select.options.length < 2;
  linkForm.append(select, linkButton);
  linkForm.onsubmit = async event => { event.preventDefault(); if (!select.value) return; linkButton.disabled = true; try { await api(`/projects/${project.id}/deadlines/${select.value}`, { method: 'POST' }); showMessage('Course deadline linked to project.', 'success'); await loadProjects(); } catch (error) { showMessage(error.message); linkButton.disabled = false; } };

  const linked = document.createElement('div'); linked.className = 'project-linked-deadlines';
  project.deadlines.forEach(item => {
    const row = document.createElement('div'); row.className = 'project-linked-row';
    const label = document.createElement('span'); label.textContent = `Course deadline · ${item.title}`;
    const unlink = document.createElement('button'); unlink.type = 'button'; unlink.className = 'text-button'; unlink.textContent = 'Unlink';
    unlink.onclick = async () => { try { await api(`/projects/${project.id}/deadlines/${item.id}`, { method: 'DELETE' }); await loadProjects(); } catch (error) { showMessage(error.message); } };
    row.append(label, unlink); linked.append(row);
  });

  const filesTitle = document.createElement('h3'); filesTitle.textContent = 'Reference files';
  const files = document.createElement('div'); files.className = 'project-files';
  if (!project.files.length) { const note = document.createElement('p'); note.className = 'admin-hint'; note.textContent = 'No files added.'; files.append(note); }
  project.files.forEach(file => {
    const row = document.createElement('div'); row.className = 'project-file-row';
    const button = document.createElement('button'); button.type = 'button'; button.className = 'text-button'; button.textContent = `↓ ${file.file_name}`;
    button.onclick = async () => { try { const blob = await api(`/projects/${project.id}/files/${file.id}`); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = file.file_name; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); } catch (error) { showMessage(error.message); } };
    row.append(button);
    if (projectView !== 'archive') {
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'text-button'; remove.textContent = 'Delete';
      remove.setAttribute('aria-label', `Delete ${file.file_name}`);
      remove.onclick = async () => { if (!confirm(`Delete “${file.file_name}” from this project?`)) return; try { await api(`/projects/${project.id}/files/${file.id}`, { method: 'DELETE' }); showMessage('Project file deleted.', 'success'); await loadProjects(); } catch (error) { showMessage(error.message); } };
      row.append(remove);
    }
    files.append(row);
  });
  const fileForm = document.createElement('form'); fileForm.className = 'project-upload';
  const fileInput = document.createElement('input'); fileInput.type = 'file'; fileInput.required = true; fileInput.accept = '.pdf,.docx,.txt,.zip,.py,.java,.cpp,.c,.js,.md,.png,.jpg,.jpeg,.csv,.xlsx'; fileInput.setAttribute('aria-label', 'Choose a project reference file');
  const upload = document.createElement('button'); upload.className = 'button button-small'; upload.textContent = 'Upload file'; upload.disabled = projectView === 'archive';
  fileForm.append(fileInput, upload);
  fileForm.onsubmit = async event => { event.preventDefault(); const body = new FormData(); body.append('file', fileInput.files[0]); upload.disabled = true; try { await api(`/projects/${project.id}/files`, { method: 'POST', body }); showMessage('File added to project workspace.', 'success'); await loadProjects(); } catch (error) { showMessage(error.message); upload.disabled = false; } };

  const archive = document.createElement('button'); archive.className = 'button button-quiet button-small'; archive.textContent = projectView === 'archive' ? 'Restore project' : 'Archive project';
  archive.onclick = async () => { if (projectView !== 'archive' && !confirm(`Archive “${project.name}”? Tasks remain in your task history.`)) return; try { await api(`/projects/${project.id}`, { method: 'PATCH', body: JSON.stringify({ is_archived: projectView === 'active' }) }); await loadProjects(); } catch (error) { showMessage(error.message); } };
  const taskLink = document.createElement('a'); taskLink.className = 'button button-small'; taskLink.href = `tasks.html?project=${project.id}`; taskLink.textContent = 'View tasks';
  const actions = document.createElement('div'); actions.className = 'task-actions'; actions.append(taskLink, archive);
  card.append(header, linkForm, linked, filesTitle, files, fileForm, actions);
  return card;
}

document.querySelector('#project-form').addEventListener('submit', async event => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget));
  try { await api('/projects', { method: 'POST', body: JSON.stringify(data) }); event.currentTarget.reset(); showMessage('Project workspace created.', 'success'); await loadProjects(); }
  catch (error) { showMessage(error.message); }
});
document.querySelectorAll('[data-project-view]').forEach(button => button.addEventListener('click', async () => {
  projectView = button.dataset.projectView;
  projectPage = 1;
  document.querySelector('#project-heading').textContent = projectView === 'archive' ? 'Archived projects' : 'Active projects';
  document.querySelectorAll('[data-project-view]').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
  document.querySelector('#project-form').classList.toggle('hidden', projectView === 'archive');
  await loadProjects();
}));
loadProjects();
