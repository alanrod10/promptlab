/* ==========================================================================
   PromptLab v8.0.2 — Glosario IA (100% Client-Side Offline)
   ========================================================================== */

(function () {
    "use strict";

    let activeCategory = "";
    let activeLevel = "";
    let searchQuery = "";
    let highlightTimer = null;

    function $(id) {
        return document.getElementById(id);
    }

    function normalizeText(str) {
        return String(str || "")
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "");
    }

    function applyGlossaryFilters() {
        const items = document.querySelectorAll(".pl-glossary-item");
        const total = items.length;
        let visibleCount = 0;
        const normQuery = normalizeText(searchQuery.trim());

        items.forEach((item) => {
            const cat = item.getAttribute("data-category") || "";
            const level = item.getAttribute("data-level") || "";
            const haystack = normalizeText(item.getAttribute("data-search") || "");

            const matchCat = !activeCategory || cat === activeCategory;
            const matchLevel = !activeLevel || level === activeLevel;
            const matchSearch = !normQuery || haystack.includes(normQuery);

            const isVisible = matchCat && matchLevel && matchSearch;
            item.classList.toggle("d-none", !isVisible);
            if (isVisible) visibleCount += 1;
        });

        const counterEl = $("glossary-results-counter");
        if (counterEl) {
            counterEl.textContent = `Mostrando ${visibleCount} de ${total} conceptos`;
        }

        const emptyEl = $("glossary-empty-state");
        if (emptyEl) {
            emptyEl.classList.toggle("d-none", visibleCount > 0);
        }

        const clearBtn = $("glossary-search-clear");
        if (clearBtn) {
            clearBtn.classList.toggle("d-none", !searchQuery.trim());
        }
    }

    function setActiveCategory(category) {
        activeCategory = category || "";
        document.querySelectorAll(".pl-glossary-cat-chip").forEach((chip) => {
            const isMatch = (chip.getAttribute("data-category") || "") === activeCategory;
            chip.classList.toggle("active", isMatch);
            chip.setAttribute("aria-pressed", isMatch ? "true" : "false");
        });
        applyGlossaryFilters();
    }

    function setActiveLevel(level) {
        activeLevel = level || "";
        document.querySelectorAll(".pl-glossary-level-chip").forEach((chip) => {
            const isMatch = (chip.getAttribute("data-level") || "") === activeLevel;
            chip.classList.toggle("active", isMatch);
            chip.setAttribute("aria-pressed", isMatch ? "true" : "false");
        });
        applyGlossaryFilters();
    }

    function resetAllFilters() {
        searchQuery = "";
        const searchInput = $("glossary-search-input");
        if (searchInput) searchInput.value = "";
        activeCategory = "";
        activeLevel = "";
        document.querySelectorAll(".pl-glossary-cat-chip").forEach((chip) => {
            const isAll = (chip.getAttribute("data-category") || "") === "";
            chip.classList.toggle("active", isAll);
            chip.setAttribute("aria-pressed", isAll ? "true" : "false");
        });
        document.querySelectorAll(".pl-glossary-level-chip").forEach((chip) => {
            const isAll = (chip.getAttribute("data-level") || "") === "";
            chip.classList.toggle("active", isAll);
            chip.setAttribute("aria-pressed", isAll ? "true" : "false");
        });
        applyGlossaryFilters();
    }

    function highlightTargetCard(rawHash) {
        const cleanId = decodeURIComponent(String(rawHash || "").replace(/^#/, "")).trim();
        if (!cleanId) return;

        const targetCard = document.getElementById(cleanId);
        if (!targetCard || !targetCard.classList.contains("pl-glossary-card")) return;

        const wrapper = targetCard.closest(".pl-glossary-item");
        if (wrapper && wrapper.classList.contains("d-none")) {
            resetAllFilters();
        }

        document.querySelectorAll(".pl-glossary-highlight").forEach((el) => {
            el.classList.remove("pl-glossary-highlight");
        });

        const prefersReducedMotion =
            typeof window.matchMedia === "function" &&
            window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        targetCard.scrollIntoView({
            behavior: prefersReducedMotion ? "auto" : "smooth",
            block: "center",
        });

        targetCard.classList.add("pl-glossary-highlight");
        if (highlightTimer) {
            clearTimeout(highlightTimer);
        }
        highlightTimer = setTimeout(() => {
            targetCard.classList.remove("pl-glossary-highlight");
        }, 3200);
    }

    function copyAnchorUrl(text) {
        if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            return navigator.clipboard.writeText(text).catch(() => copyAnchorFallback(text));
        }
        return copyAnchorFallback(text);
    }

    function copyAnchorFallback(text) {
        return new Promise((resolve) => {
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
            } catch (_e) {}
            resolve();
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        const searchInput = $("glossary-search-input");
        if (searchInput) {
            searchInput.addEventListener("input", () => {
                searchQuery = searchInput.value || "";
                applyGlossaryFilters();
            });
        }

        const clearBtn = $("glossary-search-clear");
        if (clearBtn) {
            clearBtn.addEventListener("click", () => {
                searchQuery = "";
                if (searchInput) {
                    searchInput.value = "";
                    searchInput.focus();
                }
                applyGlossaryFilters();
            });
        }

        document.querySelectorAll(".pl-glossary-cat-chip").forEach((chip) => {
            chip.addEventListener("click", () => {
                setActiveCategory(chip.getAttribute("data-category") || "");
            });
        });

        document.querySelectorAll(".pl-glossary-level-chip").forEach((chip) => {
            chip.addEventListener("click", () => {
                setActiveLevel(chip.getAttribute("data-level") || "");
            });
        });

        const resetBtn = $("btn-reset-glossary-filters");
        if (resetBtn) {
            resetBtn.addEventListener("click", resetAllFilters);
        }

        document.querySelectorAll(".pl-glossary-anchor").forEach((anchor) => {
            anchor.addEventListener("click", () => {
                const href = anchor.getAttribute("href") || "";
                if (href.startsWith("#")) {
                    const shareUrl = `${window.location.origin}${window.location.pathname}${href}`;
                    copyAnchorUrl(shareUrl).then(() => {
                        const prevTip = anchor.getAttribute("data-tip") || "Copiar enlace directo a este concepto";
                        anchor.textContent = "✓";
                        anchor.setAttribute("data-tip", "¡Enlace copiado!");
                        if (window.PromptLabTooltips && typeof window.PromptLabTooltips.refresh === "function") {
                            window.PromptLabTooltips.refresh(anchor);
                        }
                        setTimeout(() => {
                            anchor.textContent = "#";
                            anchor.setAttribute("data-tip", prevTip);
                            if (window.PromptLabTooltips && typeof window.PromptLabTooltips.refresh === "function") {
                                window.PromptLabTooltips.refresh(anchor);
                            }
                        }, 1400);
                    });
                    setTimeout(() => highlightTargetCard(href), 20);
                }
            });
        });

        applyGlossaryFilters();

        if (window.location.hash) {
            setTimeout(() => highlightTargetCard(window.location.hash), 60);
        }
    });

    window.addEventListener("hashchange", function () {
        if (window.location.hash) {
            highlightTargetCard(window.location.hash);
        }
    });
})();
