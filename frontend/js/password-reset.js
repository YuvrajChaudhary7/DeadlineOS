const resetToken = new URLSearchParams(location.search).get('token');
const requestForm = document.querySelector('#request-form');
const confirmForm = document.querySelector('#confirm-form');
async function resetApi(path, body) {
  let response;
  try { response = await fetch(`${API_BASE}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); }
  catch { throw new Error('Cannot reach DeadlineOS. Check that the server is running and try again.'); }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}
if (resetToken) { requestForm.classList.add('hidden'); confirmForm.classList.remove('hidden'); }
requestForm.addEventListener('submit', async event => {
  event.preventDefault(); const button = requestForm.querySelector('button'); button.disabled = true;
  try { const result = await resetApi('/auth/password-reset/request', { email: new FormData(requestForm).get('email') }); showMessage(result.message, 'success'); }
  catch (error) { showMessage(error.message); }
  finally { button.disabled = false; }
});
confirmForm.addEventListener('submit', async event => {
  event.preventDefault(); const button = confirmForm.querySelector('button'); button.disabled = true;
  try { const result = await resetApi('/auth/password-reset/confirm', { token: resetToken, password: new FormData(confirmForm).get('password') }); showMessage(result.message, 'success'); confirmForm.reset(); }
  catch (error) { showMessage(error.message); }
  finally { button.disabled = false; }
});
