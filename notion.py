import os
import re
import shutil
import requests
import numpy as np
import send_dropbox
import cv2

# Read API keys
keys = []
with open("./keys", "r") as file:
    keys = [file.readline().strip() for _ in range(2)]
NOTION_API_KEY = keys[0]
DATABASE_ID = keys[1]

base_url = "https://api.notion.com/v1"
page_url = f"{base_url}/pages"

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2021-08-16"
}

added_to_notion = 0
failed_add = 0



def resize_and_pad_image(cropped_brick):
    h, w = cropped_brick.shape[:2]
    
    # Calculate target size to maintain 2.5:1 aspect ratio
    target_height = h
    target_width = int(target_height * 2.5)

    horizontal_padding_percent = 1.2
    vertical_padding_percent = 0.35

    padding_h = int(target_height * vertical_padding_percent)  
    padding_w = int(target_width * horizontal_padding_percent) 

    new_h = target_height + 2 * padding_h
    new_w = target_width + 2 * padding_w
    padded_image = np.zeros((new_h, new_w, 4), dtype=np.uint8) * 255  # White background (RGBA)

    y_offset = (new_h - h) // 2
    x_offset = (new_w - w) // 2

    padded_image[y_offset:y_offset + h, x_offset:x_offset + w] = cropped_brick

    return padded_image






def fetch_parent_id_by_name(page_name):
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "Piece",
            "title": {
                "equals": page_name
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            return results[0]['id']
        else:
            return None
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None



def already_exists(part_number):
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "Part Number",
            "multi_select": {
                "contains": part_number
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            return True
        else:
            return False
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None



def add_category_to_notion(category_name, parent_category=None, depth=0):
    if not fetch_parent_id_by_name(category_name):
        print(f'{'  ' * depth}Creating notion category {category_name}!')
        try:
            if not parent_category:
                payload = {
                    "parent": {"database_id": DATABASE_ID},
                    "properties": {
                        "Piece": {"title": [{"text": {"content": category_name}}]}

                    }
                }
            else:
                payload = {
                    "parent": {"database_id": DATABASE_ID},
                    "properties": {
                        "Piece": {"title": [{"text": {"content": category_name}}]},
                        "Category": {
                            "relation": [{"id": fetch_parent_id_by_name(parent_category)}]
                        }

                    }
                }
                
            response = requests.post(page_url, headers=headers, json=payload)

            if response.status_code == 200:
                page_id = response.json().get("id", None)
                if page_id:
                    print(f"{'  ' * depth}Category Created: {page_id}")
                    return page_id
                else:
                    return None
            else:
                print(f"Failed to add {category_name}. Status code: {response.status_code}")
                print(response.text)
            pass
        except:
            print(f"Failed to add {category_name}.")


def add_image_to_notion(parent_id, image_path):
    global added_to_notion, failed_add
    try:
        # Extract the filename and path parts
        filename = os.path.basename(image_path)
        path_parts = os.path.dirname(image_path).split(os.sep)
        
        if (image_path[0] != '.'):
            path_parts = path_parts[2:]
        else:
            path_parts = path_parts[3:]


        # Create the Tags property by joining the path parts with '-'
        if (parent_id) == 'null' or not parent_id:
            parent_id = fetch_parent_id_by_name(path_parts[len(path_parts) - 1])
        depth = len(path_parts) + 1

        # Split filename to get the name and part number (Expect format: <name>-<part_number>.png)
        try:
            parts = filename.split('-')

            if len(parts) < 2:
                failed_add += 1
                print(f"Failed to process {filename}: Filename format error (no hyphen found).")
                return

            name_part = " ".join(parts[:-1]).replace('_', ' ')
            part_number = parts[-1].split('.')[0]  # Extract the part number and remove the file extension
            

            print(f"{'  ' * depth}Part: {name_part}")
            

            processed_dir = "processed"
            os.makedirs(processed_dir, exist_ok=True)
            target_directory = os.path.join(processed_dir, *path_parts)

            # Create the directory structure if it doesn't exist
            if not os.path.exists(target_directory):
                os.makedirs(target_directory)  

            target_file_path = os.path.join(target_directory, filename)
            shutil.copy(image_path, target_file_path)
            # After copying, apply resize and padding
            image = cv2.imread(target_file_path, cv2.IMREAD_UNCHANGED)
            processed_image = resize_and_pad_image(image)
            # Save the processed image back to the target file path
            cv2.imwrite(target_file_path, processed_image)

            # Upload to Dropbox
            dropbox_path = f"{'/'.join(path_parts)}/{filename}"
            link = send_dropbox.upload_to_dropbox(target_file_path, dropbox_path, depth)

            print(f"{'  ' * depth}    Notion:")
            if already_exists(part_number):
                print(f"{'  ' * depth}        Piece already exists, not adding")
                return
            print(f"{'  ' * depth}        Parent: {parent_id}\n{'  ' * depth}        Piece: {name_part}\n{'  ' * depth}        Part Numbers: {part_number}")
            
            if link:
                link = link.replace("&dl=0", "&raw=1")
                payload = {
                    "parent": {"database_id": DATABASE_ID},
                    "properties": {
                        "Piece": {"title": [{"text": {"content": name_part}}]},
                        "Part Number": {"multi_select": [{"name": part_number}]},
                        "Image": {
                            "files": [
                                {
                                    "type": "external",
                                    "name": filename,
                                    "external": {
                                        "url": link
                                    }
                                }
                            ]
                        },
                        "Category": {
                            "relation": [{"id": parent_id}]
                        }

                    }
                }

                response = requests.post(page_url, headers=headers, json=payload)

                if response.status_code == 200:
                    added_to_notion += 1
                else:
                    failed_add += 1
                    print(f"Failed to add {filename}. Status code: {response.status_code}")
                    print(response.text)
                print(f"{'  ' * depth}    Added: {added_to_notion}, Failed: {failed_add}")
        except Exception as e:
            failed_add += 1
            print(f"Failed to process {filename}: {str(e)}")
    except Exception as e:
        failed_add += 1
        print(f"Unexpected error: {str(e)}")


def process_images_depth_first(base_dir):
    # Process directories in depth-first order
    for root, dirs, files in os.walk(base_dir, topdown=True):
        dirs.sort()
        # Process files in the current directory
        for entry in files:
            if entry.endswith(".png"):
                # Process image file
                add_image_to_notion(os.path.join(root, entry))


if __name__ == "__main__":
    images_dir = "images/The LEGO Parts Guide/"  # Base directory containing images
    process_images_depth_first(images_dir)
    print(f"Added: {added_to_notion}, Failed: {failed_add}")