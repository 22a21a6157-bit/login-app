/* ═══════════════════════════════════════════════════════════════════
   Hex Network — shared rendering module for the referral constellation
   visualization. Pure rendering + interaction helpers; page-specific
   state (drill-down path, polling, search) lives in the pages that use
   this (network.html, the dashboard widget).
   ═══════════════════════════════════════════════════════════════════ */
const HexNetwork = (function () {
    "use strict";

    // Same palette already used elsewhere in the app (dashboard level
    // badges, admin status borders) - reused here, not reinvented, so the
    // network view reads as part of the same product rather than a
    // bolted-on widget.
    const STATUS_COLOR = { approved: "#10b981", pending: "#f59e0b", rejected: "#ef4444" };
    const STATUS_LABEL = { approved: "Approved", pending: "Pending", rejected: "Rejected" };
    const LEVEL_COLOR = {
        Starter: "#94a3b8", Bronze: "#f59e0b", Silver: "#cbd5e1",
        Gold: "#fbbf24", Diamond: "#22d3ee", Legend: "#f97316",
    };

    function esc(s) {
        return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
            { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
        ));
    }

    function shortLabel(name) {
        if (!name) return "?";
        const first = name.trim().split(/\s+/)[0];
        return first.length > 9 ? first.slice(0, 8) + "…" : first;
    }

    function initials(name) {
        if (!name) return "?";
        const parts = name.trim().split(/\s+/);
        return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
    }

    function hexPoints(cx, cy, r) {
        const pts = [];
        for (let i = 0; i < 6; i++) {
            const a = (Math.PI / 180) * (60 * i);
            pts.push(`${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`);
        }
        return pts.join(" ");
    }

    function satellitePos(cx, cy, dist, i, n) {
        const a = (Math.PI / 180) * (-90 + (360 / Math.max(n, 1)) * i);
        return { x: cx + dist * Math.cos(a), y: cy + dist * Math.sin(a) };
    }

    /**
     * Build the SVG markup for one hex + its ring of satellites.
     * center / satellites are plain node objects: {id,name,status,level,referrals,earned,joined,hasChildren}
     */
    function constellationSVG(center, satellites, opts) {
        opts = Object.assign({
            w: 280, h: 240, hexR: 40, spokeLen: 84, satR: 15,
            interactive: true, showSatLabels: false,
        }, opts);
        const cx = opts.w / 2, cy = opts.h / 2;
        const lvlColor = LEVEL_COLOR[center.level] || LEVEL_COLOR.Starter;
        const n = satellites.length;

        let svg = `<svg viewBox="0 0 ${opts.w} ${opts.h}" class="hexnet-svg" preserveAspectRatio="xMidYMid meet">`;

        satellites.forEach((s, i) => {
            const p = satellitePos(cx, cy, opts.spokeLen, i, n);
            svg += `<line x1="${cx}" y1="${cy}" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}" class="hexnet-spoke"/>`;
        });

        svg += `<g class="hexnet-node hexnet-hex" data-id="${esc(center.id)}" ${opts.interactive ? 'tabindex="0" role="button"' : ""} aria-label="${esc(center.name)}">
            <polygon points="${hexPoints(cx, cy, opts.hexR)}" class="hexnet-hexagon" style="--lvl:${lvlColor}"/>
            <text x="${cx}" y="${cy}" class="hexnet-hex-label">${esc(shortLabel(center.name))}</text>
        </g>`;

        satellites.forEach((s, i) => {
            const p = satellitePos(cx, cy, opts.spokeLen, i, n);
            const color = STATUS_COLOR[s.status] || STATUS_COLOR.approved;
            svg += `<g class="hexnet-node hexnet-satellite" data-id="${esc(s.id)}" ${opts.interactive ? 'tabindex="0" role="button"' : ""} aria-label="${esc(s.name)}, ${STATUS_LABEL[s.status] || s.status}">`;
            if (s.hasChildren) {
                svg += `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${opts.satR + 5}" class="hexnet-dot-ring"/>`;
            }
            svg += `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${opts.satR}" fill="${color}" class="hexnet-dot"/>`;
            if (opts.showSatLabels) {
                const anchor = p.x > cx + 4 ? "start" : (p.x < cx - 4 ? "end" : "middle");
                const dx = p.x > cx + 4 ? opts.satR + 6 : (p.x < cx - 4 ? -(opts.satR + 6) : 0);
                const dy = Math.abs(p.x - cx) < 4 ? (p.y < cy ? -(opts.satR + 8) : opts.satR + 16) : 4;
                svg += `<text x="${(p.x + dx).toFixed(1)}" y="${(p.y + dy).toFixed(1)}" text-anchor="${anchor}" class="hexnet-sat-label">${esc(shortLabel(s.name))}</text>`;
            }
            svg += `</g>`;
        });

        svg += `</svg>`;
        return svg;
    }

    function emptySVG(center, opts) {
        opts = Object.assign({ w: 280, h: 240, hexR: 40 }, opts);
        const cx = opts.w / 2, cy = opts.h / 2;
        const lvlColor = LEVEL_COLOR[center.level] || LEVEL_COLOR.Starter;
        return `<svg viewBox="0 0 ${opts.w} ${opts.h}" class="hexnet-svg">
            <g class="hexnet-node hexnet-hex" data-id="${esc(center.id)}" tabindex="0" role="button" aria-label="${esc(center.name)}">
                <polygon points="${hexPoints(cx, cy, opts.hexR)}" class="hexnet-hexagon" style="--lvl:${lvlColor}"/>
                <text x="${cx}" y="${cy}" class="hexnet-hex-label">${esc(shortLabel(center.name))}</text>
            </g>
            <text x="${cx}" y="${cy + opts.hexR + 26}" class="hexnet-empty-label">No referrals yet</text>
        </svg>`;
    }

    // ── Tooltip: one floating element, reused for every constellation on the page ──
    let tipEl = null;
    function ensureTooltip() {
        if (tipEl) return tipEl;
        tipEl = document.createElement("div");
        tipEl.className = "hexnet-tooltip";
        document.body.appendChild(tipEl);
        return tipEl;
    }

    function tooltipHTML(node) {
        const statusColor = STATUS_COLOR[node.status] || STATUS_COLOR.approved;
        const statusLabel = STATUS_LABEL[node.status] || node.status;
        return `
            <div class="hexnet-tooltip-name">${esc(node.name)}</div>
            <div class="hexnet-tooltip-row"><span class="hexnet-tooltip-dot" style="background:${statusColor}"></span>${esc(statusLabel)} &middot; ${esc(node.level)}</div>
            <div class="hexnet-tooltip-row">${node.referrals} referral${node.referrals === 1 ? "" : "s"} &middot; $${Number(node.earned).toFixed(2)} earned</div>
            ${node.joined ? `<div class="hexnet-tooltip-row hexnet-tooltip-muted">Joined ${esc(node.joined)}</div>` : ""}
            ${node.hasChildren ? `<div class="hexnet-tooltip-row hexnet-tooltip-hint">Click to explore their network →</div>` : ""}
        `;
    }

    function positionTooltip(el, evt) {
        const pad = 14;
        let x = evt.clientX + pad, y = evt.clientY + pad;
        const rect = el.getBoundingClientRect();
        if (x + rect.width > window.innerWidth - 8) x = evt.clientX - rect.width - pad;
        if (y + rect.height > window.innerHeight - 8) y = evt.clientY - rect.height - pad;
        el.style.transform = `translate(${Math.max(8, x)}px, ${Math.max(8, y)}px)`;
    }

    /**
     * Wire up hover/click/keyboard interaction for every .hexnet-node inside `root`.
     * `nodesById` maps id -> node data (center + satellites combined) so the
     * tooltip and click handler can look up full details from just the id
     * stored in the SVG's data-id attribute.
     */
    function attachInteractivity(root, nodesById, { onSelect } = {}) {
        const tip = ensureTooltip();
        root.querySelectorAll(".hexnet-node").forEach((el) => {
            const node = nodesById[el.getAttribute("data-id")];
            if (!node) return;

            el.addEventListener("mouseenter", (evt) => {
                tip.innerHTML = tooltipHTML(node);
                tip.classList.add("visible");
                positionTooltip(tip, evt);
            });
            el.addEventListener("mousemove", (evt) => positionTooltip(tip, evt));
            el.addEventListener("mouseleave", () => tip.classList.remove("visible"));

            const activate = () => {
                tip.classList.remove("visible");
                if (onSelect) onSelect(node);
            };
            el.addEventListener("click", activate);
            el.addEventListener("keydown", (evt) => {
                if (evt.key === "Enter" || evt.key === " ") { evt.preventDefault(); activate(); }
            });
        });
    }

    function nodeMap(center, satellites) {
        const map = {};
        if (center) map[center.id] = center;
        (satellites || []).forEach((s) => (map[s.id] = s));
        return map;
    }

    const SLOTS_PER_LEVEL = 5;
    const LEVEL_COUNT = 5;

    /**
     * Build the 5-levels x 5-hexagons grid. `levels` is an array of
     * { depth, total, people } from /api/my-network-levels, where `people`
     * is the real, individual referred users at that depth (never an
     * aggregate/graph node - one hexagon is always exactly one person).
     * Unfilled slots render as dull placeholder hexagons; filled slots are
     * highlighted and colored by that person's referral status.
     *
     * Progression: the first level that isn't completely filled (5/5) is
     * the "active" level and renders larger/brighter to draw the eye to
     * where to focus next. Levels before it that are already full render
     * as "completed" (normal size, checkmarked). Levels after it are
     * "locked" (smaller/dimmer) until the level ahead of them fills up.
     */
    function levelGridHTML(levels) {
        let activeIdx = LEVEL_COUNT; // default: every level full -> none "active"
        for (let i = 0; i < LEVEL_COUNT; i++) {
            if (((levels[i] || {}).total || 0) < SLOTS_PER_LEVEL) { activeIdx = i; break; }
        }

        let html = `<div class="hexnet-levels-grid">`;
        for (let i = 0; i < LEVEL_COUNT; i++) {
            const lvl = levels[i] || { depth: i + 1, total: 0, people: [] };
            const people = lvl.people || [];
            const state = i < activeIdx ? "completed" : i === activeIdx ? "active" : "locked";
            const stateBadge = state === "completed" ? '<span class="hexnet-level-badge hexnet-level-badge-done"><i class="bi bi-check-circle-fill"></i> Full</span>'
                : state === "active" ? '<span class="hexnet-level-badge hexnet-level-badge-active">Active</span>'
                : '<span class="hexnet-level-badge hexnet-level-badge-locked"><i class="bi bi-lock-fill"></i> Next up</span>';

            html += `<div class="hexnet-level-row hexnet-level-${state}" data-depth="${lvl.depth}">
                <div class="hexnet-level-label">
                    <span class="hexnet-level-num">Level ${lvl.depth}</span>
                    <span class="hexnet-level-count">${lvl.total} referred</span>
                    ${stateBadge}
                </div>
                <div class="hexnet-level-slots">`;
            for (let s = 0; s < SLOTS_PER_LEVEL; s++) {
                const person = people[s];
                if (person) {
                    const color = STATUS_COLOR[person.status] || STATUS_COLOR.approved;
                    html += `<div class="hexnet-node hexnet-slot hexnet-slot-filled" data-id="${esc(person.id)}"
                        style="--slot-color:${color}" tabindex="0" role="button"
                        aria-label="${esc(person.name)}, ${STATUS_LABEL[person.status] || person.status}">
                        <span class="hexnet-slot-initials">${esc(initials(person.name))}</span>
                    </div>`;
                } else {
                    html += `<div class="hexnet-slot hexnet-slot-dull hexnet-slot-add" tabindex="0" role="button"
                        aria-label="Empty slot - click to copy your referral link">
                        <span class="hexnet-slot-plus">+</span>
                    </div>`;
                }
            }
            if (lvl.total > SLOTS_PER_LEVEL) {
                html += `<div class="hexnet-level-more">+${lvl.total - SLOTS_PER_LEVEL} more</div>`;
            }
            html += `</div></div>`;
        }
        html += `</div>`;
        return html;
    }

    let _refPopup = null;
    function closeRefPopup() {
        if (_refPopup) { _refPopup.remove(); _refPopup = null; }
        document.removeEventListener("click", onDocClickCloseRefPopup, true);
    }
    function onDocClickCloseRefPopup(evt) {
        if (_refPopup && !_refPopup.contains(evt.target)) closeRefPopup();
    }

    /**
     * Wire every empty "+" hexagon in a levels grid so clicking it opens a
     * small popup beside that hexagon with the user's referral link,
     * copies it to the clipboard immediately, and offers a manual copy
     * button too. `copyFn` should be the app's existing copyToClipboard(text).
     */
    function attachLevelGridAddSlots(root, refLink, copyFn) {
        root.querySelectorAll(".hexnet-slot-add").forEach((el) => {
            const open = (evt) => {
                evt.stopPropagation();
                closeRefPopup();

                const rect = el.getBoundingClientRect();
                const popup = document.createElement("div");
                popup.className = "hexnet-ref-popup";
                popup.innerHTML = `
                    <div class="hexnet-ref-popup-title"><i class="bi bi-link-45deg"></i> Your referral link</div>
                    <div class="hexnet-ref-popup-copied"><i class="bi bi-check-circle-fill"></i> Copied to clipboard</div>
                    <div class="hexnet-ref-popup-row">
                        <input type="text" readonly value="${esc(refLink)}">
                        <button type="button" class="hexnet-ref-popup-copy"><i class="bi bi-clipboard"></i></button>
                    </div>
                    <div class="hexnet-ref-popup-hint">Share it - new sign-ups fill the next open slot automatically.</div>
                `;
                document.body.appendChild(popup);

                // Position aside the hexagon: prefer to the right, flip to
                // the left if it would run off the viewport edge.
                const pw = popup.offsetWidth, ph = popup.offsetHeight;
                let left = rect.right + 10;
                if (left + pw > window.innerWidth - 8) left = rect.left - pw - 10;
                if (left < 8) left = Math.max(8, Math.min(window.innerWidth - pw - 8, rect.left));
                let top = rect.top + rect.height / 2 - ph / 2;
                top = Math.max(8, Math.min(window.innerHeight - ph - 8, top));
                popup.style.left = `${left + window.scrollX}px`;
                popup.style.top = `${top + window.scrollY}px`;

                popup.querySelector(".hexnet-ref-popup-copy").addEventListener("click", () => copyFn(refLink));
                _refPopup = popup;
                if (typeof copyFn === "function") copyFn(refLink);
                requestAnimationFrame(() => document.addEventListener("click", onDocClickCloseRefPopup, true));
            };
            el.addEventListener("click", open);
            el.addEventListener("keydown", (evt) => {
                if (evt.key === "Enter" || evt.key === " ") { evt.preventDefault(); open(evt); }
            });
        });
    }

    /** Flat id -> node map built from every person across all 5 levels, for tooltip/click lookups. */
    function levelNodeMap(levels) {
        const map = {};
        (levels || []).forEach((lvl) => (lvl.people || []).forEach((p) => (map[p.id] = p)));
        return map;
    }

    function legendHTML() {
        const statuses = Object.keys(STATUS_COLOR).map((k) =>
            `<span class="hexnet-legend-item"><span class="hexnet-legend-dot" style="background:${STATUS_COLOR[k]}"></span>${STATUS_LABEL[k]}</span>`
        ).join("");
        const levels = Object.keys(LEVEL_COLOR).map((k) =>
            `<span class="hexnet-legend-item"><span class="hexnet-legend-hex" style="--lvl:${LEVEL_COLOR[k]}"></span>${k}</span>`
        ).join("");
        return `<div class="hexnet-legend-group"><span class="hexnet-legend-title">Status</span>${statuses}</div>
                <div class="hexnet-legend-group"><span class="hexnet-legend-title">Level</span>${levels}</div>`;
    }

    function statusLegendHTML() {
        const statuses = Object.keys(STATUS_COLOR).map((k) =>
            `<span class="hexnet-legend-item"><span class="hexnet-legend-dot" style="background:${STATUS_COLOR[k]}"></span>${STATUS_LABEL[k]}</span>`
        ).join("");
        return `<div class="hexnet-legend-group">${statuses}</div>`;
    }

    return {
        STATUS_COLOR, STATUS_LABEL, LEVEL_COLOR,
        esc, initials, constellationSVG, emptySVG, attachInteractivity, nodeMap, legendHTML, statusLegendHTML,
        levelGridHTML, levelNodeMap, attachLevelGridAddSlots,
    };
})();
