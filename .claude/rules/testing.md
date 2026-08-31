---
description: "Testing conventions for this project."
globs:
  - "**/tests/**"
  - "**/*_test.py"
---

# Testing Conventions

- Idempotent tests re-runnable after cluster reinstall
- Reasonable timeouts (30s API, 120s deploy waits)
- Test positive and negative auth cases
- Use conftest.py fixtures for URLs and namespaces
