/* ==========================================================================
   PromptLab v8.0.3 — Sistema Global de Tooltips Accesibles (100% Offline)
   Sin Popper ni CDNs; renderizado seguro con textContent y clamping automático al viewport.
   ========================================================================== */

(function () {
    "use strict";

    const TOOLTIP_ID = "pl-tooltip-layer";
    const EDGE_PAD = 12;
    const GAP = 8;

    let bubbleEl = null;
    let activeTrigger = null;
    let pinnedByTouchOrClick = false;
    let lastTouchTs = 0;

    function ensureBubble() {
        if (bubbleEl) return bubbleEl;
        const existing = document.getElementById(TOOLTIP_ID);
        if (existing) {
            bubbleEl = existing;
            return bubbleEl;
        }
        const el = document.createElement("div");
        el.id = TOOLTIP_ID;
        el.className = "pl-tooltip-bubble";
        el.setAttribute("role", "tooltip");
        el.setAttribute("aria-hidden", "true");
        document.body.appendChild(el);
        bubbleEl = el;
        return bubbleEl;
    }

    function stripNativeTitles(root) {
        const scope = root && root.querySelectorAll ? root : document;
        scope.querySelectorAll("[data-tip][title]").forEach((node) => {
            node.removeAttribute("title");
        });
    }

    function positionBubble() {
        if (!bubbleEl || !activeTrigger) return;
        if (!document.body.contains(activeTrigger)) {
            hideTooltip();
            return;
        }

        const rect = activeTrigger.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) {
            hideTooltip();
            return;
        }
        if (rect.bottom < 0 || rect.top > window.innerHeight) {
            hideTooltip();
            return;
        }

        const vw = window.innerWidth || document.documentElement.clientWidth || 1280;
        const vh = window.innerHeight || document.documentElement.clientHeight || 720;

        bubbleEl.style.left = "0px";
        bubbleEl.style.top = "0px";
        const bRect = bubbleEl.getBoundingClientRect();
        const bWidth = bRect.width || 240;
        const bHeight = bRect.height || 48;

        let top = rect.top - bHeight - GAP;
        if (top < EDGE_PAD) {
            top = rect.bottom + GAP;
        }
        const maxTop = Math.max(EDGE_PAD, vh - bHeight - EDGE_PAD);
        top = Math.min(Math.max(EDGE_PAD, top), maxTop);

        let left = rect.left + rect.width / 2 - bWidth / 2;
        const maxLeft = Math.max(EDGE_PAD, vw - bWidth - EDGE_PAD);
        left = Math.min(Math.max(EDGE_PAD, left), maxLeft);

        bubbleEl.style.left = `${Math.round(left)}px`;
        bubbleEl.style.top = `${Math.round(top)}px`;
    }

    function showTooltip(trigger, pinned) {
        if (!trigger) return;
        const text = (trigger.getAttribute("data-tip") || "").trim();
        if (!text) return;

        if (trigger.hasAttribute("title")) {
            trigger.removeAttribute("title");
        }

        const layer = ensureBubble();
        if (activeTrigger && activeTrigger !== trigger) {
            activeTrigger.removeAttribute("aria-describedby");
        }

        activeTrigger = trigger;
        pinnedByTouchOrClick = Boolean(pinned);
        layer.textContent = text;
        layer.setAttribute("aria-hidden", "false");
        trigger.setAttribute("aria-describedby", TOOLTIP_ID);
        layer.classList.add("is-visible");
        positionBubble();
    }

    function hideTooltip() {
        if (activeTrigger) {
            activeTrigger.removeAttribute("aria-describedby");
        }
        activeTrigger = null;
        pinnedByTouchOrClick = false;
        if (bubbleEl) {
            bubbleEl.classList.remove("is-visible");
            bubbleEl.setAttribute("aria-hidden", "true");
        }
    }

    function findTrigger(target) {
        if (!target || typeof target.closest !== "function") return null;
        return target.closest("[data-tip]");
    }

    document.addEventListener("DOMContentLoaded", function () {
        ensureBubble();
        stripNativeTitles(document);

        document.addEventListener(
            "touchstart",
            function () {
                lastTouchTs = Date.now();
            },
            { passive: true }
        );

        document.addEventListener("mouseover", function (e) {
            if (Date.now() - lastTouchTs < 650) return;
            const trigger = findTrigger(e.target);
            if (!trigger) return;
            if (e.relatedTarget && trigger.contains(e.relatedTarget)) return;
            showTooltip(trigger, false);
        });

        document.addEventListener("mouseout", function (e) {
            if (Date.now() - lastTouchTs < 650) return;
            const trigger = findTrigger(e.target);
            if (!trigger || trigger !== activeTrigger) return;
            if (e.relatedTarget && trigger.contains(e.relatedTarget)) return;
            if (!pinnedByTouchOrClick) {
                hideTooltip();
            }
        });

        document.addEventListener("focusin", function (e) {
            const trigger = findTrigger(e.target);
            if (!trigger) return;
            showTooltip(trigger, false);
        });

        document.addEventListener("focusout", function (e) {
            const trigger = findTrigger(e.target);
            if (!trigger || trigger !== activeTrigger) return;
            if (e.relatedTarget && trigger.contains(e.relatedTarget)) return;
            hideTooltip();
        });

        document.addEventListener("click", function (e) {
            const trigger = findTrigger(e.target);
            if (!trigger) {
                if (activeTrigger) hideTooltip();
                return;
            }

            const isIconBtn = trigger.classList.contains("pl-tip-icon");
            const isInlineTip = trigger.classList.contains("pl-tip");
            const isInteractiveAction =
                trigger.matches("a[href], button:not(.pl-tip-icon)") ||
                Boolean(e.target.closest("a[href], button:not(.pl-tip-icon)"));

            if (isIconBtn) {
                e.preventDefault();
                e.stopPropagation();
            }

            if (isIconBtn || (isInlineTip && !isInteractiveAction)) {
                if (activeTrigger === trigger && pinnedByTouchOrClick) {
                    hideTooltip();
                } else {
                    showTooltip(trigger, true);
                }
            }
        });

        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && activeTrigger) {
                hideTooltip();
            }
        });

        window.addEventListener("resize", positionBubble, { passive: true });
        window.addEventListener("scroll", positionBubble, true);
    });

    window.PromptLabTooltips = {
        refresh: function (trigger) {
            if (trigger && trigger === activeTrigger) {
                showTooltip(trigger, pinnedByTouchOrClick);
            } else {
                positionBubble();
            }
        },
        hide: hideTooltip,
    };
})();
