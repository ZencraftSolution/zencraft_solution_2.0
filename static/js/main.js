/* Zencraft Solution: shared UI and motion system.
   Motion tokens are defined once here so every page inherits the same character:
   slow, well-eased entrances; transform and opacity only; nothing hidden if GSAP fails. */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduceQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

  var MOTION = {
    ease: { enter: "power3.out", move: "power2.inOut", spring: "elastic.out(1, 0.65)" },
    dur: { fast: 0.3, base: 0.6, slow: 1.2 },
    stagger: 0.08,
  };
  window.ZC_MOTION = MOTION;

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }
  function motionAllowed() { return !reduceQuery.matches && !!window.gsap; }

  /* Currency toggle ---------------------------------------------------- */
  function initCurrency() {
    var buttons = $$("[data-currency]").filter(function (b) { return b.tagName === "BUTTON"; });
    function apply(code) {
      if (code === "usd") root.setAttribute("data-currency", "usd");
      else root.removeAttribute("data-currency");
      buttons.forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.currency === code)); });
      try { localStorage.setItem("zc-currency", code); } catch (e) {}
      document.dispatchEvent(new CustomEvent("zc:currency", { detail: code }));
    }
    buttons.forEach(function (b) { b.addEventListener("click", function () { apply(b.dataset.currency); }); });
    apply(root.getAttribute("data-currency") === "usd" ? "usd" : "npr");
  }

  /* Navigation --------------------------------------------------------- */
  function initMenus() {
    $$("[data-menu]").forEach(function (item) {
      var trigger = $(".nav__trigger", item);
      var timer;
      function set(open) {
        item.classList.toggle("is-open", open);
        trigger.setAttribute("aria-expanded", String(open));
      }
      trigger.addEventListener("click", function () { set(!item.classList.contains("is-open")); });
      if (window.matchMedia("(hover: hover)").matches) {
        item.addEventListener("mouseenter", function () { clearTimeout(timer); set(true); });
        item.addEventListener("mouseleave", function () { timer = setTimeout(function () { set(false); }, 160); });
      }
      document.addEventListener("keydown", function (e) { if (e.key === "Escape" && item.classList.contains("is-open")) { set(false); trigger.focus(); } });
      document.addEventListener("click", function (e) { if (!item.contains(e.target)) set(false); });
    });

    var toggle = $("[data-menu-toggle]");
    var menu = $("#mobile-menu");
    if (toggle && menu) {
      var setMenu = function (open) {
        menu.classList.toggle("is-open", open);
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
        toggle.innerHTML = open ? '<i class="ph ph-x" aria-hidden="true"></i>' : '<i class="ph ph-list" aria-hidden="true"></i>';
        document.body.style.overflow = open ? "hidden" : "";
      };
      toggle.addEventListener("click", function () { setMenu(!menu.classList.contains("is-open")); });
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && menu.classList.contains("is-open")) { setMenu(false); toggle.focus(); }
      });
      // Resizing to the desktop breakpoint hides the panel in CSS; keep body scroll and ARIA in step.
      var desktop = window.matchMedia("(min-width: 1140px)");
      var onBreakpoint = function (e) { if (e.matches) setMenu(false); };
      if (desktop.addEventListener) desktop.addEventListener("change", onBreakpoint);
      else if (desktop.addListener) desktop.addListener(onBreakpoint);
    }
  }

  /* Toasts ------------------------------------------------------------- */
  function initToasts() {
    $$(".toast").forEach(function (toast) {
      var remove = function () { toast.remove(); };
      var btn = $("[data-dismiss-toast]", toast);
      if (btn) btn.addEventListener("click", remove);
      setTimeout(remove, 7000);
    });
  }

  /* Newsletter (progressive enhancement) --------------------------------- */
  function initNewsletter() {
    $$("[data-newsletter]").forEach(function (form) {
      var msg = form.parentElement.querySelector("[data-newsletter-msg]");
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var btn = form.querySelector("button");
        btn.disabled = true;
        fetch(form.action, { method: "POST", body: new FormData(form), headers: { "x-requested-with": "fetch" } })
          .then(function (r) { return r.json().catch(function () { return { ok: false, message: "Please try again later." }; }); })
          .then(function (data) {
            if (msg) { msg.textContent = data.message; msg.style.color = data.ok ? "" : "#ffb4ab"; }
            if (data.ok) form.reset();
          })
          .catch(function () { if (msg) msg.textContent = "Network error. Please try again."; })
          .finally(function () { btn.disabled = false; });
      });
    });
  }

  /* Industries image stage ----------------------------------------------- */
  function initIndustries() {
    var wrap = $("[data-industries]");
    if (!wrap) return;
    var rows = $$("[data-industry-index]", wrap);
    var imgs = $$(".industry-stage img", wrap);
    rows.forEach(function (row) {
      var activate = function () {
        var idx = Number(row.dataset.industryIndex);
        rows.forEach(function (r) { r.classList.toggle("is-active", r === row); });
        imgs.forEach(function (img, i) { img.classList.toggle("is-active", i === idx); });
      };
      row.addEventListener("mouseenter", activate);
      row.addEventListener("focusin", activate);
    });
  }

  /* Testimonials crossfade ------------------------------------------------ */
  function initQuotes() {
    var stage = $("[data-quotes]");
    if (!stage) return;
    var items = $$(".quote", stage);
    var count = $("[data-quote-count]");
    if (items.length < 2) { stage.classList.add("quotes--static"); return; }
    var index = 0;
    var timer = null;

    function fit() {
      var tallest = 0;
      items.forEach(function (q) { tallest = Math.max(tallest, q.scrollHeight); });
      stage.style.minHeight = tallest + "px";
    }
    function show(n) {
      var prev = items[index];
      index = (n + items.length) % items.length;
      var next = items[index];
      if (prev === next) return;
      if (motionAllowed()) {
        gsap.to(prev, { autoAlpha: 0, duration: MOTION.dur.base, ease: MOTION.ease.move });
        gsap.fromTo(next, { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: 0.9, delay: 0.15, ease: MOTION.ease.enter });
      }
      prev.classList.remove("is-active");
      next.classList.add("is-active");
      prev.setAttribute("aria-hidden", "true");
      next.setAttribute("aria-hidden", "false");
      if (count) count.textContent = index + 1 + " / " + items.length;
    }
    function start() { if (!reduceQuery.matches) { stop(); timer = setInterval(function () { show(index + 1); }, 7000); } }
    function stop() { if (timer) clearInterval(timer); timer = null; }

    var prevBtn = $("[data-quote-prev]");
    var nextBtn = $("[data-quote-next]");
    if (prevBtn) prevBtn.addEventListener("click", function () { show(index - 1); start(); });
    if (nextBtn) nextBtn.addEventListener("click", function () { show(index + 1); start(); });
    stage.addEventListener("mouseenter", stop);
    stage.addEventListener("mouseleave", start);
    stage.addEventListener("focusin", stop);
    document.addEventListener("visibilitychange", function () { if (document.hidden) stop(); else start(); });
    window.addEventListener("resize", fit);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
    fit();
    start();
  }

  /* Hero slider: industry tabs, framed image, per-slide background ------------ */
  function initHeroSlider() {
    var root = $("[data-hero-slider]");
    if (!root) return;
    var slides = $$("[data-hs-slide]", root);
    var bgs = $$("[data-hs-bg]", root);
    var tabs = $$("[data-hs-tab]", root);
    var link = $("[data-hs-link]", root);
    var linkText = $("[data-hs-link-text]", root);
    var dataEl = document.getElementById("hero-slides");
    var data = [];
    try { data = JSON.parse(dataEl.textContent); } catch (e) {}
    if (slides.length < 2) return;

    var DELAY = 6.5;
    var index = 0;
    var paused = false;
    var timer = null;
    var progress = null;

    function animated() { return motionAllowed() && root.ownerDocument.documentElement.classList.contains("js-motion"); }

    function runProgress() {
      if (progress) progress.kill();
      tabs.forEach(function (t) { var bar = $(".hs__tab-bar", t); if (bar) bar.style.transform = ""; });
      if (!animated()) return;
      var bar = $(".hs__tab-bar", tabs[index]);
      if (!bar) return;
      progress = gsap.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: DELAY, ease: "none", paused: paused });
    }

    function schedule() {
      clearTimeout(timer);
      if (paused || reduceQuery.matches) return;
      timer = setTimeout(function () { go(index + 1, 1); }, DELAY * 1000);
    }

    function go(next, direction) {
      next = (next + slides.length) % slides.length;
      if (next === index) return;
      var from = slides[index];
      var to = slides[next];
      direction = direction || (next > index ? 1 : -1);

      if (animated()) {
        gsap.killTweensOf([from, to]);
        gsap.to(from, { autoAlpha: 0, x: -40 * direction, scale: 0.98, duration: 0.6, ease: MOTION.ease.move });
        gsap.fromTo(to, { autoAlpha: 0, x: 40 * direction, scale: 0.98 }, { autoAlpha: 1, x: 0, scale: 1, duration: 0.9, delay: 0.12, ease: MOTION.ease.enter });
        var nextImg = $("img", bgs[next]);
        if (nextImg) gsap.fromTo(nextImg, { scale: 1.12 }, { scale: 1.04, duration: DELAY + 1, ease: "none" });
        if (linkText) gsap.fromTo(link, { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: MOTION.dur.base, ease: MOTION.ease.enter });
      } else {
        from.style.opacity = ""; from.style.visibility = "";
        to.style.opacity = ""; to.style.visibility = "";
      }

      from.classList.remove("is-active");
      from.setAttribute("aria-hidden", "true");
      to.classList.add("is-active");
      to.removeAttribute("aria-hidden");
      bgs.forEach(function (bg, i) { bg.classList.toggle("is-active", i === next); });
      tabs.forEach(function (tab, i) {
        var on = i === next;
        tab.classList.toggle("is-active", on);
        tab.setAttribute("aria-selected", String(on));
        tab.tabIndex = on ? 0 : -1;
      });
      if (data[next] && link) {
        link.href = data[next].url;
        if (linkText) linkText.textContent = data[next].link;
      }
      index = next;
      runProgress();
      schedule();
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () { go(i, i > index ? 1 : -1); });
      tab.addEventListener("keydown", function (e) {
        var target = null;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") target = (i + 1) % tabs.length;
        if (e.key === "ArrowLeft" || e.key === "ArrowUp") target = (i - 1 + tabs.length) % tabs.length;
        if (e.key === "Home") target = 0;
        if (e.key === "End") target = tabs.length - 1;
        if (target === null) return;
        e.preventDefault();
        tabs[target].focus();
        go(target, target > i ? 1 : -1);
      });
    });
    var prev = $("[data-hs-prev]", root);
    var next = $("[data-hs-next]", root);
    if (prev) prev.addEventListener("click", function () { go(index - 1, -1); });
    if (next) next.addEventListener("click", function () { go(index + 1, 1); });

    // Swipe on touch devices
    var startX = null;
    var visual = $(".hs__visual", root);
    if (visual) {
      visual.addEventListener("touchstart", function (e) { startX = e.touches[0].clientX; }, { passive: true });
      visual.addEventListener("touchend", function (e) {
        if (startX === null) return;
        var dx = e.changedTouches[0].clientX - startX;
        if (Math.abs(dx) > 40) go(index + (dx < 0 ? 1 : -1), dx < 0 ? 1 : -1);
        startX = null;
      });
    }

    function setPaused(state) {
      paused = state;
      if (progress) { if (state) progress.pause(); else progress.resume(); }
      if (state) clearTimeout(timer);
      else schedule();
    }
    root.addEventListener("mouseenter", function () { setPaused(true); });
    root.addEventListener("mouseleave", function () { setPaused(false); });
    root.addEventListener("focusin", function () { setPaused(true); });
    root.addEventListener("focusout", function (e) { if (!root.contains(e.relatedTarget)) setPaused(false); });
    document.addEventListener("visibilitychange", function () { setPaused(document.hidden); });

    // Warm the next images so crossfades never show a blank frame
    setTimeout(function () {
      data.forEach(function (d) { var a = new Image(); a.src = d.image_url; var b = new Image(); b.src = d.background_url; });
    }, 2500);

    runProgress();
    schedule();
  }

  /* Terminal showcase ------------------------------------------------------ */
  function initTerminal() {
    var el = $("[data-terminal]");
    if (!el) return;
    var source = document.getElementById(el.dataset.terminal);
    if (!source) return;
    var lines;
    try { lines = JSON.parse(source.textContent); } catch (e) { return; }

    function span(cls, text) { var s = document.createElement("span"); if (cls) s.className = cls; s.textContent = text; return s; }
    function lineNode(line, text) {
      var frag = document.createDocumentFragment();
      if (line.t === "prompt") { frag.appendChild(span("terminal__prompt", "$ ")); frag.appendChild(document.createTextNode(text)); }
      else if (line.t === "ok") { frag.appendChild(span("terminal__ok", "[ok] ")); frag.appendChild(document.createTextNode(line.v)); if (line.k) frag.appendChild(span("terminal__dim", "  # " + line.k)); }
      else frag.appendChild(span("terminal__dim", text));
      frag.appendChild(document.createTextNode("\n"));
      return frag;
    }
    var caret = span("terminal__caret", "");

    if (reduceQuery.matches) {
      el.textContent = "";
      lines.forEach(function (l) { el.appendChild(lineNode(l, l.v)); });
      el.appendChild(caret);
      return;
    }

    var started = false;
    var io = new IntersectionObserver(function (entries) {
      if (started || !entries[0].isIntersecting) return;
      started = true;
      io.disconnect();
      el.textContent = "";
      el.appendChild(caret);
      var i = 0;
      (function next() {
        if (i >= lines.length) return;
        var line = lines[i++];
        if (line.t !== "prompt") {
          el.insertBefore(lineNode(line, line.v), caret);
          setTimeout(next, line.t === "ok" ? 140 : 420);
          return;
        }
        var holder = document.createElement("span");
        holder.appendChild(span("terminal__prompt", "$ "));
        var typed = document.createTextNode("");
        holder.appendChild(typed);
        el.insertBefore(holder, caret);
        var c = 0;
        (function type() {
          typed.data = line.v.slice(0, ++c);
          if (c < line.v.length) setTimeout(type, 34 + Math.random() * 40);
          else { el.insertBefore(document.createTextNode("\n"), caret); setTimeout(next, 520); }
        })();
      })();
    }, { threshold: 0.4 });
    io.observe(el);
  }

  /* Job filters with Flip --------------------------------------------------- */
  function initJobFilters() {
    var form = $("[data-job-filters]");
    if (!form) return;
    var list = $("[data-job-list]");
    var empty = $("[data-job-empty]");
    var submit = $("[data-job-submit]", form);
    if (submit) submit.hidden = true;
    var jobs = $$("[data-job]", list);

    function run() {
      var values = {};
      $$("select", form).forEach(function (s) { values[s.name] = s.value; });
      var state = window.Flip && motionAllowed() ? Flip.getState(jobs) : null;
      var visible = 0;
      jobs.forEach(function (job) {
        var match = Object.keys(values).every(function (k) { return !values[k] || job.dataset[k] === values[k]; });
        job.hidden = !match;
        if (match) visible++;
      });
      if (empty) empty.hidden = visible > 0;
      if (state) {
        Flip.from(state, {
          duration: MOTION.dur.base, ease: MOTION.ease.move, absolute: true,
          onEnter: function (els) { return gsap.fromTo(els, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: MOTION.dur.base }); },
          onLeave: function (els) { return gsap.to(els, { opacity: 0, duration: MOTION.dur.fast }); },
        });
      }
      var params = new URLSearchParams();
      Object.keys(values).forEach(function (k) { if (values[k]) params.set(k, values[k]); });
      history.replaceState(null, "", location.pathname + (params.toString() ? "?" + params : ""));
    }
    form.addEventListener("change", run);
  }

  /* Page views for prerendered pages ------------------------------------------
     Chrome and Edge load a page in the background when a visitor hovers a link to it (the
     speculation rules in base.html), so it appears at once on click. That background request is
     not a visit, and PageViewMiddleware skips it; this records the visit when the page is
     actually shown. Pages loaded normally are counted by the middleware and send nothing. */
  function countPrerenderedView() {
    var meta = $('meta[name="zc-pageview"]');
    if (!meta || !navigator.sendBeacon) return;
    var send = function () { navigator.sendBeacon(meta.content, location.pathname + "\n" + document.referrer); };
    if (document.prerendering) {
      document.addEventListener("prerenderingchange", send, { once: true });
      return;
    }
    var nav = performance.getEntriesByType && performance.getEntriesByType("navigation")[0];
    if (nav && nav.activationStart > 0) send();  // shown before this script had run
  }

  /* GSAP choreography ------------------------------------------------------- */
  function initMotion() {
    if (!window.gsap) { root.classList.remove("js-motion"); return; }
    window.__zcMotionReady = true;

    var plugins = [window.ScrollTrigger, window.SplitText, window.Flip].filter(Boolean);
    gsap.registerPlugin.apply(gsap, plugins);
    gsap.defaults({ duration: MOTION.dur.base, ease: MOTION.ease.enter });

    var motionOn = root.classList.contains("js-motion");
    var mm = gsap.matchMedia();

    mm.add({
      reduce: "(prefers-reduced-motion: reduce)",
      motion: "(prefers-reduced-motion: no-preference)",
      desktop: "(min-width: 1024px)",
    }, function (ctx) {
      var c = ctx.conditions;
      if (c.reduce || !motionOn || !window.ScrollTrigger) {
        $$("[data-process]").forEach(function (p) { p.classList.add("process--no-motion"); $$(".process__step", p).forEach(function (s) { s.classList.add("is-lit"); }); });
        gsap.set("[data-reveal], [data-reveal-group] > *, [data-hero-item]", { opacity: 1 });
        return;
      }
      var observers = [];
      heroIntro();
      reveals(observers);
      counters(observers);
      processLines(c.desktop, observers);
      var undoCases = casesGallery(c.desktop);
      return function () {
        observers.forEach(function (o) { o.disconnect(); });
        if (undoCases) undoCases();
      };
    });

    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { if (window.ScrollTrigger) ScrollTrigger.refresh(); });
    window.addEventListener("load", function () { if (window.ScrollTrigger) ScrollTrigger.refresh(); });
  }

  function heroIntro() {
    var heading = $("[data-split]");
    var tl = gsap.timeline({ defaults: { ease: MOTION.ease.enter } });
    if (heading && window.SplitText) {
      SplitText.create(heading, {
        type: "lines", mask: "lines", linesClass: "split-line", autoSplit: true,
        onSplit: function (self) {
          return gsap.from(self.lines, { yPercent: 115, duration: MOTION.dur.slow, stagger: MOTION.stagger, ease: MOTION.ease.enter });
        },
      });
    }
    var items = $$("[data-hero-item]");
    if (items.length) tl.fromTo(items, { opacity: 0, y: 22 }, { opacity: 1, y: 0, duration: 0.9, stagger: MOTION.stagger, clearProps: "transform" }, 0.25);
    var visual = $("[data-hero-visual]");
    if (visual) tl.fromTo(visual, { opacity: 0, scale: 0.96 }, { opacity: 1, scale: 1, duration: MOTION.dur.slow, clearProps: "transform" }, 0.2);
  }

  /* Calls start() once, when the top of `el` rises above `line` (a fraction of the window
     height, as in ScrollTrigger's "top 88%"), or at once if it is already above the window.

     An IntersectionObserver rather than a ScrollTrigger: ScrollTrigger starts a tween inside its
     scroll handler, and the tween's first frame moves the element right there, which Firefox
     reports as a "scroll-linked positioning effect". Observer callbacks run outside scroll
     events, so starting an animation from one is not scroll-linked. */
  function whenInView(el, line, start, observers) {
    var observer = new IntersectionObserver(function (entries) {
      var entry = entries[entries.length - 1];
      if (entry.isIntersecting || entry.boundingClientRect.bottom < 0) {
        observer.disconnect();
        start();
      }
    }, { rootMargin: "0px 0px -" + Math.round((1 - line) * 100) + "% 0px" });
    observer.observe(el);
    observers.push(observer);
  }

  function reveals(observers) {
    $$("[data-reveal]").forEach(function (el) {
      var tween = gsap.fromTo(el, { opacity: 0, y: 34 }, { opacity: 1, y: 0, duration: 0.9, clearProps: "transform", paused: true });
      whenInView(el, 0.88, function () { tween.play(); }, observers);
    });
    $$("[data-reveal-group]").forEach(function (group) {
      var items = Array.prototype.slice.call(group.children);
      if (!items.length) return;
      var wave = group.hasAttribute("data-grid-wave");
      var tween = gsap.fromTo(items, { opacity: 0, y: 28 }, {
        opacity: 1, y: 0, duration: 0.8, clearProps: "transform", paused: true,
        stagger: wave ? { each: MOTION.stagger, grid: "auto", from: "start" } : MOTION.stagger,
      });
      whenInView(group, 0.86, function () { tween.play(); }, observers);
    });
  }

  function counters(observers) {
    $$("[data-count]").forEach(function (el) {
      var end = parseFloat(el.dataset.count);
      if (isNaN(end)) return;
      var decimals = parseInt(el.dataset.decimals || "0", 10);
      var from = decimals ? Math.max(0, end - 4) : 0;
      var obj = { v: from };
      var format = function (v) { return decimals ? v.toFixed(decimals) : Math.round(v).toLocaleString("en-IN"); };
      el.textContent = format(from);
      whenInView(el, 0.92, function () {
        gsap.to(obj, { v: end, duration: 1.8, ease: "power2.out", onUpdate: function () { el.textContent = format(obj.v); } });
      }, observers);
    });
  }

  /* The line through the process steps fills once, on its own clock, when it comes into view,
     lighting each step as it reaches it. Started by whenInView, not by scrolling, for the reason
     given there. */
  function processLines(desktop, observers) {
    $$("[data-process]").forEach(function (p) {
      var fill = $(".process__fill", p);
      var steps = $$(".process__step", p);
      if (!fill || !steps.length) return;
      var horizontal = desktop && p.classList.contains("process--horizontal");
      var prop = horizontal ? "scaleX" : "scaleY";
      var from = {}; from[prop] = 0;
      var to = { ease: "power1.inOut", duration: 0.35 * steps.length, paused: true };
      to[prop] = 1;
      to.onUpdate = function () {
        var progress = this.progress();
        var n = steps.length - 1 || 1;
        steps.forEach(function (s, i) { s.classList.toggle("is-lit", progress >= i / n - 0.02); });
      };
      var tween = gsap.fromTo(fill, from, to);
      whenInView(p, horizontal ? 0.78 : 0.70, function () { tween.play(); }, observers);
    });
  }

  function casesGallery(desktop) {
    var section = $("[data-cases]");
    if (!section || !desktop) return null;
    var track = $("[data-cases-track]", section);
    if (!track) return null;
    section.classList.add("is-pinned");
    var distance = function () { return Math.max(0, track.scrollWidth - window.innerWidth); };
    if (distance() < 40) { section.classList.remove("is-pinned"); return null; }
    gsap.to(track, {
      x: function () { return -distance(); },
      ease: "none",
      scrollTrigger: {
        trigger: section,
        start: "top top",
        end: function () { return "+=" + distance(); },
        pin: true,
        scrub: 1,
        invalidateOnRefresh: true,
      },
    });
    return function () { section.classList.remove("is-pinned"); };
  }

  function boot() {
    initCurrency();
    initMenus();
    initToasts();
    initNewsletter();
    initIndustries();
    initTerminal();
    initMotion();
    initHeroSlider();
    initQuotes();
    initJobFilters();
    countPrerenderedView();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
