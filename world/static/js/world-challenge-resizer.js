/**
 * Cyber CTF World Theme - Challenge Modal Resizer & Persistent Sizing
 * Allows end-users to expand and resize the challenge dialog (<div class="modal-body py-4 px-4 px-sm-5">),
 * enforces minimum bounds (prevents making it too small), saves the chosen size in localStorage,
 * and maintains the size throughout all challenge views with proportional inner item matching.
 */
(function() {
  "use strict";

  const STORAGE_KEY = "world_challenge_modal_size_v2";
  const MIN_WIDTH = 550;
  const MIN_HEIGHT = 420;

  let isApplying = false;
  let rafId = null;

  function getSavedSize() {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      return data ? JSON.parse(data) : null;
    } catch (e) {
      return null;
    }
  }

  function saveSize(data) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {}
  }

  function clearSavedSize() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
  }

  function getBounds() {
    const vw = window.innerWidth || document.documentElement.clientWidth || 1024;
    const vh = window.innerHeight || document.documentElement.clientHeight || 768;
    return {
      minW: Math.min(MIN_WIDTH, Math.max(320, Math.round(vw * 0.94))),
      minH: Math.min(MIN_HEIGHT, Math.max(340, Math.round(vh * 0.85))),
      maxW: Math.min(1600, Math.round(vw * 0.96)),
      maxH: Math.min(1200, Math.round(vh * 0.92))
    };
  }

  function applySize(modalDialog, modalContent, modalBody, sizeData) {
    if (isApplying) return;
    isApplying = true;

    try {
      const modalWindow = document.getElementById("challenge-window");
      const bounds = getBounds();

      const isWide = Boolean(modalWindow && modalWindow.querySelector(
        ".incident-sequence-container, .textarea-wrapper, .image-upload-wrapper, .phishing-inbox-container, .crossword-wrapper, .bingo-wrapper, .bingo-hud-container, .branching-scenario-container, .url-anatomy-container, .red-flag-hotspot-container, .quiz-challenge-container"
      ));

      if (modalWindow) {
        if (isWide) {
          modalWindow.setAttribute("data-wide-challenge", "true");
        } else {
          modalWindow.removeAttribute("data-wide-challenge");
        }
      }

      if (!sizeData || (!sizeData.width && !sizeData.expanded && !sizeData.isCustom)) {
        // Revert to clean default
        if (modalWindow) {
          if (isWide) {
            const defW = Math.min(1100, Math.round(bounds.maxW * 0.95));
            modalWindow.style.setProperty("--challenge-modal-width", defW + "px");
          } else {
            modalWindow.style.removeProperty("--challenge-modal-width");
          }
          modalWindow.style.removeProperty("--challenge-modal-height");
          modalWindow.removeAttribute("data-challenge-expanded");
          modalWindow.removeAttribute("data-challenge-custom");
        }
        if (modalDialog) {
          if (isWide) {
            const defW = Math.min(1100, Math.round(bounds.maxW * 0.95));
            modalDialog.style.width = defW + "px";
            modalDialog.style.maxWidth = defW + "px";
          } else {
            modalDialog.style.removeProperty("width");
            modalDialog.style.removeProperty("max-width");
          }
          modalDialog.removeAttribute("data-challenge-expanded");
        }
        if (modalContent) {
          modalContent.style.removeProperty("height");
          modalContent.style.removeProperty("min-height");
        }
        if (modalBody) {
          modalBody.style.removeProperty("height");
          modalBody.style.removeProperty("min-height");
        }

        const expandBtn = document.getElementById("challenge-expand-toggle-btn");
        if (expandBtn && expandBtn.dataset.state !== "default") {
          expandBtn.dataset.state = "default";
          expandBtn.innerHTML = '<i class="fas fa-expand fa-xs"></i>';
          expandBtn.setAttribute("title", "Expand Challenge Window");
          expandBtn.classList.remove("active");
        }
        const resetBtn = document.getElementById("challenge-reset-size-btn");
        if (resetBtn) {
          resetBtn.style.display = "none";
        }
        return;
      }

      let targetW = sizeData.width;
      let targetH = sizeData.height;

      if (sizeData.expanded && !targetW) {
        targetW = Math.min(1150, Math.round(bounds.maxW * 0.92));
        targetH = Math.min(760, Math.round(bounds.maxH * 0.88));
      }

      // Clamp strictly within bounds ("don't let the user make it too small")
      targetW = Math.max(bounds.minW, Math.min(bounds.maxW, Math.round(targetW)));
      targetH = Math.max(bounds.minH, Math.min(bounds.maxH, Math.round(targetH)));

      const isExpanded = targetW >= 800;

      if (modalWindow) {
        modalWindow.style.setProperty("--challenge-modal-width", targetW + "px");
        modalWindow.style.setProperty("--challenge-modal-height", targetH + "px");
        modalWindow.setAttribute("data-challenge-expanded", isExpanded ? "true" : "false");
        modalWindow.setAttribute("data-challenge-custom", "true");
      }

      if (modalDialog) {
        modalDialog.style.width = targetW + "px";
        modalDialog.style.maxWidth = targetW + "px";
        modalDialog.setAttribute("data-challenge-expanded", isExpanded ? "true" : "false");
      }

      if (modalContent) {
        modalContent.style.height = targetH + "px";
        modalContent.style.minHeight = bounds.minH + "px";
      }

      if (modalBody) {
        modalBody.style.minHeight = (bounds.minH - 40) + "px";
      }

      const expandBtn = document.getElementById("challenge-expand-toggle-btn");
      if (expandBtn && expandBtn.dataset.state !== "expanded") {
        expandBtn.dataset.state = "expanded";
        expandBtn.innerHTML = '<i class="fas fa-compress fa-xs"></i>';
        expandBtn.setAttribute("title", "Restore Default Size");
        expandBtn.classList.add("active");
      }

      const resetBtn = document.getElementById("challenge-reset-size-btn");
      if (resetBtn) {
        resetBtn.style.display = "inline-flex";
      }
    } finally {
      isApplying = false;
    }
  }

  function initChallengeResizer() {
    const modalWindow = document.getElementById("challenge-window");
    if (!modalWindow) return;

    const modalDialog = modalWindow.querySelector(".modal-dialog") || modalWindow.querySelector("[role='document']");
    const modalContent = modalWindow.querySelector(".modal-content");
    const modalBody = modalWindow.querySelector(".modal-body");
    if (!modalDialog || !modalContent) return;

    // Apply saved size ONLY if explicitly customized by user, otherwise use content-fitting default
    const saved = getSavedSize();
    if (saved && (saved.isCustom || saved.expanded)) {
      applySize(modalDialog, modalContent, modalBody, saved);
    } else {
      applySize(modalDialog, modalContent, modalBody, null);
    }

    // Setup Expand/Restore button
    const expandBtn = document.getElementById("challenge-expand-toggle-btn");
    if (expandBtn && !expandBtn.dataset.resizerBound) {
      expandBtn.dataset.resizerBound = "true";
      expandBtn.addEventListener("click", function(e) {
        e.preventDefault();
        e.stopPropagation();

        // Enable brief CSS transition for smooth expand/collapse click
        modalWindow.classList.add("is-animating");
        setTimeout(function() {
          modalWindow.classList.remove("is-animating");
        }, 280);

        const currentSaved = getSavedSize();
        if (currentSaved) {
          clearSavedSize();
          applySize(modalDialog, modalContent, modalBody, null);
        } else {
          const bounds = getBounds();
          const expW = Math.min(1150, Math.round(bounds.maxW * 0.92));
          const expH = Math.min(760, Math.round(bounds.maxH * 0.88));
          const newSize = { width: expW, height: expH, expanded: true };
          saveSize(newSize);
          applySize(modalDialog, modalContent, modalBody, newSize);
        }
      });
    }

    // Setup Reset Size button
    const resetBtn = document.getElementById("challenge-reset-size-btn");
    if (resetBtn && !resetBtn.dataset.resizerBound) {
      resetBtn.dataset.resizerBound = "true";
      resetBtn.addEventListener("click", function(e) {
        e.preventDefault();
        e.stopPropagation();

        modalWindow.classList.add("is-animating");
        setTimeout(function() {
          modalWindow.classList.remove("is-animating");
        }, 280);

        clearSavedSize();
        applySize(modalDialog, modalContent, modalBody, null);
      });
    }

    // Setup Pointer Events on Drag Handle
    const handle = document.getElementById("challenge-resize-handle");
    if (handle && !handle.dataset.resizerBound) {
      handle.dataset.resizerBound = "true";

      const onPointerDown = function(e) {
        e.preventDefault();
        e.stopPropagation();

        try {
          handle.setPointerCapture(e.pointerId);
        } catch (err) {}

        const startRect = modalDialog.getBoundingClientRect();
        const startW = startRect.width;
        const startH = modalContent.getBoundingClientRect().height;
        const startX = e.clientX;
        const startY = e.clientY;

        let currentW = startW;
        let currentH = startH;

        document.body.classList.add("modal-resizing-active");
        handle.classList.add("is-resizing");

        const onPointerMove = function(ev) {
          ev.preventDefault();
          const deltaX = ev.clientX - startX;
          const deltaY = ev.clientY - startY;

          const bounds = getBounds();
          // modal is horizontally centered with auto margins, so deltaX * 2 keeps right edge under pointer
          currentW = Math.max(bounds.minW, Math.min(bounds.maxW, Math.round(startW + (deltaX * 2))));
          currentH = Math.max(bounds.minH, Math.min(bounds.maxH, Math.round(startH + deltaY)));

          if (rafId) cancelAnimationFrame(rafId);
          rafId = requestAnimationFrame(function() {
            const isExp = currentW >= 800;
            modalWindow.style.setProperty("--challenge-modal-width", currentW + "px");
            modalWindow.style.setProperty("--challenge-modal-height", currentH + "px");
            modalWindow.setAttribute("data-challenge-expanded", isExp ? "true" : "false");

            modalDialog.style.width = currentW + "px";
            modalDialog.style.maxWidth = currentW + "px";
            modalDialog.setAttribute("data-challenge-expanded", isExp ? "true" : "false");

            modalContent.style.height = currentH + "px";
          });
        };

        const onPointerUp = function(ev) {
          if (rafId) {
            cancelAnimationFrame(rafId);
            rafId = null;
          }

          try {
            handle.releasePointerCapture(ev.pointerId);
          } catch (err) {}

          handle.removeEventListener("pointermove", onPointerMove);
          handle.removeEventListener("pointerup", onPointerUp);
          handle.removeEventListener("pointercancel", onPointerUp);

          document.body.classList.remove("modal-resizing-active");
          handle.classList.remove("is-resizing");

          saveSize({ width: currentW, height: currentH, isCustom: true, expanded: currentW >= 800 });

          if (resetBtn) resetBtn.style.display = "inline-flex";
          if (expandBtn && expandBtn.dataset.state !== "expanded") {
            expandBtn.dataset.state = "expanded";
            expandBtn.innerHTML = '<i class="fas fa-compress fa-xs"></i>';
            expandBtn.setAttribute("title", "Restore Default Size");
            expandBtn.classList.add("active");
          }
        };

        handle.addEventListener("pointermove", onPointerMove);
        handle.addEventListener("pointerup", onPointerUp);
        handle.addEventListener("pointercancel", onPointerUp);
      };

      handle.addEventListener("pointerdown", onPointerDown);
    }
  }

  // Hook into Bootstrap modal lifecycle
  document.addEventListener("show.bs.modal", function(e) {
    if (e.target && e.target.id === "challenge-window") {
      setTimeout(initChallengeResizer, 10);
    }
  });

  document.addEventListener("shown.bs.modal", function(e) {
    if (e.target && e.target.id === "challenge-window") {
      initChallengeResizer();
    }
  });

  // Watch ONLY direct child additions to #challenge-window (Alpine setting x-html)
  // subtree: false is CRITICAL to prevent infinite loops from inner node updates
  const observer = new MutationObserver(function(mutations) {
    for (let i = 0; i < mutations.length; i++) {
      if (mutations[i].addedNodes.length > 0) {
        initChallengeResizer();
        break;
      }
    }
  });

  function startObserver() {
    const modalWindow = document.getElementById("challenge-window");
    if (modalWindow) {
      observer.observe(modalWindow, { childList: true, subtree: false });
      initChallengeResizer();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startObserver);
  } else {
    startObserver();
  }

  // Window resize debounce
  let windowResizeTimer = null;
  window.addEventListener("resize", function() {
    if (windowResizeTimer) clearTimeout(windowResizeTimer);
    windowResizeTimer = setTimeout(function() {
      const modalWindow = document.getElementById("challenge-window");
      if (!modalWindow || !modalWindow.classList.contains("show")) return;
      const saved = getSavedSize();
      if (saved) {
        const modalDialog = modalWindow.querySelector(".modal-dialog") || modalWindow.querySelector("[role='document']");
        const modalContent = modalWindow.querySelector(".modal-content");
        const modalBody = modalWindow.querySelector(".modal-body");
        applySize(modalDialog, modalContent, modalBody, saved);
      }
    }, 100);
  });

  // Expose globally
  window.WorldChallengeResizer = {
    init: initChallengeResizer,
    getSavedSize: getSavedSize,
    clearSavedSize: clearSavedSize
  };

})();
