import json
from datetime import datetime
from typing import Union

INPUT_JSON_FILE = 'user_details.json'
OUTPUT_JSON_FILE = 'standardized_user_details_fixed_dates.json'

def parse_date(date_string: Union[str, None]) -> str:
    if not date_string:
        return ''
    
    date_string = date_string.strip()
    
    # Handle "Joined" format
    if date_string.startswith('Joined'):
        date_string = date_string.replace('Joined', '').strip()
    
    # Try parsing various date formats
    date_formats = [
        "%B %Y",  # e.g., "November 2017"
        "%Y-%m-%d",  # e.g., "2017-11-01"
        "%Y-%m-%d %H:%M:%S",  # e.g., "2017-11-01 12:00:00"
    ]
    
    for date_format in date_formats:
        try:
            date_obj = datetime.strptime(date_string, date_format)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If all parsing attempts fail, return the original string
    print(f"Warning: Could not parse date '{date_string}'. Keeping original value.")
    return date_string

def fix_created_at_dates(data):
    for username, user_data in data.items():
        if 'data' in user_data and isinstance(user_data['data'], dict):
            created_at = user_data['data'].get('Created At')
            if created_at:
                user_data['data']['Created At'] = parse_date(created_at)
            
            # Also check for 'data_Created At' field
            data_created_at = user_data['data'].get('data_Created At')
            if data_created_at:
                user_data['data']['data_Created At'] = parse_date(data_created_at)
    
    return data

def main():
    try:
        with open(INPUT_JSON_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {INPUT_JSON_FILE} not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: {INPUT_JSON_FILE} is not a valid JSON file.")
        return

    fixed_data = fix_created_at_dates(data)

    with open(OUTPUT_JSON_FILE, 'w') as f:
        json.dump(fixed_data, f, indent=2)

    print(f"Fixed data has been written to {OUTPUT_JSON_FILE}")

if __name__ == "__main__":
    main()