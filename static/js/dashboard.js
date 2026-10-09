/* Zencraft HQ: kanban drag and drop, bulk selection, mobile navigation. */
(function () {
  "use strict";

  function csrf() {
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  var toggle = document.querySelector("[data-dash-toggle]");
  var side = document.querySelector("[data-dash-side]");
  if (toggle && side) toggle.addEventListener("click", function () { side.classList.toggle("is-open"); });

  document.querySelectorAll("[data-board]").forEach(function (board) {
    var endpoint = board.dataset.endpoint;
    var dragged = null;
    var origin = null;

    function refreshCounts() {
      board.querySelectorAll(".board__col").forEach(function (col) {
        col.querySelector("[data-count]").textContent = col.querySelectorAll(".bcard").length;
      });
    }

    board.addEventListener("dragstart", function (e) {
      var card = e.target.closest(".bcard");
      if (!card) return;
      dragged = card;
      origin = card.parentElement;
      card.classList.add("is-dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", card.dataset.id);
    });
    board.addEventListener("dragend", function () {
      if (dragged) dragged.classList.remove("is-dragging");
      board.querySelectorAll(".is-over").forEach(function (c) { c.classList.remove("is-over"); });
    });

    board.querySelectorAll(".board__col").forEach(function (col) {
      col.addEventListener("dragover", function (e) { e.preventDefault(); col.classList.add("is-over"); });
      col.addEventListener("dragleave", function (e) { if (!col.contains(e.relatedTarget)) col.classList.remove("is-over"); });
      col.addEventListener("drop", function (e) {
        e.preventDefault();
        col.classList.remove("is-over");
        if (!dragged) return;
        var list = col.querySelector(".board__list");
        if (list === origin) return;
        var card = dragged;
        var from = origin;
        list.prepend(card);
        refreshCounts();
        fetch(endpoint.replace("/0/", "/" + card.dataset.id + "/"), {
          method: "PATCH",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
          credentials: "same-origin",
          body: JSON.stringify({ status: col.dataset.status }),
        })
          .then(function (r) { if (!r.ok) throw new Error("status " + r.status); return r.json(); })
          .catch(function () {
            from.prepend(card);
            refreshCounts();
            alert("Could not update the status. Please refresh and try again.");
          });
      });
    });
  });

  /* Selection on every dashboard list (templates/dashboard/_bulk_bar.html). Ticking the header
     box selects every row on the page; once they are all ticked and more records match than the
     page shows, "Select all N matching" widens the selection to every one of them (scope=all,
     which the server re-resolves from the page's filters). Unticking any row narrows it back. */
  document.querySelectorAll("[data-bulk]").forEach(function (form) {
    var items = Array.prototype.slice.call(form.querySelectorAll("[data-bulk-item]"));
    var alls = Array.prototype.slice.call(form.querySelectorAll("[data-bulk-all]"));
    var bar = form.querySelector("[data-bulk-bar]");
    var count = form.querySelector("[data-bulk-count]");
    var scope = form.querySelector("[data-bulk-scope]");
    var matching = form.querySelector("[data-bulk-all-matching]");
    var del = form.querySelector("[data-bulk-delete]");
    var total = bar ? parseInt(bar.dataset.total, 10) || 0 : 0;
    var shown = bar ? parseInt(bar.dataset.shown, 10) || 0 : items.length;

    function checked() { return items.filter(function (i) { return i.checked; }).length; }

    function update() {
      var n = checked();
      var every = items.length > 0 && n === items.length;
      if (!every && scope) scope.value = "";
      var all = scope && scope.value === "all";
      alls.forEach(function (box) { box.checked = every; box.indeterminate = n > 0 && !every; });
      if (count) count.textContent = all ? "All " + total + " selected" : n + " selected";
      if (matching) matching.hidden = !(every && total > shown && !all);
      if (del) del.disabled = n === 0;
    }

    alls.forEach(function (box) {
      box.addEventListener("change", function () {
        items.forEach(function (i) { i.checked = box.checked; });
        update();
      });
    });
    items.forEach(function (i) { i.addEventListener("change", update); });
    if (matching) matching.addEventListener("click", function () { scope.value = "all"; update(); });

    form.addEventListener("submit", function (e) {
      if (!checked()) { e.preventDefault(); alert("Select at least one record first."); }
    });
    update();
  });
})();

/* Forms that cannot be undone ask first. The server does not rely on this; it is here so a
   mis-click does not erase an applicant's record. */
(function () {
  "use strict";
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
})();
