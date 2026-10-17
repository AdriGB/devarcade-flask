// Gestión conectada a la API; los datos de usuarios se insertan como texto.
let actividad, consultas;
const modales = {};
const $ = (s) => document.querySelector(s);

function boton(texto, accion, peligro = false) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = `btn-arcade btn-arcade--${peligro ? 'danger' : 'cyan'} py-1 px-2 m-1`;
  b.textContent = texto;
  b.addEventListener('click', async () => {
    b.disabled = true;
    try { await accion(); } catch (e) { mostrarToast(e.message, 'error'); }
    finally { b.disabled = false; }
  });
  return b;
}

function fila(tbody, valores, acciones = []) {
  const tr = document.createElement('tr');
  valores.forEach(v => { const td = document.createElement('td'); td.textContent = v ?? '—'; tr.append(td); });
  if (acciones.length) {
    const td = document.createElement('td'); td.append(...acciones); tr.append(td);
  }
  tbody.append(tr);
}

function limpiarTabla(id) {
  const tbody = $(id); tbody.textContent = ''; return tbody;
}

async function cargarEstadisticas() {
  const params = new URLSearchParams();
  for (const [key, val] of new FormData($('#form-filtros'))) if (val) params.set(key, val);
  const s = await api('/stats?' + params);
  const cards = $('#contadores'); cards.textContent = '';
  for (const [key, label] of Object.entries({visitasTotales:'Visitas',usuariosRegistrados:'Cuentas',accesosAutenticados:'Accesos autenticados',mensajesNuevos:'Consultas nuevas',partidasJugadas:'Partidas'})) {
    const col = document.createElement('div'); col.className = 'col-6 col-lg';
    const box = document.createElement('div'); box.className = 'stat-tile h-100 p-3';
    const value = document.createElement('p'); value.className = 'value neon-cyan'; value.textContent = s.conteos[key];
    const text = document.createElement('span'); text.className = 'small text-muted-arc'; text.textContent = label;
    box.append(value,text); col.append(box); cards.append(col);
  }
  const tbody = limpiarTabla('#tabla-top');
  s.topJugadores.forEach(p => fila(tbody,[p.nombre_jugador,p.juego,p.mejor]));
  if (!s.topJugadores.length) fila(tbody,['Sin partidas en el período','','']);
  if (typeof Chart !== 'undefined') {
    const fechas = [...new Set([...s.registrosPorDia.map(r=>r.dia),...s.accesosPorDia.map(r=>r.dia),...s.visitasPorDia.map(r=>r.fecha)])].sort();
    const dataset = (data,key,value,label,color) => ({label,borderColor:color,backgroundColor:color,data:fechas.map(d => data.find(r=>r[key]===d)?.[value] || 0),tension:.2});
    const series = [dataset(s.registrosPorDia,'dia','altas','Registros','#FF2D95'),dataset(s.accesosPorDia,'dia','accesos','Accesos','#00F5FF'),dataset(s.visitasPorDia,'fecha','contador','Visitas','#FFE600')];
    if (!actividad) actividad = new Chart($('#chartActividad'),{type:'line',data:{labels:fechas,datasets:series},options:{scales:{y:{beginAtZero:true}}}});
    else {actividad.data={labels:fechas,datasets:series};actividad.update();}
    const distribution = {labels:s.consultasPorTipo.map(r=>r.tipo),datasets:[{label:'Consultas',data:s.consultasPorTipo.map(r=>r.total),backgroundColor:['#FF2D95','#00F5FF','#FFE600']}]};
    if (!consultas) consultas = new Chart($('#chartConsultas'),{type:'bar',data:distribution,options:{scales:{y:{beginAtZero:true}}}});
    else {consultas.data=distribution;consultas.update();}
  }
}

async function cargarMensajes() {
  const {mensajes,smtp_activo} = await api('/mensajes');
  $('#modo-correo').textContent = smtp_activo ? 'SMTP configurado. Cada respuesta muestra el resultado de envío.' : 'Modo local: los correos se simulan y las respuestas se guardan en la base.';
  const tbody = limpiarTabla('#tabla-mensajes');
  mensajes.forEach(m=>fila(tbody,[m.nombre,m.email,m.tipo,m.estado],[boton('Abrir',()=>abrirMensaje(m.id))]));
  if (!mensajes.length) fila(tbody,['Todavía no hay consultas','','','','']);
}

async function abrirMensaje(id, mostrar = true) {
  const {mensaje,respuestas} = await api('/mensajes/'+id);
  $('#mensaje-info').textContent = `${mensaje.nombre} · ${mensaje.email} · ${mensaje.estado}`;
  $('#mensaje-texto').textContent = mensaje.mensaje;
  const hilo = $('#respuestas'); hilo.textContent = '';
  respuestas.forEach(r=>{
    const article=document.createElement('article'); article.className='surface p-3 my-3';
    const title=document.createElement('p'); title.className='small text-muted-arc'; title.textContent=`${r.admin_nombre} · ${r.enviado_en} · ${r.modo_envio}`;
    const body=document.createElement('p'); body.style.whiteSpace='pre-wrap'; body.textContent=r.cuerpo;
    article.append(title,body);hilo.append(article);
  });
  const form=$('#form-respuesta');form.elements.id.value=id;if(mostrar)form.querySelector('[data-error]').textContent='';
  if(mostrar) modales.mensaje.show();
}

async function cargarContenido(tipo) {
  const esProyecto=tipo==='proyecto', plural=esProyecto?'proyectos':'servicios';
  const data=await api('/'+plural+'?all=1');
  const tbody=limpiarTabla('#tabla-'+plural);
  data[plural].forEach(p=>fila(tbody,
    esProyecto?[p.titulo,p.slug,p.publicado?'Publicado':'Borrador']:[p.titulo,p.precio_estimado,p.activo?'Activo':'Inactivo'],
    [boton('Editar',()=>editar(tipo,p)),boton('Borrar',async()=>{
      if (!confirm(`¿Eliminar “${p.titulo}”?`)) return;
      await api(`/${plural}/${p.id}`,{method:'DELETE'});await cargarContenido(tipo);mostrarToast('Eliminado');
    },true)]));
  if(!data[plural].length) fila(tbody,['Sin registros','','']);
}

function editar(tipo, data=null) {
  const form=$('#form-'+tipo);form.reset();form.elements.id.value=data?.id||'';
  if(tipo==='proyecto') form.elements.orden.value=1;
  for(const el of form.elements) {
    if(el.name && el.type!=='file' && data && data[el.name]!=null) el.value=data[el.name];
  }
  form.querySelector('[data-error]').textContent='';modales[tipo].show();
}

async function guardarContenido(tipo,e) {
  e.preventDefault();const form=e.currentTarget,submit=form.querySelector('[type=submit]');
  submit.disabled=true;
  try {
    const data=Object.fromEntries(new FormData(form));const id=data.id;delete data.id;
    if(tipo==='proyecto') {
      if(data.archivo?.size) {
        const fd=new FormData();fd.append('imagen',data.archivo);
        data.imagen=(await api('/proyectos/upload-imagen',{method:'POST',body:fd})).imagen;
      }
      delete data.archivo;data.orden=Number(data.orden);data.publicado=Number(data.publicado);data.destacado=Number(data.destacado);
    } else data.activo=Number(data.activo);
    const plural=tipo==='proyecto'?'proyectos':'servicios';
    await api('/'+plural+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(data)});
    modales[tipo].hide();await cargarContenido(tipo);mostrarToast('Guardado');
  } catch(err) {form.querySelector('[data-error]').textContent=err.message;}
  finally {submit.disabled=false;}
}

async function cargarUsuarios() {
  const {usuarios}=await api('/usuarios');const tbody=limpiarTabla('#tabla-usuarios');
  usuarios.forEach(u=>fila(tbody,[u.nombre,u.email,u.rol,u.activo?'Activo':'Suspendido',`${u.total_accesos} / ${u.partidas_jugadas}`],[
    boton(u.activo?'Suspender':'Activar',async()=>{await api('/usuarios/'+u.id,{method:'PUT',body:JSON.stringify({rol:u.rol,activo:u.activo?0:1})});await cargarUsuarios();}),
    boton(u.rol==='admin'?'Hacer jugador':'Hacer admin',async()=>{await api('/usuarios/'+u.id,{method:'PUT',body:JSON.stringify({rol:u.rol==='admin'?'user':'admin',activo:u.activo})});await cargarUsuarios();}),
    boton('Borrar',async()=>{if(!confirm('¿Eliminar esta cuenta y sus partidas?'))return;await api('/usuarios/'+u.id,{method:'DELETE'});await cargarUsuarios();await cargarEstadisticas();},true)
  ]));
}

document.addEventListener('DOMContentLoaded',async()=>{
  try {
    for(const tipo of ['proyecto','servicio','mensaje']) modales[tipo]=new bootstrap.Modal($('#modal-'+tipo));
    for(const tipo of ['proyecto','servicio']) {
      $('#nuevo-'+tipo).addEventListener('click',()=>editar(tipo));
      $('#form-'+tipo).addEventListener('submit',e=>guardarContenido(tipo,e));
    }
    $('#form-filtros').addEventListener('submit',async e=>{e.preventDefault();try{await cargarEstadisticas();}catch(err){mostrarToast(err.message,'error');}});
    $('#form-respuesta').addEventListener('submit',async e=>{
      e.preventDefault();const form=e.currentTarget,b=form.querySelector('button');b.disabled=true;
      try {
        const res=await api(`/mensajes/${form.elements.id.value}/responder`,{method:'POST',body:JSON.stringify({cuerpo:form.elements.cuerpo.value})});
        form.elements.cuerpo.value='';mostrarToast(res.modo_envio==='simulado'?'Respuesta guardada en modo simulado':'Respuesta enviada al servidor de correo');
      }catch(err){form.querySelector('[data-error]').textContent=err.message;}
      finally{b.disabled=false;await cargarMensajes();await abrirMensaje(form.elements.id.value,false);await cargarEstadisticas();}
    });
    // El primer GET establece la cookie CSRF antes de cualquier operación.
    const user=await obtenerSesion();if(user?.rol!=='admin')throw new Error('Se requiere sesión de administrador');
    await Promise.all([cargarEstadisticas(),cargarMensajes(),cargarContenido('proyecto'),cargarContenido('servicio'),cargarUsuarios()]);
    $('#estado-admin').textContent='Datos actualizados desde la base local.';
  }catch(err){$('#estado-admin').textContent=err.message;mostrarToast(err.message,'error');}
});
