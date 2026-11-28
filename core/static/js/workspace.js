/* ==========================================================================
   PromptLab v7.2 — Espacio de Trabajo Progresivo (100% Offline)
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
        "plan / cronograma",
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
    let currentVersionNumber = 1;
    let iteratingParentId = null;
    let currentIsFavorite = false;
    let liveDebounceTimer = null;
    let overrideDomain = "";
    let overrideAction = "";
    let overrideDeliverable = "";
    let slotAnswers = {};
    let activeQuickRules = new Set();
    let pendingChangesCount = 0;
    let isOutputEditing = false;

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

    function formatInlineMarkdown(escapedLine) {
        const codeTokens = [];
        let out = escapedLine.replace(/`([^`]+)`/g, (_m, code) => {
            const idx = codeTokens.length;
            codeTokens.push(`<code class="pl-fmt-code">${code}</code>`);
            return `__PL_CODE_TOK_${idx}__`;
        });
        out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        out = out.replace(
            /(\[(?:COMPLETAR[^\]]*|PEG[AÁ]\s+AC[AÁ][^\]]*|PEGA\s+AQU[IÍ][^\]]*)\])/gi,
            '<span class="pl-fmt-placeholder">$1</span>'
        );
        out = out.replace(
            /(\[(?:DNI_CUIL|TELEFONO|EMAIL|CBU|ALIAS)_OCULTO\])/g,
            '<span class="pl-fmt-pii-mask">$1</span>'
        );
        codeTokens.forEach((html, idx) => {
            out = out.replace(`__PL_CODE_TOK_${idx}__`, () => html);
        });
        return out;
    }

    function renderFormattedPrompt(text) {
        const preview = $("formatted-prompt-preview");
        if (!preview) return;
        const raw = String(text || "");
        if (!raw.trim()) {
            preview.innerHTML = "";
            return;
        }

        const payloadBlocks = [];
        const withTokens = raw.replace(/<datos_entrada>\r?\n?([\s\S]*?)\r?\n?<\/datos_entrada>/g, (_m, inner) => {
            const idx = payloadBlocks.length;
            payloadBlocks.push(inner);
            return `\n__PL_PAYLOAD_FMT_${idx}__\n`;
        });

        const lines = withTokens.split(/\r?\n/);
        const htmlParts = [];

        lines.forEach((rawLine) => {
            const trimmed = rawLine.trim();
            if (!trimmed) return;

            const payloadMatch = trimmed.match(/^__PL_PAYLOAD_FMT_(\d+)__$/);
            if (payloadMatch) {
                const innerText = payloadBlocks[Number(payloadMatch[1])] || "";
                htmlParts.push(
                    `<div class="pl-fmt-payload-wrap"><div class="pl-fmt-payload-tag">&lt;datos_entrada&gt;</div><pre class="pl-fmt-payload mb-0">${escapeHtml(innerText)}</pre></div>`
                );
                return;
            }

            const headingMatch = trimmed.match(/^#\s+(.+)$/);
            if (headingMatch) {
                htmlParts.push(`<div class="pl-fmt-heading">${formatInlineMarkdown(escapeHtml(headingMatch[1]))}</div>`);
                return;
            }

            const stepMatch = trimmed.match(/^(\d+\.)\s+(.+)$/);
            if (stepMatch) {
                htmlParts.push(
                    `<div class="pl-fmt-step"><span class="pl-fmt-step-num">${escapeHtml(stepMatch[1])}</span><span>${formatInlineMarkdown(escapeHtml(stepMatch[2]))}</span></div>`
                );
                return;
            }

            const bulletMatch = trimmed.match(/^-\s+(.+)$/);
            if (bulletMatch) {
                htmlParts.push(
                    `<div class="pl-fmt-bullet"><span class="pl-fmt-bullet-dot">&bull;</span><span>${formatInlineMarkdown(escapeHtml(bulletMatch[1]))}</span></div>`
                );
                return;
            }

            htmlParts.push(`<p class="pl-fmt-para">${formatInlineMarkdown(escapeHtml(trimmed))}</p>`);
        });

        preview.innerHTML = htmlParts.join("");
    }

    function setOutputEditMode(editing) {
        isOutputEditing = Boolean(editing);
        const preview = $("formatted-prompt-preview");
        const output = $("generated-prompt-output");
        const toggleBtn = $("btn-toggle-edit-output");
        const toggleLabel = $("btn-toggle-edit-label");
        const toggleIcon = toggleBtn ? toggleBtn.querySelector("i") : null;

        if (!isOutputEditing && output) {
            renderFormattedPrompt(output.value);
        }
        if (preview) preview.classList.toggle("d-none", isOutputEditing);
        if (output) output.classList.toggle("d-none", !isOutputEditing);
        if (toggleLabel) toggleLabel.innerText = isOutputEditing ? "Vista lectura" : "Editar texto";
        if (toggleIcon) toggleIcon.className = isOutputEditing ? "bi bi-eye me-1" : "bi bi-pencil me-1";
        if (isOutputEditing) {
            autoResizeOutputTextarea();
        }
    }

    function formatAnalysisItem(item) {
        const raw = String(item || "").trim();
        if (raw.includes(" | ")) {
            const parts = raw.split(" | ").map((s) => s.trim()).filter(Boolean);
            const filtered = parts.filter((p) => !/^Datos útiles:|^Relleno:/i.test(p));
            const finalParts = filtered.length > 0 ? filtered : parts;
            const pills = finalParts
                .map((part) => {
                    const colonIdx = part.indexOf(":");
                    if (colonIdx > 0 && colonIdx < 24) {
                        const k = part.slice(0, colonIdx).trim();
                        const v = part.slice(colonIdx + 1).trim();
                        return `<span class="pl-diag-pill"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(v)}</span>`;
                    }
                    return `<span class="pl-diag-pill">${escapeHtml(part)}</span>`;
                })
                .join("");
            return `<li class="mb-2"><div class="pl-diag-row">${pills}</div></li>`;
        }
        const colonIdx = raw.indexOf(":");
        if (colonIdx > 0 && colonIdx < 34) {
            const k = raw.slice(0, colonIdx).trim();
            const v = raw.slice(colonIdx + 1).trim();
            return `<li class="mb-1"><strong class="pl-text-primary">${escapeHtml(k)}:</strong> ${escapeHtml(v)}</li>`;
        }
        return `<li class="mb-1">${escapeHtml(raw)}</li>`;
    }

    function updatePendingChangesUI() {
        const btn = $("btn-improve-assistant");
        const label = $("btn-improve-assistant-label");
        const badge = $("pending-changes-badge");
        if (!btn) return;
        const hasPending = pendingChangesCount > 0 && lastResultData !== null;
        btn.classList.toggle("btn-brand", hasPending);
        btn.classList.toggle("btn-pl-accent-outline", !hasPending);
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
        if (score >= 90) return "Excelente";
        if (score >= 80) return "Muy bueno";
        if (score >= 70) return "Bueno";
        return "Mejorable";
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
        if (mode === "estudio_pro") mode = "pro";
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
        const up = String(text).toUpperCase();
        return up.includes("[COMPLETAR:");
    }

    function enfocarDatosPendientes() {
        switchOutputTab("editor");
        setOutputEditMode(true);
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
            const hasInput = getInputText().length >= 3;
            if (hasInput) {
                container.innerHTML = `
                    <div class="pl-analysis-box p-3 small" style="border-color: rgba(16, 185, 129, 0.35);">
                        <i class="bi bi-check-circle-fill text-success me-1"></i>
                        <strong class="pl-text-primary">¡Pedido muy completo!</strong>
                        <span class="pl-text-secondary">Tu instrucción ya cubre los datos técnicos clave. Podés sumar Reglas rápidas abajo si querés afinar más.</span>
                    </div>`;
            } else {
                container.innerHTML = `
                    <div class="pl-analysis-box p-3 small">
                        <i class="bi bi-stars text-primary me-1"></i>
                        <strong class="pl-text-primary">Datos que faltan para mejorar tu resultado:</strong>
                        <span class="pl-text-secondary">Empezá a escribir tu pedido para ver preguntas simples que suman puntos reales.</span>
                    </div>`;
            }
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
                <div class="pl-analysis-box py-2 px-3 mb-2">
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
        const textEl = $("express-bridge-text");
        const list = slots || [];
        if (textEl) {
            if (list.length === 0) {
                textEl.innerHTML = "¿Querés estructurarlo por secciones completas con Rol y Criterio de éxito?";
            } else {
                const n = list.length;
                const totalPts = list.reduce((acc, s) => acc + Number(s.impact_pts || 6), 0);
                const plural = n === 1 ? "" : "s";
                textEl.innerHTML = `¿Querés afinarlo respondiendo <strong id="bridge-slots-count">${n}</strong> pregunta${plural} rápida${plural} (<span id="bridge-slots-pts" class="fw-bold text-success">+${totalPts} pts</span>)?`;
            }
            return;
        }
        const countEl = $("bridge-slots-count");
        const ptsEl = $("bridge-slots-pts");
        if (!countEl || !ptsEl) return;
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
                '<p class="pl-text-secondary small">Generá o mejorá un prompt para visualizar el mapa de origen y las reglas disparadas.</p>';
            return;
        }

        const SOURCE_LABELS_ES = {
            user: "Tus palabras",
            inferred: "Deducido por PromptLab",
            scaffold: "Estructura agregada",
        };
        segContainer.innerHTML = "";
        segments.forEach((seg) => {
            const cls =
                seg.source === "user"
                    ? "origin-user"
                    : seg.source === "inferred"
                      ? "origin-inferred"
                      : "origin-scaffold";
            const badgeLabel = SOURCE_LABELS_ES[seg.source] || seg.source;
            const div = document.createElement("div");
            div.className = `origin-block ${cls}`;
            div.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <strong class="small text-uppercase">${escapeHtml(seg.block)}</strong>
                    <span class="badge bg-secondary bg-opacity-25 pl-text-primary" style="font-size: 0.7rem;">${escapeHtml(badgeLabel)}</span>
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
                        `${t.domain || ""} / ${t.action || ""} (certeza: ${Math.round((t.confidence || 0) * 100)}%)`;
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

    function isValidCuitMod11(cuitDigits) {
        if (!/^(?:20|23|24|27|30|33|34)\d{9}$/.test(cuitDigits)) return false;
        const weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
        let acc = 0;
        for (let i = 0; i < 10; i++) {
            acc += Number(cuitDigits[i]) * weights[i];
        }
        const rem = 11 - (acc % 11);
        const dv = Number(cuitDigits[10]);
        if (rem === 11) return dv === 0;
        if (rem === 10) return cuitDigits.startsWith("23") && (dv === 9 || dv === 4);
        return dv === rem;
    }

    function isMoneyContextAround(fullStr, startIdx, endIdx, token) {
        if (token.includes("-")) return false;
        const immediateBefore = fullStr.slice(Math.max(0, startIdx - 20), startIdx);
        if (/\b(?:dni|cuil|cuit|documento|doc\.?)\s*[:=-]?\s*$/i.test(immediateBefore)) {
            return false;
        }
        const beforeChunk = fullStr.slice(Math.max(0, startIdx - 22), startIdx).split(/[,;\n]/).pop() || "";
        const afterChunk = (fullStr.slice(endIdx, Math.min(fullStr.length, endIdx + 22)).split(/[,;\n]/)[0]) || "";
        const moneyRe = /(?:\$|\b(?:pesos?|ars|usd|u\$s|d[oó]lares?|d[oó]lar|presupuesto|gastos?|monto|precios?|importe|cuotas?)\b)/i;
        return moneyRe.test(beforeChunk) || moneyRe.test(afterChunk);
    }

    function detectPiiClientSide(text) {
        if (!text) return [];
        const warnings = [];
        let working = String(text);

        const cbuMatches = working.match(/\b\d{22}\b/g) || [];
        if (cbuMatches.length) {
            working = working.replace(/\b\d{22}\b/g, "[CBU_OCULTO]");
            warnings.push({ type: "cbu", label: "CBU bancario (22 dígitos)", count: cbuMatches.length });
        }

        const aliasRe = /\b(?:alias(?:\s+(?:cbu|bancario))?\s*[:=]\s*([a-z0-9._-]{6,30})|alias(?:\s+(?:cbu|bancario))?\s+(?:de\s+|es\s+)?([a-z0-9_-]{2,}(?:\.[a-z0-9_-]{2,})+))(?![a-z0-9._-])/gi;
        let aliasCount = 0;
        working = working.replace(aliasRe, (m, g1, g2) => {
            const val = g1 || g2 || "";
            if (val.length < 6 || val.length > 30) return m;
            aliasCount += 1;
            return "alias: [ALIAS_OCULTO]";
        });
        if (aliasCount > 0) {
            warnings.push({ type: "alias_bancario", label: "Alias bancario", count: aliasCount });
        }

        const emailMatches = working.match(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g) || [];
        if (emailMatches.length) {
            working = working.replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g, "[EMAIL_OCULTO]");
            warnings.push({ type: "email", label: "Correo electrónico", count: emailMatches.length });
        }

        let phoneCount = 0;
        const phoneLabeledRe = /\b((?:tel(?:[eé]fono)?|cel(?:ular)?|wa|wsp|whatsapp|contacto|llamar\s+al)\.?\s*[:=-]?\s*)((?:\+?54\s*9?\s*)?(?:\d{10,11}|\d{2,4}\s+\d{6,8}))(?![\d-])/gi;
        working = working.replace(phoneLabeledRe, (_m, label) => {
            phoneCount += 1;
            return `${label}[TELEFONO_OCULTO]`;
        });

        const cell15Re = /(?:^|[^\d])((?:11|2\d{2,3}|3\d{2,3})[\s.-]?15[\s.-]?\d{3,4}[\s.-]?\d{3,4})(?!\d)/g;
        working = working.replace(cell15Re, (m, body, offset, fullStr) => {
            const prefix = m.slice(0, m.length - body.length);
            const cleanBody = body.trim();
            if (cleanBody.startsWith("000") || /^\d{4,5}-\d{8}$/.test(cleanBody)) return m;
            const before = fullStr.slice(Math.max(0, offset - 40), offset + prefix.length);
            if (/(?:\b(?:factura|fc|comprobante|remito|orden|ticket|recibo)(?:\s+(?:nro|n[°º]|numero|#))?\s*[:=-]?\s*)$/i.test(before)) {
                return m;
            }
            phoneCount += 1;
            return `${prefix}[TELEFONO_OCULTO]`;
        });

        let dniCount = 0;
        const cuit11Re = /\b(?:20|23|24|27|30|33|34)\d{9}\b/g;
        working = working.replace(cuit11Re, (m, offset, fullStr) => {
            const prevChar = offset > 0 ? fullStr[offset - 1] : "";
            const nextChar = offset + m.length < fullStr.length ? fullStr[offset + m.length] : "";
            if (prevChar === "$" || prevChar === "-" || nextChar === "-") return m;
            if (!isValidCuitMod11(m)) return m;
            if (isMoneyContextAround(fullStr, offset, offset + m.length, m)) return m;
            dniCount += 1;
            return "[DNI_CUIL_OCULTO]";
        });

        const dniRe = /\b(?:\d{2}-\d{7,8}-\d|[1-9]\d?\.\d{3}\.\d{3}|\d{7,8})\b/g;
        working = working.replace(dniRe, (m, offset, fullStr) => {
            const prevChar = offset > 0 ? fullStr[offset - 1] : "";
            const nextChar = offset + m.length < fullStr.length ? fullStr[offset + m.length] : "";
            if (prevChar === "$" || prevChar === "-" || nextChar === "-") {
                return m;
            }
            if (/^\d+$/.test(m)) {
                if (m.startsWith("000")) {
                    return m;
                }
                const before = fullStr.slice(Math.max(0, offset - 40), offset);
                if (/(?:\b(?:factura|fc|comprobante|remito|orden|ticket|recibo)(?:\s+(?:nro|n[°º]|numero|#))?\s*[:=-]?\s*(?:\d{4,5}\s*-\s*)?|\b\d{4,5}\s*-\s*)$/i.test(before)) {
                    return m;
                }
            }
            if (isMoneyContextAround(fullStr, offset, offset + m.length, m)) {
                return m;
            }
            dniCount += 1;
            return "[DNI_CUIL_OCULTO]";
        });
        if (dniCount > 0) {
            warnings.push({ type: "dni_cuil", label: "DNI / CUIL / CUIT", count: dniCount });
        }

        const phoneSepRe = /(?:^|[^\d])(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-])\d{3,4}[\s.-]?\d{4}(?!\d)/g;
        working = working.replace(phoneSepRe, (m, offset, fullStr) => {
            const prefix = m.length && /\D/.test(m[0]) && m[0] !== "+" && m[0] !== "(" ? m[0] : "";
            const body = prefix ? m.slice(1).trim() : m.trim();
            if (/^\d{4,5}-\d{8}$/.test(body) || body.startsWith("000")) {
                return m;
            }
            const before = fullStr.slice(Math.max(0, offset - 40), offset + prefix.length);
            if (/(?:\b(?:factura|fc|comprobante|remito|orden|ticket|recibo)(?:\s+(?:nro|n[°º]|numero|#))?\s*[:=-]?\s*)$/i.test(before)) {
                return m;
            }
            phoneCount += 1;
            return `${prefix}[TELEFONO_OCULTO]`;
        });

        if (phoneCount > 0) {
            warnings.push({ type: "telefono", label: "Teléfono", count: phoneCount });
        }

        return warnings;
    }

    function renderPiiBanner(warnings) {
        const piiBanner = $("pii-alert-banner");
        if (!piiBanner) return;
        if (warnings && warnings.length > 0) {
            $("pii-alert-details").innerText = warnings
                .map((w) => `${w.label} (${w.count})`)
                .join(", ");
            piiBanner.classList.remove("d-none");
        } else {
            piiBanner.classList.add("d-none");
        }
    }

    // ------------------------------------------------------------------
    // Ejemplos auto-ocultables, Estimador Multi-IA y Sello de Privacidad (v7.3)
    // ------------------------------------------------------------------

    function syncQuickExamplesVisibility() {
        const box = $("express-examples");
        if (!box) return;
        const hasContent = getInputText().length > 0;
        box.classList.toggle("is-hidden", hasContent);
        box.setAttribute("aria-hidden", hasContent ? "true" : "false");
        box.querySelectorAll("button.pl-example-pill").forEach((btn) => {
            btn.tabIndex = hasContent ? -1 : 0;
        });
    }

    function formatContextUsage(tokens, contextWindow) {
        if (!tokens || tokens <= 0) return "0 % del contexto";
        const pct = (tokens / contextWindow) * 100;
        if (pct <= 0.1) return "< 0,1 % del contexto";
        if (pct < 0.2) return "< 0,2 % del contexto";
        return `${pct.toFixed(1).replace(".", ",")} % del contexto`;
    }

    /**
     * Estimador determinístico 100% offline calibrado para texto en español.
     * Diferencia ChatGPT (o200k_base, 128K), Gemini (SentencePiece, 1M) y
     * Claude (BPE Anthropic, 200K) considerando palabras, caracteres, tildes/eñes,
     * signos de puntuación, saltos de línea y bloques de código.
     */
    function estimateTokensByModel(text) {
        const clean = String(text || "").trim();
        const emptyModel = (contextWindow, windowLabel) => ({
            tokens: 0,
            contextWindow,
            windowLabel,
            pct: 0,
            contextLabel: "0 % del contexto",
        });

        if (!clean) {
            return {
                words: 0,
                chars: 0,
                chatgpt: emptyModel(128000, "128K"),
                gemini: emptyModel(1000000, "1M"),
                claude: emptyModel(200000, "200K"),
            };
        }

        let codeChars = 0;
        let proseText = clean.replace(/```[\s\S]*?```/g, (block) => {
            codeChars += block.length;
            return " ";
        });
        proseText = proseText.replace(/`[^`\n]+`/g, (inline) => {
            codeChars += inline.length;
            return " ";
        });

        const words = proseText.trim() ? proseText.trim().split(/\s+/).length : 0;
        const totalWords = clean.split(/\s+/).length;
        const proseChars = proseText.length;
        const totalChars = clean.length;
        const diacritics = (clean.match(/[áéíóúüñÁÉÍÓÚÜÑ¿¡]/g) || []).length;
        const symbols = (proseText.match(/[.,;:!?()[\]{}<>#*_\-+/=\\|"'~^&%$@]/g) || []).length;
        const newlines = (clean.match(/\n/g) || []).length;

        const buildModelStats = (rawTokens, contextWindow, windowLabel) => {
            const tokens = Math.max(1, Math.round(rawTokens));
            const pct = (tokens / contextWindow) * 100;
            return {
                tokens,
                contextWindow,
                windowLabel,
                pct,
                contextLabel: formatContextUsage(tokens, contextWindow),
            };
        };

        const chatgptRaw =
            0.55 * (words * 1.24) +
            0.45 * (proseChars / 4.35) +
            diacritics * 0.06 +
            symbols * 0.18 +
            newlines * 0.20 +
            codeChars / 3.40;

        const geminiRaw =
            0.55 * (words * 1.30) +
            0.45 * (proseChars / 4.05) +
            diacritics * 0.09 +
            symbols * 0.22 +
            newlines * 0.25 +
            codeChars / 3.20;

        const claudeRaw =
            0.55 * (words * 1.38) +
            0.45 * (proseChars / 3.70) +
            diacritics * 0.18 +
            symbols * 0.26 +
            newlines * 0.30 +
            codeChars / 3.00;

        return {
            words: totalWords,
            chars: totalChars,
            chatgpt: buildModelStats(chatgptRaw, 128000, "128K"),
            gemini: buildModelStats(geminiRaw, 1000000, "1M"),
            claude: buildModelStats(claudeRaw, 200000, "200K"),
        };
    }

    function renderTokenEstimator(text) {
        const est = estimateTokensByModel(text);
        if ($("token-word-char-summary")) {
            $("token-word-char-summary").innerText = `${est.words} palabras • ${est.chars} caracteres`;
        }
        if ($("token-val-chatgpt")) $("token-val-chatgpt").innerText = `~${est.chatgpt.tokens} tokens`;
        if ($("token-ctx-chatgpt")) $("token-ctx-chatgpt").innerText = est.chatgpt.contextLabel;
        if ($("token-val-gemini")) $("token-val-gemini").innerText = `~${est.gemini.tokens} tokens`;
        if ($("token-ctx-gemini")) $("token-ctx-gemini").innerText = est.gemini.contextLabel;
        if ($("token-val-claude")) $("token-val-claude").innerText = `~${est.claude.tokens} tokens`;
        if ($("token-ctx-claude")) $("token-ctx-claude").innerText = est.claude.contextLabel;
    }

    const PII_SEAL_SPECS = [
        { type: "dni_cuil", label: "CUIL/DNI", regex: /\[DNI_CUIL_OCULTO\]/g },
        { type: "telefono", label: "Teléfono", regex: /\[TELEFONO_OCULTO\]/g },
        { type: "email", label: "Correo", regex: /\[EMAIL_OCULTO\]/g },
        { type: "cbu", label: "CBU bancario", regex: /\[CBU_OCULTO\]/g },
        { type: "alias_bancario", label: "Alias bancario", regex: /\[ALIAS_OCULTO\]/g },
    ];

    function renderPrivacyVerifiedSeal(resultData, outputText) {
        const seal = $("privacy-verified-seal");
        const detailsEl = $("privacy-verified-details");
        const afipEl = $("privacy-afip-note");
        if (!seal || !detailsEl) return;

        const outStr = String(outputText || "");
        const rawStr = String((resultData && resultData.raw_objective) || "");
        let totalOutputMarkers = 0;
        const markerCounts = {};

        PII_SEAL_SPECS.forEach((spec) => {
            const countOut = (outStr.match(spec.regex) || []).length;
            totalOutputMarkers += countOut;
            if (countOut > 0) {
                markerCounts[spec.type] = countOut;
            } else if (resultData && resultData.has_pii_masked) {
                const countRaw = (rawStr.match(spec.regex) || []).length;
                if (countRaw > 0) markerCounts[spec.type] = countRaw;
            }
        });

        const isProtected = Boolean(resultData && resultData.has_pii_masked) || totalOutputMarkers > 0;
        if (!isProtected) {
            seal.classList.add("d-none");
            if (afipEl) afipEl.classList.add("d-none");
            return;
        }

        const labelByType = Object.fromEntries(PII_SEAL_SPECS.map((s) => [s.type, s.label]));
        const items = [];

        if (
            resultData &&
            resultData.has_pii_masked &&
            Array.isArray(resultData.pii_warnings) &&
            resultData.pii_warnings.length > 0 &&
            (totalOutputMarkers > 0 || !outStr)
        ) {
            const warningMap = {};
            resultData.pii_warnings.forEach((w) => {
                if (w && w.type) {
                    warningMap[w.type] = (warningMap[w.type] || 0) + Number(w.count || 1);
                }
            });
            PII_SEAL_SPECS.forEach((spec) => {
                if (warningMap[spec.type] > 0) {
                    items.push(`${labelByType[spec.type]} (${warningMap[spec.type]})`);
                }
            });
        } else {
            PII_SEAL_SPECS.forEach((spec) => {
                if (markerCounts[spec.type] > 0) {
                    items.push(`${spec.label} (${markerCounts[spec.type]})`);
                }
            });
        }

        detailsEl.innerText =
            items.length > 0
                ? `Datos anonimizados: ${items.join(", ")}.`
                : "Datos sensibles reemplazados por marcadores seguros antes de exportar.";

        if (afipEl) {
            const hasAfipReceipt = /\b\d{4}-\d{8}\b/.test(`${outStr}\n${rawStr}`);
            afipEl.classList.toggle("d-none", !hasAfipReceipt);
        }

        seal.classList.remove("d-none");
    }

    function triggerLiveAnalyze() {
        clearTimeout(liveDebounceTimer);
        syncQuickExamplesVisibility();
        const immediateText = getInputText();
        if (immediateText && immediateText.length >= 3) {
            renderPiiBanner(detectPiiClientSide(immediateText));
        } else {
            renderPiiBanner([]);
        }
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
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCsrfToken(),
                    },
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
                if ($("live-confidence-badge")) $("live-confidence-badge").innerText = `Certeza: ${confPct}%`;
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
                const mergedPii = (data.pii_warnings && data.pii_warnings.length > 0)
                    ? data.pii_warnings
                    : detectPiiClientSide(text);
                renderPiiBanner(mergedPii);

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
                const activeSlots = data.suggested_slots || [];
                renderSmartSlots(activeSlots);
                updateExpressBridgeBanner(activeSlots);
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

    function updateVersionUI(versionNum) {
        currentVersionNumber = Number(versionNum) || 1;
        const badge = $("output-version-badge");
        if (badge) badge.innerText = `v${currentVersionNumber}`;
    }

    function enterIterationMode(promptId, versionNum) {
        if (!promptId) {
            mostrarAviso("Generá o cargá un prompt antes de crear una nueva versión.");
            return;
        }
        iteratingParentId = promptId;
        const baseVer = Number(versionNum) || currentVersionNumber || 1;
        const banner = $("iteration-mode-banner");
        const txt = $("iteration-mode-text");
        if (txt) {
            txt.innerHTML = `Iterando sobre versión <strong>v${baseVer}</strong> — los cambios se guardarán como <strong>v${baseVer + 1}</strong>`;
        }
        if (banner) banner.classList.remove("d-none");
        const noteEl = $("version-note-input");
        if (noteEl) noteEl.focus();
    }

    function cancelIterationMode() {
        iteratingParentId = null;
        const banner = $("iteration-mode-banner");
        if (banner) banner.classList.add("d-none");
        const noteEl = $("version-note-input");
        if (noteEl) noteEl.value = "";
    }

    function openSaveTemplateModal() {
        const titleEl = $("save-tpl-title");
        const catEl = $("save-tpl-category");
        const modeEl = $("save-tpl-mode");
        const bodyEl = $("save-tpl-body");
        const whyEl = $("save-tpl-why");
        const fbEl = $("save-tpl-feedback");

        if (fbEl) fbEl.classList.add("d-none");
        const rawInput = getInputText();
        const outEl = $("generated-prompt-output");
        const outVal = outEl ? outEl.value.trim() : "";

        if (bodyEl) bodyEl.value = outVal || rawInput;
        if (titleEl && !titleEl.value.trim()) {
            const snippet = rawInput.split(/\r?\n/)[0].slice(0, 64).trim();
            titleEl.value = snippet ? `Plantilla: ${snippet}` : "Mi nueva plantilla";
        }
        if (catEl) {
            const detCat = (lastResultData && lastResultData.category) || ($("category-select") ? $("category-select").value : "");
            if (detCat) {
                const matchOpt = Array.from(catEl.options).find((o) => o.value === detCat);
                if (matchOpt) catEl.value = detCat;
            }
        }
        if (modeEl) {
            modeEl.value = currentMode === "pro" ? "pro" : currentMode === "express" ? "express" : "guiado";
        }
        if (whyEl && !whyEl.value.trim() && lastResultData && lastResultData.action_label) {
            whyEl.value = `Estructura optimizada para ${String(lastResultData.action_label).toLowerCase()}.`;
        }
    }

    async function submitSaveTemplateModal(evt) {
        evt.preventDefault();
        const fbEl = $("save-tpl-feedback");
        const submitBtn = $("btn-save-tpl-submit");
        const payload = {
            title: $("save-tpl-title") ? $("save-tpl-title").value.trim() : "",
            category: $("save-tpl-category") ? $("save-tpl-category").value : "Otro / General",
            recommended_mode: $("save-tpl-mode") ? $("save-tpl-mode").value : "guiado",
            prompt_body: $("save-tpl-body") ? $("save-tpl-body").value.trim() : "",
            why_it_works: $("save-tpl-why") ? $("save-tpl-why").value.trim() : "",
        };

        if (submitBtn) submitBtn.disabled = true;
        try {
            const resp = await fetch("/plantillas/propias/crear/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify(payload),
            });
            const data = await resp.json();
            if (!resp.ok || data.error) {
                if (fbEl) {
                    fbEl.className = "alert alert-danger small py-2 px-3 mb-3";
                    fbEl.innerText = data.error || "No pudimos guardar la plantilla.";
                    fbEl.classList.remove("d-none");
                }
                return;
            }
            if (fbEl) {
                fbEl.className = "alert alert-success small py-2 px-3 mb-3";
                fbEl.innerText = data.message || "Plantilla guardada en Mis Plantillas.";
                fbEl.classList.remove("d-none");
            }
        } catch (_err) {
            if (fbEl) {
                fbEl.className = "alert alert-danger small py-2 px-3 mb-3";
                fbEl.innerText = "Error de conexión al guardar la plantilla.";
                fbEl.classList.remove("d-none");
            }
        } finally {
            if (submitBtn) submitBtn.disabled = false;
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
        const versionNote = $("version-note-input") ? ($("version-note-input").value || "").trim() : "";

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
            const reqBody = {
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
            };
            if (iteratingParentId) {
                reqBody.parent_prompt_id = iteratingParentId;
                reqBody.version_note = versionNote;
            }
            const response = await fetch("/api/improve/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify(reqBody),
            });

            const data = await response.json();
            if (data.error) {
                mostrarAviso(data.error);
                return;
            }

            succeeded = true;
            lastResultData = data;
            currentPromptId = data.prompt_id || null;
            updateVersionUI(data.version_number || 1);
            cancelIterationMode();
            updateFavoriteButtonUI(Boolean(data.is_favorite));

            if (outputEl) {
                outputEl.value = data.improved_prompt || "";
            }
            if (outputCard) {
                outputCard.classList.remove("d-none");
            }
            setOutputEditMode(false);
            autoResizeOutputTextarea();
            renderPrivacyVerifiedSeal(data, data.improved_prompt || "");
            renderTokenEstimator(data.improved_prompt || "");

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
            if ($("info-gain-lbl")) $("info-gain-lbl").innerText = `+${infoGain} pts tuyos`;
            if ($("final-score-lbl")) $("final-score-lbl").innerText = finalScore;
            if ($("score-band-lbl")) $("score-band-lbl").innerText = `(${bandLabel})`;
            if ($("gain-badge")) $("gain-badge").innerText = `Mejora total: +${qualityGain} pts`;

            const anchorPct = data.anchor_coverage_pct ?? Math.round((data.anchor_coverage ?? 0.95) * 100);
            const noisePct = data.noise_ratio_pct ?? Math.round((data.noise_ratio ?? 0.04) * 100);
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
                    .map((item) => formatAnalysisItem(item))
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

    function _fallbackCopyText(text) {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        let ok = false;
        try {
            ok = document.execCommand("copy");
        } catch (_e) {
            ok = false;
        }
        document.body.removeChild(ta);
        return ok;
    }

    function copiarAlPortapapeles() {
        const output = $("generated-prompt-output");
        if (!output || !output.value) return;
        const textToCopy = output.value;
        const onCopied = () => {
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
        };
        const onCopyError = () => {
            mostrarAviso("No se pudo acceder al portapapeles automáticamente. Copiá el texto manualmente desde Editar texto.");
        };

        if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            navigator.clipboard
                .writeText(textToCopy)
                .then(onCopied)
                .catch(() => {
                    if (_fallbackCopyText(textToCopy)) {
                        onCopied();
                    } else {
                        onCopyError();
                    }
                });
        } else if (_fallbackCopyText(textToCopy)) {
            onCopied();
        } else {
            onCopyError();
        }
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
        const est = estimateTokensByModel(texto);
        return {
            words: est.words,
            chars: est.chars,
            tokens: est.chatgpt.tokens,
            models: est,
        };
    }

    function abrirComparador() {
        const origText = (lastResultData && lastResultData.raw_objective) || getInputText();
        const impText = $("generated-prompt-output") ? $("generated-prompt-output").value.trim() : "";

        const mOrig = calcularMetricasTexto(origText);
        const mImp = calcularMetricasTexto(impText);
        const estOrig = mOrig.models;
        const estImp = mImp.models;

        if ($("cmp-orig-text")) $("cmp-orig-text").innerText = origText;
        if ($("cmp-imp-text")) $("cmp-imp-text").innerText = impText;
        if ($("cmp-orig-metrics")) {
            $("cmp-orig-metrics").innerText = `${mOrig.words} palabras • ${mOrig.chars} caracteres`;
        }
        if ($("cmp-imp-metrics")) {
            $("cmp-imp-metrics").innerText = `${mImp.words} palabras • ${mImp.chars} caracteres`;
        }
        if ($("cmp-tok-chatgpt")) {
            $("cmp-tok-chatgpt").innerText = `~${estImp.chatgpt.tokens} tokens (antes ~${estOrig.chatgpt.tokens})`;
        }
        if ($("cmp-ctx-chatgpt")) $("cmp-ctx-chatgpt").innerText = estImp.chatgpt.contextLabel;
        if ($("cmp-tok-gemini")) {
            $("cmp-tok-gemini").innerText = `~${estImp.gemini.tokens} tokens (antes ~${estOrig.gemini.tokens})`;
        }
        if ($("cmp-ctx-gemini")) $("cmp-ctx-gemini").innerText = estImp.gemini.contextLabel;
        if ($("cmp-tok-claude")) {
            $("cmp-tok-claude").innerText = `~${estImp.claude.tokens} tokens (antes ~${estOrig.claude.tokens})`;
        }
        if ($("cmp-ctx-claude")) $("cmp-ctx-claude").innerText = estImp.claude.contextLabel;

        const effBadge = $("cmp-efficiency-badge");
        if (effBadge) {
            const maxPct = Math.max(estImp.chatgpt.pct, estImp.gemini.pct, estImp.claude.pct);
            const freePct = Math.max(0, 100 - maxPct);
            const freeLabel = freePct >= 99.8 ? "> 99,8" : freePct.toFixed(1).replace(".", ",");
            effBadge.innerText = `Prompt liviano: ${freeLabel} % de contexto libre`;
        }
    }

    function limpiarEditor() {
        if ($("prompt-input")) $("prompt-input").value = "";
        if ($("generated-prompt-output")) $("generated-prompt-output").value = "";
        setOutputEditMode(false);
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
        if ($("template-loaded-banner")) $("template-loaded-banner").classList.add("d-none");
        if ($("disambiguation-card")) $("disambiguation-card").classList.add("d-none");
        if ($("btn-fill-placeholders")) $("btn-fill-placeholders").classList.add("d-none");

        renderPrivacyVerifiedSeal(null, "");
        renderTokenEstimator("");
        syncQuickExamplesVisibility();

        switchOutputTab("editor");
        lastResultData = null;
        lastLiveData = null;
        currentPromptId = null;
        updateVersionUI(1);
        cancelIterationMode();
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

        // Ejemplos rápidos auto-ocultables
        document.querySelectorAll(".pl-example-pill").forEach((btn) => {
            btn.addEventListener("click", () => {
                const sample = btn.getAttribute("data-example") || "";
                const input = $("prompt-input");
                if (input) {
                    input.value = sample;
                    input.focus();
                }
                syncQuickExamplesVisibility();
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
        if ($("btn-toggle-edit-output")) {
            $("btn-toggle-edit-output").addEventListener("click", () => setOutputEditMode(!isOutputEditing));
        }
        const outEditEl = $("generated-prompt-output");
        if (outEditEl) {
            outEditEl.addEventListener("input", () => {
                renderTokenEstimator(outEditEl.value);
                renderPrivacyVerifiedSeal(lastResultData, outEditEl.value);
            });
        }
        if ($("btn-favorite")) $("btn-favorite").addEventListener("click", toggleCurrentFavorite);
        if ($("btn-iterate-version")) {
            $("btn-iterate-version").addEventListener("click", () => {
                enterIterationMode(currentPromptId, currentVersionNumber);
            });
        }
        if ($("btn-cancel-iteration")) {
            $("btn-cancel-iteration").addEventListener("click", cancelIterationMode);
        }
        const saveTplModalEl = $("saveTemplateModal");
        if (saveTplModalEl) {
            saveTplModalEl.addEventListener("show.bs.modal", openSaveTemplateModal);
        }
        const saveTplForm = $("save-template-form");
        if (saveTplForm) {
            saveTplForm.addEventListener("submit", submitSaveTemplateModal);
        }
        if ($("btn-tpl-src-idea")) {
            $("btn-tpl-src-idea").addEventListener("click", () => {
                if ($("save-tpl-body")) $("save-tpl-body").value = getInputText();
            });
        }
        if ($("btn-tpl-src-output")) {
            $("btn-tpl-src-output").addEventListener("click", () => {
                const out = $("generated-prompt-output");
                if ($("save-tpl-body") && out) $("save-tpl-body").value = out.value.trim();
            });
        }
        if ($("btn-compare")) $("btn-compare").addEventListener("click", abrirComparador);
        if ($("btn-export-md")) $("btn-export-md").addEventListener("click", () => descargarArchivo("md"));
        if ($("btn-export-json")) $("btn-export-json").addEventListener("click", () => descargarArchivo("json"));
        if ($("btn-fill-placeholders")) $("btn-fill-placeholders").addEventListener("click", enfocarDatosPendientes);
        if ($("tab-btn-editor")) $("tab-btn-editor").addEventListener("click", () => switchOutputTab("editor"));
        if ($("tab-btn-origin")) $("tab-btn-origin").addEventListener("click", () => switchOutputTab("origin"));
        if ($("btn-dismiss-template-banner")) {
            $("btn-dismiss-template-banner").addEventListener("click", () => {
                if ($("template-loaded-banner")) $("template-loaded-banner").classList.add("d-none");
            });
        }

        // Estado inicial desde backend (?load=<id> | ?preset=<slug> | sessionStorage | default localStorage)
        let sessionTemplate = null;
        try {
            const rawSessionTpl = sessionStorage.getItem("promptlab_selected_template");
            if (rawSessionTpl) {
                sessionTemplate = JSON.parse(rawSessionTpl);
                sessionStorage.removeItem("promptlab_selected_template");
            }
        } catch (_e) {
            sessionTemplate = null;
        }

        const boot = readBootData();
        if (boot.loaded_prompt) {
            const lp = boot.loaded_prompt;
            const initialMode = LEVEL_TO_MODE[lp.level] || "guiado";
            setWorkspaceMode(initialMode, false);

            currentPromptId = lp.id;
            updateVersionUI(lp.version_number || 1);
            updateFavoriteButtonUI(Boolean(lp.is_favorite));
            if (lp.auto_iterate) {
                enterIterationMode(lp.id, lp.version_number || 1);
            }

            if (boot.loaded_rubric) {
                renderRubricBars(boot.loaded_rubric);
            }
            const outEl = $("generated-prompt-output");
            if (outEl) {
                setOutputEditMode(false);
                if ($("btn-fill-placeholders")) {
                    $("btn-fill-placeholders").classList.toggle("d-none", !hasPendingPlaceholders(outEl.value));
                }
            }
            autoResizeOutputTextarea();
            const sealEl = $("privacy-verified-seal");
            const loadedProtected = sealEl ? sealEl.getAttribute("data-loaded-protected") === "true" : false;
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
                has_pii_masked: loadedProtected,
            };
            renderPrivacyVerifiedSeal(lastResultData, outEl ? outEl.value : "");
            renderTokenEstimator(outEl ? outEl.value : "");
            if (inputEl && inputEl.value.trim().length >= 3) {
                triggerLiveAnalyze();
            }
        } else if (sessionTemplate && sessionTemplate.prompt) {
            if (inputEl) {
                inputEl.value = sessionTemplate.prompt;
            }
            const tplMode = sessionTemplate.workspace_mode || sessionTemplate.mode || LEVEL_TO_MODE[sessionTemplate.level] || "guiado";
            setWorkspaceMode(tplMode, false);
            if ($("template-loaded-banner")) {
                $("template-loaded-banner").classList.remove("d-none");
            }
            triggerLiveAnalyze();
            if (inputEl) inputEl.focus();
        } else if (boot.preset_data) {
            const presetMode = boot.preset_data.mode || LEVEL_TO_MODE[boot.preset_data.level] || "guiado";
            setWorkspaceMode(presetMode, false);
            if ($("template-loaded-banner")) {
                $("template-loaded-banner").classList.remove("d-none");
            }
            triggerLiveAnalyze();
            if (inputEl) inputEl.focus();
        } else {
            let savedMode = "express";
            try {
                savedMode = localStorage.getItem("promptlab_mode") || "express";
            } catch (_e) {
                savedMode = "express";
            }
            setWorkspaceMode(savedMode, false);
        }

        syncQuickExamplesVisibility();
    });
})();
