/* ============================================
   Portfolio — Minimal JavaScript
   ============================================ */

(function () {
  "use strict";

  // --- Scroll Reveal (IntersectionObserver) ---
  function initReveal() {
    var elements = document.querySelectorAll(".reveal");
    if (!elements.length) return;

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: "0px 0px -40px 0px" }
    );

    elements.forEach(function (el) {
      observer.observe(el);
    });
  }

  // --- Mobile Navigation Toggle ---
  function initNav() {
    var toggle = document.querySelector(".nav__toggle");
    var links = document.querySelector(".nav__links");
    if (!toggle || !links) return;

    toggle.addEventListener("click", function () {
      var isOpen = links.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", isOpen);
    });

    // Close menu when a link is clicked
    links.querySelectorAll(".nav__link").forEach(function (link) {
      link.addEventListener("click", function () {
        links.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });

    // Close menu on outside click
    document.addEventListener("click", function (e) {
      if (!toggle.contains(e.target) && !links.contains(e.target)) {
        links.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  // --- Active Nav Link ---
  function initActiveNav() {
    var path = window.location.pathname;
    var links = document.querySelectorAll(".nav__link");
    links.forEach(function (link) {
      var href = link.getAttribute("href");
      if (href && path.endsWith(href.replace("./", "/"))) {
        link.classList.add("nav__link--active");
      }
    });
  }

  // --- Init ---
  document.addEventListener("DOMContentLoaded", function () {
    initReveal();
    initNav();
    initActiveNav();
  });
})();
