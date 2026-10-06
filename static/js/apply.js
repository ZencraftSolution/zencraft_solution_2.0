/* Job application: walk through the steps, switch between CV upload and manual CV entry,
   and add repeatable formset rows. Without JavaScript every step is simply shown at once. */
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

  // One step at a time, with the markers above the form kept in step.
  var stepPanels = Array.prototype.slice.call(form.querySelectorAll("[data-step-panel]"));
  var markers = Array.prototype.slice.call(document.querySelectorAll("[data-step-marker]"));
  var nextBtn = form.querySelector("[data-step-next]");
  var submitBtn = form.querySelector("[data-apply-submit]");
  var backLink = form.querySelector("[data-step-back]");
  var emailStep = form.dataset.emailStep;
  var stepList = document.querySelector("[data-steps]");
  var numbers = stepPanels.map(function (panel) { return parseInt(panel.dataset.stepPanel, 10); });
  var firstStep = numbers[0];
  var lastStep = numbers[numbers.length - 1];
  var step = parseInt(form.dataset.startStep, 10) || firstStep;

  function markSteps() {
    markers.forEach(function (marker) {
      var n = parseInt(marker.dataset.stepMarker, 10);
      var state = n < step ? "done" : n === step ? "current" : "todo";
      marker.className = "step is-" + state;
      if (state === "current") marker.setAttribute("aria-current", "step");
      else marker.removeAttribute("aria-current");
      var dot = marker.querySelector(".step__dot");
      if (dot) dot.innerHTML = state === "done" ? '<i class="ph ph-check"></i>' : String(n);
      var state_text = marker.querySelector("[data-step-state]");
      if (state_text) state_text.textContent = state === "done" ? "Completed" : state === "current" ? "Current step" : "Not started";
    });
  }

  function cvSummary() {
    if (currentMode() !== "cv") return "Experience filled in here";
    var file = form.querySelector('input[type="file"][name="cv"]');
    return file && file.files && file.files[0] ? file.files[0].name : "No CV attached yet";
  }

  function fillReview() {
    var list = form.querySelector("[data-review]");
    if (!list) return;
    var rows = [
      ["Email", (form.querySelector('[name="email"]') || {}).value],
      ["Name", (form.querySelector('[name="full_name"]') || {}).value],
      ["Phone", (form.querySelector('[name="phone"]') || {}).value],
      ["Applying with", cvSummary()]
    ];
    list.innerHTML = "";
    rows.forEach(function (row) {
      if (!row[1]) return;
      var li = document.createElement("li");
      var label = document.createElement("span");
      label.textContent = row[0];
      var value = document.createElement("strong");
      value.textContent = row[1];
      li.appendChild(label);
      li.appendChild(value);
      list.appendChild(li);
    });
    list.hidden = !list.children.length;
  }

  function showStep(n, animate) {
    step = n;
    stepPanels.forEach(function (panel) {
      var active = parseInt(panel.dataset.stepPanel, 10) === n;
      panel.hidden = !active;
      if (active && animate && window.gsap && !reduce) {
        gsap.fromTo(panel, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.5, ease: "power3.out", clearProps: "transform" });
      }
    });
    if (nextBtn) nextBtn.hidden = n === lastStep;
    if (submitBtn) submitBtn.hidden = n !== lastStep;
    if (backLink) backLink.innerHTML = n === firstStep ? '<i class="ph ph-arrow-left"></i> Back to step 1' : '<i class="ph ph-arrow-left"></i> Back';
    if (n === lastStep) fillReview();
    markSteps();
  }

  // Scrolling to the markers rather than the form keeps the progress visible on every move.
  function scrollToSteps() {
    (stepList || form).scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }

  function fieldError(field, message) {
    var wrapper = field.closest(".field");
    if (!wrapper) return;
    var existing = wrapper.querySelector("[data-client-error]");
    if (existing) existing.remove();
    if (!message) return;
    var note = document.createElement("p");
    note.className = "field__error";
    note.setAttribute("data-client-error", "");
    note.setAttribute("role", "alert");
    note.textContent = message;
    wrapper.appendChild(note);
  }

  function stepIsValid() {
    var panel = stepPanels.filter(function (p) { return parseInt(p.dataset.stepPanel, 10) === step; })[0];
    if (!panel) return true;
    var fields = Array.prototype.slice.call(panel.querySelectorAll("input, select, textarea"));
    for (var i = 0; i < fields.length; i++) {
      var field = fields[i];
      if (field.disabled || field.type === "hidden" || field.offsetParent === null) continue;
      if (!field.checkValidity()) {
        field.reportValidity();
        return false;
      }
    }
    // The CV is only required on the upload path, which the browser cannot know on its own.
    var file = panel.querySelector('input[type="file"][name="cv"]');
    if (file && !file.disabled && currentMode() === "cv" && !file.files.length) {
      fieldError(file, "Attach your CV, or switch to filling it in manually.");
      file.focus();
      return false;
    }
    if (file) fieldError(file, "");
    return true;
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", function () {
      if (!stepIsValid()) return;
      showStep(Math.min(step + 1, lastStep), true);
      scrollToSteps();
    });
  }
  if (backLink) {
    backLink.addEventListener("click", function (event) {
      if (step === firstStep) return; // the link goes back to the email step
      event.preventDefault();
      showStep(step - 1, true);
      scrollToSteps();
    });
  }
  if (stepPanels.length) showStep(step, false);

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
