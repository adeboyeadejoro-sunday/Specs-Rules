import argparse
import csv
import json
import sys

def convert_csv_to_json(csv_path, output_path):
    data_list = []
    
    try:
        # Open with utf-8-sig to handle potential BOM from Excel CSVs
        with open(csv_path, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                # Filter out existing parameters
                existing_val = row.get('existing', '').strip().lower()
                if existing_val == 'yes':
                    continue
                
                # Helper function to clean values (handle None/Empty -> "")
                def clean(val):
                    if val is None:
                        return ""
                    return val.strip()

                # Construct the nested data object
                param_data = {
                    "name": clean(row.get('name')),
                    "group_id": clean(row.get('group_id')),
                    "DDF_days": clean(row.get('DDF_days')),
                    "DDF_price": clean(row.get('DDF_price')),
                    "description": clean(row.get('description')),
                    "einheit": clean(row.get('einheit')),
                    "DDF_GBAID": clean(row.get('DDF_GBAID')),
                    "translations": {
                        "en": {
                            "name": clean(row.get('translations_en_name')),
                            "einheit": clean(row.get('translations_en_einheit'))
                        }
                    }
                }
                
                # Wrap in the action object
                action_obj = {
                    "action": "create",
                    "data": param_data
                }
                
                data_list.append(action_obj)
        
        # Create final structure
        final_json = {"parametertypes": data_list}
        
        # Write to output file
        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(final_json, jsonfile, indent=4, ensure_ascii=False)
            
        print(f"Successfully converted '{csv_path}' to '{output_path}'.")
        print(f"Total parameters created: {len(data_list)}")

    except FileNotFoundError:
        print(f"Error: The file '{csv_path}' was not found.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Parameters CSV to LIMS JSON format.")
    parser.add_argument('--csv', required=True, help="Path to the input CSV file")
    parser.add_argument('--out', required=True, help="Path to the output JSON file")
    
    args = parser.parse_args()
    
    convert_csv_to_json(args.csv, args.out)