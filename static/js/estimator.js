/* Project estimator: guided multi-step flow, admin-configurable options, lead capture and animated result. */
(function () {
  "use strict";

  var root = document.querySelector("[data-estimator]");
  if (!root) return;

  var form = root.querySelector("[data-estimator-form]");
  var steps = Array.prototype.slice.call(form.querySelectorAll("[data-step]"));
  var total = steps.length;
  var backBtn = form.querySelector("[data-back]");
  var nextBtn = form.querySelector("[data-next]");
  var submitBtn = form.querySelector("[data-submit]");
  var nav = form.querySelector("[data-nav]");
  var progress = form.querySelector("[data-progress]");
  var progressText = form.querySelector("[data-progress-text]");
  var progressBar = form.querySelector("[role=progressbar]");
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var M = window.ZC_MOTION || { ease: { enter: "power3.out", move: "power2.inOut" }, dur: { fast: 0.3, base: 0.6 } };

  var sessionId;
  try {
    sessionId = sessionStorage.getItem("zc-est-session");
    if (!sessionId) {
      sessionId = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2);
      sessionStorage.setItem("zc-est-session", sessionId);
    }
  } catch (e) { sessionId = String(Date.now()); }

  var config = { project_types: [] };
  var current = 0;
  var seenSteps = {};
  var lastEstimate = null;

  function csrf() { var el = form.querySelector("[name=csrfmiddlewaretoken]"); return el ? el.value : ""; }

  function track(step) {
    if (seenSteps[step]) return;
    seenSteps[step] = true;
    fetch(root.dataset.eventUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf(), "x-requested-with": "fetch" },
      body: JSON.stringify({ step: step, session_id: sessionId }),
      keepalive: true,
    }).catch(function () {});
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { node.appendChild(c); });
    return node;
  }

  function tile(type, name, value, label, help, icon) {
    var input = el("input", { type: type, name: name, value: value });
    var body = el("span", { class: "tile__body" }, [
      icon ? el("i", { class: "ph ph-" + icon, "aria-hidden": "true" }) : document.createTextNode(""),
      el("strong", { text: label }),
    ].concat(help ? [el("span", { text: help })] : []));
    return el("label", { class: "tile" }, [input, body]);
  }

  function renderTypes() {
    var holder = form.querySelector("[data-types]");
    holder.textContent = "";
    config.project_types.forEach(function (t) {
      holder.appendChild(tile("radio", "project_type", t.key, t.label, t.description, t.icon));
    });
  }

  function renderFeatures() {
    var holder = form.querySelector("[data-features]");
    var type = selectedType();
    var previously = values("feature");
    holder.textContent = "";
    if (!type) return;
    type.features.forEach(function (f) {
      var t = tile("checkbox", "feature", f.key, f.label, f.help, null);
      if (previously.indexOf(f.key) !== -1) t.querySelector("input").checked = true;
      holder.appendChild(t);
    });
  }

  function values(name) {
    return Array.prototype.slice.call(form.querySelectorAll('[name="' + name + '"]:checked')).map(function (i) { return i.value; });
  }
  function value(name) { var v = values(name); return v.length ? v[0] : ""; }
  function selectedType() {
    var key = value("project_type");
    return config.project_types.filter(function (t) { return t.key === key; })[0] || null;
  }
  function labelFor(input) { return input.closest(".tile").querySelector("strong").textContent; }
  function labels(name) {
    return Array.prototype.slice.call(form.querySelectorAll('[name="' + name + '"]:checked')).map(labelFor);
  }

  function answers() {
    return {
      project_type: value("project_type"),
      features: values("feature"),
      platforms: values("platform"),
      timeline: value("timeline") || "standard",
      team_preference: value("team_preference") || "unsure",
      design_needs: value("design_needs") || "existing",
      session_id: sessionId,
    };
  }

  function updateSummary() {
    var set = function (key, text) { var n = root.querySelector('[data-sum="' + key + '"]'); if (n) n.textContent = text; };
    var type = selectedType();
    set("type", type ? type.label : "Not chosen yet");
    var f = labels("feature");
    set("features", f.length ? f.length + " selected: " + f.slice(0, 4).join(", ") + (f.length > 4 ? " and more" : "") : "None selected");
    var p = labels("platform");
    set("platforms", p.length ? p.join(", ") : "None selected");
    set("timeline", (labels("timeline")[0] || "Standard pace") + ", " + (labels("team_preference")[0] || "Not sure yet").toLowerCase());
    set("design", labels("design_needs")[0] || "I have designs");
  }

  function stepError(step, show) {
    var err = step.querySelector("[data-step-error]");
    if (err) err.hidden = !show;
  }

  function validate(index) {
    var step = steps[index];
    if (index === 0 && !value("project_type")) { stepError(step, true); return false; }
    if (index === 2 && !values("platform").length) { stepError(step, true); return false; }
    stepError(step, false);
    return true;
  }

  function updateChrome() {
    var n = current + 1;
    progress.style.transform = "scaleX(" + n / total + ")";
    progressText.textContent = "Step " + n + " of " + total;
    progressBar.setAttribute("aria-valuenow", String(n));
    backBtn.hidden = current === 0;
    nextBtn.hidden = current === total - 1;
    submitBtn.hidden = current !== total - 1;
  }

  function show(index, direction) {
    var from = steps[current];
    var to = steps[index];
    var finish = function () {
      from.hidden = true;
      to.hidden = false;
      current = index;
      updateChrome();
      track(index + 1);
      var heading = to.querySelector("h2");
      if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus({ preventScroll: true }); }
      var top = form.getBoundingClientRect().top + window.scrollY - 96;
      if (window.scrollY > top) window.scrollTo({ top: top, behavior: reduce ? "auto" : "smooth" });
      if (window.gsap && !reduce) {
        gsap.fromTo(to, { opacity: 0, x: 28 * direction }, { opacity: 1, x: 0, duration: M.dur.base, ease: M.ease.enter, clearProps: "transform" });
      }
    };
    if (from === to) return finish();
    if (window.gsap && !reduce) {
      gsap.to(from, { opacity: 0, x: -24 * direction, duration: M.dur.fast, ease: M.ease.move, onComplete: function () { gsap.set(from, { clearProps: "all" }); finish(); } });
    } else {
      finish();
    }
  }

  nextBtn.addEventListener("click", function () {
    if (!validate(current)) return;
    if (current === 0) renderFeatures();
    show(Math.min(current + 1, total - 1), 1);
  });
  backBtn.addEventListener("click", function () { show(Math.max(current - 1, 0), -1); });

  form.addEventListener("change", function (e) {
    if (e.target.name === "project_type") { stepError(steps[0], false); renderFeatures(); }
    if (e.target.name === "platform") stepError(steps[2], false);
    updateSummary();
  });

  form.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && e.target.tagName !== "TEXTAREA" && current < total - 1) {
      e.preventDefault();
      nextBtn.click();
    }
  });

  function clearErrors() {
    form.querySelectorAll("[data-error-for]").forEach(function (n) { n.textContent = ""; n.closest(".field").classList.remove("has-error"); });
    form.querySelector("[data-form-error]").hidden = true;
  }

  function showErrors(errors) {
    var generic = [];
    Object.keys(errors || {}).forEach(function (key) {
      var msg = [].concat(errors[key]).join(" ");
      var target = form.querySelector('[data-error-for="' + key + '"]');
      if (target) { target.textContent = msg; target.closest(".field").classList.add("has-error"); }
      else generic.push(msg);
    });
    if (generic.length) {
      form.querySelector("[data-form-error-text]").textContent = generic.join(" ");
      form.querySelector("[data-form-error]").hidden = false;
    }
    var first = form.querySelector(".has-error input, .has-error select, .has-error textarea");
    if (first) first.focus();
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearErrors();
    var name = form.querySelector("[name=name]");
    var email = form.querySelector("[name=email]");
    var consent = form.querySelector("[name=consent]");
    var local = {};
    if (!name.value.trim()) local.name = "Please enter your name.";
    if (!email.value.trim() || !email.checkValidity()) local.email = "Please enter a valid email address.";
    if (!consent.checked) local.consent = "Please confirm you agree so we can prepare your estimate.";
    var doc = form.querySelector("[name=document]").files[0];
    if (doc && doc.size > 5 * 1024 * 1024) local.document = "The file is larger than 5 MB.";
    if (Object.keys(local).length) { showErrors(local); return; }

    var data = new FormData(form);
    ["project_type", "feature", "platform", "timeline", "team_preference", "design_needs"].forEach(function (k) { data.delete(k); });
    data.set("answers", JSON.stringify(answers()));
    if (consent.checked) data.set("consent", "on");

    submitBtn.classList.add("is-loading");
    submitBtn.setAttribute("aria-busy", "true");
    fetch(root.dataset.submitUrl, { method: "POST", body: data, headers: { "X-CSRFToken": csrf(), "x-requested-with": "fetch" } })
      .then(function (res) {
        return res.json().catch(function () { return { ok: false, errors: { __all__: [res.status === 429 ? "Too many attempts. Please wait a few minutes and try again." : "Something went wrong. Please try again."] } }; });
      })
      .then(function (json) {
        if (!json.ok) { showErrors(json.errors || { __all__: [json.error || "Please check the form."] }); return; }
        renderResult(json);
      })
      .catch(function () { showErrors({ __all__: ["Network error. Please check your connection and try again."] }); })
      .finally(function () { submitBtn.classList.remove("is-loading"); submitBtn.removeAttribute("aria-busy"); });
  });

  function renderResult(json) {
    lastEstimate = json.estimate;
    steps.forEach(function (s) { s.hidden = true; });
    nav.hidden = true;
    form.querySelector("[data-progress-wrap]").hidden = true;
    var result = form.querySelector("[data-result]");
    result.hidden = false;
    track(7);

    var est = json.estimate;
    form.querySelector("[data-result-ref]").textContent = json.reference;
    form.querySelector("[data-result-weeks]").textContent = est.weeks_low + " to " + est.weeks_high + " weeks";
    form.querySelector("[data-result-hours]").textContent = est.hours.toLocaleString("en-IN");
    form.querySelector("[data-result-disclaimer]").textContent = est.disclaimer;
    var cta = form.querySelector("[data-result-cta]");
    if (json.consultation_url) cta.href = json.consultation_url;

    var list = form.querySelector("[data-result-team]");
    list.textContent = "";
    est.team.forEach(function (m) {
      var share = m.allocation >= 1 ? (m.allocation % 1 === 0 ? m.allocation + " full-time" : m.allocation + " FTE") : Math.round(m.allocation * 100) + "% time";
      list.appendChild(el("li", {}, [el("span", { text: m.role }), el("span", { text: share })]));
    });

    renderNumbers(true);
    result.focus({ preventScroll: true });
    var top = form.getBoundingClientRect().top + window.scrollY - 96;
    window.scrollTo({ top: top, behavior: reduce ? "auto" : "smooth" });
    if (window.gsap && !reduce) {
      gsap.fromTo(result.children, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.8, stagger: 0.08, ease: M.ease.enter, clearProps: "transform" });
    }
  }

  function groupNPR(n) {
    var s = String(Math.round(n));
    if (s.length <= 3) return s;
    var tail = s.slice(-3);
    var head = s.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
    return head + "," + tail;
  }

  function renderNumbers(animate) {
    if (!lastEstimate) return;
    var est = lastEstimate;
    var usd = document.documentElement.getAttribute("data-currency") === "usd";
    var primary = form.querySelector("[data-result-primary]");
    var secondary = form.querySelector("[data-result-secondary]");
    var lo = usd ? est.low_usd : est.low_npr;
    var hi = usd ? est.high_usd : est.high_npr;
    var fmt = usd
      ? function (v) { return "$" + Math.round(v).toLocaleString("en-US"); }
      : function (v) { return "Rs. " + groupNPR(v); };
    secondary.textContent = usd ? "About " + est.low_npr_display + " to " + est.high_npr_display : "About " + est.low_usd_display + " to " + est.high_usd_display;

    if (animate && window.gsap && !reduce) {
      var counter = { lo: lo * 0.6, hi: hi * 0.6 };
      gsap.to(counter, {
        lo: lo, hi: hi, duration: 1.6, ease: "power2.out",
        onUpdate: function () { primary.textContent = fmt(counter.lo) + " to " + fmt(counter.hi); },
      });
    } else {
      primary.textContent = fmt(lo) + " to " + fmt(hi);
    }
  }

  document.addEventListener("zc:currency", function () { renderNumbers(false); });

  fetch(root.dataset.configUrl)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      config = data;
      renderTypes();
      updateSummary();
      updateChrome();
      track(1);
    })
    .catch(function () {
      form.querySelector("[data-types]").textContent = "The estimator could not load. Please refresh the page or contact us directly.";
    });
})();
