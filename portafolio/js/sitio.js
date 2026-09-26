/* Filtros de la galería, cambio de tema y aviso de datos pendientes. */
(function () {
  "use strict";

  // ---------- año del pie ----------
  var anio = document.getElementById("anio");
  if (anio) anio.textContent = String(new Date().getFullYear());

  // ---------- aviso de borrador ----------
  // Cuenta los textos con class="pendiente" (sin contar el ejemplo del propio aviso).
  var aviso = document.getElementById("borrador");
  if (aviso) {
    var pendientes = Array.prototype.filter.call(
      document.querySelectorAll(".pendiente"),
      function (el) { return !aviso.contains(el); }
    );
    document.getElementById("borrador-n").textContent = String(pendientes.length);
    aviso.hidden = pendientes.length === 0;
  }

  // ---------- tema claro / oscuro ----------
  var raiz = document.documentElement;
  var botonTema = document.getElementById("tema");
  function temaActual() {
    var t = raiz.dataset.theme;
    if (t === "dark" || t === "light") return t;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  if (botonTema) {
    botonTema.addEventListener("click", function () {
      var nuevo = temaActual() === "dark" ? "light" : "dark";
      raiz.dataset.theme = nuevo;
      try {
        localStorage.setItem("tema", nuevo === "dark" ? "oscuro" : "claro");
      } catch (e) { /* sin almacenamiento: el cambio dura hasta recargar */ }
    });
  }

  // ---------- filtros de proyectos ----------
  var botones = document.querySelectorAll("[data-filtro]");
  var proyectos = document.querySelectorAll(".proyecto");
  var contador = document.getElementById("proyectos-n");
  var vacia = document.getElementById("galeria-vacia");
  if (contador) contador.textContent = String(proyectos.length);

  function filtrar(tema) {
    var visibles = 0;
    proyectos.forEach(function (p) {
      var temas = (p.dataset.temas || "").split(/\s+/);
      var mostrar = tema === "todos" || temas.indexOf(tema) !== -1;
      p.hidden = !mostrar;
      if (mostrar) visibles++;
    });
    botones.forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.filtro === tema));
    });
    if (vacia) vacia.hidden = visibles > 0;
  }

  botones.forEach(function (b) {
    b.addEventListener("click", function () { filtrar(b.dataset.filtro); });
  });
})();
