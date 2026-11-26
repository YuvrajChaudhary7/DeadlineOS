const accountUser = signedInUser();
if (accountUser?.role !== 'student') { showMessage('Account privacy tools are available to student accounts.'); document.querySelectorAll('main section').forEach(section => section.classList.add('hidden')); }
document.querySelector('#export-data')?.addEventListener('click', async event => {
  const button = event.currentTarget; button.disabled = true;
  try { const blob = await api('/account/export'); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'deadlineos-account-export.zip'; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); showMessage('Your data archive was downloaded.', 'success'); }
  catch (error) { showMessage(error.message); }
  finally { button.disabled = false; }
});
document.querySelector('#delete-account-form')?.addEventListener('submit', async event => {
  event.preventDefault(); const form = event.currentTarget; const button = form.querySelector('button');
  if (!window.confirm('Permanently delete your account and all associated data? This cannot be undone.')) return;
  button.disabled = true;
  try { await api('/account', { method: 'DELETE', body: JSON.stringify(Object.fromEntries(new FormData(form))) }); sessionStorage.removeItem('deadlineos_token'); sessionStorage.removeItem('deadlineos_user'); location.href = 'login.html?deleted=1'; }
  catch (error) { showMessage(error.message); button.disabled = false; }
});
