---
description: "Helm chart conventions for this project."
globs:
  - "**/charts/**/*.yaml"
  - "**/charts/**/*.tpl"
  - "**/templates/**/*.yaml"
---

# Helm Conventions

- Use `_helpers.tpl` for reusable template logic
- All values have sensible defaults
- No hardcoded namespaces — use `{{ .Release.Namespace }}`
- 2-space YAML indentation
- Gate optional resources with `{{- if .Values.<feature>.enabled }}`
