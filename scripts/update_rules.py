import csv
import json
import sys
import os

def display_menu(options, prompt):
    """Displays a numbered menu and gets a valid user choice."""
    print(f"\n{prompt}")
    for i, option in enumerate(options):
        print(f"  {i + 1}. {option}")
    
    while True:
        try:
            choice = int(input("\nEnter the number of your choice: "))
            if 1 <= choice <= len(options):
                return options[choice - 1]
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

def main():
    print("--- LIMS CSV to JSON Converter (Rules) ---")
    
    # 1. Get CSV file path
    if len(sys.argv) > 1:
        csv_file = " ".join(sys.argv[1:])
    else:
        csv_file = input("\nEnter the path to your CSV file: ").strip()
    
    # Remove both single and double quotes if the terminal added them
    if csv_file.startswith(("'", '"')) and csv_file.endswith(("'", '"')):
        csv_file = csv_file[1:-1]
        
    # Handle backslash escapes for spaces (common in Mac/Linux terminals)
    csv_file = csv_file.replace('\\ ', ' ')

    if not os.path.isfile(csv_file):
        print(f"\nError: File not found at path:\n{csv_file}")
        sys.exit(1)

    # 2. Read headers
    try:
        with open(csv_file, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    if not headers:
        print("Error: CSV file appears to be empty.")
        sys.exit(1)

    # 3. Map the ID column
    print("\nStep 1: Identify the ID column")
    id_column = display_menu(headers, "Which CSV column contains the LIMS 'rules.id'?")

    # 4. Define JSON data keys to update
    print("\nStep 2: Define the LIMS rule keys to update")
    print("Enter the exact names of the LIMS keys you want to update (e.g., color, operator, spec_id).")
    print("Type 'done' when you have finished adding keys.")
    
    target_keys = []
    while True:
        key = input("Enter a LIMS key (or 'done'): ").strip()
        if key.lower() == 'done':
            if not target_keys:
                print("You must add at least one key to update.")
                continue
            break
        if key:
            target_keys.append(key)

    # 5. Map CSV columns to the chosen LIMS keys
    print("\nStep 3: Map CSV columns to your LIMS keys")
    mappings = {}
    ignore_option = "-- DO NOT MAP (Leave Empty) --"
    menu_options = headers + [ignore_option]
    
    for target_key in target_keys:
        csv_col = display_menu(
            menu_options, 
            f"Which CSV column should map to LIMS key '{target_key}'?"
        )
        if csv_col != ignore_option:
            mappings[target_key] = csv_col

    if not mappings:
        print("Error: No mappings were created. Exiting.")
        sys.exit(1)

    # 6. Process the CSV and build the JSON
    print("\nProcessing data...")
    # Updated root key from "parametertypes" to "rules"
    json_output = {"rules": []}
    
    with open(csv_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Get the ID and skip rows where the ID is blank
            row_id = row.get(id_column, "").strip()
            if not row_id:
                continue
            
            # Convert ID to integer if it consists only of digits 
            # (Matches your example: "id": 81446)
            if row_id.isdigit():
                row_id = int(row_id)
                
            item_data = {}
            for target_key, csv_column in mappings.items():
                val = row.get(csv_column, "").strip()
                
                # Only add if there is a value to update
                if val:
                    # Convert explicit "null" text in CSV to actual JSON nulls if needed
                    if val.lower() == 'null':
                        item_data[target_key] = None
                    else:
                        item_data[target_key] = val
            
            # Only add to JSON if there's actually data to update for this ID
            if item_data:
                item = {
                    "action": "update",
                    "id": row_id,
                    "data": item_data
                }
                json_output["rules"].append(item)

    # 7. Ask for save location and save the output
    print("\nStep 4: Save Location")
    save_dir = input("Where would you like to save the json output? (Press Enter to use the CSV's folder): ").strip()
    
    if save_dir:
        # Expand '~' to the user's actual home directory
        save_dir = os.path.expanduser(save_dir)
        # Create the directory if it doesn't exist
        if not os.path.exists(save_dir):
            print(f"Creating directory: {save_dir}")
            os.makedirs(save_dir, exist_ok=True)
    else:
        # Default to the directory where the CSV is located
        save_dir = os.path.dirname(os.path.abspath(csv_file))

    # Construct the final filename (changed suffix to rules_import)
    base_name = os.path.basename(csv_file)
    name_only, _ = os.path.splitext(base_name)
    output_file = os.path.join(save_dir, f"{name_only}_rules_import.json")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, indent=4)
        print(f"\nSuccess! JSON saved to:\n{output_file}")
    except Exception as e:
        print(f"Error saving JSON: {e}")

if __name__ == "__main__":
    main()