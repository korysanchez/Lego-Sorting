import requests
import sys
import os
import re
from collections import defaultdict


 
keys = []
with open("./keys", "r") as file:
    keys = [file.readline().strip() for _ in range(3)]
NOTION_API_KEY = keys[0]
DATABASE_ID = keys[1]
REBRICKABLE_API_KEY = keys[2]

NOTION_URL = 'https://api.notion.com/v1/databases/' + DATABASE_ID + '/query'

notion_headers = {
    'Authorization': f'Bearer {NOTION_API_KEY}',
    'Content-Type': 'application/json',
    'Notion-Version': '2022-06-28'  # Replace with the appropriate version if needed
}

# --- Rebrickable API Functions ---

def get_set_details(set_number):
    """Fetch LEGO set details from Rebrickable."""
    url = f"https://rebrickable.com/api/v3/lego/sets/{set_number}/"
    headers = {'Authorization': f'key {REBRICKABLE_API_KEY}'}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        return f"{data['name']} ({data['set_num']})"
    else:
        return None

def fetch_lego_pieces(set_number):
    """Fetch all LEGO parts from Rebrickable and return a dictionary of part numbers to part names."""
    print("Fetching LEGO parts from Rebrickable...")
    url = f"https://rebrickable.com/api/v3/lego/sets/{set_number}/parts/"
    headers = {'Authorization': f'key {REBRICKABLE_API_KEY}'}
    parts_dict = {}
    page = 1
    page_size = 1000

    while True:
        response = requests.get(url, headers=headers, params={'page': page, 'page_size': page_size})

        if response.status_code == 200:
            data = response.json()
            for item in data['results']:
                part_num = re.sub(r'\D', '', str(item['part']['part_num']))
                part_name = item['part']['name']
                parts_dict[part_num] = part_name

            if data['next']:
                page += 1
            else:
                break
        else:
            print(f"Failed to fetch parts for set {set_number}. Status code: {response.status_code}")
            break
    print(f"Fetched {len(parts_dict)} parts from Rebrickable.")
    return parts_dict






# --- Notion API Functions ---

def get_notion_entries(parts_dict):
    """Fetch Notion entries that match any of the part numbers in the given dictionary, handling batch limits."""
    part_numbers = list(parts_dict.keys())
    matched_entries = []
    notion_part_numbers = []
    batch_size = 100

    # Process part numbers in batches of 100 or fewer
    for i in range(0, len(part_numbers), batch_size):
        batch = part_numbers[i:i + batch_size]

        filters = {
            "or": [
                {
                    "property": "Part Number",
                    "multi_select": {
                        "contains": part_num
                    }
                }
                for part_num in batch
            ]
        }

        payload = {"filter": filters}

        response = requests.post(NOTION_URL, headers=notion_headers, json=payload)

        if response.status_code == 200:
            data = response.json()
            matched_entries_batch = data.get("results", [])
            #matched_entries.extend(data.get("results", []))


            # Extract part numbers from matched entries
            for entry in matched_entries_batch:
                #part_number = entry["properties"].get("Part Number", {}).get("select", {}).get("name")
                part_number = entry["properties"].get("Part Number", {})
                if "multi_select" in part_number and part_number["multi_select"]:
                    for item in part_number["multi_select"]:
                        part_name = item.get("name")
                        if part_name:
                            notion_part_numbers.append(part_name)
            matched_entries.extend(matched_entries_batch)

        else:
            print(f"Failed to fetch entries for batch {i // batch_size + 1}. Status code: {response.status_code}")
            print(response.text)


    print("\n\nPieces not present in Notion:")
    for part_number, part_info in parts_dict.items():
        if part_number not in notion_part_numbers:
            print(f"- {part_number:<9}: {part_info}")


    return matched_entries

        
def get_matching_notion_pages(parts_dict):
    print("Fetching matching entries from Notion...")
    notion_pages = get_notion_entries(parts_dict)
    print(f"Fetched {len(notion_pages)} matching entries from Notion.")
    return notion_pages
















def collect_and_print_found_in_entries(notion_pages):
    """Collect and print 'Box' and 'Container' entries from notion_pages."""
    found_in_dict = defaultdict(lambda: defaultdict(set))  # Initialize the found_in_dict

    for page in notion_pages:
        properties = page.get("properties", {})
        
        # Get the first 'Box' and 'Container' (multi-select)
        box = properties.get("Box", {}).get("multi_select", [])
        container = properties.get("Container", {}).get("multi_select", [])
        
        # Get the 'Found In' value (part name)
        found_in = properties.get("Found In", {}).get("formula", {}).get("string", "")
        part_name = properties.get("Piece", {}).get("title", [{}])[0].get("text", {}).get("content", "")
        
        if not found_in or not part_name:
            continue  # Skip pages without a 'Found In' or 'Piece' entry
        
        # Only process the first box and container for each page
        if box and container:
            b = box[0]  # Take the first Box
            for c in container:
                found_in_dict[b['name']][c['name']].add(part_name)  # Store parts in a set to avoid duplicates

    return found_in_dict






def mark_needed(page_ids):
    """Update the 'Needed' checkbox to True for the given page in Notion."""
    print("Marking pages in Notion")
    print("0-5-10-15-20-25-30-35-40-45-50-55-60-65-70-75-80-85-90-95-100%")
    print("+", end='', flush=True)
    total = len(page_ids)
    tens = 0
    for i, page_id in enumerate(page_ids):
        if (float(i / total) >= float(tens / 100)):
            tens += 5
            print(f"-{"+" if tens == 5 else "-+"}", end='', flush=True)
        try:
            notion_url = f"https://api.notion.com/v1/pages/{page_id}"
            data = {
                "properties": {
                    "Needed": {
                        "checkbox": True
                    }
                }
            }
            response = requests.patch(notion_url, headers=notion_headers, json=data)

            if response.status_code == 200:
                pass
            else:
                print("Failed")
        except:
            print("Failed")
    print("\nPages marked as needed in notion")

def group_containers_as_ranges(lst):
    ranges = []
    
    # Iterate through the dictionary items (key, value)
    for name, group in lst.items():  # Use .items() to get key-value pairs
        # If the group has only one item, just append it
        if len(group) == 1:
            ranges.append(group[0])
        else:
            # If there are multiple items, append the first and last items as a range
            ranges.append(f"{group[0]}-{group[-1]}")

    return ', '.join(ranges)

def convert_to_range_format(parts_in_containers):
    # Create a new defaultdict to store the transformed data
    converted_dict = defaultdict(list)
    
    # Iterate through the original dictionary
    for part_name, containers in parts_in_containers.items():
        # Sort the containers
        containers_sorted = sorted(containers, key=lambda x: (int(x) if x.isdigit() else float('inf'), x))
        
        # Create a range string
        ranges = []
        start = containers_sorted[0]
        for i in range(1, len(containers_sorted)):
            if (containers_sorted[i].isdigit() and containers_sorted[i-1].isdigit() and int(containers_sorted[i]) != int(containers_sorted[i-1]) + 1) or \
               (containers_sorted[i].isalpha() and containers_sorted[i-1].isalpha() and ord(containers_sorted[i]) != ord(containers_sorted[i-1]) + 1):
                # When a break is found, add the range
                if start == containers_sorted[i-1]:
                    ranges.append(start)
                else:
                    ranges.append(f"{start}-{containers_sorted[i-1]}")
                start = containers_sorted[i]
        
        # Add the last range
        if start == containers_sorted[-1]:
            ranges.append(start)
        else:
            ranges.append(f"{start}-{containers_sorted[-1]}")
        
        # Store the result in the new dictionary
        converted_dict[part_name] = ranges
    
    return converted_dict

def print_formatted_entries(found_in_dict):
    # Print the formatted entries
    total_containers = 0
    for box in sorted(found_in_dict.keys()):
        all_containers = sorted(found_in_dict[box].keys(), key=lambda x: (int(x) if x.isdigit() else float('inf'), x))  # Sort numerically, then alphabetically
        total_containers += len(all_containers)
        # For each part, group containers together and print them in ascending order
        parts_in_containers = defaultdict(list)
        for container in all_containers:
            for piece_name in found_in_dict[box][container]:
                parts_in_containers[piece_name].append(container)
                
        parts_in_containers = convert_to_range_format(parts_in_containers)


        temp_list = []
        parts = ''
        for _, containers_in in parts_in_containers.items():
            if containers_in not in temp_list:
                temp_list.append(containers_in)
                parts += ', ' + containers_in[0] if parts != '' else containers_in[0]
            
        print(f"\n\n- {box} ({parts}):\n")

        container_groups = defaultdict(list)

        # Group parts by container
        for part_name, containers_for_part in parts_in_containers.items():
            for container in containers_for_part:
                container_groups[container].append(part_name)

        # Print the grouped result, sorted by container
        for container, part_names in sorted(container_groups.items(), key=lambda x: (int(x[0]) if x[0].isdigit() else float('inf'), x[0])):
            print(f"   {container}:")
            for part_name in part_names:
                print(f"       {part_name}")
                
        
        
        
    print("Total containers:", total_containers)












# --- Main Execution ---
if __name__ == "__main__":

    mark_in_notion = False
    # Check for flag in the arguments
    if '-m' in sys.argv:
        mark_in_notion = True
        sys.argv.remove('-m')  # Remove the flag from sys.argv


    if len(sys.argv) < 2:
        print("Usage: python3 find.py [-m] set_number")
        print(" [-m]: Mark pieces in Notion as needed")
        sys.exit(0)

    set_number = sys.argv[1]
    if '-' not in set_number:
        set_number += '-1'
    set_details = get_set_details(set_number)

    if set_details:
        confirm = input(f"Is this the set you want? '{set_details}' [Y/N]: ").strip().lower()
        if confirm == 'y':
            parts_dict = fetch_lego_pieces(set_number)
            notion_pages = get_matching_notion_pages(parts_dict)
            notion_page_ids = [page.get("id") for page in notion_pages if page.get("id")]

            

            if parts_dict:
                found_in_dict = collect_and_print_found_in_entries(notion_pages)
                if found_in_dict:
                    print_formatted_entries(found_in_dict)
                    if mark_in_notion:
                        mark_needed(notion_page_ids)
                    
                else:
                    print("No matching 'Found In' entries found in the Notion database.")
            else:
                print("No pieces were retrieved.")
        else:
            print("Set selection canceled.")
    else:
        print("Set not found. Please check the set number and try again.")