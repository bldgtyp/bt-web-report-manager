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

html, body, .q-page, .nicegui-content,
.q-card, .q-table, .q-table th, .q-table td,
.q-item, .q-field, .q-field__native, .q-field__input,
.q-btn, .q-badge, .log-body, .nicegui-log,
p, span, div, label, code, pre {
  -webkit-user-select: text !important;
  user-select: text !important;
}

.q-page-container {
  padding-top: 0 !important;
}

.nicegui-content {
  padding: 0 !important;
  gap: 0 !important;
  width: 100% !important;
  max-width: 100% !important;
}

/* Toolbar / header band */
.app-header {
  background: var(--ink);
  color: #fafaf9;
  width: 100% !important;
  box-sizing: border-box;
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

/* Two-screen project index + workspace */
.screen-root {
  min-height: calc(100vh - 61px);
  width: 100%;
  box-sizing: border-box;
  padding: 24px;
  overflow: auto;
}
.index-screen,
.workspace-screen {
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
}
.index-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border);
}
.index-title,
.workspace-title {
  font-size: 30px;
  line-height: 1.12;
  font-weight: 800;
  color: var(--ink);
  letter-spacing: 0;
}
.index-subtitle {
  color: var(--text-2);
  font-size: 13px;
  margin-top: 6px;
}
.index-meta,
.section-note {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
}
.summary-bar.summary-bar-large {
  margin: 18px 0 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
}
.project-index-table {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  margin-top: 8px;
}
.project-index-table .q-table th {
  background: var(--surface-2) !important;
  color: var(--text-2) !important;
  font-size: 10.5px !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.05em !important;
}
.project-index-table .q-table td {
  font-size: 12.5px !important;
  color: var(--text) !important;
  border-bottom: 1px solid var(--border) !important;
  cursor: pointer;
}
.project-index-table .q-table tr:hover td {
  background: rgba(161, 98, 7, 0.06) !important;
}
.project-list {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  overflow-x: auto;
  overflow-y: hidden;
  margin-top: 8px;
}
.project-list-header,
.project-list-row {
  display: grid;
  grid-template-columns: minmax(220px, 1.5fr) minmax(110px, 0.7fr) minmax(220px, 1.4fr) minmax(170px, 1fr) minmax(135px, 0.8fr) minmax(135px, 0.8fr) minmax(110px, 0.7fr) minmax(190px, 1fr) 54px;
  min-width: 1340px;
  gap: 0;
  align-items: center;
}
.project-list-header {
  background: var(--surface-2);
  color: var(--text-2);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--border-strong);
}
.project-list-header > *,
.project-list-row > * {
  min-width: 0;
  padding: 9px 10px;
}
.project-list-row {
  width: 100%;
  background: var(--surface);
  border: 0;
  border-bottom: 1px solid var(--border);
  color: var(--text);
  text-align: left;
  font-family: var(--font-sans);
}
.project-list-row:last-child {
  border-bottom: 0;
}
.project-list-row:hover {
  background: rgba(161, 98, 7, 0.06);
}
.project-list-row:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
.project-cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12.5px;
  cursor: pointer;
}
.project-name {
  font-weight: 700;
}
.project-status-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  white-space: normal;
  cursor: pointer;
}
.project-delete-button {
  justify-self: center;
  color: var(--danger) !important;
}
.breadcrumb-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
}
.q-btn.breadcrumb-button {
  background: var(--surface) !important;
  border: 1px solid var(--border-strong) !important;
  border-radius: 6px !important;
  color: var(--ink) !important;
  font-size: 13px !important;
  text-transform: none !important;
}
.breadcrumb-meta {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 12px;
}
.breadcrumb-current {
  color: var(--ink);
  font-weight: 700;
  font-size: 13px;
}
.project-identity {
  padding: 26px 0 22px;
  border-bottom: 1px solid var(--border);
}
.project-title-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.workspace-badges {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px;
}
.project-meta-row,
.project-link-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px 14px;
  margin-top: 12px;
}
.meta-pill {
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  padding: 4px 10px;
  font-family: var(--font-mono);
  font-size: 12px;
}
.meta-label {
  color: var(--text-muted);
  font-size: 13px;
}
.meta-value {
  color: var(--ink);
  font-weight: 700;
  font-size: 13px;
  margin-left: 5px;
}
.inline-icon {
  color: var(--text-2);
  font-size: 18px;
}
.project-url {
  color: var(--info);
  font-family: var(--font-mono);
  font-size: 13px;
  text-decoration: none;
}
.project-timestamp {
  color: var(--text-2);
  font-family: var(--font-mono);
  font-size: 12px;
}
.workspace-action-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(210px, 1fr));
  gap: 16px;
  margin: 18px 0 22px;
}
.action-card-group,
.info-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  padding: 14px;
}
.action-card-group .action-group-label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 10px;
}
.action-card-group .action-group-label::before {
  content: '';
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
}
.action-card-group .marker-run::before { background: var(--warning); }
.action-card-group .marker-author::before { background: var(--info); }
.action-card-group .marker-publish::before { background: var(--success); }
.action-card-group .marker-process::before { background: var(--danger); }
.q-btn.action-card-button {
  width: 100%;
  min-height: 68px !important;
  margin-top: 8px;
}
.q-btn.action-card-button .q-btn__content {
  width: 100%;
  justify-content: flex-start !important;
}
.action-button-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  text-align: left;
}
.action-button-icon {
  font-size: 20px;
  flex: 0 0 auto;
}
.action-button-text {
  min-width: 0;
}
.action-button-label {
  font-size: 14px;
  font-weight: 800;
  color: inherit;
}
.action-button-detail {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-2);
  white-space: normal;
}
.q-btn.action-card-button.is-primary .action-button-detail,
.q-btn.action-card-button.is-warning .action-button-detail {
  color: rgba(250, 250, 249, 0.78);
}
.q-btn.action-card-button.is-warning .action-button-detail {
  color: rgba(28, 25, 23, 0.72);
}
.workspace-lower-grid {
  display: grid;
  grid-template-columns: minmax(420px, 1.2fr) minmax(360px, 0.85fr);
  gap: 16px;
  align-items: stretch;
}
.files-panel {
  grid-column: 1;
}
.workspace-log {
  grid-column: 2;
  grid-row: span 2;
  border-radius: 8px;
  overflow: hidden;
  min-height: 310px;
}
.status-panel {
  grid-column: 1;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.panel-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--ink);
  flex: 1;
}
.q-btn.panel-tool,
.q-btn.icon-tool {
  color: var(--text-2) !important;
  text-transform: none !important;
}
.file-row {
  display: grid;
  grid-template-columns: 74px minmax(0, 1fr) 32px;
  align-items: center;
  gap: 14px;
  padding: 12px 0;
  border-top: 1px solid var(--border);
}
.file-kind {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 24px;
  border-radius: 5px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  background: var(--surface-2);
  color: var(--text-2);
}
.file-kind-xlsx { background: var(--success-soft); color: var(--success); }
.file-kind-json { background: var(--warning-soft); color: var(--warning); }
.file-kind-url { background: var(--info-soft); color: var(--info); }
.file-label {
  font-size: 13px;
  font-weight: 800;
  color: var(--ink);
}
.file-value {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-2);
  overflow-wrap: anywhere;
}
.log-scope {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
}

@media (max-width: 1100px) {
  .workspace-action-grid,
  .workspace-lower-grid {
    grid-template-columns: 1fr 1fr;
  }
  .workspace-log,
  .files-panel,
  .status-panel {
    grid-column: auto;
    grid-row: auto;
  }
}

@media (max-width: 760px) {
  .app-header {
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px 14px;
  }
  .app-header .brand {
    flex: 1 0 100%;
  }
  .app-header .root-tag {
    display: none;
  }
  .q-btn.tool-btn {
    padding: 5px 9px !important;
    font-size: 12px !important;
  }
  .screen-root {
    padding: 16px;
  }
  .index-hero,
  .project-title-row {
    align-items: flex-start;
    flex-direction: column;
  }
  .workspace-action-grid,
  .workspace-lower-grid {
    grid-template-columns: 1fr;
  }
  .workspace-title,
  .index-title {
    font-size: 24px;
  }
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

.screen-root.is-frozen {
  opacity: 0.48;
  filter: grayscale(0.9);
  pointer-events: none;
  user-select: none;
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
.scrape-dialog-message {
  color: var(--text-2);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
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
