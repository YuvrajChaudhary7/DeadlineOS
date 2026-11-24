const deadlineUser = signedInUser();
let deadlineRows = [];
let deadlineFilter = 'all';
let deadlinePage = 1;
const deadlineForm = document.querySelector('#deadline-form');
const searchInput = document.querySelector('#deadline-search');
const courseFilter = document.querySelector('#course-filter');
const sortSelect = document.querySelector('#deadline-sort');

deadlineForm?.elements.allow_resubmissions.addEventListener('change', event => {
  const attempts = deadlineForm.elements.max_attempts;
  if (event.currentTarget.checked && Number(attempts.value) < 2) attempts.value = '2';
  if (!event.currentTarget.checked) attempts.value = '1';
});

function localDateTime(value) {
  const date = new Date(value);
  const pad = part => String(part).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

if (deadlineUser?.role === 'staff') {
  document.querySelector('[data-filter="closed"]')?.classList.remove('hidden');
  deadlineForm?.classList.remove('hidden');
  api('/courses').then(courses => {
    const select = document.querySelector('#course-select');
    select.replaceChildren(...courses.map(course => {
      const option = document.createElement('option');
      option.value = course.id;
      option.textContent = `${course.code} · ${course.name}`;
      return option;
    }));
    if (!courses.length) select.innerHTML = '<option value="">Create a course first</option>';
  }).catch(error => showMessage(error.message));
}

deadlineForm?.addEventListener('submit', async event => {
  event.preventDefault();
  const formElement = event.currentTarget;
  const data = Object.fromEntries(new FormData(formElement));
  data.course_id = Number(data.course_id);
  data.max_marks = Number(data.max_marks);
  data.due_at = new Date(data.due_at).toISOString();
  data.allow_resubmissions = formElement.elements.allow_resubmissions.checked;
  data.max_attempts = data.allow_resubmissions ? Number(data.max_attempts) : 1;
  try {
    await api('/deadlines', { method: 'POST', body: JSON.stringify(data) });
    formElement.reset();
    showMessage('Assignment published to enrolled students.', 'success');
    await loadDeadlines();
  } catch (error) {
    showMessage(error.message);
  }
});

async function loadDeadlines() {
  try {
    const params = new URLSearchParams({ page: String(deadlinePage), per_page: '25' });
    if (deadlineUser?.role === 'staff' && deadlineFilter === 'closed') params.set('include_closed', 'true');
    deadlineRows = await api(`/deadlines?${params}`);
    populateCourseFilter();
    renderDeadlines();
  } catch (error) {
    showMessage(error.message);
  }
}

function populateCourseFilter() {
  const selected = courseFilter.value;
  const courses = [...new Map(deadlineRows.map(row => [row.course_id, row.course_code])).entries()]
    .sort((a, b) => a[1].localeCompare(b[1]));
  courseFilter.replaceChildren(new Option('All courses', 'all'));
  courses.forEach(([id, code]) => courseFilter.add(new Option(code, String(id))));
  courseFilter.value = courses.some(([id]) => String(id) === selected) ? selected : 'all';
}

function renderDeadlines() {
  const host = document.querySelector('#deadline-list');
  const now = Date.now();
  const query = searchInput.value.trim().toLocaleLowerCase();
  let rows = deadlineRows.filter(deadline => {
    const due = new Date(deadline.due_at).getTime();
    const matchesTime = deadlineFilter === 'closed' ? !deadline.is_active : deadline.is_active && (deadlineFilter === 'all' || (deadlineFilter === 'upcoming' ? due >= now : due < now));
    const matchesCourse = courseFilter.value === 'all' || String(deadline.course_id) === courseFilter.value;
    const searchable = `${deadline.title} ${deadline.course_code} ${deadline.description || ''}`.toLocaleLowerCase();
    return matchesTime && matchesCourse && (!query || searchable.includes(query));
  });

  if (sortSelect.value === 'title') rows.sort((a, b) => a.title.localeCompare(b.title));
  else rows.sort((a, b) => {
    const difference = new Date(a.due_at) - new Date(b.due_at);
    return sortSelect.value === 'latest' ? -difference : difference;
  });

  document.querySelector('#deadline-count').textContent = `${rows.length} ${rows.length === 1 ? 'assignment' : 'assignments'} shown`;
  renderPagination(host, deadlineRows, page => { deadlinePage = page; loadDeadlines(); });
  if (!rows.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    const icon = document.createElement('span'); icon.textContent = '⌕';
    const title = document.createElement('h3'); title.textContent = deadlineRows.length ? 'No matching assignments' : 'Your board is clear';
    const description = document.createElement('p');
    description.textContent = deadlineRows.length ? 'Try another search or clear the filters.' : 'There are no assignments in this view right now.';
    empty.append(icon, title, description);
    if (deadlineRows.length) {
      const clear = document.createElement('button'); clear.className = 'button button-small'; clear.textContent = 'Clear filters';
      clear.addEventListener('click', clearDeadlineFilters);
      empty.append(clear);
    }
    host.replaceChildren(empty);
    return;
  }

  host.replaceChildren(...rows.map(deadline => {
    const card = document.createElement('article');
    card.className = 'deadline-card';
    const course = document.createElement('span'); course.className = 'course-code'; course.textContent = deadline.course_code || 'COURSE';
    const state = document.createElement('span');
    const dueTime = new Date(deadline.due_at).getTime();
    state.className = `status ${!deadline.is_active ? 'status-late' : deadline.submission_status === 'graded' ? 'status-done' : deadline.submission_status ? 'status-submitted' : dueTime < Date.now() ? 'status-late' : 'status-open'}`;
    state.textContent = !deadline.is_active ? 'Closed' : deadline.submission_status === 'graded' ? 'Graded' : deadline.submission_status ? 'Submitted' : dueTime < Date.now() ? 'Past due' : 'To do';
    const head = document.createElement('div'); head.className = 'card-topline'; head.append(course, state);
    const title = document.createElement('h3'); title.textContent = deadline.title;
    const description = document.createElement('p'); description.textContent = deadline.description || 'No additional instructions were provided.';
    const meta = document.createElement('div'); meta.className = 'deadline-meta';
    meta.textContent = `${new Date(deadline.due_at).toLocaleString()} · ${deadline.max_marks} marks`;
    card.append(head, title, description, meta);

    if (deadlineUser?.role === 'student') {
      if (deadline.submission_status) {
        const status = document.createElement('p'); status.className = 'inline-note';
        status.textContent = deadline.marks_obtained == null ? `Attempt ${deadline.submission_attempt_count} of ${deadline.max_attempts}. Your work is submitted; view feedback in Submissions.` : `Score: ${deadline.marks_obtained} / ${deadline.max_marks}`;
        card.append(status);
      }
      if (!deadline.submission_status || (deadline.allow_resubmissions && deadline.submission_attempt_count < deadline.max_attempts)) {
        const form = document.createElement('form'); form.className = 'submit-form';
        if (deadline.submission_status) { const heading = document.createElement('strong'); heading.textContent = `Submit attempt ${deadline.submission_attempt_count + 1} of ${deadline.max_attempts}`; form.append(heading); }
        const note = document.createElement('textarea'); note.name = 'note'; note.placeholder = 'Add a note for your instructor (optional)'; note.maxLength = 4000;
        const fileLabel = document.createElement('label'); fileLabel.className = 'file-pick';
        fileLabel.textContent = 'Attach work · PDF, DOCX, ZIP or code · max 16 MB';
        const file = document.createElement('input'); file.type = 'file'; file.name = 'file';
        file.accept = '.pdf,.docx,.txt,.zip,.py,.java,.cpp,.c,.js,.md';
        fileLabel.append(file);
        const button = document.createElement('button'); button.className = 'button button-small'; button.textContent = 'Submit assignment';
        form.append(note, fileLabel, button);
        form.onsubmit = async event => {
          event.preventDefault();
          const payload = new FormData(); payload.append('deadline_id', deadline.id); payload.append('note', note.value);
          if (file.files[0]) payload.append('file', file.files[0]);
          button.disabled = true; button.textContent = 'Submitting…';
          try {
            await api('/submissions', { method: 'POST', body: payload });
            showMessage('Assignment submitted. Track it in Submissions.', 'success');
            await loadDeadlines();
          } catch (error) {
            showMessage(error.message); button.disabled = false; button.textContent = 'Submit assignment';
          }
        };
        card.append(form);
      }
    }
    if (deadlineUser?.role === 'staff') {
      const edit = document.createElement('details'); edit.className = 'deadline-edit';
      const summary = document.createElement('summary'); summary.textContent = 'Edit assignment';
      const form = document.createElement('form'); form.className = 'deadline-edit-form';
      const fields = [
        ['Title', 'title', 'text', deadline.title],
        ['Due date and time', 'due_at', 'datetime-local', localDateTime(deadline.due_at)],
        ['Maximum marks', 'max_marks', 'number', deadline.max_marks]
      ];
      for (const [labelText, name, type, value] of fields) {
        const label = document.createElement('label'); label.textContent = labelText;
        const input = document.createElement('input'); input.name = name; input.type = type; input.value = value; input.required = true;
        if (name === 'title') input.maxLength = 160;
        if (name === 'max_marks') input.min = '1';
        label.append(input); form.append(label);
      }
      const descLabel = document.createElement('label'); descLabel.textContent = 'Instructions';
      const desc = document.createElement('textarea'); desc.name = 'description'; desc.maxLength = 4000; desc.value = deadline.description || ''; descLabel.append(desc); form.append(descLabel);
      const resubmitLabel = document.createElement('label'); resubmitLabel.className = 'resubmission-toggle';
      const resubmit = document.createElement('input'); resubmit.type = 'checkbox'; resubmit.name = 'allow_resubmissions'; resubmit.checked = deadline.allow_resubmissions;
      resubmitLabel.append(resubmit, document.createTextNode('Allow resubmissions')); form.append(resubmitLabel);
      const attemptsLabel = document.createElement('label'); attemptsLabel.textContent = 'Maximum attempts';
      const attempts = document.createElement('select'); attempts.name = 'max_attempts';
      [1, 2, 3, 5, 10].forEach(value => attempts.add(new Option(`${value} attempts`, String(value)))); attempts.value = String(deadline.max_attempts);
      resubmit.addEventListener('change', () => { if (resubmit.checked && Number(attempts.value) < 2) attempts.value = '2'; if (!resubmit.checked) attempts.value = '1'; });
      attemptsLabel.append(attempts); form.append(attemptsLabel);
      const save = document.createElement('button'); save.className = 'button button-small'; save.textContent = 'Save changes'; form.append(save);
      form.onsubmit = async event => {
        event.preventDefault(); const values = Object.fromEntries(new FormData(form));
        values.max_marks = Number(values.max_marks); values.max_attempts = resubmit.checked ? Number(values.max_attempts) : 1;
        values.allow_resubmissions = resubmit.checked; values.due_at = new Date(values.due_at).toISOString();
        save.disabled = true;
        try { await api(`/deadlines/${deadline.id}`, { method: 'PATCH', body: JSON.stringify(values) }); showMessage('Assignment updated.', 'success'); await loadDeadlines(); }
        catch (error) { showMessage(error.message); save.disabled = false; }
      };
      edit.append(summary, form); card.append(edit);
      const close = document.createElement('button'); close.className = 'button button-quiet button-small'; close.textContent = deadline.is_active ? 'Close assignment' : 'Reopen assignment';
      close.onclick = async () => { if (deadline.is_active && !confirm(`Close “${deadline.title}”? Students will no longer see or submit to it.`)) return; close.disabled = true; try { await api(`/deadlines/${deadline.id}`, { method: 'PATCH', body: JSON.stringify({ is_active: !deadline.is_active }) }); showMessage(deadline.is_active ? 'Assignment closed.' : 'Assignment reopened.', 'success'); await loadDeadlines(); } catch (error) { showMessage(error.message); close.disabled = false; } };
      card.append(close);
    }
    return card;
  }));
}

function clearDeadlineFilters() {
  searchInput.value = '';
  courseFilter.value = 'all';
  sortSelect.value = 'soonest';
  deadlineFilter = 'all';
  document.querySelectorAll('.filter').forEach(button => {
    const active = button.dataset.filter === 'all';
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  renderDeadlines();
}

document.querySelectorAll('.filter').forEach(button => button.addEventListener('click', () => {
  deadlineFilter = button.dataset.filter;
  if (deadlineUser?.role === 'staff') loadDeadlines();
  document.querySelectorAll('.filter').forEach(filter => {
    const active = filter === button;
    filter.classList.toggle('active', active);
    filter.setAttribute('aria-pressed', String(active));
  });
  renderDeadlines();
}));
searchInput.addEventListener('input', renderDeadlines);
courseFilter.addEventListener('change', renderDeadlines);
sortSelect.addEventListener('change', renderDeadlines);
document.querySelector('#clear-deadline-filters').addEventListener('click', clearDeadlineFilters);
loadDeadlines();
