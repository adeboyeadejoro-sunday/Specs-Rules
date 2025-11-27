import csv
import json
import argparse
import os
import sys

def parse_int_or_null(value):
    """Helper to convert string values to int or None if empty."""
    if value and value.strip():
        try:
            return int(value)
        except ValueError:
            return value # Keep as string if it's not a valid number, though int expected
    return None

def convert_specs(csv_file_path, json_file_path, delimiter):
    specs = []

    if not os.path.exists(csv_file_path):
        print(f"Error: The input file '{csv_file_path}' does not exist.")
        sys.exit(1)

    try:
        with open(csv_file_path, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=delimiter)

            for row in reader:
                data = {}
                
                # 1. Map simple fields
                data['name'] = row.get('name')

                # 2. Convert numeric fields
                data['type'] = parse_int_or_null(row.get('type'))
                data['status'] = parse_int_or_null(row.get('status'))
                data['archiviert'] = parse_int_or_null(row.get('archiviert'))
                data['order'] = parse_int_or_null(row.get('order'))

                # 3. Hardcode translations to null (Legacy Requirement)
                data['translations'] = None

                # 4. Construct the spec object
                spec_entry = {
                    "action": "create",
                    "data": data
                }
                specs.append(spec_entry)

        final_output = {"specs": specs}

        with open(json_file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(final_output, jsonfile, indent=4)
            
        print(f"Successfully converted '{csv_file_path}' to '{json_file_path}' using delimiter '{delimiter}'")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Specs CSV to JSON.")
    parser.add_argument("--from", dest="input_file", required=True, help="Path to input CSV file")
    parser.add_argument("--to", dest="output_file", required=True, help="Path to output JSON file")
    parser.add_argument("--delim", dest="delimiter", required=True, help="CSV delimiter (e.g., ',' or ';')")
    
    args = parser.parse_args()

    convert_specs(args.input_file, args.output_file, args.delimiter)