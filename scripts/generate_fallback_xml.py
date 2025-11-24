import argparse
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
import re
import sys
import os

def create_xml_element(parent, tag, text=None, attributes=None):
    """Helper to create an XML element with optional text and attributes."""
    elem = ET.SubElement(parent, tag, attributes if attributes else {})
    if text and str(text).strip():
        elem.text = str(text).strip()
    return elem

def generate_gba_xml(input_path, output_path):
    # 1. Load JSON Data
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{input_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{input_path}'.")
        sys.exit(1)

    if not data:
        print("Error: JSON data is empty.")
        sys.exit(1)

    # 2. Initialize Root Element <Auftrag>
    # We manually set the attributes to ensure namespaces appear exactly as required
    root = ET.Element("Auftrag", {
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xmlns:xsd": "http://www.w3.org/2001/XMLSchema"
    })

    # 3. Add Header Information
    # Hardcoded based on your JS implementation
    create_xml_element(root, "Auftraggeber_ID", "24630")
    create_xml_element(root, "Auftraggeber", "Sunday Natural Products GmbH")
    
    # Dynamic Order Name from the first row
    # Using .get() to avoid errors if key is missing
    create_xml_element(root, "Auftragsbezeichnung", data[0].get('Auftragsbezeichnung', ''))

    # 4. Group Data by Sample (Probe_Nr_extern)
    # The SQL returns flat rows; we need to group them into Samples -> Analyses
    samples_map = {}
    for row in data:
        p_id = row.get('Probe_Nr_extern')
        if not p_id:
            continue 
            
        if p_id not in samples_map:
            samples_map[p_id] = []
        samples_map[p_id].append(row)

    # 5. Iterate through Groups to build <Probe> tags
    for p_id, rows in samples_map.items():
        # Get sample-level metadata from the first row of the group
        probe_data = rows[0]
        
        probe_elem = ET.SubElement(root, "Probe")
        
        # Map JSON keys to XML tags
        # Only creates tags if value exists (mimicking the JS 'if' checks)
        fields_map = [
            ("Probe_Nr_extern", "Probe_Nr_extern"),
            ("Probenbezeichnung", "Probenbezeichnung"),
            ("Probenahmedatum", "Probenahmedatum"),
            ("Artikelbezeichnung", "Artikelbezeichnung"),
            ("Charge", "Charge"),
            ("MHD", "MHD"),
            ("Probenbemerkung", "Probenbemerkung"),
            # Mapping specific Info_extern keys based on JS logic
            ("Probe_Info_extern_03", "Info_extern_03"),
            ("Probe_Info_extern_04", "Info_extern_04"),
        ]

        for json_key, xml_tag in fields_map:
            val = probe_data.get(json_key)
            if val and str(val).strip():
                create_xml_element(probe_elem, xml_tag, val)

        # --- Analysis Scope ---
        scope_elem = ET.SubElement(probe_elem, "Analysenumfang")

        # A. HANDLE PACKAGES (Pruefpaket_ID)
        # Extracted from 'Pakete' column in the first row
        raw_packages = probe_data.get('Pakete', '')
        if raw_packages:
            # Split by comma
            package_list = raw_packages.split(',')
            for pkg_str in package_list:
                pkg_str = pkg_str.strip()
                if not pkg_str: 
                    continue
                
                # Regex: matches the last sequence of digits (e.g., "Name_123" -> "123")
                match = re.search(r'\d+$', pkg_str)
                
                if match:
                    paket_id = match.group(0)
                    
                    # Prepare attributes dictionary
                    attrs = {}
                    if probe_data.get('Para_Info_extern_01'):
                        attrs['Info_extern_01'] = str(probe_data.get('Para_Info_extern_01'))
                    if probe_data.get('Para_Info_extern_02'):
                        attrs['Info_extern_02'] = str(probe_data.get('Para_Info_extern_02'))

                    # Create <Analyse> tag
                    analyse_elem = create_xml_element(scope_elem, "Analyse", attributes=attrs)
                    create_xml_element(analyse_elem, "Pruefpaket_ID", paket_id)

        # B. HANDLE PARAMETERS (Pruefmethode_ID)
        # Iterate through ALL rows for this sample to catch individual methods
        for row in rows:
            method_id = row.get('Pruefmethode_ID')
            
            # Only add if ID exists and is not empty
            if method_id and str(method_id).strip():
                
                # Prepare attributes dictionary (from the specific row)
                attrs = {}
                if row.get('Para_Info_extern_01'):
                    attrs['Info_extern_01'] = str(row.get('Para_Info_extern_01'))
                if row.get('Para_Info_extern_02'):
                    attrs['Info_extern_02'] = str(row.get('Para_Info_extern_02'))
                
                # Create <Analyse> tag
                analyse_elem = create_xml_element(scope_elem, "Analyse", attributes=attrs)
                create_xml_element(analyse_elem, "Pruefmethode_ID", method_id)

    # 6. Format and Write Output
    # minidom is used to make the XML "pretty" (indented)
    xml_str = minidom.parseString(ET.tostring(root, encoding='utf-8')).toprettyxml(indent="  ")
    
    # Fix minidom's tendency to add extra newlines between tags
    xml_str = os.linesep.join([s for s in xml_str.splitlines() if s.strip()])

    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_str)
        
        print(f"Success: XML generated at '{output_path}'")
        
    except OSError as e:
        print(f"Error: Could not write to file '{output_path}'. Reason: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Convert SQL JSON export to GBA-compliant XML.")
    
    # Define required arguments
    parser.add_argument("--from", dest="input_file", required=True, help="Path to the source JSON file")
    parser.add_argument("--out", dest="output_file", required=True, help="Path where the XML file will be saved")

    args = parser.parse_args()

    # Run the generator
    generate_gba_xml(args.input_file, args.output_file)