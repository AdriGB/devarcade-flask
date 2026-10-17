// API común: sesión, CSRF y reintento del mismo resultado sin duplicarlo.
const API = '/api';
let JUEGO = null, USUARIO = null;
async function api(path, options={}) {
  const token=document.cookie.split('; ').find(v=>v.startsWith('csrf_token='))?.split('=')[1];
  const res=await fetch(API+path,{...options,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':decodeURIComponent(token||''),...options.headers}});
  const data=await res.json().catch(()=>({}));
  if(!res.ok)throw new Error(data.error||'No se pudo completar la operación');
  return data;
}
async function initJuego(slug) {
  JUEGO=slug;
  try { USUARIO=(await api('/auth/me')).usuario;hud('#hud-usuario','👤 '+USUARIO.nombre);return true; }
  catch {location.href='../login.html?next='+encodeURIComponent(location.pathname);return false;}
}
async function guardarPuntaje(puntaje, resultadoId=(globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`)) {
  if(!USUARIO || !Number.isInteger(puntaje) || puntaje<0)return false;
  try {
    await api('/partidas',{method:'POST',body:JSON.stringify({juego:JUEGO,puntaje,resultado_id:resultadoId})});
    mostrarAviso('🏆 Puntaje guardado en tu perfil');return true;
  } catch(err) {
    const box=mostrarAviso(err.message,true,0);
    const retry=document.createElement('button');retry.textContent='Reintentar guardado';retry.className='btn-arcade btn-arcade--cyan mt-2';
    retry.onclick=async()=>{retry.disabled=true;box.remove();await guardarPuntaje(puntaje,resultadoId);};box.append(retry);return false;
  }
}
function mostrarAviso(texto,esError=false,duracion=4500) {
  const box=document.createElement('div');box.className='surface p-3 position-fixed bottom-0 end-0 m-3 shadow';
  box.style.cssText='z-index:2000;max-width:calc(100vw - 2rem)';box.style.borderColor=esError?'var(--arc-danger)':'var(--arc-success)';
  const msg=document.createElement('p');msg.className='small mb-1';msg.textContent=texto;box.append(msg);document.body.append(box);
  if(duracion)setTimeout(()=>box.remove(),duracion);return box;
}
function hud(id,valor){const el=document.querySelector(id);if(el)el.textContent=valor;}
