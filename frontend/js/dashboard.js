let dashboardEvents = [];
let dashboardData = {};
let calendarCursor = new Date();
calendarCursor.setDate(1);

async function loadDashboard() {
  try {
    dashboardData = await api('/dashboard');
    dashboardEvents = dashboardData.events;
    renderSummary(dashboardData.summary);
    renderBriefing(dashboardData.briefing, dashboardData.streak);
    renderCalendar(); renderAgenda(); renderSuggestions();
  } catch (error) { showMessage(error.message); }
}

function renderSummary(summary) {
  const cards = [['Open items', summary.open, 'Across course and personal deadlines'], ['Due in 7 days', summary.next_7_days, 'A good week to plan ahead'], ['Overdue', summary.overdue, 'Items that need attention']];
  document.querySelector('#summary-cards').replaceChildren(...cards.map(([label, value, caption]) => {
    const card = document.createElement('article'); card.className = 'summary-card';
    const n = document.createElement('strong'); n.textContent = value;
    const h = document.createElement('span'); h.textContent = label;
    const p = document.createElement('small'); p.textContent = caption;
    card.append(n, h, p); return card;
  }));
}

function renderBriefing(briefing, streak) {
  document.querySelector('#briefing-headline').textContent = `${briefing.overdue.length ? `${briefing.overdue.length} overdue` : 'Your day, at a glance'}`;
  document.querySelector('#briefing-message').textContent = briefing.message;
  document.querySelector('#dashboard-streak').textContent = `Your steady-work streak: ${streak.current} ${streak.current === 1 ? 'day' : 'days'} · personal best ${streak.best}. This is private progress, not a competition.`;
  const host = document.querySelector('#briefing-items');
  const entries = [
    ...briefing.overdue.map(item => ({ ...item, group: 'Overdue' })),
    ...briefing.today.map(item => ({ ...item, group: 'Due today' })),
    ...briefing.next_7_days.slice(0, 3).map(item => ({ ...item, group: item.risk === 'at risk' ? 'At risk this week' : 'Coming this week' }))
  ];
  if (!entries.length) { host.textContent = 'Nothing urgent today. Use the calendar to preview upcoming workload.'; return; }
  host.replaceChildren(...entries.slice(0, 7).map(item => {
    const row = document.createElement('div'); row.className = 'briefing-row';
    const label = document.createElement('span'); label.textContent = item.group;
    const title = document.createElement('strong'); title.textContent = item.title;
    const due = document.createElement('time'); due.textContent = new Date(item.due_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    row.append(label, title, due); return row;
  }));
}

function localDayKey(value) {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function renderCalendar() {
  const host = document.querySelector('#calendar-grid');
  const year = calendarCursor.getFullYear(), month = calendarCursor.getMonth();
  document.querySelector('#calendar-month').textContent = calendarCursor.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  host.replaceChildren();
  for (const dayName of ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']) { const head = document.createElement('div'); head.className = 'calendar-weekday'; head.textContent = dayName; host.append(head); }
  const first = new Date(year, month, 1), offset = (first.getDay() + 6) % 7;
  for (let i = 0; i < offset; i++) { const blank = document.createElement('div'); blank.className = 'calendar-cell calendar-empty'; host.append(blank); }
  const dayCount = new Date(year, month + 1, 0).getDate();
  for (let day = 1; day <= dayCount; day++) {
    const cell = document.createElement('div'); cell.className = 'calendar-cell';
    const dayDate = new Date(year, month, day); const dayKey = localDayKey(dayDate);
    const dayEvents = dashboardEvents.filter(event => localDayKey(event.due_at) === dayKey);
    const openCount = dayEvents.filter(event => !event.is_complete).length;
    const heat = openCount === 0 ? 0 : openCount === 1 ? 1 : openCount === 2 ? 2 : 3;
    cell.classList.add(`heat-${heat}`); cell.setAttribute('aria-label', `${dayDate.toLocaleDateString()}: ${openCount} open item(s)`);
    const number = document.createElement('span'); number.className = 'calendar-day'; number.textContent = day; cell.append(number);
    for (const event of dayEvents.slice(0, 3)) {
      const chip = document.createElement('div'); chip.className = `event-chip ${event.kind === 'personal' ? 'event-personal' : 'event-course'} ${event.is_complete ? 'event-complete' : ''}`;
      chip.title = event.title; chip.textContent = event.title; cell.append(chip);
    }
    if (dayEvents.length > 3) { const more = document.createElement('small'); more.className = 'calendar-more'; more.textContent = `+${dayEvents.length - 3} more`; cell.append(more); }
    host.append(cell);
  }
}

function renderSuggestions() {
  const host = document.querySelector('#workload-suggestions');
  const loads = new Map();
  for (const event of dashboardEvents.filter(item => !item.is_complete)) {
    const key = localDayKey(event.due_at); loads.set(key, (loads.get(key) || 0) + 1);
  }
  const busy = [...loads.entries()].filter(([, count]) => count >= 4).sort((a, b) => b[1] - a[1]);
  const suggestions = [];
  for (const [day, count] of busy) {
    const task = dashboardEvents.find(event => event.kind === 'personal' && !event.is_complete && localDayKey(event.due_at) === day);
    if (!task) continue;
    const from = new Date(`${day}T12:00:00`);
    for (let step = 1; step <= 7; step++) {
      const target = new Date(from); target.setDate(target.getDate() + step);
      const targetKey = localDayKey(target);
      if ((loads.get(targetKey) || 0) < 3) { suggestions.push({ task, day, count, target, targetKey, targetCount: loads.get(targetKey) || 0 }); break; }
    }
  }
  if (!suggestions.length) { host.textContent = 'No overloaded days detected in the next 90 days. Days with four or more open items are flagged; course deadlines are never moved automatically.'; return; }
  host.replaceChildren(...suggestions.slice(0, 5).map(item => {
    const row = document.createElement('article'); row.className = 'suggestion-row';
    const text = document.createElement('p'); text.textContent = `${item.count} open items fall on ${new Date(`${item.day}T12:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}. Consider moving “${item.task.title}” to ${item.target.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })} (${item.targetCount} items planned).`;
    const button = document.createElement('button'); button.className = 'button button-small'; button.textContent = 'Reschedule this task';
    button.onclick = async () => {
      const previous = new Date(item.task.due_at); const suggested = new Date(item.target);
      suggested.setHours(previous.getHours(), previous.getMinutes(), 0, 0);
      button.disabled = true;
      try { await api(`/personal-tasks/${item.task.id.split('-')[1]}`, { method: 'PATCH', body: JSON.stringify({ due_at: suggested.toISOString() }) }); showMessage('Task rescheduled. Review the updated calendar.', 'success'); await loadDashboard(); }
      catch (error) { showMessage(error.message); button.disabled = false; }
    };
    row.append(text, button); return row;
  }));
}

function renderAgenda() {
  const host = document.querySelector('#agenda'), now = Date.now();
  const rows = dashboardEvents.filter(event => !event.is_complete && new Date(event.due_at).getTime() >= now).slice(0, 8);
  if (!rows.length) { host.innerHTML = '<div class="empty-state"><h3>You are all caught up</h3><p>Add a personal task or check your course deadlines when new work appears.</p></div>'; return; }
  host.replaceChildren(...rows.map(event => {
    const row = document.createElement('article'); row.className = 'agenda-row';
    const date = document.createElement('div'); date.className = 'agenda-date'; const due = new Date(event.due_at);
    const day = document.createElement('strong'); day.textContent = due.toLocaleDateString(undefined, { day: '2-digit' });
    const month = document.createElement('span'); month.textContent = due.toLocaleDateString(undefined, { month: 'short' }); date.append(day, month);
    const info = document.createElement('div'); info.className = 'agenda-info';
    const type = document.createElement('span'); type.className = `event-label ${event.kind === 'personal' ? 'event-label-personal' : 'event-label-course'}`; type.textContent = event.kind === 'personal' ? 'Personal task' : `${event.course_code} assignment`;
    const title = document.createElement('strong'); title.textContent = event.title; info.append(type, title);
    if (event.risk) { const risk = document.createElement('small'); risk.className = 'risk-caption'; risk.textContent = `Risk ${event.risk.score}/100 · ${event.risk.label}`; info.append(risk); }
    const time = document.createElement('time'); time.textContent = due.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    row.append(date, info, time); return row;
  }));
}

document.querySelector('#month-prev').onclick = () => { calendarCursor.setMonth(calendarCursor.getMonth() - 1); renderCalendar(); };
document.querySelector('#month-next').onclick = () => { calendarCursor.setMonth(calendarCursor.getMonth() + 1); renderCalendar(); };
loadDashboard();
