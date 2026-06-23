# Git Ignore Baseline

```gitignore
# OS/editor
.DS_Store
Thumbs.db
.idea/
.vscode/*
!.vscode/extensions.json
!.vscode/launch.json
!.vscode/tasks.json

# Secrets
.env
.env.*
!.env.example
*.pem
*.key
*.pfx

# Python
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.mypy_cache/
.pyright/
.coverage
htmlcov/
dist/
build/
*.egg-info/

# Node
node_modules/
dist/
build/
coverage/
.vite/

# .NET
bin/
obj/
TestResults/
*.user
*.suo

# Docker/local data
.local/
data/
volumes/
```
