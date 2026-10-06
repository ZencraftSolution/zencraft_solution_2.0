/* Highlights the code sample on a case study page once highlight.js has loaded.
   Kept out of the template so the page needs no inline script under the CSP. */
(function () {
  "use strict";
  window.addEventListener("DOMContentLoaded", function () {
    if (!window.hljs) return;
    document.querySelectorAll(".code-block code").forEach(function (block) {
      window.hljs.highlightElement(block);
    });
  });
})();
