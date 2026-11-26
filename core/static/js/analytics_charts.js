/* ==========================================================================
   PromptLab v7.2.3 — Gráficos SVG Interactivos 100% Offline
   ========================================================================== */

(function () {
    "use strict";

    const SVG_NS = "http://www.w3.org/2000/svg";
    const PALETTE_DARK = [
        "#6366f1",
        "#10b981",
        "#06b6d4",
        "#f59e0b",
        "#ec4899",
        "#8b5cf6",
        "#3b82f6",
        "#14b8a6",
    ];
    const PALETTE_LIGHT = [
        "#4f46e5",
        "#059669",
        "#0891b2",
        "#d97706",
        "#db2777",
        "#7c3aed",
        "#2563eb",
        "#0d9488",
    ];

    function isLightTheme() {
        return document.documentElement.getAttribute("data-theme") === "light";
    }

    function getThemeChartColors() {
        if (isLightTheme()) {
            return {
                beforeColor: "#64748b",
                afterGreen: "#059669",
                afterViolet: "#5b52f5",
                gridStroke: "#cbd5e1",
                barGradStart: "#4f46e5",
                barGradEnd: "#0891b2",
                palette: PALETTE_LIGHT,
            };
        }
        return {
            beforeColor: "#94a3b8",
            afterGreen: "#10b981",
            afterViolet: "#7c73ff",
            gridStroke: "rgba(148, 163, 184, 0.24)",
            barGradStart: "#6366f1",
            barGradEnd: "#22d3ee",
            palette: PALETTE_DARK,
        };
    }

    let activeDonutView = "styles";
    let activeGroupedView = "by_technique";
    let tooltipEl = null;

    function $(id) {
        return document.getElementById(id);
    }

    function createSvgEl(tag, attrs) {
        const el = document.createElementNS(SVG_NS, tag);
        if (attrs) {
            Object.entries(attrs).forEach(([k, v]) => {
                el.setAttribute(k, String(v));
            });
        }
        return el;
    }

    function truncateLabel(text, maxLen) {
        const clean = String(text || "").trim();
        if (clean.length <= maxLen) return clean;
        return clean.slice(0, Math.max(1, maxLen - 1)).trimEnd() + "…";
    }

    function ensureTooltip() {
        if (tooltipEl) return tooltipEl;
        tooltipEl = document.createElement("div");
        tooltipEl.id = "pl-chart-tooltip";
        tooltipEl.className = "stats-svg-tooltip d-none";
        tooltipEl.setAttribute("role", "status");
        tooltipEl.setAttribute("aria-live", "polite");
        document.body.appendChild(tooltipEl);
        return tooltipEl;
    }

    function showTooltip(evt, title, detail, badge) {
        const tip = ensureTooltip();
        tip.innerHTML = "";

        const titleEl = document.createElement("div");
        titleEl.className = "stats-tooltip-title";
        titleEl.textContent = title || "";
        tip.appendChild(titleEl);

        if (detail) {
            const detailEl = document.createElement("div");
            detailEl.className = "stats-tooltip-detail";
            detailEl.textContent = detail;
            tip.appendChild(detailEl);
        }

        if (badge) {
            const badgeEl = document.createElement("div");
            badgeEl.className = "stats-tooltip-badge";
            badgeEl.textContent = badge;
            tip.appendChild(badgeEl);
        }

        tip.classList.remove("d-none");
        positionTooltip(evt);
    }

    function positionTooltip(evt) {
        if (!tooltipEl || tooltipEl.classList.contains("d-none")) return;
        const pad = 12;
        let clientX = 0;
        let clientY = 0;
        if (evt && typeof evt.clientX === "number" && (evt.clientX !== 0 || evt.clientY !== 0)) {
            clientX = evt.clientX;
            clientY = evt.clientY;
        } else if (evt && evt.target && evt.target.getBoundingClientRect) {
            const rect = evt.target.getBoundingClientRect();
            clientX = rect.left + rect.width / 2;
            clientY = rect.top;
        }

        const tipW = tooltipEl.offsetWidth || 180;
        const tipH = tooltipEl.offsetHeight || 56;
        let left = clientX + pad;
        let top = clientY - tipH - pad;

        if (left + tipW > window.innerWidth - 10) {
            left = Math.max(10, clientX - tipW - pad);
        }
        if (top < 10) {
            top = Math.min(window.innerHeight - tipH - 10, clientY + pad + 8);
        }

        left = Math.max(10, Math.min(left, window.innerWidth - tipW - 10));
        top = Math.max(10, Math.min(top, window.innerHeight - tipH - 10));

        tooltipEl.style.left = `${Math.round(left)}px`;
        tooltipEl.style.top = `${Math.round(top)}px`;
    }

    function hideTooltip() {
        if (tooltipEl) {
            tooltipEl.classList.add("d-none");
        }
    }

    function attachInteractiveEvents(el, getInfo) {
        el.setAttribute("tabindex", "0");
        el.classList.add("stats-svg-interactive");
        el.addEventListener("mouseenter", (e) => {
            const info = getInfo();
            showTooltip(e, info.title, info.detail, info.badge);
        });
        el.addEventListener("mousemove", positionTooltip);
        el.addEventListener("mouseleave", hideTooltip);
        el.addEventListener("focus", (e) => {
            const info = getInfo();
            showTooltip(e, info.title, info.detail, info.badge);
        });
        el.addEventListener("blur", hideTooltip);
    }

    function niceAxisMax(val) {
        const num = Number(val) || 1;
        if (num <= 4) return Math.max(2, Math.ceil(num));
        if (num <= 10) return Math.ceil(num / 2) * 2;
        const step = Math.pow(10, Math.floor(Math.log10(num)));
        return Math.ceil(num / step) * step;
    }

    // ------------------------------------------------------------------
    // Gráfico 1: Barras horizontales con eje numérico (Temas)
    // ------------------------------------------------------------------
    function renderHorizontalDomainsChart(domains) {
        const container = $("chart-domains-svg");
        if (!container) return;
        container.innerHTML = "";

        if (!domains || domains.length === 0) {
            container.innerHTML = '<div class="text-center py-4 small pl-text-secondary">Sin temas registrados aún.</div>';
            return;
        }

        const colors = getThemeChartColors();
        const items = domains.slice(0, 8);
        const rowH = 38;
        const topPad = 14;
        const bottomPad = 28;
        const width = 580;
        const height = topPad + items.length * rowH + bottomPad;
        const leftPad = 176;
        const rightPad = 84;
        const plotW = width - leftPad - rightPad;

        const maxCount = Math.max(...items.map((d) => Number(d.count) || 0), 1);
        const axisMax = niceAxisMax(maxCount);
        const ticksCount = Math.min(4, axisMax);

        const svg = createSvgEl("svg", {
            viewBox: `0 0 ${width} ${height}`,
            class: "stats-svg-canvas",
            role: "img",
            "aria-label": "Gráfico de barras horizontales con los temas más consultados",
        });

        const defs = createSvgEl("defs");
        const grad = createSvgEl("linearGradient", {
            id: "plGradBarHorizontal",
            x1: "0%",
            y1: "0%",
            x2: "100%",
            y2: "0%",
        });
        grad.appendChild(createSvgEl("stop", { offset: "0%", "stop-color": colors.barGradStart }));
        grad.appendChild(createSvgEl("stop", { offset: "100%", "stop-color": colors.barGradEnd }));
        defs.appendChild(grad);
        svg.appendChild(defs);

        // Gridlines verticales y ticks numéricos en eje X
        for (let i = 0; i <= ticksCount; i += 1) {
            const val = Math.round((axisMax * i) / ticksCount);
            const x = leftPad + (val / axisMax) * plotW;

            svg.appendChild(createSvgEl("line", {
                x1: x,
                y1: topPad,
                x2: x,
                y2: height - bottomPad,
                stroke: colors.gridStroke,
                "stroke-dasharray": i === 0 ? "none" : "3 4",
                "stroke-width": 1,
            }));

            const tickTxt = createSvgEl("text", {
                x: x,
                y: height - 8,
                "text-anchor": "middle",
                fill: "var(--pl-text-secondary)",
                "font-size": "11",
            });
            tickTxt.textContent = String(val);
            svg.appendChild(tickTxt);
        }

        items.forEach((item, idx) => {
            const count = Number(item.count) || 0;
            const pct = Number(item.pct) || 0;
            const yCenter = topPad + idx * rowH + rowH / 2;
            const barH = 18;
            const barY = yCenter - barH / 2;
            const barW = Math.max((count / axisMax) * plotW, count > 0 ? 8 : 0);

            const lbl = createSvgEl("text", {
                x: leftPad - 10,
                y: yCenter + 4,
                "text-anchor": "end",
                fill: "var(--pl-text)",
                "font-size": "12",
                "font-weight": "600",
            });
            lbl.textContent = truncateLabel(item.name, 22);
            svg.appendChild(lbl);

            // Fondo sutil del riel
            svg.appendChild(createSvgEl("rect", {
                x: leftPad,
                y: barY,
                width: plotW,
                height: barH,
                rx: 6,
                fill: "var(--pl-surface-soft)",
                opacity: "0.55",
            }));

            const bar = createSvgEl("rect", {
                x: leftPad,
                y: barY,
                width: barW,
                height: barH,
                rx: 6,
                fill: "url(#plGradBarHorizontal)",
            });

            attachInteractiveEvents(bar, () => ({
                title: item.name,
                detail: `${count} prompt${count === 1 ? "" : "s"} (${pct}% del período)`,
                badge: "Área temática",
            }));
            svg.appendChild(bar);

            const valTxt = createSvgEl("text", {
                x: leftPad + barW + 8,
                y: yCenter + 4,
                "text-anchor": "start",
                fill: "var(--pl-text-secondary)",
                "font-size": "11.5",
                "font-weight": "700",
            });
            valTxt.textContent = `${count} (${pct}%)`;
            svg.appendChild(valTxt);
        });

        container.appendChild(svg);
    }

    // ------------------------------------------------------------------
    // Gráfico 2: Dona / Donut interactivo (Estilos y Modos)
    // ------------------------------------------------------------------
    function polarToCartesian(cx, cy, r, angleDeg) {
        const rad = ((angleDeg - 90) * Math.PI) / 180.0;
        return {
            x: cx + r * Math.cos(rad),
            y: cy + r * Math.sin(rad),
        };
    }

    function describeArc(cx, cy, r, startAngle, endAngle) {
        const start = polarToCartesian(cx, cy, r, endAngle);
        const end = polarToCartesian(cx, cy, r, startAngle);
        const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
        return `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x.toFixed(2)} ${end.y.toFixed(2)}`;
    }

    function renderDonutChart(donutData, total) {
        const svgContainer = $("chart-donut-svg");
        const legendContainer = $("chart-donut-legend");
        if (!svgContainer || !legendContainer) return;

        svgContainer.innerHTML = "";
        legendContainer.innerHTML = "";

        const colors = getThemeChartColors();
        const rawSeries = (donutData && donutData[activeDonutView]) || [];
        const items = rawSeries.filter((item) => Number(item.count) > 0);
        const sumCount = items.reduce((acc, it) => acc + (Number(it.count) || 0), 0);

        if (items.length === 0 || sumCount === 0) {
            svgContainer.innerHTML = '<div class="text-center py-4 small pl-text-secondary">Sin datos en esta vista.</div>';
            return;
        }

        const svg = createSvgEl("svg", {
            viewBox: "0 0 220 220",
            class: "stats-donut-svg",
            role: "img",
            "aria-label": "Gráfico de dona de estilos y modos",
        });

        const cx = 110;
        const cy = 110;
        const radius = 74;
        const strokeWidth = 26;

        // Anillo base
        svg.appendChild(createSvgEl("circle", {
            cx,
            cy,
            r: radius,
            fill: "none",
            stroke: "var(--pl-surface-soft)",
            "stroke-width": strokeWidth,
        }));

        if (items.length === 1) {
            // Caso borde 100%: usar <circle> completo para evitar bug de arco SVG de 360°
            const only = items[0];
            const color = colors.palette[0];
            const ring = createSvgEl("circle", {
                cx,
                cy,
                r: radius,
                fill: "none",
                stroke: color,
                "stroke-width": strokeWidth,
            });
            attachInteractiveEvents(ring, () => ({
                title: only.label,
                detail: `${only.count} prompt${only.count === 1 ? "" : "s"} (${only.pct}%)`,
                badge: activeDonutView === "styles" ? "Estilo de respuesta" : "Modo de profundidad",
            }));
            svg.appendChild(ring);
        } else {
            let currentAngle = 0;
            items.forEach((item, idx) => {
                const count = Number(item.count) || 0;
                const sliceAngle = (count / sumCount) * 360;
                const gap = sliceAngle > 8 ? 2 : 0.6;
                const startA = currentAngle + gap / 2;
                const endA = currentAngle + sliceAngle - gap / 2;
                const color = colors.palette[idx % colors.palette.length];

                if (endA > startA) {
                    const path = createSvgEl("path", {
                        d: describeArc(cx, cy, radius, startA, endA),
                        fill: "none",
                        stroke: color,
                        "stroke-width": strokeWidth,
                        "stroke-linecap": "butt",
                    });
                    attachInteractiveEvents(path, () => ({
                        title: item.label,
                        detail: `${count} prompt${count === 1 ? "" : "s"} (${item.pct}%)`,
                        badge: activeDonutView === "styles" ? "Estilo de respuesta" : "Modo de profundidad",
                    }));
                    svg.appendChild(path);
                }
                currentAngle += sliceAngle;
            });
        }

        // Centro del donut con total
        const totalTxt = createSvgEl("text", {
            x: cx,
            y: cy - 2,
            "text-anchor": "middle",
            fill: "var(--pl-text)",
            "font-size": "28",
            "font-weight": "800",
        });
        totalTxt.textContent = String(total || sumCount);
        svg.appendChild(totalTxt);

        const subTxt = createSvgEl("text", {
            x: cx,
            y: cy + 18,
            "text-anchor": "middle",
            fill: "var(--pl-text-secondary)",
            "font-size": "12",
            "font-weight": "600",
        });
        subTxt.textContent = (total || sumCount) === 1 ? "prompt" : "prompts";
        svg.appendChild(subTxt);

        svgContainer.appendChild(svg);

        // Leyenda ordenada
        items.forEach((item, idx) => {
            const color = colors.palette[idx % colors.palette.length];
            const row = document.createElement("div");
            row.className = "stats-donut-legend-item";
            row.innerHTML = `
                <span class="d-inline-flex align-items-center gap-2 min-w-0">
                    <span class="stats-legend-dot flex-shrink-0" style="background-color: ${color};"></span>
                    <span class="small fw-semibold pl-text-primary text-truncate"></span>
                </span>
                <span class="small pl-text-secondary fw-semibold flex-shrink-0"></span>
            `;
            row.querySelector(".pl-text-primary").textContent = item.label;
            row.querySelector(".pl-text-secondary").textContent = `${item.count} · ${item.pct}%`;
            legendContainer.appendChild(row);
        });
    }

    // ------------------------------------------------------------------
    // Gráfico 3: Líneas con área sombreada (Evolución Antes vs. Después)
    // ------------------------------------------------------------------
    function renderEvolutionAreaChart(items) {
        const container = $("chart-evolution-svg");
        if (!container) return;
        container.innerHTML = "";

        if (!items || items.length === 0) {
            container.innerHTML = '<div class="text-center py-4 small pl-text-secondary">Sin puntajes para graficar todavía.</div>';
            return;
        }

        const colors = getThemeChartColors();
        const width = 660;
        const height = 250;
        const leftPad = 42;
        const rightPad = 28;
        const topPad = 18;
        const bottomPad = 42;
        const plotW = width - leftPad - rightPad;
        const plotH = height - topPad - bottomPad;

        const svg = createSvgEl("svg", {
            viewBox: `0 0 ${width} ${height}`,
            class: "stats-svg-canvas",
            role: "img",
            "aria-label": "Gráfico de líneas con área de evolución Antes vs. Después",
        });

        const defs = createSvgEl("defs");
        const areaGrad = createSvgEl("linearGradient", {
            id: "plGradEvolutionArea",
            x1: "0%",
            y1: "0%",
            x2: "0%",
            y2: "100%",
        });
        areaGrad.appendChild(createSvgEl("stop", { offset: "0%", "stop-color": colors.afterGreen, "stop-opacity": "0.28" }));
        areaGrad.appendChild(createSvgEl("stop", { offset: "100%", "stop-color": colors.barGradStart, "stop-opacity": "0.06" }));
        defs.appendChild(areaGrad);
        svg.appendChild(defs);

        // Eje Y 0-100 con gridlines cada 25 pts
        [0, 25, 50, 75, 100].forEach((val) => {
            const y = topPad + plotH - (val / 100) * plotH;
            svg.appendChild(createSvgEl("line", {
                x1: leftPad,
                y1: y,
                x2: width - rightPad,
                y2: y,
                stroke: colors.gridStroke,
                "stroke-dasharray": val === 0 ? "none" : "3 4",
                "stroke-width": 1,
            }));

            const txt = createSvgEl("text", {
                x: leftPad - 8,
                y: y + 4,
                "text-anchor": "end",
                fill: "var(--pl-text-secondary)",
                "font-size": "11",
            });
            txt.textContent = String(val);
            svg.appendChild(txt);
        });

        const coords = items.map((item, idx) => {
            const x = items.length === 1
                ? leftPad + plotW / 2
                : leftPad + (idx / (items.length - 1)) * plotW;
            const beforeVal = Math.max(0, Math.min(100, Number(item.before) || 0));
            const afterVal = Math.max(0, Math.min(100, Number(item.after) || 0));
            return {
                x,
                yBefore: topPad + plotH - (beforeVal / 100) * plotH,
                yAfter: topPad + plotH - (afterVal / 100) * plotH,
                beforeVal,
                afterVal,
                item,
            };
        });

        if (coords.length >= 2) {
            const upperPts = coords.map((c) => `${c.x.toFixed(1)},${c.yAfter.toFixed(1)}`);
            const lowerPts = [...coords].reverse().map((c) => `${c.x.toFixed(1)},${c.yBefore.toFixed(1)}`);

            svg.appendChild(createSvgEl("polygon", {
                points: [...upperPts, ...lowerPts].join(" "),
                fill: "url(#plGradEvolutionArea)",
            }));

            svg.appendChild(createSvgEl("polyline", {
                points: coords.map((c) => `${c.x.toFixed(1)},${c.yBefore.toFixed(1)}`).join(" "),
                fill: "none",
                stroke: colors.beforeColor,
                "stroke-width": 2.4,
                "stroke-dasharray": "5 4",
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
            }));

            svg.appendChild(createSvgEl("polyline", {
                points: coords.map((c) => `${c.x.toFixed(1)},${c.yAfter.toFixed(1)}`).join(" "),
                fill: "none",
                stroke: colors.afterGreen,
                "stroke-width": 3,
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
            }));
        } else if (coords.length === 1) {
            const c = coords[0];
            svg.appendChild(createSvgEl("line", {
                x1: c.x,
                y1: c.yBefore,
                x2: c.x,
                y2: c.yAfter,
                stroke: colors.afterGreen,
                "stroke-width": 4,
                "stroke-linecap": "round",
            }));
        }

        // Puntos interactivos y etiquetas X
        coords.forEach((c) => {
            const infoFn = () => ({
                title: c.item.full_title || c.item.title,
                detail: `${c.item.date} · Antes: ${c.beforeVal} → Después: ${c.afterVal}`,
                badge: `${c.item.gain_fmt} · Modo ${c.item.mode}`,
            });

            // Conector vertical sutil en cada punto
            svg.appendChild(createSvgEl("line", {
                x1: c.x,
                y1: c.yBefore,
                x2: c.x,
                y2: c.yAfter,
                stroke: colors.gridStroke,
                "stroke-width": 1.2,
            }));

            const dotBefore = createSvgEl("circle", {
                cx: c.x,
                cy: c.yBefore,
                r: 4.5,
                fill: colors.beforeColor,
                stroke: "var(--pl-surface)",
                "stroke-width": 1.8,
            });
            attachInteractiveEvents(dotBefore, infoFn);
            svg.appendChild(dotBefore);

            const dotAfter = createSvgEl("circle", {
                cx: c.x,
                cy: c.yAfter,
                r: 5.5,
                fill: colors.afterGreen,
                stroke: "var(--pl-surface)",
                "stroke-width": 2,
            });
            attachInteractiveEvents(dotAfter, infoFn);
            svg.appendChild(dotAfter);

            const xLabel = createSvgEl("text", {
                x: c.x,
                y: height - 14,
                "text-anchor": "middle",
                fill: "var(--pl-text-secondary)",
                "font-size": "10.5",
            });
            xLabel.textContent = (c.item.date || "").split(" ")[0] || `#${c.item.order}`;
            svg.appendChild(xLabel);
        });

        container.appendChild(svg);
    }

    // ------------------------------------------------------------------
    // Gráficos 4 y 5: Barras verticales agrupadas (Técnica/Modo y Tarea)
    // ------------------------------------------------------------------
    function renderGroupedVerticalChart(containerId, items, options) {
        const container = $(containerId);
        if (!container) return;
        container.innerHTML = "";

        if (!items || items.length === 0) {
            container.innerHTML = '<div class="text-center py-4 small pl-text-secondary">Sin datos suficientes en esta vista.</div>';
            return;
        }

        const colors = getThemeChartColors();
        const rotatedLabels = Boolean(options && options.rotatedLabels);
        const afterColor = (options && options.afterColor) || colors.afterGreen;
        const afterLabel = (options && options.afterLabel) || "Prompt mejorado promedio";
        const beforeLabel = (options && options.beforeLabel) || "Idea inicial promedio";

        const minWidth = rotatedLabels ? Math.max(560, items.length * 90 + 36) : 520;
        const width = minWidth;
        const height = rotatedLabels ? 308 : 256;
        const leftPad = rotatedLabels ? 76 : 40;
        const rightPad = rotatedLabels ? 22 : 18;
        const topPad = 24;
        const bottomPad = rotatedLabels ? 88 : 44;
        const plotW = width - leftPad - rightPad;
        const plotH = height - topPad - bottomPad;

        const svg = createSvgEl("svg", {
            viewBox: `0 0 ${width} ${height}`,
            class: rotatedLabels ? "stats-svg-canvas stats-svg-wide" : "stats-svg-canvas",
            style: rotatedLabels ? `min-width: ${width}px;` : "",
            role: "img",
            "aria-label": options && options.ariaLabel ? options.ariaLabel : "Gráfico comparativo vertical",
        });

        // Gridlines horizontales 0-100
        [0, 25, 50, 75, 100].forEach((val) => {
            const y = topPad + plotH - (val / 100) * plotH;
            svg.appendChild(createSvgEl("line", {
                x1: leftPad,
                y1: y,
                x2: width - rightPad,
                y2: y,
                stroke: colors.gridStroke,
                "stroke-dasharray": val === 0 ? "none" : "3 4",
                "stroke-width": 1,
            }));

            const tickTxt = createSvgEl("text", {
                x: leftPad - 8,
                y: y + 4,
                "text-anchor": "end",
                fill: "var(--pl-text-secondary)",
                "font-size": "11",
            });
            tickTxt.textContent = String(val);
            svg.appendChild(tickTxt);
        });

        const groupW = plotW / items.length;
        const barW = Math.min(26, Math.max(14, groupW * 0.28));
        const pairGap = 5;

        items.forEach((item, idx) => {
            const cx = leftPad + idx * groupW + groupW / 2;
            const beforeVal = Math.max(0, Math.min(100, Number(item.before_avg) || 0));
            const afterVal = Math.max(0, Math.min(100, Number(item.after_avg) || 0));

            const hBefore = Math.max((beforeVal / 100) * plotH, beforeVal > 0 ? 4 : 0);
            const hAfter = Math.max((afterVal / 100) * plotH, afterVal > 0 ? 4 : 0);
            const yBefore = topPad + plotH - hBefore;
            const yAfter = topPad + plotH - hAfter;
            const xBefore = cx - barW - pairGap / 2;
            const xAfter = cx + pairGap / 2;

            const infoFn = () => ({
                title: item.label,
                detail: `${beforeLabel}: ${beforeVal}/100 · ${afterLabel}: ${afterVal}/100`,
                badge: `${item.gain_fmt} · ${item.count} prompt${item.count === 1 ? "" : "s"}`,
            });

            const rectBefore = createSvgEl("rect", {
                x: xBefore,
                y: yBefore,
                width: barW,
                height: hBefore,
                rx: 5,
                fill: colors.beforeColor,
            });
            attachInteractiveEvents(rectBefore, infoFn);
            svg.appendChild(rectBefore);

            const rectAfter = createSvgEl("rect", {
                x: xAfter,
                y: yAfter,
                width: barW,
                height: hAfter,
                rx: 5,
                fill: afterColor,
            });
            attachInteractiveEvents(rectAfter, infoFn);
            svg.appendChild(rectAfter);

            // Etiquetas numéricas encima de cada barra
            const lblBefore = createSvgEl("text", {
                x: xBefore + barW / 2,
                y: Math.max(12, yBefore - 5),
                "text-anchor": "middle",
                fill: "var(--pl-text-secondary)",
                "font-size": "10.5",
                "font-weight": "700",
            });
            lblBefore.textContent = String(beforeVal);
            svg.appendChild(lblBefore);

            const lblAfter = createSvgEl("text", {
                x: xAfter + barW / 2,
                y: Math.max(12, yAfter - 5),
                "text-anchor": "middle",
                fill: "var(--pl-text)",
                "font-size": "10.5",
                "font-weight": "800",
            });
            lblAfter.textContent = String(afterVal);
            svg.appendChild(lblAfter);

            // Etiqueta de eje X
            if (rotatedLabels) {
                const axisY = topPad + plotH + 14;
                const xLbl = createSvgEl("text", {
                    x: cx,
                    y: axisY,
                    "text-anchor": "end",
                    transform: `rotate(-32 ${cx.toFixed(1)} ${axisY.toFixed(1)})`,
                    fill: "var(--pl-text)",
                    "font-size": "11",
                    "font-weight": "600",
                });
                xLbl.textContent = truncateLabel(item.label, 20);
                svg.appendChild(xLbl);
            } else {
                const xLbl = createSvgEl("text", {
                    x: cx,
                    y: height - 16,
                    "text-anchor": "middle",
                    fill: "var(--pl-text)",
                    "font-size": "11.5",
                    "font-weight": "600",
                });
                xLbl.textContent = truncateLabel(item.label, 16);
                svg.appendChild(xLbl);
            }
        });

        container.appendChild(svg);
    }

    function initDashboardCharts() {
        const payloadEl = $("analytics-chart-data");
        if (!payloadEl) return;

        let data = null;
        try {
            data = JSON.parse(payloadEl.textContent || "{}");
        } catch (_e) {
            return;
        }
        if (!data || !data.total || Number(data.total) <= 0) return;

        const renderAll = () => {
            const colors = getThemeChartColors();
            renderHorizontalDomainsChart(data.domains || []);
            renderDonutChart(data.donut || {}, data.total);
            renderGroupedVerticalChart(
                "chart-tech-grouped-svg",
                data[activeGroupedView] || [],
                {
                    rotatedLabels: false,
                    afterColor: colors.afterGreen,
                    beforeLabel: "Puntaje inicial promedio",
                    afterLabel: "Puntaje final promedio",
                    ariaLabel: "Gráfico comparativo por técnica o modo",
                }
            );
            renderGroupedVerticalChart(
                "chart-task-grouped-svg",
                data.by_task || [],
                {
                    rotatedLabels: true,
                    afterColor: colors.afterViolet,
                    beforeLabel: "Idea inicial promedio",
                    afterLabel: "Prompt mejorado promedio",
                    ariaLabel: "Gráfico comparativo por tarea",
                }
            );
            renderEvolutionAreaChart(data.evolution || []);
        };

        document.querySelectorAll("[data-donut-view]").forEach((btn) => {
            btn.addEventListener("click", () => {
                const view = btn.getAttribute("data-donut-view");
                if (!view || view === activeDonutView) return;
                activeDonutView = view;
                document.querySelectorAll("[data-donut-view]").forEach((b) => {
                    const active = b.getAttribute("data-donut-view") === activeDonutView;
                    b.classList.toggle("active", active);
                    b.setAttribute("aria-pressed", active ? "true" : "false");
                });
                renderDonutChart(data.donut || {}, data.total);
            });
        });

        document.querySelectorAll("[data-grouped-view]").forEach((btn) => {
            btn.addEventListener("click", () => {
                const view = btn.getAttribute("data-grouped-view");
                if (!view || view === activeGroupedView) return;
                activeGroupedView = view;
                document.querySelectorAll("[data-grouped-view]").forEach((b) => {
                    const active = b.getAttribute("data-grouped-view") === activeGroupedView;
                    b.classList.toggle("active", active);
                    b.setAttribute("aria-pressed", active ? "true" : "false");
                });
                const colors = getThemeChartColors();
                renderGroupedVerticalChart(
                    "chart-tech-grouped-svg",
                    data[activeGroupedView] || [],
                    {
                        rotatedLabels: false,
                        afterColor: colors.afterGreen,
                        beforeLabel: "Puntaje inicial promedio",
                        afterLabel: "Puntaje final promedio",
                        ariaLabel: "Gráfico comparativo por técnica o modo",
                    }
                );
            });
        });

        renderAll();
        window.addEventListener("themeChanged", renderAll);
        window.addEventListener("scroll", hideTooltip, { passive: true, capture: true });
        window.addEventListener("resize", hideTooltip, { passive: true });
        document.addEventListener("show.bs.offcanvas", hideTooltip);
        document.addEventListener("show.bs.modal", hideTooltip);
    }

    document.addEventListener("DOMContentLoaded", initDashboardCharts);
})();
