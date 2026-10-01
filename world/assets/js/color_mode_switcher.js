"use strict";

/**
 * Get user preferred theme from their past choice or browser
 * @returns {String} User preferred theme
 */
function getPreferredTheme() {
  const storedTheme = localStorage.getItem("theme");
  if (storedTheme) {
    return storedTheme;
  }
  const defaultTheme = document.documentElement.getAttribute("data-default-theme");
  if (defaultTheme) {
    return defaultTheme;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Update navbar icon to match given theme.
 * @param {String} theme - 'dark' or 'light'
 */
function showActiveTheme(theme) {
  const icons = document.querySelectorAll(".theme-switch i.fas");
  icons.forEach(icon => {
    icon.classList.toggle("fa-moon", theme === "dark");
    icon.classList.toggle("fa-sun", theme !== "dark");
  });
}

// Change body theme early to prevent flash
let currentTheme = getPreferredTheme();
document.documentElement.setAttribute("data-bs-theme", currentTheme);

// On browser color-scheme change, update
try {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    currentTheme = getPreferredTheme();
    document.documentElement.setAttribute("data-bs-theme", currentTheme);
    showActiveTheme(currentTheme);
  });
} catch (e) {}

function initThemeSwitcher() {
  showActiveTheme(currentTheme);

  document.querySelectorAll(".theme-switch").forEach(btn => {
    if (btn.dataset.themeBound) return;
    btn.dataset.themeBound = "true";
    btn.addEventListener("click", ev => {
      ev.preventDefault();
      currentTheme = currentTheme === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-bs-theme", currentTheme);
      localStorage.setItem("theme", currentTheme);
      showActiveTheme(currentTheme);
    });
  });
}

window.toggleTheme = function() {
  currentTheme = currentTheme === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-bs-theme", currentTheme);
  localStorage.setItem("theme", currentTheme);
  showActiveTheme(currentTheme);
  return currentTheme;
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initThemeSwitcher);
  window.addEventListener("load", initThemeSwitcher);
} else {
  initThemeSwitcher();
}
