const API_BASE = `${window.location.origin}/api`;
function authToken(){return sessionStorage.getItem('deadlineos_token')}
function signedInUser(){try{return JSON.parse(sessionStorage.getItem('deadlineos_user')||'null')}catch{return null}}
async function api(path, options={}){
  const headers={...(options.headers||{})};
  if(options.body && !(options.body instanceof FormData)) headers['Content-Type']='application/json';
  if(authToken()) headers.Authorization=`Bearer ${authToken()}`;
  const response=await fetch(`${API_BASE}${path}`,{...options,headers});
  if(response.status===401){sessionStorage.removeItem('deadlineos_token');sessionStorage.removeItem('deadlineos_user');if(!location.pathname.endsWith('login.html'))location.href='login.html';throw new Error('Your session expired. Please sign in again.')}
  if(response.headers.get('content-type')?.includes('application/json')){const data=await response.json();if(!response.ok)throw new Error(data.error||`Request failed (${response.status})`);return data}
  if(!response.ok)throw new Error(`Request failed (${response.status})`);return response.blob();
}
function showMessage(message,kind='error'){const host=document.querySelector('#message');if(!host)return;host.textContent=message;host.classList.toggle('success',kind==='success')}
function requireAuth(){if(!authToken()){location.href='login.html';return false}return true}
function syncHeader(){const user=signedInUser();const name=document.querySelector('#user-name');const role=document.querySelector('#role-tag');const tasksLink=document.querySelector('#student-tasks-link');const dashboardLink=document.querySelector('#dashboard-link');const analyticsLink=document.querySelector('#staff-analytics-link');const adminLink=document.querySelector('#admin-link');if(name&&user)name.textContent=user.name||user.email;if(role&&user)role.textContent=user.role==='staff'?'Instructor':user.role==='admin'?'Administrator':'Student';if(tasksLink&&user?.role==='student')tasksLink.classList.remove('hidden');if(dashboardLink&&user?.role==='student')dashboardLink.classList.remove('hidden');if(analyticsLink&&user?.role==='staff')analyticsLink.classList.remove('hidden');if(adminLink&&user?.role==='admin')adminLink.classList.remove('hidden')}
document.querySelector('#logout')?.addEventListener('click',async()=>{try{if(authToken())await api('/auth/logout',{method:'POST'})}catch{}finally{sessionStorage.removeItem('deadlineos_token');sessionStorage.removeItem('deadlineos_user');location.href='login.html'}});
const publicPage=['/','/index.html','/login.html','/register.html'].includes(location.pathname);
if(!publicPage)requireAuth();syncHeader();
