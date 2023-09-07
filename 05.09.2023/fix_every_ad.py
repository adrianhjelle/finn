from bs4 import BeautifulSoup
import requests
import json
import copy


def find_similar_cars(new_car, data, make, model):
    similar_cars_sold = []  
    similar_cars_unsold = []  
    
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
            car.get('Year', 0) <= new_car.get('Year', 0) 
            and car.get('KM', 0) >= new_car.get('KM', 0)
            and (car.get('Price') is not None and new_car.get('Price') is not None and car.get('Price', 0) >= new_car.get('Price', 0))
            and car.get('Transmission', '') == new_car.get('Transmission', '')
            and car.get('Electric', False) == new_car.get('Electric', False)
            and car.get('Reg_nr', False) != new_car.get('Reg_nr', False)
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
    avg_price_sold = round(sum(car['Price'] for car in sold_cars) / num_sold) if num_sold > 0 else 0

    # Compute statistics for unsold cars
    num_unsold = len(unsold_cars)
    avg_price_unsold = round(sum(car['Price'] for car in unsold_cars) / num_unsold) if num_unsold > 0 else 0

    # Compute the ratio of sold to unsold cars
    ratio = num_sold / (num_sold + num_unsold) if (num_sold + num_unsold) > 0 else 0
    rounded_ratio = round(ratio * 10) / 10  # Rounding to the nearest tenth

    stats = {
        'Number of Sold Cars': num_sold,
        'Number of Unsold Cars': num_unsold,
        'Sold to Unsold Ratio': rounded_ratio,
        'Average Price (Sold Cars)': avg_price_sold,
        'Average Price (Unsold Cars)': avg_price_unsold
    }

    return stats

def get_page(url):
    try:
        r = requests.get(url)
        r.raise_for_status()
        return r.text
    except requests.exceptions.HTTPError as err:
        if err.response.status_code in [410, 404]:
            print(f"The URL {url} is no longer available (HTTP {err.response.status_code}).")
            return None
        else:
            raise



def update_ads():
    # Load your data (adjust the file path as necessary)
    try:
        with open('test.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("JSON file not found!")
        exit()

    # Iterate over all cars and fetch missing descriptions
    for make, models in data.items():
        print(f"Processing make: {make}")  # Print the make it is currently processing
        for model, cars in models.items():
            print(f"  Processing model: {model}")  # Print the model it is currently processing
            for car in cars:
                print(f"Processing car with reg nr: {car.get('Reg_nr')}")  # Print the reg nr of the car it is currently processing
                # If the 'Description' field is missing or empty, fetch it
                if not car.get('Description'):
                    url = car.get('URL')
                    reg_nr = car.get('Reg_nr')

                    if url:
                        page_content = get_page(url)
                        if page_content is None:
                            print(f"Skipping car with reg nr: {reg_nr} (URL returned 410)")
                            continue
                        
                        if page_content:
                            soup = BeautifulSoup(page_content, 'html.parser')
                            
                            # Get the description
                            description_h2 = soup.find('h2', class_='u-t3', string='Beskrivelse')
                            description_p = description_h2.find_next_sibling('p') if description_h2 else None
                            full_description_text = description_p.text if description_p else ''
                            
                            # Cut the description if it's too long
                            max_length = 700
                            if len(full_description_text) > max_length:
                                description = full_description_text[:max_length] + '...'
                            else:
                                description = full_description_text

                            transmission = soup.find_all('div', class_='u-strong')[2].text.strip()

                            electric = False
                            if reg_nr and reg_nr.startswith(('EL', 'EK', 'EV', 'EB', 'EC', 'ED', 'EE', 'EF', 'EH')):
                                electric = True

                            # Update the car data with the new description
                            car['Description'] = description
                            car['Transmission'] = transmission
                            car['Electric'] = electric

        # Save the partially updated data
        with open('test.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)



    # Create a deep copy of your original data
    data_copy = copy.deepcopy(data)

    # First loop: Find similar cars for each car in your dataset
    for make, models in data_copy.items():
        for model, cars in models.items():
            for car in cars:
                similar_cars_info = find_similar_cars(car, data, make, model)
                car['Similar cars'] = similar_cars_info

    # Second loop: Update the 'Similar cars' field with statistics for each car in your dataset
    for make, models in data_copy.items():
        for model, cars in models.items():
            for car in cars:
                similar_cars_info = car.get('Similar cars', {})

                # Update the 'Similar cars' field with statistics
                if similar_cars_info:
                    stats = analyze_similar_cars(similar_cars_info)
                    similar_cars_info.update(stats)

                    # Handle the full lists and extract necessary lists for further use
                    similar_cars_info.pop('Full Sold List', None)
                    similar_cars_info.pop('Full Unsold List', None)
                    
                    sold_list = similar_cars_info.pop('Sold', [])
                    unsold_list = similar_cars_info.pop('Unsold', [])
                    
                    # Re-add the 'Sold' and 'Unsold' lists under certain conditions
                    if similar_cars_info.get('Number of Sold Cars', 0) > 1:
                        similar_cars_info['Sold'] = sold_list
                        similar_cars_info['Unsold'] = unsold_list

        # Save the updated data back to the file
        try:
            with open('test.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error while saving JSON file: {e}")


update_ads()