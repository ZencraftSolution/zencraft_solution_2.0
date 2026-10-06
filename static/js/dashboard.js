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

  var bulk = document.querySelector("[data-bulk]");
  if (bulk) {
    var all = bulk.querySelector("[data-bulk-all]");
    var items = Array.prototype.slice.call(bulk.querySelectorAll("[data-bulk-item]"));
    var count = bulk.querySelector("[data-bulk-count]");
    var update = function () { count.textContent = items.filter(function (i) { return i.checked; }).length + " selected"; };
    if (all) all.addEventListener("change", function () { items.forEach(function (i) { i.checked = all.checked; }); update(); });
    items.forEach(function (i) { i.addEventListener("change", update); });
    bulk.addEventListener("submit", function (e) {
      if (!items.some(function (i) { return i.checked; })) { e.preventDefault(); alert("Select at least one application."); }
    });
  }
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
