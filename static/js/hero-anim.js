/* Zencraft Solution: the scroll-controlled animation behind the home-page hero.

   The hero pins under the header and scroll position picks a frame from a WebP sequence drawn on
   a canvas; scrolling up plays it backwards. Five HTML chapter labels follow the scenes. The
   canvas is decoration: it is aria-hidden, and the headline and chapters carry the meaning.

   Whenever the animation cannot or should not run -- reduced motion, a slow connection, no GSAP,
   frames that will not download -- the hero stays as the server drew it: a still picture with
   all five chapters lit. Loaded only on the home page, only when the frames exist
   (apps/core/hero_anim.py). No inline script and no new library. */
(function () {
  "use strict";

  var DESKTOP = "(min-width: 768px)";
  var PIN_DESKTOP = 3;     // viewport heights of scroll the pinned hero consumes
  var PIN_MOBILE = 1.8;
  var SCRUB = 0.6;
  var MAX_DPR = 2;
  var STRIDE = 4;          // first pass loads every 4th frame, so scrubbing works early
  var PARALLEL = 6;        // downloads in flight at once
  var MAX_FAILED = 0.3;    // beyond this share of failed frames, give up and keep the still

  var section = document.querySelector("[data-hero-anim]");
  if (!section) return;
  var stage = section.querySelector("[data-ha-stage]");
  var canvas = section.querySelector("[data-ha-canvas]");
  var bar = section.querySelector("[data-ha-bar]");
  var chapters = Array.prototype.slice.call(section.querySelectorAll("[data-ha-chapter]"));
  var source = document.getElementById("hero-anim-frames");
  if (!stage || !canvas || !source || !chapters.length) return;

  var data;
  try { data = JSON.parse(source.textContent); } catch (e) { return; }
  if (!data || !data.desktop || !data.mobile) return;

  var starts = chapters.map(function (c) { return parseFloat(c.getAttribute("data-ha-chapter")) || 0; });

  function slowConnection() {
    var net = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    return !!net && (net.saveData || /^(slow-2g|2g|3g)$/.test(net.effectiveType || ""));
  }

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduce.matches || slowConnection() || !window.gsap || !window.ScrollTrigger) return;

  var gsap = window.gsap;
  var ScrollTrigger = window.ScrollTrigger;
  gsap.registerPlugin(ScrollTrigger);
  section.classList.add("ha--live");

  var context = canvas.getContext("2d", { alpha: false });

  /* One screen size of frames. Frame 1 first (it is the poster, so the canvas matches what is
     already on screen), then every STRIDE-th frame, then the gaps: a quick scrub early on shows
     a coarse but complete animation rather than stalling at the first missing frame. Loading
     pauses while the tab is hidden. */
  function Sequence(urls, onReady, onFail) {
    var images = new Array(urls.length);
    var ready = new Array(urls.length);
    var order = [0];
    var i;
    for (i = STRIDE; i < urls.length; i += STRIDE) order.push(i);
    if (order[order.length - 1] !== urls.length - 1) order.push(urls.length - 1);
    for (i = 1; i < urls.length; i++) if (order.indexOf(i) === -1) order.push(i);

    var next = 0;
    var inFlight = 0;
    var failed = 0;
    var stopped = false;

    function pump() {
      while (!stopped && !document.hidden && inFlight < PARALLEL && next < order.length) load(order[next++]);
    }

    function load(index) {
      var img = new Image();
      inFlight += 1;
      img.decoding = "async";
      img.addEventListener("load", function () {
        inFlight -= 1;
        if (stopped) return;
        images[index] = img;
        ready[index] = true;
        onReady(index);
        pump();
      });
      img.addEventListener("error", function () {
        inFlight -= 1;
        failed += 1;
        if (stopped) return;
        if (failed > urls.length * MAX_FAILED) { onFail(); return; }
        pump();
      });
      img.src = urls[index];
    }

    function onVisibility() { if (!document.hidden) pump(); }
    document.addEventListener("visibilitychange", onVisibility);

    return {
      length: urls.length,
      start: pump,
      /* The loaded frame nearest to i, looking both ways, or null before anything has arrived. */
      nearest: function (index) {
        if (ready[index]) return images[index];
        for (var d = 1; d < urls.length; d++) {
          if (index - d >= 0 && ready[index - d]) return images[index - d];
          if (index + d < urls.length && ready[index + d]) return images[index + d];
        }
        return null;
      },
      stop: function () {
        stopped = true;
        document.removeEventListener("visibilitychange", onVisibility);
      }
    };
  }

  function headerHeight() {
    var header = document.querySelector(".site-header");
    return header ? header.offsetHeight : 0;
  }

  function build(isDesktop) {
    var wanted = 0;
    var drawn = null;
    var queued = false;
    var active = -1;

    var frames = Sequence(isDesktop ? data.desktop.frames : data.mobile.frames, function (index) {
      if (index === 0) resize();
      schedule();
    }, giveUp);

    function resize() {
      var box = canvas.getBoundingClientRect();
      if (!box.width || !box.height) return;
      var dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      var w = Math.round(box.width * dpr);
      var h = Math.round(box.height * dpr);
      if (canvas.width === w && canvas.height === h) return;
      canvas.width = w;
      canvas.height = h;
      drawn = null;
      schedule();
    }

    /* Drawing happens at most once per animation frame, and only when the picture changes. */
    function schedule() {
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(draw);
    }

    /* "cover": the frame fills the canvas and the overflow is cropped, centred. */
    function draw() {
      queued = false;
      var img = frames.nearest(wanted);
      if (!img || !canvas.width || img === drawn) return;
      var scale = Math.max(canvas.width / img.naturalWidth, canvas.height / img.naturalHeight);
      var w = img.naturalWidth * scale;
      var h = img.naturalHeight * scale;
      context.drawImage(img, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
      if (!drawn) section.classList.add("ha--drawn");
      drawn = img;
    }

    function chapterAt(progress) {
      var current = 0;
      for (var i = 0; i < starts.length; i++) if (progress >= starts[i]) current = i;
      if (current === active) return;
      active = current;
      chapters.forEach(function (c, i) {
        c.classList.toggle("is-active", i === current);
        if (i === current) c.setAttribute("aria-current", "step");
        else c.removeAttribute("aria-current");
      });
    }

    var trigger = ScrollTrigger.create({
      trigger: stage,
      /* The hero sits directly under the sticky header, so it pins from the very first pixel. */
      start: function () { return "top " + headerHeight() + "px"; },
      end: function () { return "+=" + Math.round(window.innerHeight * (isDesktop ? PIN_DESKTOP : PIN_MOBILE)); },
      pin: true,
      scrub: SCRUB,
      invalidateOnRefresh: true,
      /* Measured before everything below it: every other trigger on the page sits under this
         pin's spacing (see the same note in exploded.js). */
      refreshPriority: 2,
      onRefresh: resize,
      onUpdate: function (self) {
        wanted = Math.min(frames.length - 1, Math.round(self.progress * (frames.length - 1)));
        if (bar) bar.style.transform = "scaleX(" + self.progress.toFixed(4) + ")";
        chapterAt(self.progress);
        schedule();
      }
    });

    ScrollTrigger.sort();
    ScrollTrigger.refresh();
    chapterAt(0);

    /* The poster is already on screen, so the rest of the frames wait for the page to finish
       loading rather than compete with the fonts and the headline. */
    if (document.readyState === "complete") frames.start();
    else window.addEventListener("load", frames.start);

    return function () {
      frames.stop();
      window.removeEventListener("load", frames.start);
      trigger.kill(true);
      if (bar) bar.style.transform = "";
      chapters.forEach(function (c, i) {
        c.classList.toggle("is-active", i === 0);
        c.removeAttribute("aria-current");
      });
    };
  }

  /* Crossing the breakpoint swaps in the other frame set and pin length. */
  var mm = gsap.matchMedia();
  mm.add({ desktop: DESKTOP, mobile: "(max-width: 767px)" }, function (ctx) {
    return build(!!ctx.conditions.desktop);
  });

  /* Frames that will not download, or reduced motion switched on mid-visit: back to the still,
     with the pin gone too. */
  var gaveUp = false;
  function giveUp() {
    if (gaveUp) return;
    gaveUp = true;
    mm.revert();
    section.classList.remove("ha--live", "ha--drawn");
    ScrollTrigger.sort();
    ScrollTrigger.refresh();
  }
  var onReduce = function (e) { if (e.matches) giveUp(); };
  if (reduce.addEventListener) reduce.addEventListener("change", onReduce);
  else if (reduce.addListener) reduce.addListener(onReduce);
})();
