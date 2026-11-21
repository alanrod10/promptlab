/* ==========================================================================
   PromptLab v7.0 — Espacio de Trabajo Progresivo (100% Offline)
   Modos: Express (Ligera) | Guiado (Completa) | Estudio Pro (Profunda)
   ========================================================================== */

(function () {
    "use strict";

    const MODE_TO_LEVEL = {
        express: "Ligera",
        guiado: "Completa",
        pro: "Profunda",
    };

    const LEVEL_TO_MODE = {
        Ligera: "express",
        Completa: "guiado",
        Profunda: "pro",
    };

    const ALL_DOMAINS = [
        "Ciencia de Datos e IA",
        "Tecnología y programación",
        "Estudio y academia",
        "Negocios y comercio",
        "Redacción y comunicación",
        "Investigar y analizar",
        "Trámites y documentos",
        "Planificación y productividad",
        "Toma de decisiones",
        "Otro / General",
    ];

    const ALL_ACTIONS = [
        { key: "depurar_error", label: "Depurar error" },
        { key: "generar_codigo", label: "Generar código" },
        { key: "analizar_datos", label: "Analizar datos" },
        { key: "comparar_evaluar", label: "Comparar y evaluar" },
        { key: "resumir_sintetizar", label: "Resumir y sintetizar" },
        { key: "planificar_pasos", label: "Planificar pasos" },
        { key: "redactar_contenido", label: "Redactar contenido" },
        { key: "explicar_concepto", label: "Explicar concepto" },
        { key: "transformar_formato", label: "Transformar o estructurar datos" },
        { key: "extraer_informacion", label: "Extraer datos puntuales" },
        { key: "clasificar_categorizar", label: "Clasificar o etiquetar" },
        { key: "traducir_adaptar", label: "Traducir o adaptar tono" },
        { key: "reescribir_mejorar", label: "Pulir o mejorar redacción" },
        { key: "auditar_criticar", label: "Revisar riesgos o cláusulas" },
        { key: "simular_practicar", label: "Simular diálogo o entrenamiento" },
        { key: "idear_alternativas", label: "Generar ideas o alternativas" },
        { key: "calcular_modelar", label: "Calcular números o escenarios" },
        { key: "razonar_resolver", label: "Resolver problema lógico" },
        { key: "decidir_recomendar", label: "Evaluar opciones y recomendar" },
        { key: "diagnosticar_resolver", label: "Diagnosticar fallas generales" },
        { key: "consultar_dato", label: "Consulta directa breve" },
    ];

    const ALL_DELIVERABLES = [
        "código",
        "tabla",
        "lista",
        "guía paso a paso",
        "email / mensaje",
        "informe estructurado",
        "json",
        "resumen ejecutivo",
        "diálogo interactivo",
    ];

    const UNIVERSAL_SLOT_KEYS = new Set([
        "general_audience",
        "audience",
        "Público",
        "Nivel Educativo",
    ]);

    // Estado del espacio de trabajo
    let currentMode = "express";
    let lastResultData = null;
    let lastLiveData = null;
    let currentPromptId = null;
    let currentIsFavorite = false;
    let liveDebounceTimer = null;
    let overrideDomain = "";
    let overrideAction = "";
    let overrideDeliverable = "";
    let slotAnswers = {};
    let activeQuickRules = new Set();
    let pendingChangesCount = 0;

    function $(id) {
        return document.getElementById(id);
    }

    function autoResizeOutputTextarea() {
        const output = $("generated-prompt-output");
        if (!output) return;
        const minH = currentMode === "express" ? 220 : 360;
        const maxH = currentMode === "express" ? 380 : 480;
        output.style.height = "auto";
        const targetH = Math.min(Math.max(output.scrollHeight + 8, minH), maxH);
        output.style.height = `${targetH}px`;
    }

    function updatePendingChangesUI() {
        const btn = $("btn-improve-assistant");
        const label = $("btn-improve-assistant-label");
        const badge = $("pending-changes-badge");
        if (!btn) return;
        const hasPending = pendingChangesCount > 0 && lastResultData !== null;
        btn.classList.toggle("pl-btn-has-changes", hasPending);
        if (label) {
            label.innerText = hasPending ? "Aplicar cambios y regenerar" : "Aplicar y Mejorar Prompt";
        }
        if (badge) {
            badge.innerText = String(pendingChangesCount);
            badge.classList.toggle("d-none", !hasPending);
        }
    }

    function markPendingAssistantChange() {
        if (!lastResultData) return;
        pendingChangesCount += 1;
        updatePendingChangesUI();
    }

    function clearPendingAssistantChanges() {
        pendingChangesCount = 0;
        updatePendingChangesUI();
    }

    function pruneStaleSlotAnswers(data) {
        const activeIds = new Set(data.active_slot_ids || []);
        (data.suggested_slots || []).forEach((s) => {
            if (s && s.id) activeIds.add(s.id);
        });
        if (activeIds.size === 0) return;
        Object.keys(slotAnswers).forEach((k) => {
            if (!activeIds.has(k) && !UNIVERSAL_SLOT_KEYS.has(k)) {
                delete slotAnswers[k];
            }
        });
    }

    function escapeHtml(str) {
        return String(str || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function getCsrfToken() {
        const input = document.querySelector('#workspace-csrf-holder input[name="csrfmiddlewaretoken"]');
        if (input && input.value) return input.value;
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function getScoreBandText(score) {
        if (score >= 80) return "Muy bueno";
        if (score >= 60) return "Bueno";
        if (score >= 40) return "Aceptable";
        return "Para mejorar";
    }

    function mostrarAviso(mensaje) {
        const banner = $("ui-alert-banner");
        const textEl = $("ui-alert-text");
        if (!banner || !textEl) return;
        textEl.innerText = mensaje;
        banner.classList.remove("d-none");
        setTimeout(() => banner.classList.add("d-none"), 4500);
    }

    // ------------------------------------------------------------------
    // Selector de 3 Modos (Express / Guiado / Estudio Pro)
    // ------------------------------------------------------------------

    function setWorkspaceMode(mode, persist) {
        if (!MODE_TO_LEVEL[mode]) mode = "express";
        currentMode = mode;

        const shell = $("workspace-root");
        if (shell) shell.setAttribute("data-mode", mode);

        const levelSelect = $("improvement-level");
        if (levelSelect) levelSelect.value = MODE_TO_LEVEL[mode];

        document.querySelectorAll(".pl-mode-btn").forEach((btn) => {
            const isActive = btn.getAttribute("data-mode") === mode;
            btn.classList.toggle("active", isActive);
            btn.setAttribute("aria-pressed", isActive ? "true" : "false");
        });

        if (mode !== "pro") {
            switchOutputTab("editor");
        }
        autoResizeOutputTextarea();

        if (persist !== false) {
            try {
                localStorage.setItem("promptlab_mode", mode);
            } catch (_e) {
                // Storage deshabilitado
            }
        }
    }

    function switchOutputTab(tab) {
        const editorPane = $("view-editor-pane");
        const originPane = $("view-origin-pane");
        const btnEditor = $("tab-btn-editor");
        const btnOrigin = $("tab-btn-origin");
        if (!editorPane || !originPane || !btnEditor || !btnOrigin) return;

        if (tab === "origin") {
            editorPane.classList.add("d-none");
            originPane.classList.remove("d-none");
            btnEditor.classList.remove("active");
            btnOrigin.classList.add("active");
        } else {
            originPane.classList.add("d-none");
            editorPane.classList.remove("d-none");
            btnOrigin.classList.remove("active");
            btnEditor.classList.add("active");
        }
    }

    // ------------------------------------------------------------------
    // Placeholders pendientes (corregido para voseo [PEGÁ ACÁ])
    // ------------------------------------------------------------------

    function hasPendingPlaceholders(text) {
        if (!text) return false;
        const up = text.toUpperCase();
        return (
            up.includes("[PEGÁ ACÁ") ||
            up.includes("[PEGA AQUÍ") ||
            up.includes("[PEGA AQUI") ||
            up.includes("[COMPLETAR") ||
            text.includes("<datos_entrada>")
        );
    }

    function enfocarDatosPendientes() {
        switchOutputTab("editor");
        const output = $("generated-prompt-output");
        if (!output) return;
        const val = output.value || "";
        const up = val.toUpperCase();
        const markers = ["[PEGÁ ACÁ", "[PEGA AQUÍ", "[PEGA AQUI", "[COMPLETAR"];
        let idx = -1;
        for (const m of markers) {
            const found = up.indexOf(m);
            if (found !== -1 && (idx === -1 || found < idx)) {
                idx = found;
            }
        }
        output.focus();
        if (idx !== -1) {
            const end = val.indexOf("]", idx);
            output.setSelectionRange(idx, end !== -1 ? end + 1 : idx + 12);
        }
    }

    // ------------------------------------------------------------------
    // Chips editables en Estudio Pro (con botón X para revertir individual)
    // ------------------------------------------------------------------

    function populateChipDropdowns() {
        const domMenu = $("dropdown-domain-menu");
        const actMenu = $("dropdown-action-menu");
        const delMenu = $("dropdown-deliverable-menu");
        if (!domMenu || !actMenu || !delMenu) return;

        domMenu.innerHTML = ALL_DOMAINS.map(
            (d) =>
                `<li><button type="button" class="dropdown-item small" data-override-type="domain" data-override-val="${escapeHtml(d)}">${escapeHtml(d)}</button></li>`
        ).join("");

        actMenu.innerHTML = ALL_ACTIONS.map(
            (a) =>
                `<li><button type="button" class="dropdown-item small" data-override-type="action" data-override-val="${escapeHtml(a.key)}" data-override-label="${escapeHtml(a.label)}">${escapeHtml(a.label)}</button></li>`
        ).join("");

        delMenu.innerHTML = ALL_DELIVERABLES.map(
            (del) =>
                `<li><button type="button" class="dropdown-item small" data-override-type="deliverable" data-override-val="${escapeHtml(del)}">${escapeHtml(del)}</button></li>`
        ).join("");

        [domMenu, actMenu, delMenu].forEach((menu) => {
            menu.addEventListener("click", (e) => {
                const btn = e.target.closest("button[data-override-type]");
                if (!btn) return;
                selectOverride(
                    btn.getAttribute("data-override-type"),
                    btn.getAttribute("data-override-val"),
                    btn.getAttribute("data-override-label") || ""
                );
            });
        });
    }

    function updateChipResetUI(type, isCorrected) {
        const chip = $(`chip-${type}`);
        const resetBtn = $(`chip-${type}-reset`);
        if (chip) chip.classList.toggle("corrected", isCorrected);
        if (resetBtn) resetBtn.classList.toggle("d-none", !isCorrected);
    }

    function selectOverride(type, value, label) {
        if (type === "domain") {
            overrideDomain = value;
            if ($("chip-domain-val")) $("chip-domain-val").innerText = value;
            updateChipResetUI("domain", true);
        } else if (type === "action") {
            overrideAction = value;
            const resolvedLabel = label || ALL_ACTIONS.find((a) => a.key === value)?.label || value;
            if ($("chip-action-val")) $("chip-action-val").innerText = resolvedLabel;
            updateChipResetUI("action", true);
        } else if (type === "deliverable") {
            overrideDeliverable = value;
            if ($("chip-deliverable-val")) $("chip-deliverable-val").innerText = value;
            updateChipResetUI("deliverable", true);
        }
        triggerLiveAnalyze();
    }

    function clearOverride(type) {
        if (type === "domain") {
            overrideDomain = "";
            updateChipResetUI("domain", false);
        } else if (type === "action") {
            overrideAction = "";
            updateChipResetUI("action", false);
        } else if (type === "deliverable") {
            overrideDeliverable = "";
            updateChipResetUI("deliverable", false);
        }
        triggerLiveAnalyze();
    }

    // ------------------------------------------------------------------
    // Smart Slots, Reglas Rápidas y Desambiguación
    // ------------------------------------------------------------------

    function toggleQuickRule(btn) {
        const rule = btn.getAttribute("data-rule");
        if (!rule) return;
        if (activeQuickRules.has(rule)) {
            activeQuickRules.delete(rule);
            btn.classList.remove("active");
        } else {
            activeQuickRules.add(rule);
            btn.classList.add("active");
        }
        markPendingAssistantChange();
        triggerLiveAnalyze();
    }

    function selectSlotOption(slotId, optionText, btnEl) {
        const group = btnEl.closest(".slot-options-group");
        if (slotAnswers[slotId] === optionText) {
            delete slotAnswers[slotId];
            btnEl.classList.remove("active");
        } else {
            slotAnswers[slotId] = optionText;
            if (group) {
                group.querySelectorAll(".pl-quick-option").forEach((b) => b.classList.remove("active"));
            }
            btnEl.classList.add("active");
        }
        markPendingAssistantChange();
        triggerLiveAnalyze();
    }

    function renderSmartSlots(slots) {
        const container = $("smart-slots-container");
        if (!container) return;

        if (!slots || slots.length === 0) {
            container.innerHTML = `
                <div class="pl-analysis-box p-3 small">
                    <i class="bi bi-stars text-primary me-1"></i>
                    <strong class="pl-text-primary">Datos que faltan para mejorar tu resultado:</strong>
                    <span class="pl-text-secondary">Empezá a escribir tu pedido para ver preguntas simples que suman puntos reales.</span>
                </div>`;
            return;
        }

        let html =
            '<div class="d-flex justify-content-between align-items-center mb-2">' +
            '<label class="form-label fw-bold pl-text-primary small text-uppercase mb-0">Datos que faltan para mejorar tu resultado</label>' +
            "</div>";

        slots.forEach((slot) => {
            const currentAns = slotAnswers[slot.id] || "";
            const optsHtml = (slot.options || [])
                .map((opt) => {
                    const isActive = currentAns === opt ? "active" : "";
                    return `<button type="button" class="pl-quick-option ${isActive}" data-slot-id="${escapeHtml(slot.id)}" data-slot-opt="${escapeHtml(opt)}">${escapeHtml(opt)}</button>`;
                })
                .join("");

            html += `
                <div class="pl-analysis-box p-3 mb-2">
                    <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
                        <span class="small fw-semibold pl-text-primary">${escapeHtml(slot.question)}</span>
                        <span class="pl-impact-badge flex-shrink-0">+${Number(slot.impact_pts || 5)} pts</span>
                    </div>
                    <div class="d-flex flex-wrap gap-1 slot-options-group">${optsHtml}</div>
                </div>`;
        });

        container.innerHTML = html;
        container.querySelectorAll("button[data-slot-id]").forEach((btn) => {
            btn.addEventListener("click", () => {
                selectSlotOption(
                    btn.getAttribute("data-slot-id"),
                    btn.getAttribute("data-slot-opt"),
                    btn
                );
            });
        });
    }

    function renderDisambiguationCard(data) {
        const card = $("disambiguation-card");
        const titleEl = $("disambiguation-title");
        const bodyEl = $("disambiguation-options-list");
        if (!card || !titleEl || !bodyEl) return;

        // Caso 1: Pedido vago -> mostrar 3 caminos rápidos
        if (data.is_vague && data.suggested_paths && data.suggested_paths.length > 0) {
            titleEl.innerText = "Tu pedido es breve o abierto — elegí un camino rápido para completarlo:";
            bodyEl.innerHTML = `<div class="d-flex flex-wrap gap-2">${data.suggested_paths
                .map(
                    (sp) =>
                        `<button type="button" class="pl-quick-option" data-suggested-prompt="${escapeHtml(sp.prompt)}">${escapeHtml(sp.label)}</button>`
                )
                .join("")}</div>`;
            bodyEl.querySelectorAll("button[data-suggested-prompt]").forEach((btn) => {
                btn.addEventListener("click", () => {
                    const input = $("prompt-input");
                    if (input) {
                        input.value = btn.getAttribute("data-suggested-prompt") || "";
                        input.focus();
                    }
                    triggerLiveAnalyze();
                });
            });
            card.classList.remove("d-none");
            return;
        }

        // Caso 2: Ambigüedad entre 2 intenciones (y el usuario aún no eligió overrideAction)
        if (
            !overrideAction &&
            data.needs_disambiguation &&
            data.disambiguation_options &&
            data.disambiguation_options.length >= 2
        ) {
            titleEl.innerText = "¿Qué querés priorizar en este pedido? Elegí una opción:";
            bodyEl.innerHTML = `<div class="row g-2">${data.disambiguation_options
                .slice(0, 2)
                .map(
                    (opt) => `
                    <div class="col-sm-6">
                        <button type="button" class="pl-disamb-option" data-disamb-action="${escapeHtml(opt.action)}" data-disamb-label="${escapeHtml(opt.label)}">
                            <span class="fw-semibold small text-primary">${escapeHtml(opt.label)}</span>
                            <span class="pl-text-secondary" style="font-size: 0.76rem;">${escapeHtml(opt.hint || "")}</span>
                        </button>
                    </div>`
                )
                .join("")}</div>`;
            bodyEl.querySelectorAll("button[data-disamb-action]").forEach((btn) => {
                btn.addEventListener("click", () => {
                    selectOverride(
                        "action",
                        btn.getAttribute("data-disamb-action"),
                        btn.getAttribute("data-disamb-label")
                    );
                    card.classList.add("d-none");
                });
            });
            card.classList.remove("d-none");
            return;
        }

        card.classList.add("d-none");
    }

    function updateExpressBridgeBanner(slots) {
        const countEl = $("bridge-slots-count");
        const ptsEl = $("bridge-slots-pts");
        if (!countEl || !ptsEl) return;
        const list = slots || [];
        const n = list.length || 3;
        const totalPts = list.reduce((acc, s) => acc + Number(s.impact_pts || 6), 0) || 18;
        countEl.innerText = String(n);
        ptsEl.innerText = `+${totalPts} pts`;
    }

    // ------------------------------------------------------------------
    // Rúbrica v2 y Mapa de Origen (Estudio Pro)
    // ------------------------------------------------------------------

    function renderRubricBars(breakdown) {
        const rubricBars = $("rubric-bars");
        if (!rubricBars || !breakdown) return;
        rubricBars.innerHTML = Object.entries(breakdown)
            .map(([crit, val]) => {
                const pct = Math.min(Math.max((Number(val) / 20) * 100, 0), 100);
                return `
                    <div class="mb-2">
                        <div class="d-flex justify-content-between pl-text-primary" style="font-size: 0.76rem;">
                            <span>${escapeHtml(crit)}</span>
                            <span class="fw-bold">${val}/20</span>
                        </div>
                        <div class="pl-progress mt-1">
                            <div class="pl-progress-bar h-100" style="width: ${pct}%"></div>
                        </div>
                    </div>`;
            })
            .join("");
    }

    function renderOriginSegments(segments, trace) {
        const segContainer = $("origin-segments-container");
        const traceContainer = $("trace-container");
        const traceList = $("trace-list");
        const inspector = $("origin-rule-inspector");
        if (!segContainer) return;

        if (!segments || segments.length === 0) {
            segContainer.innerHTML =
                '<p class="pl-text-secondary small">Genera o mejora un prompt para visualizar el mapa de origen y las reglas disparadas.</p>';
            return;
        }

        segContainer.innerHTML = "";
        segments.forEach((seg) => {
            const cls =
                seg.source === "user"
                    ? "origin-user"
                    : seg.source === "inferred"
                      ? "origin-inferred"
                      : "origin-scaffold";
            const div = document.createElement("div");
            div.className = `origin-block ${cls}`;
            div.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <strong class="small text-uppercase">${escapeHtml(seg.block)}</strong>
                    <span class="badge bg-secondary bg-opacity-10 pl-text-secondary" style="font-size: 0.7rem;">${escapeHtml(seg.source)}</span>
                </div>
                <div class="small" style="white-space: pre-wrap;">${escapeHtml(seg.text)}</div>`;
            div.addEventListener("click", () => {
                if (inspector) {
                    inspector.innerText = seg.rule_plain
                        ? `Por qué se agregó: ${seg.rule_plain} (${seg.rule})`
                        : `Regla: ${seg.rule}`;
                }
            });
            segContainer.appendChild(div);
        });

        if (traceList && traceContainer && trace && trace.length > 0) {
            traceList.innerHTML = trace
                .map((t) => {
                    const detail =
                        t.rule ||
                        `${t.domain || ""} / ${t.action || ""} (conf: ${Math.round((t.confidence || 0) * 100)}%)`;
                    return `<li><strong>${escapeHtml(t.stage)}:</strong> ${escapeHtml(detail)}</li>`;
                })
                .join("");
            traceContainer.classList.remove("d-none");
        }
    }

    // ------------------------------------------------------------------
    // Recolección de datos y Análisis en Vivo (debounce 350 ms)
    // ------------------------------------------------------------------

    function getInputText() {
        const el = $("prompt-input");
        return el ? el.value.trim() : "";
    }

    function collectFormData() {
        const formData = { ...slotAnswers };
        if (activeQuickRules.size > 0) {
            formData["Reglas Rápidas"] = Array.from(activeQuickRules).join(", ");
        }
        return formData;
    }

    function getNegativeConstraintsList() {
        const el = $("negative-constraints-input");
        const raw = el ? (el.value || "").trim() : "";
        if (!raw) return [];
        return raw
            .split(/[;\n,]+/)
            .map((s) => s.trim())
            .filter(Boolean);
    }

    function triggerLiveAnalyze() {
        clearTimeout(liveDebounceTimer);
        liveDebounceTimer = setTimeout(async () => {
            const text = getInputText();
            if (!text || text.length < 3) {
                lastLiveData = null;
                if ($("live-detection-bar")) $("live-detection-bar").classList.add("d-none");
                if ($("pii-alert-banner")) $("pii-alert-banner").classList.add("d-none");
                if ($("contradiction-banner")) $("contradiction-banner").classList.add("d-none");
                if ($("disambiguation-card")) $("disambiguation-card").classList.add("d-none");
                if ($("live-payload-badge")) $("live-payload-badge").classList.add("d-none");
                if ($("live-calc-badge")) $("live-calc-badge").classList.add("d-none");
                return;
            }

            try {
                const resp = await fetch("/api/analyze-live/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        text: text,
                        category: $("category-select") ? $("category-select").value : "",
                        form_data: collectFormData(),
                        technique: $("technique-select") ? $("technique-select").value : "Estándar",
                        override_domain: overrideDomain,
                        override_action: overrideAction,
                        override_deliverable: overrideDeliverable,
                        negative_constraints: getNegativeConstraintsList(),
                    }),
                });
                if (!resp.ok) return;
                const data = await resp.json();
                lastLiveData = data;

                // Barra de detección en vivo (visible en Estudio Pro)
                if ($("live-detection-bar")) $("live-detection-bar").classList.remove("d-none");
                if ($("chip-domain-val")) $("chip-domain-val").innerText = overrideDomain || data.domain;
                if ($("chip-action-val")) {
                    $("chip-action-val").innerText = overrideAction
                        ? ALL_ACTIONS.find((a) => a.key === overrideAction)?.label || overrideAction
                        : data.action_label;
                }
                if ($("chip-deliverable-val")) {
                    $("chip-deliverable-val").innerText = overrideDeliverable || data.deliverable;
                }

                const confPct = Math.round((data.confidence || 0) * 100);
                if ($("live-confidence-badge")) $("live-confidence-badge").innerText = `Seguridad: ${confPct}%`;
                const entBadge = $("live-entities-badge");
                if (entBadge) {
                    const entList = data.entities || [];
                    const keyCount = entList.length > 0 ? entList.length : data.topic_anchor ? 1 : 0;
                    entBadge.innerText = `Datos clave: ${keyCount}`;
                    entBadge.title =
                        entList.length > 0
                            ? `Entidades: ${entList.join(", ")}`
                            : data.topic_anchor
                              ? `Tema principal: ${data.topic_anchor}`
                              : "Términos clave detectados";
                }

                const payloadBadge = $("live-payload-badge");
                if (payloadBadge) {
                    if (data.payload_kind && data.payload_kind !== "sin_insumo") {
                        payloadBadge.innerText = `Insumo: ${data.payload_summary || data.payload_kind}`;
                        payloadBadge.classList.remove("d-none");
                    } else {
                        payloadBadge.classList.add("d-none");
                    }
                }

                const calcBadge = $("live-calc-badge");
                if (calcBadge) {
                    calcBadge.classList.toggle("d-none", !data.has_calculation);
                }

                const confMsgEl = $("live-confidence-msg");
                if (confMsgEl) {
                    if ((data.confidence || 0) >= 0.70 && !data.is_vague) {
                        confMsgEl.innerText = "Entendimos tu pedido con claridad";
                        confMsgEl.className = "small fw-semibold text-success";
                    } else if ((data.confidence || 0) >= 0.50 && !data.is_vague) {
                        confMsgEl.innerText = "Creemos que buscás esto (tocá cualquier etiqueta para ajustar)";
                        confMsgEl.className = "small fw-semibold text-primary";
                    } else {
                        confMsgEl.innerText = "Pedido breve o abierto — podés afinarlo o elegir un camino";
                        confMsgEl.className = "small fw-semibold text-warning";
                    }
                }

                // Alerta PII (siempre visible en los 3 modos)
                const piiBanner = $("pii-alert-banner");
                if (piiBanner) {
                    if (data.pii_warnings && data.pii_warnings.length > 0) {
                        $("pii-alert-details").innerText = data.pii_warnings
                            .map((w) => `${w.label} (${w.count})`)
                            .join(", ");
                        piiBanner.classList.remove("d-none");
                    } else {
                        piiBanner.classList.add("d-none");
                    }
                }

                // Contradicciones
                const contraBanner = $("contradiction-banner");
                if (contraBanner) {
                    if (data.contradictions && data.contradictions.length > 0) {
                        $("contradiction-text").innerText = data.contradictions.join(" ");
                        contraBanner.classList.remove("d-none");
                    } else {
                        contraBanner.classList.add("d-none");
                    }
                }

                // Tarjeta de desambiguación / caminos rápidos
                renderDisambiguationCard(data);

                // Limpiar respuestas de slots obsoletos antes de renderizar los activos
                pruneStaleSlotAnswers(data);

                // Smart Slots + contador en puente Express -> Guiado
                if (data.suggested_slots && data.suggested_slots.length > 0) {
                    renderSmartSlots(data.suggested_slots);
                    updateExpressBridgeBanner(data.suggested_slots);
                }
            } catch (err) {
                console.error("Error en live analyze:", err);
            }
        }, 350);
    }

    // ------------------------------------------------------------------
    // Favorito desde Espacio de Trabajo (POST /historial/favorito/<id>/)
    // ------------------------------------------------------------------

    function updateFavoriteButtonUI(isFav) {
        currentIsFavorite = Boolean(isFav);
        const btn = $("btn-favorite");
        if (!btn) return;
        const icon = btn.querySelector("i");
        btn.classList.toggle("btn-fav-active", currentIsFavorite);
        btn.title = currentIsFavorite ? "Quitar de favoritos" : "Guardar en favoritos";
        if (icon) {
            icon.className = currentIsFavorite ? "bi bi-star-fill" : "bi bi-star";
        }
    }

    async function toggleCurrentFavorite() {
        if (!currentPromptId) {
            mostrarAviso("Generá un prompt primero para guardarlo en favoritos.");
            return;
        }
        const btn = $("btn-favorite");
        if (btn) btn.disabled = true;
        try {
            const resp = await fetch(`/historial/favorito/${currentPromptId}/`, {
                method: "POST",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    Accept: "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
            });
            if (!resp.ok) {
                mostrarAviso("No se pudo actualizar el estado de favorito.");
                return;
            }
            const data = await resp.json();
            updateFavoriteButtonUI(data.is_favorite);
        } catch (err) {
            console.error(err);
            mostrarAviso("Error de conexión al guardar favorito.");
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    // ------------------------------------------------------------------
    // Generación principal (POST /api/improve/) — NO sobrescribe entrada
    // ------------------------------------------------------------------

    async function mejorarPrompt() {
        const inputEl = $("prompt-input");
        const outputEl = $("generated-prompt-output");
        const outputCard = $("output-card");
        const btnMain = $("btn-improve-main");
        const btnAssist = $("btn-improve-assistant");

        const text = getInputText();
        if (!text || text.length < 3) {
            mostrarAviso("Por favor, escribí al menos 3 caracteres en tu idea para mejorarla.");
            if (inputEl) inputEl.focus();
            return;
        }

        const level = MODE_TO_LEVEL[currentMode] || "Completa";
        const category = currentMode === "express" ? "" : ($("category-select") ? $("category-select").value : "");
        const technique = currentMode === "pro" && $("technique-select") ? $("technique-select").value : "Estándar";
        const formData = currentMode === "express" ? {} : collectFormData();
        const negConstraints = currentMode === "pro" ? getNegativeConstraintsList() : [];
        const userExample =
            currentMode === "pro" && $("user-example-input") ? ($("user-example-input").value || "").trim() : "";
        const maskPii = $("mask-pii-checkbox") ? $("mask-pii-checkbox").checked : true;

        const origMainHtml = btnMain ? btnMain.innerHTML : "";
        const origAssistHtml = btnAssist ? btnAssist.innerHTML : "";
        if (btnMain) {
            btnMain.disabled = true;
            btnMain.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Mejorando...';
        }
        if (btnAssist) {
            btnAssist.disabled = true;
            btnAssist.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Generando...';
        }

        let succeeded = false;
        try {
            const response = await fetch("/api/improve/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: text,
                    category: category || "Ninguna especificada",
                    form_data: formData,
                    level: level,
                    technique: technique,
                    override_domain: overrideDomain,
                    override_action: overrideAction,
                    override_deliverable: overrideDeliverable,
                    negative_constraints: negConstraints,
                    user_example: userExample,
                    mask_pii: maskPii,
                }),
            });

            const data = await response.json();
            if (data.error) {
                mostrarAviso(data.error);
                return;
            }

            succeeded = true;
            lastResultData = data;
            currentPromptId = data.prompt_id || null;
            updateFavoriteButtonUI(Boolean(data.is_favorite));

            if (outputEl) {
                outputEl.value = data.improved_prompt || "";
            }
            if (outputCard) {
                outputCard.classList.remove("d-none");
            }
            autoResizeOutputTextarea();

            // Botón completar placeholders pendientes
            const fillBtn = $("btn-fill-placeholders");
            if (fillBtn) {
                fillBtn.classList.toggle("d-none", !hasPendingPlaceholders(data.improved_prompt));
            }

            // Banda de puntaje superior en #output-card
            const finalScore = data.final_score ?? 0;
            const userScore = data.user_score ?? data.initial_score ?? 0;
            const infoGain = data.information_gain ?? 0;
            const qualityGain = data.quality_gain ?? 0;
            const bandLabel = getScoreBandText(finalScore);

            if ($("output-score-val")) $("output-score-val").innerText = `${finalScore}/100`;
            if ($("output-score-band")) $("output-score-band").innerText = bandLabel;

            // Barra de puntaje simplificada (Guiado)
            if ($("guiado-init-score")) $("guiado-init-score").innerText = `${userScore}/100`;
            if ($("guiado-info-gain")) $("guiado-info-gain").innerText = `+${infoGain} pts`;
            if ($("guiado-final-score")) $("guiado-final-score").innerText = `${finalScore}/100`;
            if ($("guiado-score-bar")) $("guiado-score-bar").style.width = `${Math.min(finalScore, 100)}%`;

            // Panel completo de Rúbrica v2 (Estudio Pro)
            if ($("init-score-lbl")) $("init-score-lbl").innerText = userScore;
            if ($("info-gain-lbl")) $("info-gain-lbl").innerText = `+${infoGain} pts sumados`;
            if ($("final-score-lbl")) $("final-score-lbl").innerText = finalScore;
            if ($("score-band-lbl")) $("score-band-lbl").innerText = `(${bandLabel})`;
            if ($("gain-badge")) $("gain-badge").innerText = `+${qualityGain} pts`;

            const anchorPct = Math.round((data.anchor_coverage ?? 0.95) * 100);
            const noisePct = Math.round((data.noise_ratio ?? 0.04) * 100);
            if ($("anchor-coverage-badge")) $("anchor-coverage-badge").innerText = `${anchorPct}%`;
            const noiseEl = $("noise-ratio-badge");
            if (noiseEl) {
                noiseEl.innerText = `${noisePct}%`;
                noiseEl.className = noisePct < 10 ? "text-success" : "text-warning";
            }

            if (data.rubric_breakdown) {
                renderRubricBars(data.rubric_breakdown);
            }
            renderOriginSegments(data.segments, data.trace);

            const analysisList = $("analysis-list");
            if (analysisList && data.analysis && data.analysis.length > 0) {
                analysisList.innerHTML = data.analysis
                    .map((item) => `<li class="mb-1">${escapeHtml(item)}</li>`)
                    .join("");
            }

            // Puente progresivo en Express
            const bridge = $("express-bridge-banner");
            if (bridge) {
                updateExpressBridgeBanner(data.suggested_slots || (lastLiveData && lastLiveData.suggested_slots) || []);
                bridge.classList.remove("d-none");
            }

            // Desplazar suavemente hacia el resultado generado
            if (outputCard) {
                outputCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
        } catch (error) {
            mostrarAviso("Error de conexión con el servidor local.");
            console.error(error);
        } finally {
            if (btnMain) {
                btnMain.disabled = false;
                btnMain.innerHTML = origMainHtml;
            }
            if (btnAssist) {
                btnAssist.disabled = false;
                btnAssist.innerHTML = origAssistHtml;
            }
            if (succeeded) {
                clearPendingAssistantChanges();
            }
        }
    }

    // ------------------------------------------------------------------
    // Copiar, Exportar, Comparar, Limpiar
    // ------------------------------------------------------------------

    function copiarAlPortapapeles() {
        const output = $("generated-prompt-output");
        if (!output || !output.value) return;
        navigator.clipboard.writeText(output.value).then(() => {
            const btnCopy = $("btn-copy");
            if (!btnCopy) return;
            const originalHtml = btnCopy.innerHTML;
            btnCopy.innerHTML = '<i class="bi bi-check2 me-1"></i> ¡Copiado!';
            btnCopy.classList.add("btn-success");
            btnCopy.classList.remove("btn-brand");
            setTimeout(() => {
                btnCopy.innerHTML = originalHtml;
                btnCopy.classList.remove("btn-success");
                btnCopy.classList.add("btn-brand");
            }, 2000);
        });
    }

    function descargarArchivo(formato) {
        const output = $("generated-prompt-output");
        const content = output ? output.value : "";
        if (!content) return;

        let blob, filename;
        if (formato === "md") {
            blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
            filename = "prompt_estructurado.md";
        } else {
            const payload = lastResultData || {
                improved_prompt: content,
                level: MODE_TO_LEVEL[currentMode] || "Completa",
                technique: $("technique-select") ? $("technique-select").value : "Estándar",
            };
            blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
            filename = "prompt_especificacion.json";
        }

        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    function calcularMetricasTexto(texto) {
        const clean = (texto || "").trim();
        const words = clean ? clean.split(/\s+/).length : 0;
        const chars = clean.length;
        const tokens = Math.ceil(words * 1.3);
        return { words, chars, tokens };
    }

    function abrirComparador() {
        const origText = (lastResultData && lastResultData.raw_objective) || getInputText();
        const impText = $("generated-prompt-output") ? $("generated-prompt-output").value.trim() : "";

        const mOrig = calcularMetricasTexto(origText);
        const mImp = calcularMetricasTexto(impText);

        if ($("cmp-orig-text")) $("cmp-orig-text").innerText = origText;
        if ($("cmp-imp-text")) $("cmp-imp-text").innerText = impText;
        if ($("cmp-orig-metrics")) {
            $("cmp-orig-metrics").innerText = `${mOrig.words} palabras • ${mOrig.chars} chars • ~${mOrig.tokens} tokens`;
        }
        if ($("cmp-imp-metrics")) {
            $("cmp-imp-metrics").innerText = `${mImp.words} palabras • ${mImp.chars} chars • ~${mImp.tokens} tokens`;
        }
    }

    function limpiarEditor() {
        if ($("prompt-input")) $("prompt-input").value = "";
        if ($("generated-prompt-output")) $("generated-prompt-output").value = "";
        if ($("category-select")) $("category-select").value = "";
        if ($("technique-select")) $("technique-select").value = "Estándar";
        if ($("negative-constraints-input")) $("negative-constraints-input").value = "";
        if ($("user-example-input")) $("user-example-input").value = "";

        overrideDomain = "";
        overrideAction = "";
        overrideDeliverable = "";
        ["domain", "action", "deliverable"].forEach((t) => updateChipResetUI(t, false));

        slotAnswers = {};
        activeQuickRules.clear();
        document.querySelectorAll("#quick-rules-container .pl-quick-option").forEach((b) => b.classList.remove("active"));

        renderSmartSlots([]);
        if ($("output-card")) $("output-card").classList.add("d-none");
        if ($("express-bridge-banner")) $("express-bridge-banner").classList.add("d-none");
        if ($("live-detection-bar")) $("live-detection-bar").classList.add("d-none");
        if ($("pii-alert-banner")) $("pii-alert-banner").classList.add("d-none");
        if ($("contradiction-banner")) $("contradiction-banner").classList.add("d-none");
        if ($("disambiguation-card")) $("disambiguation-card").classList.add("d-none");
        if ($("btn-fill-placeholders")) $("btn-fill-placeholders").classList.add("d-none");

        switchOutputTab("editor");
        lastResultData = null;
        lastLiveData = null;
        currentPromptId = null;
        clearPendingAssistantChanges();
        updateFavoriteButtonUI(false);
        if ($("prompt-input")) $("prompt-input").focus();
    }

    // ------------------------------------------------------------------
    // Inicialización al cargar el DOM
    // ------------------------------------------------------------------

    function readBootData() {
        const el = $("workspace-boot-data");
        if (!el) return {};
        try {
            return JSON.parse(el.textContent || "{}");
        } catch (_e) {
            return {};
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        populateChipDropdowns();

        // Selector de 3 modos
        document.querySelectorAll(".pl-mode-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                setWorkspaceMode(btn.getAttribute("data-mode"), true);
            });
        });

        // Botones X para revertir un solo override en chip
        ["domain", "action", "deliverable"].forEach((type) => {
            const resetBtn = $(`chip-${type}-reset`);
            if (resetBtn) {
                resetBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    clearOverride(type);
                });
            }
        });

        // Ejemplos rápidos en Express
        document.querySelectorAll(".pl-example-pill").forEach((btn) => {
            btn.addEventListener("click", () => {
                const sample = btn.getAttribute("data-example") || "";
                const input = $("prompt-input");
                if (input) {
                    input.value = sample;
                    input.focus();
                }
                triggerLiveAnalyze();
            });
        });

        // Reglas rápidas (1 clic)
        document.querySelectorAll("#quick-rules-container .pl-quick-option").forEach((btn) => {
            btn.addEventListener("click", () => toggleQuickRule(btn));
        });

        // Puente Express -> Guiado
        const bridgeBtn = $("btn-bridge-to-guiado");
        if (bridgeBtn) {
            bridgeBtn.addEventListener("click", () => {
                setWorkspaceMode("guiado", true);
                triggerLiveAnalyze();
                const aside = $("smart-slots-container");
                if (aside) aside.scrollIntoView({ behavior: "smooth", block: "nearest" });
            });
        }

        // Eventos principales de entrada
        const inputEl = $("prompt-input");
        if (inputEl) {
            inputEl.addEventListener("input", triggerLiveAnalyze);
            inputEl.addEventListener("keydown", (e) => {
                if (e.ctrlKey && e.key === "Enter") {
                    e.preventDefault();
                    mejorarPrompt();
                }
            });
        }

        const catSelect = $("category-select");
        if (catSelect) {
            catSelect.addEventListener("change", () => {
                markPendingAssistantChange();
                triggerLiveAnalyze();
            });
        }

        const techSelect = $("technique-select");
        if (techSelect) {
            techSelect.addEventListener("change", () => {
                markPendingAssistantChange();
                triggerLiveAnalyze();
            });
        }

        const negInput = $("negative-constraints-input");
        if (negInput) {
            negInput.addEventListener("input", () => {
                markPendingAssistantChange();
                triggerLiveAnalyze();
            });
        }

        const userExInput = $("user-example-input");
        if (userExInput) {
            userExInput.addEventListener("input", markPendingAssistantChange);
        }

        // Botones de acción
        if ($("btn-improve-main")) $("btn-improve-main").addEventListener("click", mejorarPrompt);
        if ($("btn-improve-assistant")) $("btn-improve-assistant").addEventListener("click", mejorarPrompt);
        if ($("btn-clear-all")) $("btn-clear-all").addEventListener("click", limpiarEditor);
        if ($("btn-copy")) $("btn-copy").addEventListener("click", copiarAlPortapapeles);
        if ($("btn-favorite")) $("btn-favorite").addEventListener("click", toggleCurrentFavorite);
        if ($("btn-compare")) $("btn-compare").addEventListener("click", abrirComparador);
        if ($("btn-export-md")) $("btn-export-md").addEventListener("click", () => descargarArchivo("md"));
        if ($("btn-export-json")) $("btn-export-json").addEventListener("click", () => descargarArchivo("json"));
        if ($("btn-fill-placeholders")) $("btn-fill-placeholders").addEventListener("click", enfocarDatosPendientes);
        if ($("tab-btn-editor")) $("tab-btn-editor").addEventListener("click", () => switchOutputTab("editor"));
        if ($("tab-btn-origin")) $("tab-btn-origin").addEventListener("click", () => switchOutputTab("origin"));

        // Estado inicial desde backend (?load=<id> | ?preset=<slug> | default localStorage)
        const boot = readBootData();
        if (boot.loaded_prompt) {
            const lp = boot.loaded_prompt;
            const initialMode = LEVEL_TO_MODE[lp.level] || "guiado";
            setWorkspaceMode(initialMode, false);

            currentPromptId = lp.id;
            updateFavoriteButtonUI(Boolean(lp.is_favorite));

            if (boot.loaded_rubric) {
                renderRubricBars(boot.loaded_rubric);
            }
            const outEl = $("generated-prompt-output");
            if (outEl && $("btn-fill-placeholders")) {
                $("btn-fill-placeholders").classList.toggle("d-none", !hasPendingPlaceholders(outEl.value));
            }
            autoResizeOutputTextarea();
            lastResultData = {
                prompt_id: lp.id,
                raw_objective: inputEl ? inputEl.value : "",
                improved_prompt: outEl ? outEl.value : "",
                category: lp.category,
                level: lp.level,
                technique: lp.technique,
                initial_score: lp.initial_score,
                final_score: lp.final_score,
                quality_gain: lp.quality_gain,
                rubric_breakdown: boot.loaded_rubric || null,
            };
            if (inputEl && inputEl.value.trim().length >= 3) {
                triggerLiveAnalyze();
            }
        } else if (boot.preset_data) {
            setWorkspaceMode("guiado", false);
            triggerLiveAnalyze();
        } else {
            let savedMode = "express";
            try {
                savedMode = localStorage.getItem("promptlab_mode") || "express";
            } catch (_e) {
                savedMode = "express";
            }
            setWorkspaceMode(savedMode, false);
        }
    });
})();
