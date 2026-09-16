# v0.0.26

Certification pathway selection.

- The Project Workspace now includes a Certification pathways panel and edit
  dialog. Choose which pathways appear in the report, set their order, and
  optionally mark one as recommended.
- Saving writes the ordered `certification_pathways.show` list and optional
  `certification_pathways.recommended` ID to `project.yaml`. The Use default
  action removes the block so the renderer uses its standard pathway set.
- The picker reads IDs and titles from the renderer template catalog. An older
  renderer runtime without that catalog shows a clear error in the dialog
  instead of crashing the Manager.
