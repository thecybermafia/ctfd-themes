// Interactive Onboarding Tutorial for CTFd World Theme
(function() {
    const TOUR_STORAGE_KEY = "world_theme_tutorial_completed_v1";

    const steps = [
        {
            target: ".gameboard-hud-header",
            title: "MATRIX COMMAND GRID",
            content: "Welcome, Operative. This is your central cyber warfare console. From here, you can monitor global geopolitical targets, filter threat vectors, and execute attacks.",
            position: "bottom"
        },
        {
            target: ".hud-filter-group",
            title: "TELEMETRY FILTERS",
            content: "Filter targets across the globe: view 'ALL NODES', targets you have successfully 'BREACHED', or countries controlled by 'HOSTILE' opponents.",
            position: "bottom"
        },
        {
            target: "#fb-gameboard-map",
            title: "GEOPOLITICAL WAR BOARD",
            content: "Every country on the map represents a target node. Countries with radar beacons are active challenges. Click on any country to deploy exploits and submit flags.",
            position: "center"
        },
        {
            target: ".gameboard-zoom-controls",
            title: "ORBITAL CONTROLS",
            content: "Use the zoom controls or scroll wheel to zoom directly onto any nation. Click the crosshairs icon to instantly re-center the orbital telemetry grid.",
            position: "right"
        },
        {
            target: "#hud-feed-btn",
            title: "REAL-TIME CAPTURE FEED",
            content: "Click 'LIVE FEED' to watch live country conquests, breaches, and First Blood strikes across all competing teams in real time.",
            position: "bottom"
        }
    ];

    let currentStep = 0;
    let overlayEl = null;
    let cardEl = null;

    function createTutorialElements() {
        if (overlayEl) return;

        overlayEl = document.createElement("div");
        overlayEl.id = "world-tutorial-overlay";
        overlayEl.className = "world-tutorial-overlay";

        cardEl = document.createElement("div");
        cardEl.id = "world-tutorial-card";
        cardEl.className = "world-tutorial-card";

        document.body.appendChild(overlayEl);
        document.body.appendChild(cardEl);

        overlayEl.addEventListener("click", closeTutorial);
    }

    function showStep(index) {
        if (index < 0 || index >= steps.length) {
            closeTutorial();
            return;
        }

        currentStep = index;
        const step = steps[index];
        const target = document.querySelector(step.target);

        // Highlight element (do not highlight entire map SVG to avoid elevating map geometries above card)
        document.querySelectorAll(".tutorial-highlighted").forEach(el => el.classList.remove("tutorial-highlighted"));
        if (target && step.target !== "#fb-gameboard-map") {
            target.classList.add("tutorial-highlighted");
        }

        cardEl.innerHTML = `
            <div class="tutorial-header d-flex justify-content-between align-items-center mb-2">
                <span class="tutorial-badge font-monospace">FIELD GUIDE BRIEFING [${index + 1}/${steps.length}]</span>
                <button type="button" class="btn-close tutorial-close-btn" aria-label="Close"></button>
            </div>
            <h5 class="tutorial-title mb-2 text-success font-monospace">${step.title}</h5>
            <p class="tutorial-body mb-4 font-monospace small" style="color: var(--matrix-text-main);">${step.content}</p>
            <div class="tutorial-actions d-flex justify-content-between align-items-center">
                <button type="button" class="btn btn-sm btn-outline-secondary tutorial-skip-btn">SKIP BRIEFING</button>
                <div class="d-flex gap-2">
                    ${index > 0 ? '<button type="button" class="btn btn-sm btn-outline-success tutorial-prev-btn">BACK</button>' : ''}
                    <button type="button" class="btn btn-sm btn-success tutorial-next-btn">
                        ${index === steps.length - 1 ? 'DEPLOY NOW' : 'NEXT TARGET'}
                    </button>
                </div>
            </div>
        `;

        cardEl.querySelector(".tutorial-close-btn").addEventListener("click", closeTutorial);
        cardEl.querySelector(".tutorial-skip-btn").addEventListener("click", closeTutorial);
        if (cardEl.querySelector(".tutorial-prev-btn")) {
            cardEl.querySelector(".tutorial-prev-btn").addEventListener("click", () => showStep(currentStep - 1));
        }
        cardEl.querySelector(".tutorial-next-btn").addEventListener("click", () => showStep(currentStep + 1));

        overlayEl.classList.add("active");
        cardEl.classList.add("active");
        positionCard(target, step.position);
    }

    function positionCard(target, position) {
        cardEl.style.transform = "none";
        const cardWidth = Math.min(380, window.innerWidth - 32);
        const cardHeight = cardEl.offsetHeight || 220;
        const maxLeft = window.innerWidth - cardWidth - 16;
        const maxTop = window.innerHeight - cardHeight - 16;

        if (!target || position === "center") {
            cardEl.style.top = `${Math.max(16, (window.innerHeight - cardHeight) / 2)}px`;
            cardEl.style.left = `${Math.max(16, (window.innerWidth - cardWidth) / 2)}px`;
            return;
        }

        const rect = target.getBoundingClientRect();

        if (position === "bottom") {
            const top = rect.bottom + 10;
            const desiredLeft = rect.left + (rect.width / 2) - (cardWidth / 2);
            cardEl.style.top = `${Math.min(maxTop, Math.max(16, top))}px`;
            cardEl.style.left = `${Math.max(16, Math.min(maxLeft, desiredLeft))}px`;
        } else if (position === "right") {
            const left = rect.right + 12;
            // For elements anchored near the bottom of the screen (like zoom controls)
            let top;
            if (rect.bottom > window.innerHeight - 150) {
                top = rect.bottom - cardHeight;
            } else {
                top = rect.top + (rect.height / 2) - (cardHeight / 2);
            }
            cardEl.style.left = `${Math.min(maxLeft, Math.max(16, left))}px`;
            cardEl.style.top = `${Math.max(16, Math.min(maxTop, top))}px`;
        } else if (position === "top") {
            const top = rect.top - cardHeight - 10;
            const desiredLeft = rect.left + (rect.width / 2) - (cardWidth / 2);
            cardEl.style.top = `${Math.max(16, top)}px`;
            cardEl.style.left = `${Math.max(16, Math.min(maxLeft, desiredLeft))}px`;
        } else if (position === "left") {
            const left = rect.left - cardWidth - 12;
            const top = rect.top + (rect.height / 2) - (cardHeight / 2);
            cardEl.style.left = `${Math.max(16, left)}px`;
            cardEl.style.top = `${Math.max(16, Math.min(maxTop, top))}px`;
        } else {
            cardEl.style.top = `${Math.min(maxTop, rect.bottom + 10)}px`;
            cardEl.style.left = `${Math.max(16, Math.min(maxLeft, rect.left))}px`;
        }
    }

    function closeTutorial() {
        if (overlayEl) overlayEl.classList.remove("active");
        if (cardEl) cardEl.classList.remove("active");
        document.querySelectorAll(".tutorial-highlighted").forEach(el => el.classList.remove("tutorial-highlighted"));
        try {
            localStorage.setItem(TOUR_STORAGE_KEY, "true");
            localStorage.setItem("world_user_guide_enabled", "false");
            window.dispatchEvent(new CustomEvent("world:guide-completed"));
        } catch(e) {}
    }

    window.startWorldTutorial = function(force = true) {
        createTutorialElements();
        showStep(0);
    };

    // Auto-launch for first-time visitors if enabled in settings
    document.addEventListener("DOMContentLoaded", () => {
        try {
            const hasCompleted = localStorage.getItem(TOUR_STORAGE_KEY);
            if (!hasCompleted) {
                // Check if tutorial feature is enabled (deduped via window.getWorldSettings)
                const getSettings = window.getWorldSettings || function() {
                    return fetch("/api/v1/world/settings").then(r => r.json()).then(res => res.data || {}).catch(() => ({}));
                };
                getSettings()
                    .then(settings => {
                        if (settings && settings.tutorial_enabled !== false) {
                            setTimeout(() => {
                                window.startWorldTutorial(false);
                            }, 1200);
                        }
                    })
                    .catch(() => {});
            }
        } catch(e) {}
    });
})();
