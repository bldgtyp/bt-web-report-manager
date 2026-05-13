"""Global theme + CSS for the manager.

Design direction: "Studio Console" — a refined, architectural-studio
aesthetic. Warm-neutral light theme with a deep-ink header, a single muted
amber accent, and JetBrains Mono for technical strings (paths, slugs,
timestamps). The visual language is meant to feel like a well-laid-out
drawing sheet: dense data, generous breathing room around action surfaces,
semantic color used sparingly.
"""

from __future__ import annotations

from nicegui import ui

FONT_LINK = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
"""

CSS = """
:root {
  --bg: #fafaf9;
  --surface: #ffffff;
  --surface-2: #f5f5f4;
  --ink: #1c1917;
  --ink-soft: #292524;
  --text: #1c1917;
  --text-2: #57534e;
  --text-muted: #a8a29e;
  --border: #e7e5e4;
  --border-strong: #d6d3d1;
  --accent: #a16207;
  --accent-soft: #fef3c7;
  --accent-strong: #854d0e;
  --success: #15803d;
  --success-soft: #dcfce7;
  --warning: #b45309;
  --warning-soft: #fef3c7;
  --danger: #b91c1c;
  --danger-soft: #fee2e2;
  --info: #1d4ed8;
  --info-soft: #dbeafe;
  --shadow-sm: 0 1px 2px rgba(28, 25, 23, 0.05);
  --shadow-md: 0 4px 12px rgba(28, 25, 23, 0.08);
  --shadow-lg: 0 12px 32px rgba(28, 25, 23, 0.12);
  --font-sans: 'Manrope', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;
}

html, body, .q-page, .nicegui-content {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: var(--font-sans) !important;
  -webkit-font-smoothing: antialiased;
  font-feature-settings: 'cv11', 'ss01', 'ss03';
}

.q-page-container {
  padding-top: 0 !important;
}

.nicegui-content {
  padding: 0 !important;
  gap: 0 !important;
  max-width: 100% !important;
}

/* Toolbar / header band */
.app-header {
  background: var(--ink);
  color: #fafaf9;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid #000;
  box-shadow: var(--shadow-md);
}
.app-header .brand {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 700;
  font-size: 15px;
  letter-spacing: -0.01em;
}
.app-header .brand-mark {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: var(--ink);
  font-weight: 800;
  font-family: var(--font-mono);
  border-radius: 6px;
  font-size: 14px;
}
.app-header .root-tag {
  color: #d6d3d1;
  font-family: var(--font-mono);
  font-size: 12px;
  margin-left: auto;
  background: rgba(255,255,255,0.04);
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.06);
  max-width: 540px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Main content frame */
.app-body {
  padding: 16px 20px 20px;
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  width: 100%;
}
.pane {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
}
.pane-left {
  flex: 1.55;
  overflow: hidden;
  min-width: 0;
}
.pane-right {
  flex: 1;
  min-width: 420px;
  max-width: 560px;
  overflow: hidden;
}
.pane-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
  border-radius: 10px 10px 0 0;
  display: flex;
  align-items: center;
  gap: 12px;
}
.pane-header .pane-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-2);
}
.pane-header .pane-meta {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
  margin-left: auto;
}

/* Project table */
.project-table {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: auto;
}
.project-table .q-table__container,
.project-table .q-table__middle {
  max-width: 100%;
  overflow: auto !important;
}
.project-table .q-table {
  background: transparent;
  border-radius: 0;
}
.project-table .q-table th {
  background: var(--surface-2) !important;
  color: var(--text-2) !important;
  font-size: 10.5px !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.05em !important;
  border-bottom: 1px solid var(--border-strong) !important;
  position: sticky !important;
  top: 0 !important;
  z-index: 2;
  padding: 8px 8px !important;
  white-space: nowrap !important;
}
.project-table .q-table td {
  font-size: 12.5px !important;
  color: var(--text) !important;
  border-bottom: 1px solid var(--border) !important;
  padding: 8px 8px !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  max-width: 200px !important;
}
.project-table .q-table td.col-mono,
.project-table .q-table .col-mono {
  font-family: var(--font-mono) !important;
  font-size: 11.5px !important;
}
.project-table .q-table tr:hover td {
  background: rgba(161, 98, 7, 0.04) !important;
}
.project-table .q-table tr.selected td,
.project-table .q-table tr.q-table--row-selected td {
  background: rgba(161, 98, 7, 0.10) !important;
}
.project-table .col-mono {
  font-family: var(--font-mono) !important;
  font-size: 12px !important;
}

/* Status chip */
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  font-family: var(--font-sans);
  border: 1px solid transparent;
  white-space: nowrap;
}
.chip + .chip { margin-left: 4px; }
.chip-neutral { background: var(--surface-2); color: var(--text-2); border-color: var(--border-strong); }
.chip-success { background: var(--success-soft); color: var(--success); border-color: #bbf7d0; }
.chip-warning { background: var(--warning-soft); color: var(--warning); border-color: #fde68a; }
.chip-danger  { background: var(--danger-soft);  color: var(--danger);  border-color: #fecaca; }
.chip-info    { background: var(--info-soft);    color: var(--info);    border-color: #bfdbfe; }
.chip-accent  { background: var(--accent-soft);  color: var(--accent-strong); border-color: #fde68a; }

/* Summary strip */
.summary-bar {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-2);
}
.summary-bar .metric {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}
.summary-bar .metric .num {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  font-family: var(--font-sans);
}
.summary-bar .divider {
  width: 1px;
  height: 16px;
  background: var(--border-strong);
}

/* Right pane */
.detail-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.02em;
}
.detail-subtitle {
  font-size: 12px;
  color: var(--text-2);
  font-family: var(--font-mono);
  margin-top: 2px;
}
.detail-section {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.detail-section:last-child { border-bottom: none; }
.detail-section .section-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.kv-grid {
  display: grid;
  grid-template-columns: 110px 1fr;
  row-gap: 4px;
  column-gap: 12px;
  font-size: 12.5px;
}
.kv-grid .k {
  color: var(--text-muted);
  text-transform: uppercase;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding-top: 2px;
}
.kv-grid .v {
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 12px;
  word-break: break-all;
}

/* Action button cluster */
.action-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding: 14px 16px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
}
.action-group-label {
  grid-column: 1 / -1;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-top: 4px;
  margin-bottom: 2px;
}
.action-group-label:first-child {
  margin-top: 0;
}

/* High specificity overrides for Quasar's bg-primary default */
.q-btn.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  padding: 10px 12px !important;
  border-radius: 8px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  letter-spacing: -0.005em !important;
  text-transform: none !important;
  border: 1px solid var(--border-strong) !important;
  background: var(--surface) !important;
  color: var(--text) !important;
  min-height: 38px !important;
  box-shadow: none !important;
  transition: background-color 120ms ease, border-color 120ms ease, transform 80ms ease !important;
}
.q-btn.action-btn .q-btn__content {
  color: var(--text) !important;
}
.q-btn.action-btn:hover:not(:disabled):not([disabled]) {
  border-color: var(--ink-soft) !important;
  background: var(--surface-2) !important;
}
.q-btn.action-btn:active:not(:disabled):not([disabled]) {
  transform: translateY(1px);
}
.q-btn.action-btn.is-primary {
  background: var(--ink) !important;
  border-color: var(--ink) !important;
}
.q-btn.action-btn.is-primary .q-btn__content,
.q-btn.action-btn.is-primary {
  color: #fafaf9 !important;
}
.q-btn.action-btn.is-primary:hover:not(:disabled):not([disabled]) {
  background: var(--ink-soft) !important;
}
.q-btn.action-btn.is-warning {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
}
.q-btn.action-btn.is-warning .q-btn__content,
.q-btn.action-btn.is-warning {
  color: var(--ink) !important;
}
.q-btn.action-btn.is-warning:hover:not(:disabled):not([disabled]) {
  background: #b58510 !important;
  border-color: #b58510 !important;
}
.q-btn.action-btn.is-danger {
  background: var(--surface) !important;
  border-color: var(--danger-soft) !important;
}
.q-btn.action-btn.is-danger .q-btn__content,
.q-btn.action-btn.is-danger {
  color: var(--danger) !important;
}
.q-btn.action-btn.is-danger:hover:not(:disabled):not([disabled]) {
  background: var(--danger-soft) !important;
  border-color: var(--danger) !important;
}
.q-btn.action-btn[disabled],
.q-btn.action-btn:disabled,
.q-btn.action-btn.disabled {
  opacity: 0.45 !important;
  cursor: not-allowed !important;
}

.q-btn.action-btn .q-icon {
  font-size: 16px !important;
}

/* High specificity for toolbar buttons too */
.q-btn.tool-btn {
  background: transparent !important;
  color: #d6d3d1 !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  border-radius: 6px !important;
  padding: 6px 12px !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  letter-spacing: -0.005em !important;
  text-transform: none !important;
  min-height: 32px !important;
  box-shadow: none !important;
  transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease !important;
}
.q-btn.tool-btn .q-btn__content {
  color: #d6d3d1 !important;
}
.q-btn.tool-btn:hover {
  background: rgba(255,255,255,0.06) !important;
  border-color: rgba(255,255,255,0.16) !important;
}
.q-btn.tool-btn:hover .q-btn__content {
  color: #fafaf9 !important;
}
.q-btn.tool-btn.is-primary,
.q-btn.tool-btn.is-primary .q-btn__content {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: var(--ink) !important;
  font-weight: 700 !important;
}
.q-btn.tool-btn.is-primary {
  /* background already set above; keep border consistent */
  background: var(--accent) !important;
  border-color: var(--accent) !important;
}
.q-btn.tool-btn.is-primary:hover {
  background: #b58510 !important;
  border-color: #b58510 !important;
}

/* Log pane */
.log-shell {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--border);
}
.log-shell .log-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: var(--ink);
  color: #fafaf9;
  font-family: var(--font-mono);
  font-size: 11px;
}
.log-shell .log-header .led {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #4ade80;
  box-shadow: 0 0 6px rgba(74, 222, 128, 0.6);
}
.log-shell .log-header .led.idle { background: #71717a; box-shadow: none; }
.log-shell .log-body {
  background: #0c0a09;
  color: #d6d3d1;
  font-family: var(--font-mono);
  font-size: 11.5px;
  padding: 10px 12px;
  flex: 1;
  min-height: 140px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* NiceGUI ui.log overrides */
.nicegui-log {
  background: #0c0a09 !important;
  color: #d6d3d1 !important;
  font-family: var(--font-mono) !important;
  font-size: 11.5px !important;
  border-radius: 0 !important;
  padding: 10px 12px !important;
}

/* Dialogs */
.q-dialog__inner > .q-card {
  background: var(--surface) !important;
  border-radius: 12px !important;
  border: 1px solid var(--border) !important;
  box-shadow: var(--shadow-lg) !important;
}
.dialog-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--ink);
}
.dialog-subtitle {
  font-size: 12px;
  color: var(--text-2);
  margin-top: -2px;
}
.dialog-section-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-top: 4px;
}

/* Scrollbars */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* Quasar overrides for form inputs */
.q-field__control {
  font-family: var(--font-sans) !important;
}
.q-field--outlined .q-field__control {
  border-radius: 8px !important;
}
.q-field--outlined .q-field__control:before {
  border-color: var(--border-strong) !important;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 24px;
  color: var(--text-muted);
  text-align: center;
}
.empty-state .empty-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-2);
}
.empty-state .empty-body {
  font-size: 13px;
  max-width: 480px;
  line-height: 1.5;
}

/* Tooltip refinement */
.q-tooltip {
  background: var(--ink) !important;
  color: #fafaf9 !important;
  font-size: 12px !important;
  font-family: var(--font-sans) !important;
  padding: 6px 10px !important;
  border-radius: 6px !important;
  max-width: 320px !important;
  line-height: 1.4 !important;
}

/* Stepper polish for the wizard */
.q-stepper {
  background: transparent !important;
  box-shadow: none !important;
}
.q-stepper__nav { padding-top: 8px !important; }
"""


def apply_theme() -> None:
    """Inject fonts + CSS. Call once per page (inside ``@ui.page``)."""
    ui.add_head_html(FONT_LINK)
    ui.add_css(CSS)
    # Quasar color tokens — primary stays warm amber, secondary deep ink
    ui.colors(
        primary="#a16207",
        secondary="#1c1917",
        accent="#a16207",
        positive="#15803d",
        negative="#b91c1c",
        warning="#b45309",
        info="#1d4ed8",
    )
