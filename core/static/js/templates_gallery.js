/* ==========================================================================
   PromptLab v7.2 — Galería de Plantillas (100% Client-Side Offline)
   ========================================================================== */

(function () {
    "use strict";

    let activeCategory = "";
    let activeMode = "";
    let searchQuery = "";

    function $(id) {
        return document.getElementById(id);
    }

    function normalizeText(str) {
        return String(str || "")
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "");
    }

    function applyTemplateFilters() {
        const items = document.querySelectorAll(".tpl-gallery-item");
        const total = items.length;
        let visibleCount = 0;
        const normQuery = normalizeText(searchQuery.trim());

        items.forEach((item) => {
            const cat = item.getAttribute("data-category") || "";
            const mode = item.getAttribute("data-mode") || "";
            const haystack = normalizeText(item.getAttribute("data-search") || "");

            const matchCat = !activeCategory || cat === activeCategory;
            const matchMode = !activeMode || mode === activeMode;
            const matchSearch = !normQuery || haystack.includes(normQuery);

            const isVisible = matchCat && matchMode && matchSearch;
            item.classList.toggle("d-none", !isVisible);
            if (isVisible) visibleCount += 1;
        });

        const counterEl = $("tpl-results-counter");
        if (counterEl) {
            counterEl.textContent = `Mostrando ${visibleCount} de ${total} plantillas`;
        }

        const emptyEl = $("tpl-empty-state");
        if (emptyEl) {
            emptyEl.classList.toggle("d-none", visibleCount > 0);
        }

        const clearSearchBtn = $("tpl-search-clear");
        if (clearSearchBtn) {
            clearSearchBtn.classList.toggle("d-none", !searchQuery.trim());
        }
    }

    function setActiveCategory(category) {
        activeCategory = category || "";
        document.querySelectorAll(".tpl-cat-chip").forEach((chip) => {
            const isMatch = (chip.getAttribute("data-category") || "") === activeCategory;
            chip.classList.toggle("active", isMatch);
            chip.setAttribute("aria-pressed", isMatch ? "true" : "false");
        });
        applyTemplateFilters();
    }

    function setActiveMode(mode) {
        activeMode = mode || "";
        document.querySelectorAll(".tpl-mode-chip").forEach((chip) => {
            const isMatch = (chip.getAttribute("data-mode") || "") === activeMode;
            chip.classList.toggle("active", isMatch);
            chip.setAttribute("aria-pressed", isMatch ? "true" : "false");
        });
        applyTemplateFilters();
    }

    function resetAllFilters() {
        searchQuery = "";
        const searchInput = $("tpl-search-input");
        if (searchInput) searchInput.value = "";
        activeCategory = "";
        activeMode = "";
        document.querySelectorAll(".tpl-cat-chip").forEach((chip) => {
            const isAll = (chip.getAttribute("data-category") || "") === "";
            chip.classList.toggle("active", isAll);
            chip.setAttribute("aria-pressed", isAll ? "true" : "false");
        });
        document.querySelectorAll(".tpl-mode-chip").forEach((chip) => {
            const isAll = (chip.getAttribute("data-mode") || "") === "";
            chip.classList.toggle("active", isAll);
            chip.setAttribute("aria-pressed", isAll ? "true" : "false");
        });
        applyTemplateFilters();
    }

    function copyTextToClipboard(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text);
        }
        return new Promise((resolve, reject) => {
            try {
                const ta = document.createElement("textarea");
                ta.value = text;
                ta.setAttribute("readonly", "");
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.select();
                document.execCommand("copy");
                document.body.removeChild(ta);
                resolve();
            } catch (err) {
                reject(err);
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        const searchInput = $("tpl-search-input");
        if (searchInput) {
            searchInput.addEventListener("input", () => {
                searchQuery = searchInput.value || "";
                applyTemplateFilters();
            });
        }

        const clearSearchBtn = $("tpl-search-clear");
        if (clearSearchBtn) {
            clearSearchBtn.addEventListener("click", () => {
                searchQuery = "";
                if (searchInput) {
                    searchInput.value = "";
                    searchInput.focus();
                }
                applyTemplateFilters();
            });
        }

        document.querySelectorAll(".tpl-cat-chip").forEach((chip) => {
            chip.addEventListener("click", () => {
                setActiveCategory(chip.getAttribute("data-category") || "");
            });
        });

        document.querySelectorAll(".tpl-mode-chip").forEach((chip) => {
            chip.addEventListener("click", () => {
                setActiveMode(chip.getAttribute("data-mode") || "");
            });
        });

        const resetBtn = $("btn-reset-tpl-filters");
        if (resetBtn) {
            resetBtn.addEventListener("click", resetAllFilters);
        }

        document.querySelectorAll(".tpl-copy-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                const card = btn.closest(".tpl-gallery-item, .user-tpl-card-item");
                const rawEl = card ? card.querySelector(".tpl-raw-prompt") : null;
                const rawText = rawEl ? rawEl.value : "";
                if (!rawText) return;

                copyTextToClipboard(rawText).then(() => {
                    const originalHtml = btn.innerHTML;
                    btn.innerHTML = '<i class="bi bi-check2 me-1"></i> Copiado';
                    btn.classList.add("btn-success", "text-white");
                    btn.classList.remove("btn-pl-secondary");
                    setTimeout(() => {
                        btn.innerHTML = originalHtml;
                        btn.classList.remove("btn-success", "text-white");
                        btn.classList.add("btn-pl-secondary");
                    }, 1500);
                });
            });
        });

        document.querySelectorAll(".tpl-use-btn").forEach((link) => {
            link.addEventListener("click", () => {
                const card = link.closest(".tpl-gallery-item, .user-tpl-card-item");
                if (!card) return;
                const rawEl = card.querySelector(".tpl-raw-prompt");
                const wsMode = card.getAttribute("data-workspace-mode") || "guiado";
                const payload = {
                    slug: card.getAttribute("data-slug") || "",
                    title: card.getAttribute("data-title") || "",
                    category: card.getAttribute("data-category") || "",
                    mode: card.getAttribute("data-mode") || "guiado",
                    workspace_mode: wsMode,
                    prompt: rawEl ? rawEl.value : "",
                };
                try {
                    sessionStorage.setItem("promptlab_selected_template", JSON.stringify(payload));
                } catch (_e) {
                    // Fallback: continúa con ?preset=<slug> o ?user_tpl=<id> en el href
                }
            });
        });

        document.querySelectorAll(".btn-user-tpl-del-init").forEach((btn) => {
            btn.addEventListener("click", () => {
                const form = btn.closest(".user-tpl-delete-form");
                if (!form) return;
                btn.classList.add("d-none");
                const grp = form.querySelector(".user-tpl-del-confirm");
                if (grp) {
                    grp.classList.remove("d-none");
                    grp.classList.add("d-inline-flex");
                }
            });
        });

        document.querySelectorAll(".btn-user-tpl-del-cancel").forEach((btn) => {
            btn.addEventListener("click", () => {
                const form = btn.closest(".user-tpl-delete-form");
                if (!form) return;
                const grp = form.querySelector(".user-tpl-del-confirm");
                const initBtn = form.querySelector(".btn-user-tpl-del-init");
                if (grp) {
                    grp.classList.add("d-none");
                    grp.classList.remove("d-inline-flex");
                }
                if (initBtn) initBtn.classList.remove("d-none");
            });
        });

        applyTemplateFilters();
    });
})();
