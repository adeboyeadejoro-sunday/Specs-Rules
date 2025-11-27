import csv
import json
import argparse
import os
import sys

def parse_int_or_null(value):
    """Parses string to int, returns None if empty."""
    if value and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None

def smart_parse(value):
    """
    Parses value to int or float if possible, otherwise returns string.
    Returns None if empty.
    Applied to 'value' and 'value2'.
    """
    if not value or not value.strip():
        return None
    
    val = value.strip()
    
    # 1. Try Integer (Cleanest for whole numbers like 30)
    try:
        return int(val)
    except ValueError:
        pass
    
    # 2. Try Float (For decimals like 30.5)
    try:
        return float(val)
    except ValueError:
        pass
    
    # 3. Return as String (For text like "negative")
    return val

def parse_string_or_null(value):
    """Returns string value or None if empty."""
    if value and value.strip():
        return value.strip()
    return None

def convert_rules(csv_path, json_path, delimiter):
    rules_list = []

    if not os.path.exists(csv_path):
        print(f"Error: Input file '{csv_path}' not found.")
        sys.exit(1)

    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            
            for row in reader:
                data = {}
                
                # 1. Integer Fields
                data['spec_id'] = parse_int_or_null(row.get('spec_id'))
                data['show'] = parse_int_or_null(row.get('show'))
                data['column'] = parse_int_or_null(row.get('column'))
                data['inverse'] = parse_int_or_null(row.get('inverse'))
                data['parametertype_id'] = parse_int_or_null(row.get('parametertype_id'))
                
                # 2. Polymorphic Fields (Number or String)
                # Both value and value2 can be Int, Float, String, or Null
                data['value'] = smart_parse(row.get('value'))
                data['value2'] = smart_parse(row.get('value2'))
                
                # 3. String Fields
                data['DDF_unit'] = parse_string_or_null(row.get('DDF_unit'))
                data['DDF_target_value'] = parse_string_or_null(row.get('DDF_target_value'))
                data['DDF_type'] = parse_string_or_null(row.get('DDF_type'))
                data['color'] = parse_string_or_null(row.get('color'))
                data['operator'] = parse_string_or_null(row.get('operator'))
                data['linker'] = parse_string_or_null(row.get('linker'))
                data['operator2'] = parse_string_or_null(row.get('operator2'))
                data['regex_filter'] = parse_string_or_null(row.get('regex_filter'))
                data['text'] = parse_string_or_null(row.get('text'))
                data['translations'] = parse_string_or_null(row.get('translations'))

                # Construct the wrapper
                rule_entry = {
                    "action": "create",
                    "data": data
                }
                rules_list.append(rule_entry)

        # Final wrapper
        final_json = {"rules": rules_list}

        with open(json_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(final_json, jsonfile, indent=4)
            
        print(f"Successfully converted '{csv_path}' to '{json_path}' using delimiter '{delimiter}'")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Rules CSV to JSON.")
    parser.add_argument("--from", dest="input_file", required=True, help="Path to input CSV file")
    parser.add_argument("--to", dest="output_file", required=True, help="Path to output JSON file")
    parser.add_argument("--delim", dest="delimiter", required=True, help="CSV delimiter (e.g., ',' or ';')")
    
    args = parser.parse_args()
    
    convert_rules(args.input_file, args.output_file, args.delimiter)