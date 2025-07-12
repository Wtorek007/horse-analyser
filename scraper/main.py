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
