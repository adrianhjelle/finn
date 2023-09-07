import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import validators
import json


def get_page(url):
    try:
        r = requests.get(url)
        r.raise_for_status()
        return r.text
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 410:
            print(f"The URL {url} is no longer available.")
            return "Fjernet"
        else:
            raise


def check_sold_ads():
    # Load the data from JSON
    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("JSON file not found!")
        return

    current_date = datetime.now()
    current_date = current_date.date()

    for make, models in data.items():
        for model, car_ads in models.items():
            for car in car_ads:
                date_posted = car.get('Date_posted')
                if date_posted:
                    try:
                        date_posted = datetime.strptime(date_posted, '%d.%m.%Y').date()
                        date_diff = (current_date - date_posted).days

                        """ if date_posted != current_date:
                            date_diff -= 1 """

                        if date_diff > 6:
                            car["Days until sold"] = "x"

                    except ValueError:
                        print(f"Car with Reg_nr {car.get('Reg_nr')} has a date not in the 'dd.mm.yyyy' format.")
                        continue

                if car.get("Days until sold") is None:
                    url = car.get('URL')
                    if url is None or not validators.url(url):
                        continue

                    try:
                        page = get_page(url)

                        if page == "Fjernet":
                            car["Days until sold"] = date_diff
                            car["Date_sold"] = (datetime.now() - timedelta(days=date_diff)).strftime('%d.%m.%Y')
                            continue

                        if page is not None:
                            soup = BeautifulSoup(page, 'html.parser')
                            sold_status = soup.find('span', {'class': 'u-capitalize status status--warning u-mb0'})

                            if sold_status:
                                status_text = sold_status.text.strip().lower()

                                if status_text in ['solgt', 'inaktiv']:
                                    car["Days until sold"] = date_diff
                                    car["Date_sold"] = (datetime.now() - timedelta(days=date_diff)).strftime('%d.%m.%Y')

                    except Exception as e:
                        print(f"An error occurred while processing the URL {url}: {e}")

        print("Neste merke")

    # Save the modified data back to the JSON file
    try:
        with open('data.json', 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error while saving JSON file: {e}")

    print("Da var alle linkene sjekket!")


if __name__ == "__main__":
    check_sold_ads()