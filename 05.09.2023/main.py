from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium import webdriver
import time
import requests
from bs4 import BeautifulSoup
import datetime
import schedule
import openpyxl
from openpyxl.styles import PatternFill
from is_it_sold import check_sold_ads
import re
import traceback
import json


def move_to_good_cars():
    # Load the data from data.json
    with open("data.json", 'r') as file:
        data = json.load(file)

    # Filter data to keep only the cars with "Sold to Unsold Ratio" greater than 1
    good_cars_data = {}

    for brand, models in data.items():
        for model, details in models.items():
            cars_with_good_ratio = [car for car in details if "Similar cars" in car and car["Similar cars"]["Sold to Unsold Ratio"] > 1]
            if cars_with_good_ratio:
                if brand not in good_cars_data:
                    good_cars_data[brand] = {}
                good_cars_data[brand][model] = cars_with_good_ratio

    # Saving the good_cars_data to a JSON file
    with open("good_cars.json", "w") as file:
        json.dump(good_cars_data, file, indent=4)


def get_ads(url):
    for _ in range(2):  # Try up to 2 times
        options = Options()
        options.add_argument("--headless")  # Run Chrome in headless mode (without GUI)

        # Automatically download and set up ChromeDriver
        driver = webdriver.Chrome(options=options)

        # Set the timeout
        driver.set_page_load_timeout(10)

        try:
            driver.get(url)
            time.sleep(2)

            page_source = driver.page_source

            # Parse the HTML content of the page with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')

            # Find all ads - now looking for 'a' elements with class 'sf-search-ad-link link link--dark hover:no-underline'
            ads = soup.find_all('a', class_='sf-search-ad-link link link--dark hover:no-underline')

            # Prepare a list to hold the results
            results = []

            # Iterate over the first 6 ads found
            for ad in ads[:6]:
                # If a hyperlink was found in the ad, append it to the results
                if ad and ad.has_attr('href'):
                    results.append(ad['href'])

            # Return the results
            driver.quit()
            return results

        except TimeoutException:
            print("Page took too long to load. Quitting.")
            driver.quit()


def get_ad_info(url):
    for _ in range(2):  # Try up to 2 times
        try:
            r = requests.get(url)
            r.raise_for_status()

            soup = BeautifulSoup(r.text, 'html.parser')

            title = soup.find('h1', class_='u-t2 u-word-break').text
            title_words = title.split(' ')
            make = title_words[0]
            model = ' '.join(title_words[1:])  # Join the rest of the words back into a single string

            year = int(soup.find('div', class_='u-strong').text)

            km = int(soup.find_all('div', class_='u-strong')[1].text.replace('\xa0', '').replace(' km', ''))
            km = round(km/10000) * 10000
            # If km is a 7-digit number, remove the last 0
            if 1000000 <= km < 10000000:
                km = km // 10

            # Find the dd element that follows dt with 'Reg.nr.'
            reg_nr = None
            for dt in soup.find_all('dt'):
                if dt.text.strip() == 'Reg.nr.':
                    reg_nr = dt.find_next_sibling('dd').text
                    break

            date_posted = datetime.date.today().strftime('%d.%m.%Y')

            # Find the dd element that follows dt with 'Pris eks omreg'
            price = None
            for dt in soup.find_all('dt'):
                if dt.text.strip() == 'Pris eks omreg':
                    price = int(dt.find_next_sibling('dd').text.replace('\xa0', '').replace(' kr', ''))
                    # Round price to the nearest 1000
                    price = round(price / 1000) * 1000
                    break

            # Get the description
            description_h2 = soup.find('h2', class_='u-t3', string='Beskrivelse')
            description_p = description_h2.find_next_sibling('p') if description_h2 else None
            description_text = description_p.text if description_p else ''

            # Convert the description and search words to lowercase for case-insensitive search
            description = description_text
            description_lower = description_text.lower()
            words_delebil = ["delebil", "rep objekt", "rep. objekt", "repobjekt", "reperasjonsobjekt", "reparasjons objekt", "dele bil", "ikke eu", "mangler eu",
                     "ikke godkjent", "motorhavari", "feil med motor", "defekt motor", "bilen er ikke kjørbar"]

            # Initialize the description rating to None
            rating = None

            # Check if any of the words exist in the description
            for word in words_delebil:
                if word in description_lower:
                    rating = "Delebil"
                    break

            span = soup.find('span', class_='u-mh16', string=re.compile(r'^\d{4}\s'))
            if span:
                postal_code = span.text.split()[0]
            else:
                postal_code = None

            days_until_sold = None

            # Determine place based on the first digit of postal_code
            if postal_code:
                first_digit = postal_code[0]
                if first_digit == '0':
                    place = "Oslo"
                elif first_digit == '1':
                    place = "Ostfold"
                elif first_digit == '2':
                    place = "Oppland"
                elif first_digit == '3':
                    place = "Vestfold"
                elif first_digit == '4':
                    place = "Sornorge"
                elif first_digit == '5':
                    place = "Hordaland"
                elif first_digit == '6':
                    place = "Sogn og Fjordane"
                elif first_digit == '7':
                    place = "Tronderlag"
                elif first_digit == '8':
                    place = "Nordalnd"
                elif first_digit == '9':
                    place = "Til helvete"
                else:
                    place = "Unknown"
            else:
                place = "Unknown"

            return {
                'Make': make,
                'Model': model,
                'Reg_nr': reg_nr,
                'Price': price,
                'Rating': rating,
                'Year': year,
                'KM': km,
                'Place': place,
                'Date_posted': date_posted,
                'URL': url,
                'Description': description,
                'Days until sold': days_until_sold
            }

        except (requests.RequestException, ValueError):
            print(f"Failed to fetch {url}, retrying in 5 seconds...")
            time.sleep(5)  # Wait for 5 seconds before trying again


def find_similar_cars(new_car, data):
    similar_cars_sold = []  
    similar_cars_unsold = []  
    
    make = new_car['Make']
    model = new_car['Model']
    
    # Check if the make exists in data
    if make not in data:
        print(f"Make {make} not found in data.")
        return {
            "Sold": similar_cars_sold,
            "Unsold": similar_cars_unsold,
        }
    
    # Check if the model exists under the make
    if model not in data[make]:
        print(f"Model {model} not found under make {make}.")
        return {
            "Sold": similar_cars_sold,
            "Unsold": similar_cars_unsold,
        }

    # Now, retrieve the list of cars of that specific model
    cars_in_model = data[make][model]

    for car in cars_in_model:
        # Criteria to find a similar car
        if (
            car['Year'] <= new_car['Year']
            and car['KM'] >= new_car['KM']
            and (car['Price'] is not None and new_car['Price'] is not None and car['Price'] >= new_car['Price'])

        ):
            # Remove unnecessary keys
            car = car.copy()  # Work on a copy to avoid modifying the original car data
            for key in ['Year', 'KM', 'Date_posted', 'Place', 'Similar cars', 'Make', 'Model', 'Rating']:
                car.pop(key, None)

            days_until_sold = car.get("Days until sold")
            if days_until_sold == 0:
                print(f"Appending car {car['Reg_nr']} to 'Sold'.")
                similar_cars_sold.append(car)
            else: 
                similar_cars_unsold.append(car)

    # Limit the number of cars to 5 for display
    displayed_similar_cars_sold = similar_cars_sold[:3]
    displayed_similar_cars_unsold = similar_cars_unsold[:3]

    return {
        "Sold": displayed_similar_cars_sold,
        "Unsold": displayed_similar_cars_unsold,
        "Full Sold List": similar_cars_sold,
        "Full Unsold List": similar_cars_unsold
    }


def analyze_similar_cars(similar_cars):
    sold_cars = similar_cars['Full Sold List']
    unsold_cars = similar_cars['Full Unsold List']

    # Compute statistics for sold cars
    num_sold = len(sold_cars)
    avg_price_sold = sum(car['Price'] for car in sold_cars) / num_sold if num_sold > 0 else 0

    # Compute statistics for unsold cars
    num_unsold = len(unsold_cars)
    avg_price_unsold = sum(car['Price'] for car in unsold_cars) / num_unsold if num_unsold > 0 else 0

    # Compute the ratio of sold to unsold cars
    ratio = num_sold / (num_sold + num_unsold) if (num_sold + num_unsold) > 0 else 0

    stats = {
        'Number of Sold Cars': num_sold,
        'Number of Unsold Cars': num_unsold,
        'Sold to Unsold Ratio': ratio,
        'Average Price (Sold Cars)': avg_price_sold,
        'Average Price (Unsold Cars)': avg_price_unsold
    }

    return stats


def add_car_to_data(new_car, data):
    # Ensure the make exists in the data
    if new_car['Make'] not in data:
        data[new_car['Make']] = {}
    
    # Ensure the model exists under the make
    if new_car['Model'] not in data[new_car['Make']]:
        data[new_car['Make']][new_car['Model']] = []

    # Check if the car with the same Reg_nr already exists
    existing_cars = [car for car in data[new_car['Make']][new_car['Model']] if car['Reg_nr'] == new_car['Reg_nr']]
    if existing_cars:
        # If the car already exists, we won't add it again
        return

    # If the car does not exist, find similar cars within the same model
    new_car['Similar cars'] = find_similar_cars(new_car, data)

    # Update the 'Similar cars' with statistics
    stats = analyze_similar_cars(new_car['Similar cars'])
    new_car['Similar cars'].update(stats)

    # Remove the full lists now that we've computed the statistics
    new_car['Similar cars'].pop('Full Sold List', None)
    new_car['Similar cars'].pop('Full Unsold List', None)

    # Get the "Sold" and "Unsold" lists and pop them from the dictionary
    sold_list = new_car['Similar cars'].pop('Sold', [])
    unsold_list = new_car['Similar cars'].pop('Unsold', [])

    # Now, re-add the "Sold" and "Unsold" lists at the end
    new_car['Similar cars']['Sold'] = sold_list
    new_car['Similar cars']['Unsold'] = unsold_list

    # Append the new car to the list of cars under its make and model
    data[new_car['Make']][new_car['Model']].append(new_car)
    print("Legges inn i filen \n")


def main():
    url = 'https://www.finn.no/car/used/search.html?d' \
          'ealer_segment=3&price_to=200000&published=1&sales_form=1&sort' \
          '=PUBLISHED_DESC&stored-id=60509806&year_from=1990'

    ads = get_ads(url)
    print("\n", ads)
    current_time = datetime.datetime.now()
    print("Current time:", current_time)

    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    if ads is not None:
        for ad in ads:
            ad_info = get_ad_info(ad)
            if ad_info is None:
                print(f"Failed to get info for ad: {ad}")
                continue

            print(f"Make: {ad_info.get('Make')} {ad_info.get('Model')}"
                f"\nLink: {ad_info.get('URL')}")

            add_car_to_data(ad_info, data)

    else:
        print("No ads to process.")

    try:
        with open('data.json', 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error while saving JSON file: {e}")


main()

schedule.every().day.at("23:10").do(check_sold_ads)
schedule.every(100).seconds.do(main)

while True:
    try:
        schedule.run_pending()
        time.sleep(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
        time.sleep(60)
