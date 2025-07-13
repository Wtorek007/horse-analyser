#!/usr/bin/env bash
set -euo pipefail

# Ścieżka do katalogu projektu
PROJECT_DIR="$(pwd)"

# Zawartość Dockerfile
cat > "$PROJECT_DIR/Dockerfile" << 'EOF'
FROM python:3.12

WORKDIR /app

COPY scraper/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY scraper/ .

CMD ["python", "main.py"]
EOF

echo "✔ Plik Dockerfile został utworzony w katalogu głównym projektu."

# Dodanie do Gita i wypchnięcie na GitHub
git add Dockerfile
git commit -m "Add Dockerfile to root directory"
git push origin main

echo "✔ Dockerfile dodany do repozytorium i wypchnięty na GitHub."
