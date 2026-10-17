// ============================================================
// prototipo/app.js — Cliente API con CSRF, aviso SMTP y DOM seguro
// ============================================================

const API = '/api';

function leerCookie(nombre) {
  const par = document.cookie
    .split('; ')
    .find((row) => row.startsWith(nombre + '='));
  return par ? decodeURIComponent(par.split('=')[1]) : '';
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const csrf = leerCookie('csrf_token');
  if (csrf) headers['X-CSRF-Token'] = csrf;

  const res = await fetch(API + path, {
    credentials: 'same-origin',
    ...options,
    headers
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Error inesperado');
  return data;
}

async function obtenerSesion() {
  try {
    const { usuario } = await api('/auth/me');
    return usuario;
  } catch {
    return null;
  }
}

function pintarAuth(usuario) {
  const links = document.querySelectorAll('a[href="login.html"]');
  links.forEach((a) => {
    const li = a.closest('.nav-item');
    if (!li || li.dataset.authListo) return;
    if (a.classList.contains('btn-arcade') && usuario) {
      li.remove();
      return;
    }
    if (usuario) {
      li.dataset.authListo = '1';
      li.textContent = '';
      const chip = document.createElement('span');
      chip.className = 'tech-chip py-1';
      const dot = document.createElement('span');
      dot.className = 'dot';
      dot.style.background = 'var(--arc-success)';
      const etiquetaRol = usuario.rol === 'admin' ? ' · admin' : '';
      const texto = document.createTextNode(` ${usuario.nombre}${etiquetaRol}`);
      chip.appendChild(dot);
      chip.appendChild(texto);
      li.appendChild(chip);
    }
  });

  if (usuario) {
    const nav = document.querySelector('.navbar-nav');
    if (nav && !document.querySelector('#btn-logout')) {
      if (usuario.rol === 'admin' && !location.pathname.endsWith('admin.html')) {
        const liAdmin = document.createElement('li');
        liAdmin.className = 'nav-item';
        const aAdmin = document.createElement('a');
        aAdmin.className = 'nav-link neon-cyan';
        aAdmin.href = 'admin.html';
        aAdmin.textContent = '👑 Admin';
        liAdmin.appendChild(aAdmin);
        nav.appendChild(liAdmin);
      }

      const li = document.createElement('li');
      li.className = 'nav-item';
      const btn = document.createElement('button');
      btn.className = 'btn-arcade btn-arcade--danger py-2 px-3';
      btn.id = 'btn-logout';
      btn.textContent = 'Salir';
      btn.addEventListener('click', async () => {
        await api('/auth/logout', { method: 'POST' });
        location.href = 'index.html';
      });
      li.appendChild(btn);
      nav.appendChild(li);
    }
  }
}

function marcarError(input, mensaje) {
  if (!input) return;
  input.classList.add('is-invalid');
  input.classList.remove('is-valid');
  const fb =
    input.parentElement.querySelector('.invalid-feedback') ||
    input.nextElementSibling;
  if (fb && fb.classList.contains('invalid-feedback')) {
    fb.textContent = mensaje;
  }
}

function limpiarErrores(form) {
  form
    .querySelectorAll('.is-invalid')
    .forEach((el) => el.classList.remove('is-invalid'));
}

function mostrarToast(mensaje, tipo = 'ok') {
  const div = document.createElement('div');
  div.className = 'position-fixed bottom-0 end-0 p-3';
  div.style.zIndex = '2000';

  const card = document.createElement('div');
  card.className = 'surface p-3 px-4 shadow';
  const colorBorde =
    tipo === 'ok'
      ? 'var(--arc-success)'
      : tipo === 'warn'
        ? 'var(--arc-warning)'
        : 'var(--arc-danger)';
  card.style.borderColor = colorBorde;

  const span = document.createElement('span');
  span.className = 'font-display small';
  const icono = tipo === 'ok' ? '✅' : '⚠️';
  span.textContent = `${icono} ${mensaje}`;

  card.appendChild(span);
  div.appendChild(card);
  document.body.appendChild(div);
  setTimeout(() => div.remove(), 4500);
}

async function cargarServiciosHome() {
  const contenedor = document.querySelector('#lista-servicios');
  if (!contenedor) return;
  try {
    const { servicios } = await api('/servicios');
    if (!servicios.length) return;
    contenedor.textContent = '';
    servicios.forEach((s, idx) => {
      const esUltimo = idx === servicios.length - 1;
      const row = document.createElement('div');
      row.className = 'service-row' + (esUltimo ? ' border-bottom' : '');

      const num = document.createElement('span');
      num.className = 'num';
      num.textContent = String(idx + 1).padStart(2, '0');

      const body = document.createElement('div');
      const h3 = document.createElement('h3');
      h3.textContent = `${s.icono ? s.icono + ' ' : ''}${s.titulo}`;
      const p = document.createElement('p');
      const precioTxt = s.precio_estimado ? ` · (${s.precio_estimado})` : '';
      p.textContent = s.descripcion + precioTxt;
      body.appendChild(h3);
      body.appendChild(p);

      const cta = document.createElement('a');
      cta.className = 'btn-arcade btn-arcade--cyan d-none d-md-inline-flex';
      cta.href = '#contacto';
      cta.textContent = 'Consultar';

      row.appendChild(num);
      row.appendChild(body);
      row.appendChild(cta);
      contenedor.appendChild(row);
    });
  } catch {}
}

// Distingue claramente: envío SMTP real, simulación local o fallo de acuse SMTP
function cablearContacto() {
  const form = document.querySelector('#form-contacto');
  if (!form) return;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    limpiarErrores(form);
    const acepta = form.querySelector('#acepta');
    if (acepta && !acepta.checked) {
      marcarError(acepta, 'Debés aceptar para enviar el formulario.');
      return;
    }
    const body = {
      nombre: form.querySelector('#nombre').value,
      email: form.querySelector('#email').value,
      tipo: form.querySelector('#tipo').value,
      mensaje: form.querySelector('#mensaje').value
    };
    try {
      const res = await api('/mensajes', {
        method: 'POST',
        body: JSON.stringify(body)
      });
      form.reset();
      if (res.modo_envio === 'fallido') {
        mostrarToast(
          res.aviso_correo ||
            'Consulta guardada en bandeja, pero falló el correo de confirmación.',
          'warn'
        );
      } else if (res.modo_envio === 'simulado') {
        mostrarToast(
          'Consulta guardada (modo simulación local sin SMTP configurado).'
        );
      } else {
        mostrarToast('Consulta enviada y confirmada por email.');
      }
    } catch (err) {
      const msg = err.message || 'Error al enviar';
      if (msg.startsWith('nombre')) marcarError(form.querySelector('#nombre'), msg);
      else if (msg.startsWith('email')) marcarError(form.querySelector('#email'), msg);
      else if (msg.startsWith('mensaje')) marcarError(form.querySelector('#mensaje'), msg);
      else if (msg.startsWith('tipo')) marcarError(form.querySelector('#tipo'), msg);
      else mostrarToast(msg, 'error');
    }
  });
}

function cablearAcceso() {
  const loginForm = document.querySelector('#tab-login form');
  const regForm = document.querySelector('#tab-registro form');
  const params = new URLSearchParams(location.search);
  const nextUrl = params.get('next') || 'arcade.html';
  const destino = new URL(nextUrl, location.origin);
  const nextSeguro = destino.origin === location.origin ? destino.pathname + destino.search : '/arcade.html';

  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      limpiarErrores(loginForm);
      try {
        await api('/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            email: loginForm.querySelector('#login-email').value,
            password: loginForm.querySelector('#login-pass').value
          })
        });
        location.href = nextSeguro;
      } catch (err) {
        mostrarToast(err.message, 'error');
      }
    });
  }

  if (regForm) {
    regForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      limpiarErrores(regForm);
      const pass = regForm.querySelector('#reg-pass');
      const pass2 = regForm.querySelector('#reg-pass2');
      const tyc = regForm.querySelector('#reg-tyc');
      if (pass.value !== pass2.value) {
        marcarError(pass2, 'Las contraseñas no coinciden.');
        return;
      }
      if (tyc && !tyc.checked) {
        marcarError(tyc, 'Debés aceptar los términos.');
        return;
      }
      try {
        await api('/auth/registro', {
          method: 'POST',
          body: JSON.stringify({
            nombre: regForm.querySelector('#reg-user').value,
            email: regForm.querySelector('#reg-email').value,
            password: pass.value
          })
        });
        location.href = nextSeguro;
      } catch (err) {
        mostrarToast(err.message, 'error');
      }
    });
  }
}

function crearArtePantalla(slug) {
  const wrap = document.createElement('div');
  wrap.className = 'screen-art';
  if (slug === 'snake') {
    wrap.innerHTML =
      '<div class="snake"><i class="head"></i><i></i><i></i>' +
      '<span></span><span></span><span></span><i></i>' +
      '<span class="apple"></span></div>';
  } else if (slug === 'memory' || slug === 'ta-te-ti') {
    const cols = slug === 'ta-te-ti' ? 'repeat(3,30px)' : 'repeat(4,30px)';
    wrap.innerHTML =
      `<div class="memory" style="grid-template-columns:${cols}">` +
      '<i class="flip"></i><i></i><i class="flip"></i>' +
      '<i></i><i></i><i class="flip"></i></div>';
  } else {
    wrap.innerHTML =
      '<div class="bricks"><i></i><i></i><i></i><i></i><i></i><i></i>' +
      '<i></i><i></i><i></i><i></i><i></i><i></i></div>';
  }
  return wrap;
}

async function cargarSalaArcade(usuario) {
  const grilla = document.querySelector('#grilla-maquinas');
  if (!grilla) return;
  try {
    const { proyectos } = await api('/proyectos');
    grilla.textContent = '';

    proyectos.forEach((p) => {
      const col = document.createElement('div');
      col.className = 'col-md-6 col-xl-4';

      const estadoCab = usuario ? 'cabinet--on' : 'cabinet--locked';
      const cab = document.createElement('div');
      cab.className = `cabinet ${estadoCab} h-100 d-flex flex-column`;

      const marquee = document.createElement('div');
      marquee.className =
        'cabinet__marquee ' + (usuario ? 'neon-cyan' : 'text-muted-arc');
      marquee.textContent = p.titulo.toUpperCase();

      const screen = document.createElement('div');
      screen.className = 'cabinet__screen scanlines';
      if (p.imagen) {
        const img = document.createElement('img');
        img.src = p.imagen;
        img.alt = p.titulo;
        img.className = 'w-100 h-100 object-fit-cover';
        screen.appendChild(img);
      } else {
        screen.appendChild(crearArtePantalla(p.slug));
      }

      if (!usuario) {
        const lock = document.createElement('div');
        lock.className = 'cabinet__lock';
        const inner = document.createElement('div');
        const pLock = document.createElement('p');
        pLock.className = 'font-display mb-2';
        pLock.textContent = '🔒 MÁQUINA BLOQUEADA';
        const aReg = document.createElement('a');
        aReg.className = 'btn-arcade btn-arcade--cyan py-2 px-3';
        const dest = `/maquina.html?slug=${encodeURIComponent(p.slug)}`;
        aReg.href = `login.html?next=${encodeURIComponent(dest)}`;
        aReg.textContent = 'Registrate';
        inner.appendChild(pLock);
        inner.appendChild(aReg);
        lock.appendChild(inner);
        screen.appendChild(lock);
      }

      const info = document.createElement('div');
      info.className =
        'p-3 flex-grow-1 d-flex flex-column justify-content-between';
      const desc = document.createElement('p');
      desc.className = 'small text-muted-arc mb-2';
      desc.textContent = p.descripcion;
      const badge = document.createElement('span');
      const clsBadge = p.jugable ? 'badge-arc--done' : 'badge-arc--quote';
      badge.className = `badge-arc ${clsBadge} align-self-start`;
      badge.textContent = p.jugable
        ? '🕹 Demo interactiva'
        : '📁 Proyecto Fullstack';
      info.appendChild(desc);
      info.appendChild(badge);

      const deck = document.createElement('div');
      deck.className = 'cabinet__deck';
      deck.innerHTML =
        '<span class="arcade-key arcade-key--pink"></span>' +
        '<span class="arcade-key arcade-key--cyan"></span>';

      const actions = document.createElement('div');
      actions.className = 'ms-auto d-flex gap-2';

      const btnDetalle = document.createElement('a');
      btnDetalle.className = 'btn-arcade btn-arcade--cyan py-2 px-3';
      btnDetalle.href = `maquina.html?slug=${encodeURIComponent(p.slug)}`;
      btnDetalle.textContent = 'Ficha';
      actions.appendChild(btnDetalle);

      if (usuario && p.jugable && p.demo_url) {
        const btnJugar = document.createElement('a');
        btnJugar.className = 'btn-arcade btn-arcade--coin py-2 px-3';
        btnJugar.href = p.demo_url;
        btnJugar.textContent = '▶ Jugar';
        actions.appendChild(btnJugar);
      }
      deck.appendChild(actions);

      cab.append(marquee, screen, info, deck);
      col.appendChild(cab);
      grilla.appendChild(col);
    });
  } catch {}
}

async function cargarRankingSala(usuario) {
  const tbody = document.querySelector('#tabla-ranking-sala');
  if (!tbody) return;
  try {
    const limite = usuario ? 10 : 3;
    const { ranking } = await api(`/partidas/ranking?limite=${limite}`);
    tbody.textContent = '';
    if (!ranking.length) {
      tbody.innerHTML =
        '<tr><td colspan="4" class="text-center text-muted-arc py-3">' +
        'Aún no hay partidas registradas.</td></tr>';
      return;
    }
    ranking.forEach((r, idx) => {
      const tr = document.createElement('tr');
      const tdPos = document.createElement('td');
      tdPos.className =
        'font-display ' + (idx === 0 ? 'text-warning' : 'text-muted-arc');
      tdPos.textContent = idx + 1;

      const tdUser = document.createElement('td');
      tdUser.textContent = r.nombre_jugador;

      const tdJuego = document.createElement('td');
      tdJuego.textContent = (r.juego || 'general').toUpperCase();

      const tdPts = document.createElement('td');
      tdPts.className = 'text-end font-display';
      tdPts.textContent = Number(r.mejor_puntaje).toLocaleString('es-AR');

      tr.append(tdPos, tdUser, tdJuego, tdPts);
      tbody.appendChild(tr);
    });
  } catch {}
}

async function cargarDetalleMaquina(usuario) {
  const vistaVisitante = document.querySelector('#vista-visitante');
  const vistaRegistrado = document.querySelector('#vista-registrado');
  if (!vistaVisitante || !vistaRegistrado) return;

  const params = new URLSearchParams(location.search);
  const slug = params.get('slug') || 'snake';
  const loginLink=document.querySelector('#detalle-login');
  if(loginLink)loginLink.href='login.html?next='+encodeURIComponent(location.pathname+location.search);

  if (!usuario) {
    vistaVisitante.classList.remove('d-none');
    vistaRegistrado.classList.add('d-none');
    try {
      const { proyectos } = await api('/proyectos');
      const p = proyectos.find((x) => x.slug === slug) || proyectos[0];
      if (p) {
        document.querySelector('#vis-marquee').textContent =
          p.titulo.toUpperCase();
        document.querySelector('#vis-titulo').textContent = p.titulo;
        document.querySelector('#vis-desc').textContent = p.descripcion;
      }
    } catch {}
    return;
  }

  vistaVisitante.classList.add('d-none');
  vistaRegistrado.classList.remove('d-none');
  try {
    const { proyecto } = await api(`/proyectos/${encodeURIComponent(slug)}`);
    document.querySelector('#reg-marquee').textContent =
      proyecto.titulo.toUpperCase();
    document.querySelector('#reg-titulo').textContent = proyecto.titulo;
    document.querySelector('#reg-desc').textContent = proyecto.descripcion;

    const btnJugar = document.querySelector('#reg-btn-jugar');
    if (proyecto.jugable && proyecto.demo_url) {
      btnJugar.href = proyecto.demo_url;
      btnJugar.textContent = '▶ Jugar Demo';
      btnJugar.classList.remove('d-none');
    } else {
      btnJugar.classList.add('d-none');
    }

    const chips = document.querySelector('#reg-tecnologias');
    chips.textContent = '';
    (proyecto.tecnologias || 'Fullstack').split(',').forEach((t) => {
      const chip = document.createElement('span');
      chip.className = 'tech-chip';
      chip.innerHTML = '<span class="dot"></span>';
      chip.appendChild(document.createTextNode(t.trim()));
      chips.appendChild(chip);
    });

    const { partidas } = await api(
      `/partidas/mias?juego=${encodeURIComponent(slug)}`
    );
    const tbody = document.querySelector('#reg-tabla-partidas');
    tbody.textContent = '';
    if (!partidas.length) {
      tbody.innerHTML =
        '<tr><td colspan="2" class="text-muted-arc small py-2">' +
        'Aún no registraste partidas en esta máquina.</td></tr>';
    } else {
      partidas.slice(0, 8).forEach((part) => {
        const tr = document.createElement('tr');
        const tdFecha = document.createElement('td');
        tdFecha.textContent = part.jugado_en;
        const tdPts = document.createElement('td');
        tdPts.className = 'text-end font-display';
        tdPts.textContent = Number(part.puntaje).toLocaleString('es-AR');
        tr.append(tdFecha, tdPts);
        tbody.appendChild(tr);
      });
    }
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function contarVisita() {
  if (location.pathname.endsWith('index.html') || location.pathname === '/') {
    api('/visitas', { method: 'POST' }).catch(() => {});
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  const usuario = await obtenerSesion();
  pintarAuth(usuario);
  contarVisita();
  cargarServiciosHome();
  cablearContacto();
  cablearAcceso();
  cargarSalaArcade(usuario);
  cargarRankingSala(usuario);
  cargarDetalleMaquina(usuario);
});
