// Controla o intervalo de atualização da tela. Dispara o evento "refresh-tick"
// no body na cadência escolhida; os elementos HTMX (hx-trigger="refresh-tick
// from:body") e os gráficos (addEventListener) reagem a ele. A escolha é
// persistida em localStorage. "Off" (0) desliga a atualização automática.
(function () {
  const sel = document.getElementById("refresh-rate");
  if (!sel) return;
  const KEY = "refreshRate";
  let timer = null;

  function apply(seconds) {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    if (seconds > 0) {
      timer = setInterval(function () {
        if (window.htmx) {
          htmx.trigger(document.body, "refresh-tick");
        } else {
          document.body.dispatchEvent(new CustomEvent("refresh-tick"));
        }
      }, seconds * 1000);
    }
  }

  const saved = localStorage.getItem(KEY);
  const initial = saved !== null ? saved : sel.dataset.default || "5";
  sel.value = initial;
  if (sel.selectedIndex < 0) sel.value = "5"; // valor de config fora das opções

  apply(parseInt(sel.value, 10) || 0);

  sel.addEventListener("change", function () {
    localStorage.setItem(KEY, sel.value);
    apply(parseInt(sel.value, 10) || 0);
  });
})();
