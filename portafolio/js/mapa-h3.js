/*
 * Mapa de la portada: celdas H3 del centro de Guadalajara coloreadas según la
 * distancia, en anillos de celdas, al punto más cercano (búsqueda en anchura
 * desde todos los puntos a la vez). Un clic agrega o quita un punto.
 * Requiere h3-js (https://github.com/uber/h3-js), cargado antes que este archivo.
 */
(function () {
  "use strict";

  var lienzo = document.getElementById("mapa-lienzo");
  if (!lienzo) return;
  var lectura = document.getElementById("mapa-lectura");
  var botonesRes = document.querySelectorAll("[data-res]");
  var reiniciar = document.getElementById("mapa-reiniciar");
  var h3 = window.h3;

  var CENTRO = { lat: 20.6736, lng: -103.344 };
  var MEDIA_ALTURA = 0.05;      // grados de latitud entre el centro y el borde superior
  var KM_MAX = 5;               // distancia a la que la rampa llega a su último color
  var KM_POR_GRADO_LAT = 110.57;
  var KM_POR_MS = 0.009;        // velocidad de la animación de entrada
  var COS_LAT = Math.cos((CENTRO.lat * Math.PI) / 180);
  var FONDO = "#0b1519";
  var SIN_DATO = "#13232a";
  var VIRIDIS = ["#fde725", "#aadc32", "#5cc863", "#27ad81", "#21908d",
                 "#2c718e", "#3b518b", "#472c7a", "#440154"];
  // Puntos de ejemplo para que el mapa no arranque vacío; no son datos reales.
  var EJEMPLO = [
    { lat: 20.6767, lng: -103.3469 },
    { lat: 20.7010, lng: -103.3800 },
    { lat: 20.6470, lng: -103.3880 },
    { lat: 20.6560, lng: -103.3060 },
    { lat: 20.7040, lng: -103.3160 }
  ];
  var MAX_PUNTOS = 16;
  var movimientoReducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var sinCursor = window.matchMedia("(hover: none)").matches;

  var estado = {
    res: 8,
    puntos: EJEMPLO.slice(),
    ancho: 0,
    alto: 0,
    dpr: 1,
    escala: 0,          // píxeles por grado de latitud
    celdas: [],         // { id, ruta, k, km, color }
    porId: new Map(),
    kmMax: 0,
    encima: null,
    animInicio: 0,
    dibujoPedido: false
  };

  if (!h3) {
    lectura.textContent = "No se pudo cargar la biblioteca h3-js. Revisa tu conexión y recarga la página.";
    botonesRes.forEach(function (b) { b.disabled = true; });
    if (reiniciar) reiniciar.disabled = true;
    return;
  }

  // ---------- utilidades ----------
  var RGB = VIRIDIS.map(function (h) {
    return [1, 3, 5].map(function (i) { return parseInt(h.slice(i, i + 2), 16); });
  });

  function colorPara(km) {
    var t = (Math.min(km / KM_MAX, 1)) * (RGB.length - 1);
    var i = Math.min(Math.floor(t), RGB.length - 2);
    var f = t - i;
    var a = RGB[i], b = RGB[i + 1];
    return "rgb(" + [0, 1, 2].map(function (k) {
      return Math.round(a[k] + (b[k] - a[k]) * f);
    }).join(",") + ")";
  }

  function aPixel(lat, lng) {
    return [
      estado.ancho / 2 + (lng - CENTRO.lng) * COS_LAT * estado.escala,
      estado.alto / 2 - (lat - CENTRO.lat) * estado.escala
    ];
  }

  function aGrados(x, y) {
    return {
      lat: CENTRO.lat - (y - estado.alto / 2) / estado.escala,
      lng: CENTRO.lng + (x - estado.ancho / 2) / (COS_LAT * estado.escala)
    };
  }

  // Distancia media entre los centros de dos celdas vecinas.
  function separacionKm() {
    return h3.getHexagonEdgeLengthAvg(estado.res, "km") * Math.sqrt(3);
  }

  function formato(n) {
    return n.toLocaleString("es-MX", { maximumFractionDigits: n < 1 ? 2 : 1 });
  }

  // ---------- geometría y distancias ----------
  function construir() {
    var ancho = lienzo.clientWidth;
    var alto = lienzo.clientHeight;
    if (!ancho || !alto) return false;
    estado.dpr = window.devicePixelRatio || 1;
    lienzo.width = Math.round(ancho * estado.dpr);
    lienzo.height = Math.round(alto * estado.dpr);
    estado.ancho = ancho;
    estado.alto = alto;
    estado.escala = alto / (2 * MEDIA_ALTURA);

    // Un margen de una celda para que no queden huecos en los bordes.
    var margen = separacionKm() / KM_POR_GRADO_LAT;
    var dLat = MEDIA_ALTURA + margen;
    var dLng = ancho / 2 / (COS_LAT * estado.escala) + margen / COS_LAT;
    var caja = [
      [CENTRO.lat - dLat, CENTRO.lng - dLng],
      [CENTRO.lat - dLat, CENTRO.lng + dLng],
      [CENTRO.lat + dLat, CENTRO.lng + dLng],
      [CENTRO.lat + dLat, CENTRO.lng - dLng]
    ];

    estado.porId = new Map();
    estado.celdas = h3.polygonToCells(caja, estado.res).map(function (id) {
      var ruta = new Path2D();
      h3.cellToBoundary(id).forEach(function (v, i) {
        var p = aPixel(v[0], v[1]);
        if (i) ruta.lineTo(p[0], p[1]);
        else ruta.moveTo(p[0], p[1]);
      });
      ruta.closePath();
      var celda = { id: id, ruta: ruta, k: Infinity, km: Infinity, color: SIN_DATO };
      estado.porId.set(id, celda);
      return celda;
    });
    estado.encima = null;
    calcular();
    return true;
  }

  // Búsqueda en anchura desde todos los puntos: k = anillos hasta el más cercano.
  function calcular() {
    estado.celdas.forEach(function (c) { c.k = Infinity; });
    var frontera = [];
    estado.puntos.forEach(function (p) {
      var c = estado.porId.get(h3.latLngToCell(p.lat, p.lng, estado.res));
      if (c && c.k !== 0) {
        c.k = 0;
        frontera.push(c);
      }
    });
    for (var k = 1; frontera.length; k++) {
      var siguiente = [];
      frontera.forEach(function (c) {
        h3.gridDisk(c.id, 1).forEach(function (id) {
          var v = estado.porId.get(id);
          if (v && v.k === Infinity) {
            v.k = k;
            siguiente.push(v);
          }
        });
      });
      frontera = siguiente;
    }
    var sep = separacionKm();
    estado.kmMax = 0;
    estado.celdas.forEach(function (c) {
      c.km = c.k * sep;
      c.color = c.k === Infinity ? SIN_DATO : colorPara(c.km);
      if (c.km !== Infinity && c.km > estado.kmMax) estado.kmMax = c.km;
    });
  }

  // ---------- dibujo ----------
  function dibujar(ahora) {
    estado.dibujoPedido = false;
    var ctx = lienzo.getContext("2d");
    ctx.setTransform(estado.dpr, 0, 0, estado.dpr, 0, 0);
    ctx.fillStyle = FONDO;
    ctx.fillRect(0, 0, estado.ancho, estado.alto);

    var revelado = Infinity;
    if (estado.animInicio) {
      revelado = ((ahora || performance.now()) - estado.animInicio) * KM_POR_MS;
      if (revelado > estado.kmMax) {
        estado.animInicio = 0;
        revelado = Infinity;
      }
    }

    var anchoCelda = (separacionKm() * estado.escala) / KM_POR_GRADO_LAT;
    ctx.lineWidth = Math.max(0.6, Math.min(1.5, anchoCelda / 14));
    ctx.lineJoin = "round";
    ctx.strokeStyle = FONDO;
    estado.celdas.forEach(function (c) {
      ctx.fillStyle = c.km <= revelado ? c.color : SIN_DATO;
      ctx.fill(c.ruta);
      ctx.stroke(c.ruta);
    });

    reticula(ctx);

    estado.puntos.forEach(function (p) {
      var q = aPixel(p.lat, p.lng);
      ctx.beginPath();
      ctx.arc(q[0], q[1], 4.5, 0, Math.PI * 2);
      ctx.fillStyle = FONDO;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();
    });

    if (estado.encima) {
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke(estado.encima.ruta);
    }

    barraDeEscala(ctx);

    if (estado.animInicio) requestAnimationFrame(dibujar);
  }

  function texto(ctx, cadena, x, y) {
    ctx.strokeText(cadena, x, y);
    ctx.fillText(cadena, x, y);
  }

  // Paralelos y meridianos cada 0.02°, rotulados en el borde.
  function reticula(ctx) {
    var paso = 0.02;
    var arriba = aGrados(0, 0);
    var abajo = aGrados(estado.ancho, estado.alto);
    ctx.save();
    ctx.font = "10px 'IBM Plex Mono', ui-monospace, monospace";
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
    var i, x, y;
    var lineas = [];
    var ultimoX = -Infinity;  // evita que los rótulos se encimen en pantallas angostas
    for (i = Math.ceil(abajo.lat / paso); i * paso < arriba.lat; i++) {
      y = Math.round(aPixel(i * paso, CENTRO.lng)[1]) + 0.5;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(estado.ancho, y); ctx.stroke();
      if (y > 24 && y < estado.alto - 30) lineas.push([(i * paso).toFixed(2) + "° N", 6, y - 5]);
    }
    for (i = Math.ceil(arriba.lng / paso); i * paso < abajo.lng; i++) {
      x = Math.round(aPixel(CENTRO.lat, i * paso)[0]) + 0.5;
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, estado.alto); ctx.stroke();
      if (x > 60 && x < estado.ancho - 70 && x - ultimoX >= 84) {
        lineas.push([Math.abs(i * paso).toFixed(2) + "° O", x + 5, 14]);
        ultimoX = x;
      }
    }
    ctx.setLineDash([]);
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(11, 21, 25, 0.85)";
    ctx.fillStyle = "rgba(211, 224, 220, 0.9)";
    lineas.forEach(function (l) { texto(ctx, l[0], l[1], l[2]); });
    ctx.restore();
  }

  function barraDeEscala(ctx) {
    var pxPorKm = estado.escala / KM_POR_GRADO_LAT;
    var km = pxPorKm * 2 > estado.ancho * 0.3 ? 1 : 2;
    var largo = km * pxPorKm;
    var x1 = estado.ancho - 14;
    var x0 = x1 - largo;
    var y = estado.alto - 14;
    ctx.save();
    ctx.strokeStyle = "rgba(11, 21, 25, 0.85)";
    ctx.lineWidth = 5;
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x0, y - 5); ctx.lineTo(x0, y); ctx.lineTo(x1, y); ctx.lineTo(x1, y - 5);
    ctx.stroke();
    ctx.font = "10px 'IBM Plex Mono', ui-monospace, monospace";
    ctx.textAlign = "center";
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(11, 21, 25, 0.85)";
    ctx.fillStyle = "#ffffff";
    texto(ctx, km + " km", (x0 + x1) / 2, y - 7);
    ctx.restore();
  }

  function pedirDibujo() {
    if (estado.dibujoPedido || estado.animInicio) return;
    estado.dibujoPedido = true;
    requestAnimationFrame(dibujar);
  }

  // Revela los colores desde los puntos hacia afuera.
  function animar() {
    if (movimientoReducido || document.visibilityState !== "visible") {
      dibujar();
      return;
    }
    estado.animInicio = performance.now();
    dibujar(estado.animInicio);
    // Por si requestAnimationFrame no corre (pestaña en segundo plano).
    setTimeout(function () {
      if (estado.animInicio) {
        estado.animInicio = 0;
        dibujar();
      }
    }, 2500);
  }

  // ---------- lectura ----------
  function actualizarLectura() {
    var arista = h3.getHexagonEdgeLengthAvg(estado.res, "km");
    var area = h3.getHexagonAreaAvg(estado.res, "km2");
    var c = estado.encima;
    var primera;
    if (c) {
      var detalle;
      if (c.k === Infinity) detalle = "sin puntos en el mapa";
      else if (c.k === 0) detalle = "contiene un punto";
      else detalle = c.k + (c.k === 1 ? " anillo" : " anillos") + " · ≈ " + formato(c.km) + " km";
      primera = "<b>" + c.id + "</b> · " + detalle;
    } else if (!estado.puntos.length) {
      primera = "Haz clic en el mapa para agregar un punto.";
    } else if (sinCursor) {
      primera = "Toca una celda para ver su índice H3.";
    } else {
      primera = "Pasa el cursor sobre una celda para ver su índice H3.";
    }
    lectura.innerHTML = primera + "<br>res " + estado.res +
      " · arista media " + formato(arista) + " km · área media " + formato(area) +
      " km² · " + estado.celdas.length + " celdas";
  }

  // ---------- eventos ----------
  function celdaEn(evento) {
    var r = lienzo.getBoundingClientRect();
    var g = aGrados(evento.clientX - r.left, evento.clientY - r.top);
    return { g: g, id: h3.latLngToCell(g.lat, g.lng, estado.res) };
  }

  lienzo.addEventListener("pointermove", function (e) {
    var c = estado.porId.get(celdaEn(e).id) || null;
    if (c !== estado.encima) {
      estado.encima = c;
      pedirDibujo();
      actualizarLectura();
    }
  });

  lienzo.addEventListener("pointerleave", function () {
    estado.encima = null;
    pedirDibujo();
    actualizarLectura();
  });

  lienzo.addEventListener("click", function (e) {
    var sel = celdaEn(e);
    var quedan = estado.puntos.filter(function (p) {
      return h3.latLngToCell(p.lat, p.lng, estado.res) !== sel.id;
    });
    if (quedan.length !== estado.puntos.length) {
      estado.puntos = quedan;
    } else {
      if (estado.puntos.length >= MAX_PUNTOS) estado.puntos.shift();
      estado.puntos.push(sel.g);
    }
    calcular();
    estado.encima = estado.porId.get(sel.id) || null;
    pedirDibujo();
    actualizarLectura();
  });

  botonesRes.forEach(function (boton) {
    boton.addEventListener("click", function () {
      var res = Number(boton.dataset.res);
      if (res === estado.res) return;
      estado.res = res;
      botonesRes.forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === boton));
      });
      construir();
      animar();
      actualizarLectura();
    });
  });

  if (reiniciar) {
    reiniciar.addEventListener("click", function () {
      estado.puntos = EJEMPLO.slice();
      calcular();
      animar();
      actualizarLectura();
    });
  }

  // ---------- arranque ----------
  var ultimoTamano = "";
  function alCambiarTamano() {
    var tamano = lienzo.clientWidth + "x" + lienzo.clientHeight;
    if (tamano === ultimoTamano) return;
    var primeraVez = ultimoTamano === "";
    ultimoTamano = tamano;
    if (!construir()) return;
    if (primeraVez) animar();
    else pedirDibujo();
    actualizarLectura();
  }

  if ("ResizeObserver" in window) new ResizeObserver(alCambiarTamano).observe(lienzo);
  else window.addEventListener("resize", alCambiarTamano);
  alCambiarTamano();

  // Vuelve a dibujar cuando llegue la fuente de los rótulos.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () { if (estado.celdas.length) pedirDibujo(); });
  }
})();
