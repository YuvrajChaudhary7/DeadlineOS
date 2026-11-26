const submissionUser = signedInUser();
let submissionPage = 1;
let auditPage = 1;

const exportButton = document.querySelector('#export-submissions');
if (exportButton && submissionUser?.role === 'staff') {
  exportButton.classList.remove('hidden');
  exportButton.addEventListener('click', async () => { exportButton.disabled = true; try { await downloadFile('/exports/submissions.csv', 'deadlineos-submissions.csv'); } catch (error) { showMessage(error.message); } finally { exportButton.disabled = false; } });
}

async function downloadFile(path, name) {
  const blob = await api(path); const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function showAttempts(row, card) {
  if (!row.attempt_count || row.attempt_count < 2) return;
  const details = document.createElement('details'); details.className = 'attempt-history';
  const summary = document.createElement('summary'); summary.textContent = `Submission history · ${row.attempt_count} attempts`;
  const list = document.createElement('div'); list.className = 'attempt-list'; list.textContent = 'Loading attempt history…';
  details.append(summary, list); card.append(details);
  try {
    const attempts = await api(`/submissions/${row.id}/attempts`);
    list.replaceChildren(...attempts.map(attempt => {
      const item = document.createElement('div'); item.className = 'attempt-row';
      const label = document.createElement('strong'); label.textContent = `Attempt ${attempt.attempt_number} · ${attempt.status}`;
      const time = document.createElement('time'); time.textContent = new Date(attempt.submitted_at).toLocaleString();
      item.append(label, time);
      if (attempt.file_name) {
        const file = document.createElement('button'); file.type = 'button'; file.className = 'text-button'; file.textContent = `↓ ${attempt.file_name}`;
        file.onclick = async () => { try { await downloadFile(`/submissions/${row.id}/attempts/${attempt.attempt_number}/file`, attempt.file_name); } catch (error) { showMessage(error.message); } };
        item.append(file);
      }
      return item;
    }));
  } catch (error) { list.textContent = error.message; }
}

async function loadSubmissions() {
  const host = document.querySelector('#submission-list');
  try {
    const rows = await api(`/submissions?page=${submissionPage}&per_page=25`);
    renderPagination(host, rows, page => { submissionPage = page; loadSubmissions(); });
    if (!rows.length) { host.innerHTML = '<div class="empty-state"><span>✦</span><h3>No submissions yet</h3><p>Submitted work and instructor feedback will show up here.</p><a class="button button-small" href="deadlines.html">View deadlines</a></div>'; return; }
    const cards = rows.map(row => {
      const card = document.createElement('article'); card.className = 'submission-card';
      const head = document.createElement('div'); head.className = 'card-topline';
      const title = document.createElement('div'); const course = document.createElement('span'); course.className = 'course-code'; course.textContent = row.course_code;
      const name = document.createElement('h3'); name.textContent = row.deadline_title; title.append(course, name);
      const badge = document.createElement('span'); badge.className = `status ${row.status === 'graded' ? 'status-done' : row.status === 'late' ? 'status-late' : 'status-submitted'}`; badge.textContent = row.status;
      head.append(title, badge); card.append(head);
      const details = document.createElement('p'); details.className = 'submission-detail';
      details.textContent = `${submissionUser?.role === 'staff' ? `From ${row.student_name} · ` : ''}Attempt ${row.attempt_count} · Submitted ${new Date(row.submitted_at).toLocaleString()}`;
      card.append(details);
      if (row.note) { const note = document.createElement('p'); note.className = 'submission-note'; note.textContent = row.note; card.append(note); }
      if (row.file_name) {
        const file = document.createElement('button'); file.className = 'text-button'; file.textContent = `↓ ${row.file_name}`;
        file.onclick = async () => { try { await downloadFile(`/submissions/${row.id}/file`, row.file_name); } catch (error) { showMessage(error.message); } };
        card.append(file);
      }
      if (row.status === 'graded') {
        const score = document.createElement('div'); score.className = 'grade-result';
        const points = document.createElement('strong'); points.textContent = `${row.marks_obtained} / ${row.max_marks}`;
        const label = document.createElement('span'); label.textContent = 'Instructor feedback'; score.append(points, label);
        const feedback = document.createElement('p'); feedback.className = 'feedback'; feedback.textContent = row.feedback || 'No written feedback.'; card.append(score, feedback);
      }
      if (submissionUser?.role === 'staff' && row.status !== 'graded') {
        const form = document.createElement('form'); form.className = 'grade-form';
        const marks = document.createElement('input'); marks.type = 'number'; marks.min = '0'; marks.max = row.max_marks; marks.required = true; marks.placeholder = `Mark / ${row.max_marks}`; marks.setAttribute('aria-label', `Grade for ${row.student_name || 'student'}, maximum ${row.max_marks}`);
        const feedback = document.createElement('input'); feedback.placeholder = 'Feedback for student'; feedback.maxLength = 4000; feedback.setAttribute('aria-label', `Feedback for ${row.student_name || 'student'}`);
        const button = document.createElement('button'); button.type = 'submit'; button.className = 'button button-small'; button.textContent = 'Save grade'; form.append(marks, feedback, button);
        form.onsubmit = async event => { event.preventDefault(); button.disabled = true; try { await api(`/submissions/${row.id}/grade`, { method: 'PUT', body: JSON.stringify({ marks_obtained: Number(marks.value), feedback: feedback.value }) }); showMessage('Grade saved and audit logged.', 'success'); await loadSubmissions(); } catch (error) { showMessage(error.message); button.disabled = false; } };
        card.append(form);
      }
      showAttempts(row, card);
      return card;
    });
    host.replaceChildren(...cards);
  } catch (error) { showMessage(error.message); }
}

async function loadAudit() {
  if (submissionUser?.role !== 'staff') return;
  document.querySelector('#audit-panel')?.classList.remove('hidden');
  try {
    const host = document.querySelector('#audit-list'); const rows = await api(`/activity-logs?page=${auditPage}&per_page=25`);
    renderPagination(host, rows, page => { auditPage = page; loadAudit(); });
    if (!rows.length) { host.textContent = 'No activity recorded yet.'; return; }
    host.replaceChildren(...rows.map(row => {
      const item = document.createElement('div'); item.className = 'audit-row';
      const action = document.createElement('strong'); action.textContent = row.action;
      const target = document.createElement('span'); target.textContent = `${row.entity_type}${row.entity_id ? ` #${row.entity_id}` : ''}`;
      const time = document.createElement('time'); time.textContent = new Date(row.occurred_at).toLocaleString(); item.append(action, target, time); return item;
    }));
  } catch (error) { showMessage(error.message); }
}

loadSubmissions(); loadAudit();
