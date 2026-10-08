/* Zencraft Solution: the scroll-driven exploded view on the home page.

   A pinned canvas scrubs through a WebP frame sequence while five HTML labels fade in beside the
   layer they describe. The canvas is decoration: it is aria-hidden, and every word on screen is
   real markup. Whenever the animation cannot or should not run -- reduced motion, no GSAP, a slow
   connection, a thin device, frames that failed to download -- the section switches to a single
   still with all five labels showing, which says the same thing without the scroll.

   Loaded only on the home page, and only when the artwork exists (apps/core/exploded.py).
   No inline script, no new library: GSAP and ScrollTrigger are already on the page. */
(function () {
  "use strict";

  var DESKTOP = "(min-width: 768px)";
  var PIN_DESKTOP = 2.5;   // viewport heights of scroll the pinned stage consumes
  var PIN_MOBILE = 1.5;
  var SCRUB = 0.5;
  var MAX_DPR = 2;         // beyond this the pixels cost more than they show
  var MIN_LOADED = 0.6;    // below this share of frames the sequence would stutter: use the still
  var EARLY = 0.02;        // name a layer just before it settles, not after

  var section = document.querySelector("[data-exploded]");
  if (!section) return;

  var canvas = section.querySelector("[data-exploded-canvas]");
  var stage = section.querySelector("[data-exploded-stage]");
  var labels = Array.prototype.slice.call(section.querySelectorAll("[data-exploded-layer]"));
  var source = document.getElementById("exploded-frames");
  if (!canvas || !stage || !labels.length || !source) return;

  var data;
  try { data = JSON.parse(source.textContent); } catch (e) { return; }
  if (!data || !data.desktop || !data.mobile) return;

  /* Does this visitor get the animation at all? ------------------------------ */

  function thinDevice() {
    var net = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (net) {
      if (net.saveData) return true;
      if (/^(slow-)?2g$/.test(net.effectiveType || "")) return true;
    }
    var cores = navigator.hardwareConcurrency;
    if (typeof cores === "number" && cores > 0 && cores <= 2) return true;
    if (typeof navigator.deviceMemory === "number" && navigator.deviceMemory <= 1) return true;
    return false;
  }

  function showStill() {
    section.classList.add("exploded--static");
    section.classList.remove("exploded--live");
  }

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduce.matches || !window.gsap || !window.ScrollTrigger || thinDevice()) { showStill(); return; }

  var gsap = window.gsap;
  gsap.registerPlugin(window.ScrollTrigger);
  section.classList.add("exploded--live");

  /* The frame sequence ------------------------------------------------------- */

  /* One screen size of frames: images loaded in order, with whatever has arrived drawable at any
     time. A frame still in flight falls back to the nearest earlier one, so scrubbing ahead of
     the download shows a slightly stale picture rather than a blank canvas. */
  function Sequence(variant) {
    /* The build script slows parts of the clip down by listing a frame more than once (see
       scripts/build_exploded_frames.py), so each position maps to one distinct file, downloaded
       once however often it repeats. */
    var urls = [];
    var slot = variant.frames.map(function (url) {
      var at = urls.indexOf(url);
      if (at === -1) { at = urls.length; urls.push(url); }
      return at;
    });
    var images = new Array(urls.length);
    var ready = new Array(urls.length);
    var failed = 0;
    var started = false;
    var onFirst = null;
    var cancelled = false;

    function load(i) {
      var img = new Image();
      images[i] = img;
      img.decoding = "async";
      img.addEventListener("load", function () {
        if (cancelled) return;
        ready[i] = true;
        if (i === 0 && onFirst) onFirst();
      });
      img.addEventListener("error", function () {
        failed += 1;
        if (!cancelled && failed > urls.length * (1 - MIN_LOADED)) giveUp();
      });
      img.src = urls[i];
    }

    return {
      length: slot.length,
      /* The first frame goes out at once so the band is never empty; the rest wait until the
         section is near, because a hundred images is not something to spend on a visitor who
         never scrolls this far. */
      first: function (then) { onFirst = then; load(0); },
      rest: function () {
        if (started || cancelled) return;
        started = true;
        for (var i = 1; i < urls.length; i++) load(i);
      },
      /* The nearest drawable frame at or before position i, or null if nothing has arrived. */
      at: function (i) {
        for (var j = Math.min(i, slot.length - 1); j >= 0; j--) if (ready[slot[j]]) return images[slot[j]];
        return null;
      },
      cancel: function () { cancelled = true; }
    };
  }

  /* Drawing ----------------------------------------------------------------- */

  var context = canvas.getContext("2d", { alpha: false });

  function build(isDesktop) {
    var frames = Sequence(isDesktop ? data.desktop : data.mobile);
    var drawn = null;  // the image on the canvas now, which may stand in for one still loading
    var wanted = 0;

    function resize() {
      var box = canvas.getBoundingClientRect();
      if (!box.width || !box.height) return;
      var dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      var w = Math.round(box.width * dpr);
      var h = Math.round(box.height * dpr);
      if (canvas.width === w && canvas.height === h) return;
      canvas.width = w;
      canvas.height = h;
      drawn = null;  // the surface was cleared by the resize
      draw(true);
    }

    /* The frame is letterboxed to fit, never stretched: the artwork keeps its proportions at
       every window size. */
    function draw(force) {
      var img = frames.at(wanted);
      if (!img || !canvas.width || (img === drawn && !force)) return;
      var scale = Math.min(canvas.width / img.naturalWidth, canvas.height / img.naturalHeight);
      var w = img.naturalWidth * scale;
      var h = img.naturalHeight * scale;
      context.fillStyle = "#0b1220";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(img, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
      drawn = img;
    }

    /* The frames are retimed so that layer k of n settles at k/(n+1) of the scroll; that is
       when its label appears. Toggling a class rather than animating from here keeps the easing
       in CSS and the work off the scroll thread; scrubbing back up reverses it for free. */
    var lit = labels.map(function () { return false; });
    function light(progress) {
      for (var i = 0; i < labels.length; i++) {
        var on = progress >= (i + 1) / (labels.length + 1) - EARLY;
        if (on === lit[i]) continue;
        lit[i] = on;
        labels[i].classList.toggle("is-on", on);
      }
    }

    frames.first(function () { resize(); draw(true); });

    /* The section sits only a screen or so below the hero, so "near" alone would start the
       download during the first paint. It also waits for the page's own load event: the hero
       and its images always go first. */
    var near = new IntersectionObserver(function (entries) {
      if (!entries.some(function (e) { return e.isIntersecting; })) return;
      near.disconnect();
      if (document.readyState === "complete") frames.rest();
      else window.addEventListener("load", frames.rest);
    }, { rootMargin: "100% 0px" });
    near.observe(section);

    var trigger = window.ScrollTrigger.create({
      trigger: stage,
      /* The stage is one screen tall with the header's height as top padding, so pinning it at
         the top of the viewport puts the picture in the clear space under the header. */
      start: "top top",
      end: function () { return "+=" + Math.round(window.innerHeight * (isDesktop ? PIN_DESKTOP : PIN_MOBILE)); },
      pin: true,
      pinSpacing: true,
      scrub: SCRUB,
      anticipatePin: 1,
      invalidateOnRefresh: true,
      /* ScrollTrigger measures triggers in the order they were made, and main.js makes the ones
         further down the page (the reveals, the pinned case-study gallery) before this file runs.
         Measured first, they never see the two and a half screens this pin adds above them, so
         the gallery pinned over the services grid and the reveals fired early. A higher priority
         plus the sort below has this pin measured before everything after it. */
      refreshPriority: 1,
      onRefresh: resize,
      onUpdate: function (self) {
        wanted = Math.min(frames.length - 1, Math.round(self.progress * (frames.length - 1)));
        light(self.progress);
        draw(false);
      }
    });

    window.ScrollTrigger.sort();
    window.ScrollTrigger.refresh();
    resize();

    return function () {
      frames.cancel();
      near.disconnect();
      window.removeEventListener("load", frames.rest);
      trigger.kill(true);
      labels.forEach(function (l) { l.classList.remove("is-on"); });
    };
  }

  /* Crossing the breakpoint swaps the whole thing for the other frame set, because a 1600px
     sequence on a phone is a waste and an 800px one on a desktop is a blur. */
  var mm = gsap.matchMedia();
  mm.add({ desktop: DESKTOP, mobile: "(max-width: 767px)" }, function (ctx) {
    return build(!!ctx.conditions.desktop);
  });

  /* Too many frames failed: drop the pin as well as the canvas, or the visitor would scroll
     through two and a half screens of nothing. */
  var gaveUp = false;
  function giveUp() {
    if (gaveUp) return;
    gaveUp = true;
    mm.revert();
    showStill();
    window.ScrollTrigger.sort();
    window.ScrollTrigger.refresh();
  }

  /* Someone who turns reduced motion on mid-visit should get the still, not a dead canvas. */
  var onReduce = function (e) { if (e.matches) giveUp(); };
  if (reduce.addEventListener) reduce.addEventListener("change", onReduce);
  else if (reduce.addListener) reduce.addListener(onReduce);

  window.addEventListener("load", function () { window.ScrollTrigger.refresh(); });
})();
