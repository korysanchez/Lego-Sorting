
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
import requests
import notion
import time
import sys
import os
import re



BASE_URL = "https://brickarchitect.com/parts/"

notion_flag = False
retired_flag = False

# Remember some pages will have sub-links in their main category. 
# Thus, check all paths. Might be able to fix in future. i.e.
# Minifigure:
#     Index:
#         Minidolls (skipped)
#         ...
#     Minidoll/Minidoll legs (not skipped, seperate category link)

visited_urls = set() #Global checks
visited_urls.add("https://brickarchitect.com/parts/category-89") #ignore duplo
visited_urls.add("https://brickarchitect.com/parts/category-13") #ignore electronics

# Vehicles
visited_urls.add("https://brickarchitect.com/parts/category-135") #ignore trains
visited_urls.add("https://brickarchitect.com/parts/category-136") #ignore coaster
visited_urls.add("https://brickarchitect.com/parts/category-137") #ignore stuntz
visited_urls.add("https://brickarchitect.com/parts/category-188") #ignore webz

#minidolls
visited_urls.add("https://brickarchitect.com/parts/category-111") #ignore minidoll
visited_urls.add("https://brickarchitect.com/parts/category-114")   #ignore minidoll
visited_urls.add("https://brickarchitect.com/parts/category-115")   #ignore minidoll
visited_urls.add("https://brickarchitect.com/parts/category-117")   #ignore minidoll








skip_url_nums = ['1', '2', '3', '7', '8', '106', '4', '10', '11', '9', '12', '131']
for url_num in skip_url_nums:
    visited_urls.add(f"https://brickarchitect.com/parts/category-{url_num}")


current_parent_id = ''


def traverse_category(category_url, current_path=None, category_hierarchy=None, depth=0):
    global current_parent_id
    if current_path is None:
        current_path = set()  # Track visited URLs within this traversal
    if category_hierarchy is None:
        category_hierarchy = []  # Track the category path

    if category_url in visited_urls:
        print(f"{'  ' * depth}Skipping {category_url} (visited)")
        return

    visited_urls.add(category_url)
    try:
        response = requests.get(category_url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"{'  ' * depth}Error fetching {category_url}: {e}")
        return


    soup = BeautifulSoup(response.text, 'html.parser')
    category_name = get_category_name_from_page(soup, True if depth <= 1 else False)

    # Create a new hierarchy list for this branch to avoid affecting sibling paths
    old_hierarchy_len = len(category_hierarchy)
    new_hierarchy = category_hierarchy + [category_name]
    print(new_hierarchy)
    if (len(new_hierarchy) > old_hierarchy_len):
        old_category = new_hierarchy[old_hierarchy_len - 1]
        if (old_category != 'The LEGO Parts Guide'):
            current_parent_id = notion.add_category_to_notion(category_name, old_category, depth)
        elif (category_name != 'The LEGO Parts Guide'):
            current_parent_id = notion.add_category_to_notion(category_name, depth=depth)

    # Create the directory based on the new hierarchy
    category_folder = os.path.join('images', *new_hierarchy)
    print("CAT:::", category_folder)
    os.makedirs(category_folder, exist_ok=True)

    print(f"{'  ' * depth}📂 {category_folder}")

    
    # Collect subcategory links
    seen_links = set()
    subcategory_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/parts/category-' in href and '?' not in href:
            full_url = href if href.startswith('http') else BASE_URL + href.lstrip('/')
            if full_url not in seen_links:
                seen_links.add(full_url)
                subcategory_links.append(full_url)


    # If there is only one subcategory link and it has already been visited, scrape parts
    if all(link in visited_urls for link in subcategory_links):
        # Scrape parts from the current page instead of continuing to the subcategory
        scrape_parts_from_page(category_url, category_folder)
    elif subcategory_links:
        print(f"{'  ' * depth}Found subcategories, traversing deeper...")
        for href in subcategory_links:
            traverse_category(href, current_path, new_hierarchy, depth=depth + 1)
    else:
        print(f"{'  ' * depth}No subcategories found. Scraping parts...")
        scrape_parts_from_page(category_url, category_folder)










# Function to clean up the part URL by removing query parameters
def clean_part_url_query_params(part_url):
    parsed_url = urlparse(part_url)
    return urlunparse(parsed_url._replace(query=''))

# Scrape all part links from a category page
def scrape_parts_from_page(category_url, category_folder):
    if (retired_flag):
        category_url += '?&retired=1'
    try:
        response = requests.get(category_url)
        response.raise_for_status()
    except requests.RequestException as e:
        print("Error fetching {category_url}: {e}")
        return
    soup = BeautifulSoup(response.text, 'html.parser')

    part_links = [
        a['href'] for a in soup.find_all('a', href=True)
        if '/parts/' in a['href'] and '?&partstyle' not in a['href'] and 'category-' not in a['href']
    ]
    

    for part_url in part_links:
        full_url = part_url if part_url.startswith('http') else BASE_URL + part_url.lstrip('/')
        clean_part_url = clean_part_url_query_params(full_url)
        scrape_part(clean_part_url, category_folder)
        #sleep between scraping to avoid sending too many requests
        #time.sleep(1.0) 






# Extract and clean category name
def get_category_name_from_page(soup, do_split):
    title_tag = soup.find('h1')
    category_name = title_tag.get_text(strip=True) if title_tag else 'Unknown_Category'
    category_name = re.sub(r'\(.*?\)', '', category_name).strip()  # Remove parentheses and content within i.e. (Part 3005)
    category_name = re.sub(r'[^a-zA-Z0-9.&½⅓⅔¼⅖ºØ× _-]', '_', category_name)

    # change "10. Vehicle" to "a. Vehicle"
    do_split = True
    if do_split:
        if (category_name.count('.')):
            split = category_name.split('.')
            if (int(split[0]) == 13):
                split[0] = hex(int(split[0])-1)[2:]
            else:
                split[0] = hex(int(split[0]))[2:]
            category_name = (split[0] + '.' + split[1])
    return category_name

def scrape_category(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        return
    soup = BeautifulSoup(response.text, 'html.parser')

    category = "./images/The LEGO Parts Guide/"
    backlinks = [
        a['href'] for a in soup.find_all('a', href=True)
        if '/parts/category-'  in a['href']
    ]
    for link in backlinks:
        try:
            response2 = requests.get(link)
            response2.raise_for_status()
        except requests.RequestException as e:
            return
        soup2 = BeautifulSoup(response2.text, 'html.parser')
        category += get_category_name_from_page(soup2, False)
        category += "/"
    return category




# Function to scrape title and image from a part page
def scrape_part(part_url, category_folder):
    try:
        response = requests.get(part_url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching part page {part_url}: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    title = soup.find('h1')
    title_text = title.get_text(strip=True) if title else 'No title found'

    # Construct the image URL by appending the part number to the correct image path
    part_number = part_url.split('/')[-1]  # Extract part number from URL
    image_url = f"https://brickarchitect.com/content/parts/{part_number}.png"

    download_image(image_url, title_text, category_folder)




def sanitize_filename(filename):
    name, ext = os.path.splitext(filename)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[^a-zA-Z0-9.½⅓⅔¼⅖ºØ× _-]', '_', name)
    return name + ext



def download_image(image_url, title, category_folder):
    try:
        # Extract the part number (after 'Part_') and clean the title
        part_number = re.search(r'\(Part ([A-Za-z0-9]+)\)', title)
        if part_number:
            part_number = part_number.group(1)
        else:
            print(f"Part number not found in {title}")
            return

        formatted_title = re.sub(r'Part \d+', '', title)  # Remove "Part number"

        #formatted_title = formatted_title.replace('.', '_')  # Replace periods with underscores
        formatted_title = formatted_title.replace(' ', '_')  # Replace spaces with underscores
        formatted_title = formatted_title.replace('__', '_')  # Fix double underscores
        formatted_title = re.sub(r'[^A-Za-z0-9._×½⅓⅔¼⅖ºØ-]', '', formatted_title)
        filename = f"{formatted_title}-{part_number}.png"

        sanitized_filename = sanitize_filename(filename)
        image_path = os.path.join(category_folder, sanitized_filename)

        response = requests.get(image_url)
        response.raise_for_status()
        
        with open(image_path, 'wb') as f:
            f.write(response.content)
        if notion_flag:
            notion.add_image_to_notion(current_parent_id, image_path)
    except requests.RequestException as e:
        print(f"Error downloading image {image_url}: {e}")
        







def main():
    print(f"Starting traversal from {BASE_URL}")
    traverse_category(BASE_URL)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 lego.py [-r] [-n] [-p \"link\"]")
        print("    [-r]: Do you track retired pieces")
        print("    [-n]: Whether or not to also upload to notion")
        print("[-p ...]: Only grab one specific parts link")
    if '-n' in sys.argv:
        notion_flag = True
    if '-r' in sys.argv:
        retired_flag = True
    if '-p' in sys.argv:
        p_index = sys.argv.index('-p')
        if len(sys.argv) <= p_index + 1:
            print("Usage: python3 lego.py [-r] [-n] [-p \"link\"]")
            sys.exit(0)
        part_link = sys.argv[len(sys.argv) - 1]
        if not part_link.startswith('http'):
            part_link = "https://brickarchitect.com/parts/" + part_link
        scrape_part(part_link, scrape_category(part_link))
        sys.exit(0)
    main()