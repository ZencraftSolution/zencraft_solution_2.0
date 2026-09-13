/* Job application: switch between CV upload and manual CV entry, and add repeatable formset rows. */
(function () {
  "use strict";
  var form = document.querySelector("[data-apply-form]");
  if (!form) return;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var panels = Array.prototype.slice.call(form.querySelectorAll("[data-mode-panel]"));
  var radios = Array.prototype.slice.call(form.querySelectorAll('input[name="application_mode"]'));

  function currentMode() {
    var checked = radios.filter(function (r) { return r.checked; })[0];
    return checked ? checked.value : "cv";
  }

  function applyMode(animate) {
    var mode = currentMode();
    panels.forEach(function (panel) {
      var active = panel.dataset.modePanel === mode;
      panel.hidden = !active;
      // Only the visible panel's fields are submitted, so hidden inputs never block the browser.
      panel.querySelectorAll("input, textarea, select").forEach(function (input) { input.disabled = !active; });
      if (active && animate && window.gsap && !reduce) {
        gsap.fromTo(panel, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out", clearProps: "transform" });
      }
    });
  }
  radios.forEach(function (r) { r.addEventListener("change", function () { applyMode(true); }); });
  applyMode(false);

  // Re-enable everything just before submit so Django receives management forms for both paths.
  form.addEventListener("submit", function () {
    form.querySelectorAll("[name$='-TOTAL_FORMS'], [name$='-INITIAL_FORMS'], [name$='-MIN_NUM_FORMS'], [name$='-MAX_NUM_FORMS']").forEach(function (i) { i.disabled = false; });
    var btn = form.querySelector("[data-apply-submit]");
    if (btn) btn.classList.add("is-loading");
  });

  // Formset rows
  function renumber(list) {
    Array.prototype.slice.call(list.querySelectorAll("[data-formset-item]")).forEach(function (item, i) {
      var n = item.querySelector("[data-formset-number]");
      if (n) n.textContent = String(i + 1);
    });
  }

  form.querySelectorAll("[data-formset-add]").forEach(function (button) {
    var prefix = button.dataset.formsetAdd;
    var list = form.querySelector('[data-formset-list="' + prefix + '"]');
    var template = form.querySelector('[data-formset-template="' + prefix + '"]');
    var totalInput = form.querySelector('[name="' + prefix + '-TOTAL_FORMS"]');
    var max = parseInt(button.dataset.max || "10", 10);

    function sync() { button.hidden = parseInt(totalInput.value, 10) >= max; }
    sync();

    button.addEventListener("click", function () {
      var index = parseInt(totalInput.value, 10);
      if (index >= max) return;
      var html = template.innerHTML.replace(/__prefix__/g, String(index));
      var wrapper = document.createElement("div");
      wrapper.innerHTML = html.trim();
      var item = wrapper.firstElementChild;
      list.appendChild(item);
      totalInput.value = String(index + 1);
      renumber(list);
      sync();
      if (window.gsap && !reduce) gsap.fromTo(item, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.5, ease: "power3.out", clearProps: "transform" });
      var first = item.querySelector("input, textarea");
      if (first) first.focus();

      var remove = item.querySelector("[data-formset-remove]");
      if (remove) {
        remove.addEventListener("click", function () {
          // Only the last added row can be removed cleanly without renumbering Django field names.
          var items = list.querySelectorAll("[data-formset-item]");
          if (items[items.length - 1] !== item) {
            item.querySelectorAll("input, textarea, select").forEach(function (input) {
              if (input.type === "checkbox") input.checked = false; else input.value = "";
            });
            return;
          }
          item.remove();
          totalInput.value = String(parseInt(totalInput.value, 10) - 1);
          renumber(list);
          sync();
        });
      }
    });
  });

  // Client-side file checks for faster feedback (the server validates the file contents too)
  var cv = form.querySelector('input[type="file"][name="cv"]');
  if (cv) {
    cv.setAttribute("accept", ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document");
    cv.addEventListener("change", function () {
      var file = cv.files[0];
      var field = cv.closest(".field");
      var existing = field.querySelector("[data-client-error]");
      if (existing) existing.remove();
      if (!file) return;
      var message = "";
      if (!/\.(pdf|docx)$/i.test(file.name)) message = "Please choose a PDF or DOCX file.";
      else if (file.size > 5 * 1024 * 1024) message = "This file is larger than 5 MB.";
      if (message) {
        var p = document.createElement("p");
        p.className = "field__error";
        p.setAttribute("data-client-error", "");
        p.setAttribute("role", "alert");
        p.textContent = message;
        field.appendChild(p);
        cv.value = "";
      }
    });
  }
})();
