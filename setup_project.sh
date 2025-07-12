#!/usr/bin/env bash
set -euo pipefail

# Ścieżka do katalogu projektu (katalog, w którym uruchamiasz skrypt)
PROJECT_DIR="$(pwd)"

# 1. Utworzenie katalogów
dirs=(
  "scraper"
  "scripts"
  "infrastructure"
)

echo "Tworzę katalogi..."
for d in "${dirs[@]}"; do
  if [ ! -d "$PROJECT_DIR/$d" ]; then
    mkdir -p "$PROJECT_DIR/$d"
    echo "  • utworzono $d"
  else
    echo "  • $d już istnieje"
  fi
done

# 2. Utworzenie plików w katalogu głównym
declare -A root_files
root_files[buildspec.yml]='version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.11
    commands:
      - echo Installing dependencies
      - pip install -r scraper/requirements.txt
  build:
    commands:
      - echo Running tests
      - pytest --maxfail=1 --disable-warnings -q

artifacts:
  files:
    - appspec.yml
    - scraper/**/*
    - scripts/**/*'
root_files[appspec.yml]='version: 0.0
Resources:
  - myLambdaFunction:
      Type: AWS::Lambda::Function
      Properties:
        Name: "career-equine-scraper"
        Alias: "live"
        CurrentVersion: "1"
        TargetVersion: "2"'

echo
echo "Tworzę pliki w katalogu głównym..."
for file in "${!root_files[@]}"; do
  filepath="$PROJECT_DIR/$file"
  if [ ! -f "$filepath" ]; then
    printf "%s\n" "${root_files[$file]}" > "$filepath"
    echo "  • utworzono $file"
  else
    echo "  • $file już istnieje"
  fi
done

# 3. scraper/main.py i scraper/requirements.txt
echo
echo "Tworzę pliki w scraper/..."
cat > "$PROJECT_DIR/scraper/main.py" << 'EOF'
import json
import logging

def lambda_handler(event, context):
    logging.info("Scraper został uruchomiony!")
    # TODO: logika scrapingu
    return {
        'statusCode': 200,
        'body': json.dumps('Scraper działa poprawnie!')
    }

if __name__ == "__main__":
    print("Test scrapera lokalnie")
EOF
echo "  • utworzono scraper/main.py"

cat > "$PROJECT_DIR/scraper/requirements.txt" << 'EOF'
requests==2.31.0
beautifulsoup4==4.12.2
psycopg2-binary==2.9.7
pytest==7.4.2
EOF
echo "  • utworzono scraper/requirements.txt"

# 4. scripts/after_allow_traffic.sh
echo
echo "Tworzę skrypt deploymentowy w scripts/..."
cat > "$PROJECT_DIR/scripts/after_allow_traffic.sh" << 'EOF'
#!/usr/bin/env bash
echo "Deployment completed successfully!"
EOF
chmod +x "$PROJECT_DIR/scripts/after_allow_traffic.sh"
echo "  • utworzono scripts/after_allow_traffic.sh (chmod +x)"

echo
echo "✔ Struktura projektu i podstawowe pliki zostały utworzone."
echo "Teraz wykonaj:"
echo "  git add ."
echo "  git commit -m \"Init project structure via setup_project.sh\""
echo "  git push origin main"
