"""
AWS Lambda scraper wyścigów konnych - kompletny kod
Przeznaczony do wklejenia w PyCharm dla projektu horse-analyser
"""

import json
import os
import time
import logging
import psycopg2
import re
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import boto3
from botocore.exceptions import ClientError

# Konfiguracja logowania dla AWS Lambda
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    """
    Główny handler Lambda dla scrapera wyścigów konnych
    """
    try:
        logger.info("Rozpoczynanie scrapingu wyścigów konnych...")

        # Sprawdź czy podano konkretny dzień wyścigowy w event
        if 'race_day' in event:
            os.environ['NEXT_RACE_DAY'] = str(event['race_day'])
            logger.info(f"Używam race_day z event: {event['race_day']}")

        # Pobranie URL-i do przetworzenia
        urls_to_scrape = generate_weekly_urls()
        logger.info(f"Będę scrapować {len(urls_to_scrape)} URL-i")

        # Inicjalizacja Chrome WebDriver
        driver = setup_chrome_driver()

        # Połączenie z bazą danych RDS
        conn = connect_to_rds()

        total_processed = 0
        successful_urls = []
        failed_urls = []

        # Przetwarzanie każdego URL
        for url in urls_to_scrape:
            try:
                logger.info(f"Pobieranie strony: {url}")

                # Wykonaj scraping dla pojedynczego URL
                result = scrape_single_url(driver, url, conn)

                if result['success']:
                    total_processed += result['races_count']
                    successful_urls.append(url)
                    logger.info(f"✓ Pomyślnie przetworzono {result['races_count']} gonitw z {url}")
                else:
                    failed_urls.append(url)
                    logger.warning(f"× Niepowodzenie dla {url}: {result['error']}")

            except Exception as e:
                failed_urls.append(url)
                logger.error(f"× Błąd podczas przetwarzania {url}: {str(e)}")

        # Zamknięcie połączeń
        driver.quit()
        conn.close()

        # Zwrócenie rezultatu
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Scraping zakończony',
                'total_races_processed': total_processed,
                'successful_urls': len(successful_urls),
                'failed_urls': len(failed_urls),
                'failed_url_list': failed_urls,
                'processed_urls': successful_urls,
                'timestamp': datetime.now().isoformat()
            })
        }

    except Exception as e:
        logger.error(f"Błąd główny: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }


def generate_weekly_urls():
    """
    Generuje URL-e dla aktualnych wyścigów na podstawie konfiguracji
    """
    # Pobierz aktualny numer dnia wyścigowego z zmiennej środowiskowej
    current_race_day = get_current_race_day()

    # Generuj URL-e dla najbliższych dni wyścigowych
    urls = []

    # Sprawdź kilka kolejnych numerów (na wypadek przerw w wyścigach)
    for day_offset in range(5):  # sprawdź 5 kolejnych numerów
        race_day = current_race_day + day_offset
        url = f"https://torsluzewiec.pl/dzien-wyscigowy/dzien-{race_day}-2025/"
        urls.append(url)

    logger.info(f"Wygenerowano URLs począwszy od dzień-{current_race_day}-2025: {urls}")
    return urls


def get_current_race_day():
    """
    Pobiera aktualny numer dnia wyścigowego do scrapowania
    """
    # Metoda 1: Ze zmiennej środowiskowej
    env_race_day = os.environ.get('NEXT_RACE_DAY')
    if env_race_day:
        return int(env_race_day)

    # Metoda 2: Z pliku konfiguracyjnego w S3 (opcjonalnie)
    race_day = get_race_day_from_s3()
    if race_day:
        return race_day

    # Metoda 3: Domyślnie - następny do scrapowania to 17
    return 17


def get_race_day_from_s3():
    """
    Opcjonalnie: pobierz numer dnia wyścigowego z pliku w S3
    """
    try:
        s3 = boto3.client('s3')

        # Pobierz plik konfiguracyjny z S3
        bucket_name = os.environ.get('CONFIG_BUCKET', 'horse-analyser-config')

        response = s3.get_object(
            Bucket=bucket_name,
            Key='race-config.json'
        )

        config = json.loads(response['Body'].read())
        return config.get('next_race_day', 17)

    except Exception as e:
        logger.warning(f"Nie udało się pobrać konfiguracji z S3: {e}")
        return None


def setup_chrome_driver():
    """
    Konfiguracja Chrome WebDriver dla środowiska AWS Lambda
    """
    try:
        chrome_options = Options()

        # Ustawienia dla headless Chrome w Lambda
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--single-process')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')

        # Ścieżki do Chrome i ChromeDriver w Lambda
        chrome_options.binary_location = '/opt/chrome/chrome'

        service = Service(
            executable_path="/opt/chromedriver")
        driver = webdriver.Chrome(
            service=service, options=options
        )

        # Ustaw timeout dla strony
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)

        logger.info("Chrome WebDriver zainicjalizowany pomyślnie")
        return driver

    except Exception as e:
        logger.error(f"Błąd inicjalizacji Chrome WebDriver: {str(e)}")
        raise


def connect_to_rds():
    """
    Nawiązuje połączenie z bazą danych AWS RDS PostgreSQL
    """
    try:
        # Pobranie konfiguracji z zmiennych środowiskowych
        db_config = {
            "host": os.environ['RDS_ENDPOINT'],
            "port": int(os.environ.get('DB_PORT', '5432')),
            "dbname": os.environ['DB_NAME'],
            "user": os.environ['DB_USER'],
            "password": get_database_password(),
            "connect_timeout": 30,
            "sslmode": 'require'
        }

        # Nawiązanie połączenia
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False  # Używamy transakcji

        logger.info(f"Połączono z bazą danych RDS: {db_config['host']}")

        return conn

    except Exception as e:
        logger.error(f"Błąd połączenia z bazą danych: {str(e)}")
        raise


def get_database_password():
    """
    Pobiera hasło do bazy danych z AWS Secrets Manager lub zmiennych środowiskowych
    """
    # Sprawdź czy używamy Secrets Manager
    secret_name = os.environ.get('DB_SECRET_NAME')

    if secret_name:
        try:
            # Pobierz hasło z Secrets Manager
            session = boto3.session.Session()
            client = session.client('secretsmanager')

            response = client.get_secret_value(SecretId=secret_name)
            secret = json.loads(response['SecretString'])

            return secret['password']

        except ClientError as e:
            logger.error(f"Błąd pobierania sekretu z Secrets Manager: {str(e)}")
            # Fallback na zmienną środowiskową
            return os.environ.get('DB_PASSWORD')
    else:
        # Użyj zmiennej środowiskowej
        return os.environ.get('DB_PASSWORD')


def scrape_single_url(driver, url, conn):
    """
    Scrapuje pojedynczy URL i zwraca rezultat
    """
    try:
        driver.get(url)

        # Czekaj na załadowanie strony
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "race-result"))
        )
        time.sleep(2)

        # Pobierz datę wyścigu
        try:
            raw_date = clean(driver.find_element(
                By.CSS_SELECTOR,
                "#content > div.page-blocks > div > div > div > section > div.info > h2"
            ).text)
            race_date = extract_race_date(raw_date)
        except Exception as e:
            logger.warning(f"Nie można pobrać daty z {url}: {str(e)}")
            race_date = None

        if not race_date:
            return {'success': False, 'error': 'Brak daty wyścigu', 'races_count': 0}

        # Parsuj gonitwy
        soup = BeautifulSoup(driver.page_source, "html.parser")
        gonitwy = parse_gonitwy(soup, race_date)

        if gonitwy:
            # Zapisz do bazy danych
            insert_to_rds(gonitwy, conn)
            return {'success': True, 'races_count': len(gonitwy)}
        else:
            return {'success': False, 'error': 'Brak gonitw na stronie', 'races_count': 0}

    except Exception as e:
        return {'success': False, 'error': str(e), 'races_count': 0}


def clean(text: str) -> str:
    """Czyści tekst z niepotrzebnych znaków"""
    if not text:
        return ""
    return text.replace('\xa0', ' ').replace('\n', ' ').replace('\r', '').strip()


def extract_race_date(raw_text: str) -> str | None:
    """
    Z „DZIEŃ X - 19.04.2015" wyciąga „2015-04-19" (ISO 8601).
    """
    match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', raw_text)
    if not match:
        logger.warning(f"Nie znaleziono daty w: {raw_text}")
        return None
    day, month, year = match.groups()
    try:
        return datetime(int(year), int(month), int(day)).strftime('%Y-%m-%d')
    except ValueError:
        logger.error(f"Błędna data: {raw_text}")
        return None


def int_or_none(value: str) -> int | None:
    """
    Zwraca int jeśli w wartości są cyfry, w przeciwnym razie None.
    """
    if not value:
        return None
    digits = re.sub(r'[^\d]', '', value)
    return int(digits) if digits else None


def parse_gonitwy(soup: BeautifulSoup, race_date: str) -> list[dict]:
    """
    Parsuje gonitwy z HTML (zachowana oryginalna logika)
    """
    gonitwy = []
    for race_div in soup.find_all('div', class_='race-result'):
        h3 = race_div.find('h3')
        dist_div = race_div.find('div', class_='distance')
        opis_div = race_div.find('div', class_='desc')

        nazwa = clean(h3.text) if h3 else ""
        dystans = clean(dist_div.text) if dist_div else ""
        opis = clean(opis_div.text) if opis_div else ""

        konie = []
        table = race_div.find('table', class_='results')
        if table:
            for row in table.find_all('tr')[1:]:
                cells = row.find_all('td')
                if len(cells) >= 5:
                    konie.append({
                        "miejsce": clean(cells[0].text),
                        "nazwa_konia": clean(cells[2].text),
                        "jezdziec": clean(cells[3].text),
                        "nr_startowy": clean(cells[4].text)
                    })

        # Dodatkowe informacje
        czas = temperatura = styl = odleglosci = stan_toru = ""
        add_info_div = race_div.find('div', class_='add-info-content')
        if add_info_div:
            for row in add_info_div.select('table.add-info-table tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label, val = [clean(t.text) for t in cells[:2]]
                    label = label.lower()
                    if 'czas' in label:
                        czas = val
                    elif 'temperatura' in label:
                        temperatura = val
                    elif 'styl' in label:
                        styl = val
                    elif 'odległości' in label:
                        odleglosci = val
                    elif 'stan toru' in label:
                        stan_toru = val

        gonitwy.append({
            "nazwa": nazwa,
            "dystans": dystans,
            "opis": opis,
            "konie": konie,
            "czas": czas,
            "temperatura": temperatura,
            "styl": styl,
            "odleglosci": odleglosci,
            "stan_toru": stan_toru,
            "data": race_date
        })
    return gonitwy


def insert_to_rds(gonitwy: list[dict], conn):
    """
    Zapisuje gonitwy do bazy danych AWS RDS
    """
    INSERT_SQL = """
                 INSERT INTO wyniki_gonitw (nazwa_gonitwy, dystans, opis, miejsce, nazwa_konia, jezdziec, nr_startowy, \
                                            czas, temperatura, styl, odleglosci, stan_toru, data_wyscigu) \
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, \
                         %s) ON CONFLICT (nazwa_gonitwy, data_wyscigu, nazwa_konia, jezdziec) DO NOTHING \
                 """

    try:
        with conn.cursor() as cur:
            total_inserted = 0
            for g in gonitwy:
                dystans_int = int_or_none(g["dystans"])
                for kon in g["konie"]:
                    try:
                        cur.execute(
                            INSERT_SQL,
                            (
                                g["nazwa"],
                                dystans_int,
                                g["opis"],
                                int_or_none(kon["miejsce"]),
                                kon["nazwa_konia"] or None,
                                kon["jezdziec"] or None,
                                int_or_none(kon["nr_startowy"]),
                                g["czas"] or None,
                                g["temperatura"] or None,
                                g["styl"] or None,
                                g["odleglosci"] or None,
                                g["stan_toru"] or None,
                                g["data"]
                            )
                        )
                        if cur.rowcount > 0:
                            total_inserted += 1

                    except Exception as e:
                        logger.error(f"Błąd INSERT: {e} | Gonitwa={g['nazwa']} | Koń={kon['nazwa_konia']}")
                        conn.rollback()
                        raise

            # Commit wszystkich zmian na raz
            conn.commit()
            logger.info(f"Zapisano {total_inserted} nowych rekordów do bazy")

    except Exception as e:
        logger.error(f"Błąd zapisu do bazy: {str(e)}")
        conn.rollback()
        raise


def update_race_day_after_scraping(last_processed_day):
    """
    Aktualizuje numer następnego dnia wyścigowego po zakończeniu scrapingu
    """
    try:
        s3 = boto3.client('s3')

        # Aktualizuj plik konfiguracyjny
        config = {
            'next_race_day': last_processed_day + 1,
            'last_updated': datetime.now().isoformat(),
            'last_processed_day': last_processed_day
        }

        bucket_name = os.environ.get('CONFIG_BUCKET', 'horse-analyser-config')

        s3.put_object(
            Bucket=bucket_name,
            Key='race-config.json',
            Body=json.dumps(config),
            ContentType='application/json'
        )

        logger.info(f"Zaktualizowano next_race_day na {last_processed_day + 1}")

    except Exception as e:
        logger.error(f"Nie udało się zaktualizować konfiguracji: {e}")


# Funkcja pomocnicza do testowania lokalnego
def main():
    """
    Funkcja do testowania lokalnego (nie używana w Lambda)
    """
    # Symulacja event i context dla testów lokalnych
    event = {}
    context = {}

    # Ustaw zmienne środowiskowe dla testów lokalnych
    os.environ['RDS_ENDPOINT'] = 'horse-analyser-db.czwk8cqg2o63.eu-central-1.rds.amazonaws.com'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = 'twoje-haslo-z-secrets-manager'
    os.environ['DB_PORT'] = '5432'
    os.environ['NEXT_RACE_DAY'] = '17'  # Następny dzień do scrapowania

    result = lambda_handler(event, context)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
