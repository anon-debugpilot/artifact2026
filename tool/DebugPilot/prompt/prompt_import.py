import json
import os

def load_template_from_txt(group_name):
    txt_file = f"{group_name}_template.txt"
    if not os.path.exists(txt_file):
        raise FileNotFoundError(f"Template file {txt_file} not found")
    
    with open(txt_file, 'r', encoding='utf-8') as f:
        return f.read().strip()

def update_json_with_templates(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for group_name in data['prompt_groups']:
        try:
            template_content = load_template_from_txt(group_name)
            data['prompt_groups'][group_name]['template'] = template_content
            print(f"Successfully updated template for {group_name}")
        except FileNotFoundError as e:
            print(f"Warning: {e}. Skipping {group_name}")
        except Exception as e:
            print(f"Error processing {group_name}: {str(e)}")
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("JSON file updated successfully")

if __name__ == "__main__":
    json_filename = "prompts.json"
    
    if not os.path.exists(json_filename):
        print(f"Error: JSON file {json_filename} not found")
    else:
        update_json_with_templates(json_filename)