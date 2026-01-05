import argparse
import csv
import json
import sys

def convert_packages_csv(csv_path, output_path):
    data_list = []
    
    try:
        # Open with utf-8-sig to handle potential BOM
        with open(csv_path, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                # Construct the data object
                # Using .strip() to clean up whitespace
                package_data = {
                    "template_id": row.get('template_id', '').strip(),
                    "field": row.get('field', '').strip()
                }
                
                # Wrap in the action object
                action_obj = {
                    "action": "create",
                    "data": package_data
                }
                
                data_list.append(action_obj)
        
        # Create final structure with root key "templatefields"
        final_json = {"templatefields": data_list}
        
        # Write to output file
        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(final_json, jsonfile, indent=4, ensure_ascii=False)
            
        print(f"Successfully converted '{csv_path}' to '{output_path}'.")
        print(f"Total package links created: {len(data_list)}")

    except FileNotFoundError:
        print(f"Error: The file '{csv_path}' was not found.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Packages CSV to LIMS JSON format.")
    parser.add_argument('--csv', required=True, help="Path to the input CSV file")
    parser.add_argument('--out', required=True, help="Path to the output JSON file")
    
    args = parser.parse_args()
    
    convert_packages_csv(args.csv, args.out)