// Injected on admin pages to integrate World Map country selection directly into challenge views
(function() {
    let countriesList = [];

    function fetchCountries() {
        return fetch("/api/v1/world/countries")
            .then(r => r.json())
            .then(data => {
                if (data.success && data.data) {
                    countriesList = Object.values(data.data).sort((a, b) => a.name.localeCompare(b.name));
                }
                return countriesList;
            })
            .catch(e => {
                console.error("[WorldTheme Admin] Error loading countries:", e);
                return [];
            });
    }

    function createCountryDropdown(selectedIso = "", currentChalId = null, inputName = "country_iso", omitName = false) {
        const div = document.createElement("div");
        div.className = "form-group mb-3 world-country-group";
        const nameAttr = omitName ? "" : `name="${inputName}"`;
        div.innerHTML = `
            <label for="world-country-select-${inputName}">
                <b>World Map Country</b><br>
                <small class="form-text text-muted">Assign this challenge to a country on the World Map (1:1 mapping — already assigned countries are disabled)</small>
            </label>
            <select class="form-control custom-select" ${nameAttr} id="world-country-select-${inputName}">
                <option value="">-- No Country (Unassigned) --</option>
            </select>
        `;
        const select = div.querySelector("select");
        countriesList.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c.iso;

            const isAlreadyAssigned = Boolean(c.challenge && (!currentChalId || String(c.challenge.id) !== String(currentChalId)));

            if (isAlreadyAssigned) {
                opt.disabled = true;
                opt.textContent = `${c.name} (${c.iso}) — [ASSIGNED: ${c.challenge.name}]`;
                opt.style.color = "#888888";
            } else {
                opt.textContent = `${c.name} (${c.iso})`;
            }

            if (c.iso === selectedIso) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });
        return div;
    }

    function saveCountryForChallenge(chalId, iso) {
        if (!chalId) return Promise.resolve();
        const csrfToken = (window.init && window.init.csrfNonce) || "";
        return fetch("/api/v1/world/challenges/" + chalId + "/country", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "CSRF-Token": csrfToken
            },
            body: JSON.stringify({ country_iso: iso || null })
        }).catch(err => console.error("[WorldTheme Admin] Error saving country for challenge:", err));
    }

    // --- Challenge Creation Page (/admin/challenges/new) ---
    function initChallengeCreate() {
        fetchCountries().then(() => {
            const entryDiv = document.getElementById("create-chal-entry-div");
            if (!entryDiv) return;

            let selectedCountryIso = "";

            // Intercept window.fetch to automatically save country when /api/v1/challenges returns newly created ID
            const origFetch = window.fetch;
            window.fetch = function(...args) {
                const url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url);
                const method = (args[1] && args[1].method) || "GET";
                const p = origFetch.apply(this, args);

                if (url && url.includes("/api/v1/challenges") && method.toUpperCase() === "POST") {
                    p.then(r => r.clone().json()).then(res => {
                        if (res && res.success && res.data && res.data.id) {
                            const newChalId = res.data.id;
                            if (selectedCountryIso) {
                                saveCountryForChallenge(newChalId, selectedCountryIso);
                            }
                        }
                    }).catch(() => {});
                }
                return p;
            };

            function checkAndInject(targetDiv) {
                const form = targetDiv.querySelector("form");
                if (!form || form.querySelector(".world-country-group")) return;

                // Omit name attribute so jQuery serializeJSON() will NOT send country_iso to /api/v1/challenges
                const dropdownGroup = createCountryDropdown(selectedCountryIso, null, "country_iso", true);
                const sel = dropdownGroup.querySelector("select");
                sel.addEventListener("change", (e) => {
                    selectedCountryIso = e.target.value;
                    const modalSel = document.querySelector("#challenge-create-options #world-country-select-modal_country_iso");
                    if (modalSel) modalSel.value = selectedCountryIso;
                });

                const submitBtn = form.querySelector("button[type='submit'], input[type='submit'], .create-challenge-submit");
                if (submitBtn && submitBtn.parentElement) {
                    submitBtn.parentElement.parentElement.insertBefore(dropdownGroup, submitBtn.parentElement);
                } else {
                    form.appendChild(dropdownGroup);
                }
            }

            const observer = new MutationObserver(() => {
                checkAndInject(entryDiv);
            });
            observer.observe(entryDiv, { childList: true, subtree: true });
            checkAndInject(entryDiv);

            // Inject into the modal options form (#challenge-create-options)
            function injectModalDropdown() {
                const modal = document.getElementById("challenge-create-options");
                if (!modal) return;
                const modalForm = modal.querySelector("form");
                if (!modalForm || modalForm.querySelector(".world-country-group")) return;

                // Also omit name attribute from modal form so it does not collide with CTFd serializers
                const modalDropdown = createCountryDropdown(selectedCountryIso, null, "modal_country_iso", true);
                const modalSel = modalDropdown.querySelector("select");
                modalSel.addEventListener("change", (e) => {
                    selectedCountryIso = e.target.value;
                    const mainSel = entryDiv.querySelector("#world-country-select-country_iso");
                    if (mainSel) mainSel.value = selectedCountryIso;

                    const chalIdInput = modalForm.querySelector("#challenge_id") || modalForm.querySelector("input[name='challenge_id']");
                    const chalId = chalIdInput ? chalIdInput.value : null;
                    if (chalId) {
                        saveCountryForChallenge(chalId, selectedCountryIso);
                    }
                });

                const stateGroup = modalForm.querySelector("select[name='state']")?.closest(".form-group");
                if (stateGroup) {
                    stateGroup.parentElement.insertBefore(modalDropdown, stateGroup);
                } else {
                    const finishBtn = modalForm.querySelector(".create-challenge-submit");
                    if (finishBtn && finishBtn.parentElement) {
                        finishBtn.parentElement.parentElement.insertBefore(modalDropdown, finishBtn.parentElement);
                    } else {
                        modalForm.appendChild(modalDropdown);
                    }
                }

                modalForm.addEventListener("submit", () => {
                    const chalIdInput = modalForm.querySelector("#challenge_id") || modalForm.querySelector("input[name='challenge_id']");
                    const chalId = chalIdInput ? chalIdInput.value : null;
                    const iso = selectedCountryIso || (modalSel ? modalSel.value : "");
                    if (chalId && iso) {
                        saveCountryForChallenge(chalId, iso);
                    }
                });
            }

            injectModalDropdown();
            const modalEl = document.getElementById("challenge-create-options");
            if (modalEl) {
                const modalObserver = new MutationObserver(injectModalDropdown);
                modalObserver.observe(modalEl, { childList: true, subtree: true });
            }
        });
    }

    // --- Challenge Detail Page (/admin/challenges/<id>) ---
    function initChallengeDetail() {
        if (typeof CHALLENGE_ID === "undefined" && !window.CHALLENGE_ID) return;
        const chalId = typeof CHALLENGE_ID !== "undefined" ? CHALLENGE_ID : window.CHALLENGE_ID;

        fetchCountries().then(() => {
            fetch("/api/v1/world/challenges/" + chalId + "/country")
                .then(r => r.json())
                .then(res => {
                    const data = (res && res.data) || {};
                    const currentIso = data.country_iso || "";
                    const bLevels = data.bonus_levels || [
                        data.bonus_first || 0,
                        data.bonus_second || 0,
                        data.bonus_third || 0,
                        data.bonus_fourth || 0,
                        data.bonus_fifth || 0
                    ];

                    // Determine active count based on existing non-zero bonuses
                    let activeCount = 0;
                    for (let i = 4; i >= 0; i--) {
                        if (bLevels[i] > 0) {
                            activeCount = i + 1;
                            break;
                        }
                    }
                    if (activeCount === 0 && (bLevels[0] > 0 || bLevels[1] > 0 || bLevels[2] > 0)) {
                        activeCount = 3;
                    }

                    const navTabs = document.getElementById("challenge-properties");
                    const tabContent = document.getElementById("nav-tabContent");

                    if (navTabs && tabContent && !document.getElementById("world-territory-tab")) {
                        const tabLink = document.createElement("a");
                        tabLink.id = "world-territory-tab";
                        tabLink.className = "nav-item nav-link small";
                        tabLink.setAttribute("data-toggle", "tab");
                        tabLink.setAttribute("data-bs-toggle", "tab");
                        tabLink.setAttribute("href", "#world-territory");
                        tabLink.setAttribute("role", "tab");
                        tabLink.innerHTML = 'Country & Bonus';
                        navTabs.appendChild(tabLink);

                        const tabPane = document.createElement("div");
                        tabPane.className = "tab-pane fade";
                        tabPane.id = "world-territory";
                        tabPane.setAttribute("role", "tabpanel");

                        const dropdownGroup = createCountryDropdown(currentIso, chalId, "detail_country_iso", true);
                        tabPane.innerHTML = `
                            <div class="row">
                                <div class="col-md-12 py-3">
                                    <h4 class="mb-3">World Map Country & Early-Solver Bonuses</h4>
                                    <div id="world-detail-dropdown-slot"></div>

                                    <div class="card mt-4">
                                        <div class="card-header d-flex justify-content-between align-items-center">
                                            <div>
                                                <strong>Early-Solver Decaying Bonuses (Locked-in)</strong>
                                                <div class="small text-muted">Configurable bonus levels (1 to 5). Earned points remain permanently locked in via Awards.</div>
                                            </div>
                                            <div class="d-flex align-items-center gap-2">
                                                <label class="small mb-0 fw-bold">Active Levels:</label>
                                                <select class="form-select form-select-sm" id="world-bonus-levels-count" style="width: auto;">
                                                    <option value="0" ${activeCount === 0 ? 'selected' : ''}>0 (No Bonuses)</option>
                                                    <option value="1" ${activeCount === 1 ? 'selected' : ''}>1 Level (First Blood)</option>
                                                    <option value="2" ${activeCount === 2 ? 'selected' : ''}>2 Levels</option>
                                                    <option value="3" ${activeCount === 3 ? 'selected' : ''}>3 Levels</option>
                                                    <option value="4" ${activeCount === 4 ? 'selected' : ''}>4 Levels</option>
                                                    <option value="5" ${activeCount === 5 ? 'selected' : ''}>5 Levels (Max)</option>
                                                </select>
                                            </div>
                                        </div>
                                        <div class="card-body">
                                            <div class="row g-3" id="world-bonus-inputs-container">
                                                <div class="col-md-4 world-bonus-col" data-level="1" style="${activeCount >= 1 ? '' : 'display:none;'}">
                                                    <label class="form-label">1st Blood Bonus (+pts)</label>
                                                    <input type="number" class="form-control" id="world-bonus-1" value="${bLevels[0] || 0}" min="0" placeholder="e.g. 100">
                                                </div>
                                                <div class="col-md-4 world-bonus-col" data-level="2" style="${activeCount >= 2 ? '' : 'display:none;'}">
                                                    <label class="form-label">2nd Solver Bonus (+pts)</label>
                                                    <input type="number" class="form-control" id="world-bonus-2" value="${bLevels[1] || 0}" min="0" placeholder="e.g. 50">
                                                </div>
                                                <div class="col-md-4 world-bonus-col" data-level="3" style="${activeCount >= 3 ? '' : 'display:none;'}">
                                                    <label class="form-label">3rd Solver Bonus (+pts)</label>
                                                    <input type="number" class="form-control" id="world-bonus-3" value="${bLevels[2] || 0}" min="0" placeholder="e.g. 25">
                                                </div>
                                                <div class="col-md-4 world-bonus-col" data-level="4" style="${activeCount >= 4 ? '' : 'display:none;'}">
                                                    <label class="form-label">4th Solver Bonus (+pts)</label>
                                                    <input type="number" class="form-control" id="world-bonus-4" value="${bLevels[3] || 0}" min="0" placeholder="e.g. 15">
                                                </div>
                                                <div class="col-md-4 world-bonus-col" data-level="5" style="${activeCount >= 5 ? '' : 'display:none;'}">
                                                    <label class="form-label">5th Solver Bonus (+pts)</label>
                                                    <input type="number" class="form-control" id="world-bonus-5" value="${bLevels[4] || 0}" min="0" placeholder="e.g. 10">
                                                </div>
                                            </div>
                                            <div id="world-bonus-empty-msg" class="text-muted small py-2" style="${activeCount === 0 ? '' : 'display:none;'}">
                                                No bonus levels active for this challenge. Select 1 to 5 levels above to configure early solver bonuses.
                                            </div>
                                        </div>
                                    </div>

                                    <button type="button" class="btn btn-success mt-3" id="world-save-country-btn">
                                        <i class="fas fa-save me-1"></i> Save Country & Bonuses
                                    </button>
                                    <span id="world-country-msg" class="ms-2 font-weight-bold"></span>
                                </div>
                            </div>
                        `;
                        tabPane.querySelector("#world-detail-dropdown-slot").appendChild(dropdownGroup);
                        tabContent.appendChild(tabPane);

                        // Handle changing bonus level count
                        const countSelect = tabPane.querySelector("#world-bonus-levels-count");
                        const emptyMsg = tabPane.querySelector("#world-bonus-empty-msg");
                        countSelect.addEventListener("change", (e) => {
                            const count = parseInt(e.target.value) || 0;
                            emptyMsg.style.display = count === 0 ? "" : "none";
                            tabPane.querySelectorAll(".world-bonus-col").forEach(col => {
                                const lvl = parseInt(col.getAttribute("data-level"));
                                col.style.display = lvl <= count ? "" : "none";
                            });
                        });

                        document.getElementById("world-save-country-btn").addEventListener("click", () => {
                            const select = dropdownGroup.querySelector("select");
                            const msg = document.getElementById("world-country-msg");
                            const iso = select.value;
                            const count = parseInt(countSelect.value) || 0;

                            const b1 = count >= 1 ? (parseInt(document.getElementById("world-bonus-1").value) || 0) : 0;
                            const b2 = count >= 2 ? (parseInt(document.getElementById("world-bonus-2").value) || 0) : 0;
                            const b3 = count >= 3 ? (parseInt(document.getElementById("world-bonus-3").value) || 0) : 0;
                            const b4 = count >= 4 ? (parseInt(document.getElementById("world-bonus-4").value) || 0) : 0;
                            const b5 = count >= 5 ? (parseInt(document.getElementById("world-bonus-5").value) || 0) : 0;

                            const csrfToken = (window.init && window.init.csrfNonce) || "";
                            const opts = {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json",
                                    "CSRF-Token": csrfToken
                                },
                                body: JSON.stringify({
                                    country_iso: iso || null,
                                    bonus_first: b1,
                                    bonus_second: b2,
                                    bonus_third: b3,
                                    bonus_fourth: b4,
                                    bonus_fifth: b5,
                                    bonus_levels: [b1, b2, b3, b4, b5]
                                })
                            };

                            msg.className = "ms-2 text-success font-weight-bold";
                            msg.textContent = "Saving...";

                            fetch("/api/v1/world/challenges/" + chalId + "/country", opts)
                                .then(r => r.json())
                                .then(sdata => {
                                    if (sdata.success) {
                                        msg.className = "ms-2 text-success font-weight-bold";
                                        msg.textContent = "Saved!";
                                        setTimeout(() => { msg.textContent = ""; }, 3000);
                                    } else {
                                        msg.className = "ms-2 text-danger font-weight-bold";
                                        msg.textContent = sdata.message || "Error saving";
                                    }
                                })
                                .catch(err => {
                                    msg.className = "ms-2 text-danger font-weight-bold";
                                    msg.textContent = "Network error";
                                });
                        });
                    }
                });
        });
    }

    // --- Challenges List Page (/admin/challenges) ---
    function initChallengesListing() {
        fetchCountries().then(() => {
            const table = document.getElementById("challenges");
            if (!table) return;

            const chalToCountry = {};
            countriesList.forEach(c => {
                if (c.challenge && c.challenge.id) {
                    chalToCountry[String(c.challenge.id)] = c;
                }
            });

            function injectCountryColumns() {
                const theadRow = table.querySelector("thead tr");
                if (!theadRow) return;

                let catIndex = -1;
                const ths = Array.from(theadRow.children);
                ths.forEach((th, idx) => {
                    const txt = th.textContent.trim().toLowerCase();
                    if (txt === "category") {
                        catIndex = idx;
                    }
                });

                if (!theadRow.querySelector(".world-country-header")) {
                    const countryTh = document.createElement("th");
                    countryTh.className = "sort-col text-center world-country-header";
                    countryTh.innerHTML = "<b>Country</b>";
                    if (catIndex >= 0 && ths[catIndex]) {
                        ths[catIndex].after(countryTh);
                    } else {
                        theadRow.appendChild(countryTh);
                    }
                }

                const rows = table.querySelectorAll("tbody tr");
                rows.forEach(row => {
                    if (row.querySelector(".world-country-cell")) return;
                    const input = row.querySelector("input[data-challenge-id]");
                    const chalId = input ? input.getAttribute("data-challenge-id") : null;
                    const countryTd = document.createElement("td");
                    countryTd.className = "text-center world-country-cell";

                    const c = chalId ? chalToCountry[String(chalId)] : null;
                    if (c) {
                        countryTd.innerHTML = `<span class="badge badge-primary bg-primary text-white px-2 py-1">${c.name} (${c.iso})</span>`;
                    } else {
                        countryTd.innerHTML = `<span class="text-muted small">—</span>`;
                    }

                    if (catIndex >= 0 && row.children[catIndex]) {
                        row.children[catIndex].after(countryTd);
                    } else {
                        row.appendChild(countryTd);
                    }
                });
            }

            injectCountryColumns();

            const tbody = table.querySelector("tbody");
            if (tbody) {
                const obs = new MutationObserver(() => {
                    injectCountryColumns();
                });
                obs.observe(tbody, { childList: true, subtree: true });
            }
        });
    }

    function init() {
        const p = window.location.pathname;
        if (p.includes("/admin/challenges/new")) {
            initChallengeCreate();
        } else if (p.match(/\/admin\/challenges\/\d+/)) {
            initChallengeDetail();
        } else if (p.includes("/admin/challenges")) {
            initChallengesListing();
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
