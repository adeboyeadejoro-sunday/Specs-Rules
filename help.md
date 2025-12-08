**export_specs_rules.py**

python export_specs_rules.py --specs /Users/adeboye/projects/specs_rules/Specs.csv --rules /Users/adeboye/projects/specs_rules/Rules.csv --out /Users/adeboye/projects/specs_rules/output

**BOTH_V2** 
python export_specs_rules.py \
  --specs /Users/adeboye/projects/specs_rules/Specs.csv \
  --rules /Users/adeboye/projects/specs_rules/Rules.csv \
  --out /Users/adeboye/projects/specs_rules/output

**SPECS**
python export_specs_rules.py \
  --specs /Users/adeboye/projects/specs_rules/Specs.csv \
  --out /Users/adeboye/projects/specs_rules/output

**RULES**
python export_specs_rules.py \
  --rules /Users/adeboye/projects/specs_rules/Rules.csv \
  --out /Users/adeboye/projects/specs_rules/output


**update_spec_id.py**
python update_spec_id.py --in Rules_20251105.json --spec-id 789
python update_spec_id.py --in [Rules_20251105.json] --spec-id [789] --out [Rules_new.json] 
python update_spec_id.py --in [**path_to_template.json path_to_another_template.json**] --spec-id [789] --out [Rules_new.json] 
python update_spec_id.py --in Rules_20251105.json --spec-id 789 --inplace
note: can accept multiple inputs

**remove_parameter.py**
*python remove_parameter.py --in ICP_Template.json --param-id 5282 5283 --in-place*
python remove_parameter.py --in ICP_Template.json --param-id 5282 --out ICP_Template_no5282.json
python remove_parameter.py --in ICP_Template.json --param-id 5282 5283 5284 --out ICP_Template_filtered.json

***update_spec_id.py + remove_parameter.py***
python scripts/update_spec_id.py --in Templates/ICP_Template.json --spec-id 1166 --out Specs_Updated/ICP_1166.json \
&& python scripts/remove_parameter.py --in Specs_Updated/ICP_1166.json --param-id 5292 --in-place




**generate_standalone_rules.py**
# Active (Spermidine-like)
python generate_standalone_rules.py \
  --spec-id 1083 \
  --param 5253 3 mg active \
  --out Spermidine_Rules_1083.json

# Multiple params, mixed modes
python generate_standalone_rules.py \
  --spec-id 1083 \
  --param 5253 3 mg active \
  --param 6002 0.01 "mg/kg" limit2 \
  --param 6010 1000 "CFU/g" limit3 \
  --out Standalone_Rules_1083.json

# Qualitative perfect + numeric not OK
python generate_standalone_rules.py \
  --spec-id 1083 \
  --param 5369 0 "mg/kg" qualitative \
  --qual "not detectable" "nicht nachw." \
  --out Qual_Rules_1083.json
# dummy  
python generate_standalone_rules.py \
  --spec-id 1029 \
  --param 5587 null null dummy \
  --out Dummy_Rules_1029.json

python generate_standalone_rules.py \
  --spec-id 1083 \
  --param 5253 3 mg active \
  --param 7001 100 mg mineral \
  --param 5587 null null dummy \
  --out Rules.json  


**range_calculator.py**
python range_calculator.py --target 12 --type active
python range_calculator.py --target 12 --type limit
python range_calculator.py --target 0 --type limit

**generate_rules_for_internal_lab.py**
python generate_rules_for_internal_lab.py --from Internal_Lab_Templates.json --spec-id 978 --targets "[0.55, 2, 0.85, 90]" \
--out Internal_Lab_Rules_Final.json



***update_unit.py***
python update_unit.py --in Rules_20251105.json --unit "µg/kg" --out Rules_20251105_unit_ugkg.json
python update_unit.py --in Rules_20251105.json --unit "ppm" --parametertype-id 101 202
python update_unit.py --in Rules_20251105.json --unit "CFU/g" --only-missing
python update_unit.py --in Rules_20251105.json --clear --inplace
python update_unit.py --in Rules_20251105.json --unit "mg/kg"

***update_any_key.py***
python update_any_key.py --in Rules_20251105.json --key action --value "update" --as str --out Rules_20251105_action_update.json
python update_any_key.py --in Rules_20251105.json --key data.spec_id --value 789 --as int
python update_any_key.py --in Rules_20251105.json --key data.DDF_unit --value null --as null --inplace
python update_any_key.py --in Rules_20251105.json --key data.DDF_unit --value null --as null --inplace
python update_any_key.py --in Rules_20251105.json --key data.DDF_unit --value "mg/kg" --as str --only-missing
python update_any_key.py --in Rules_20251105.json --key data.DDF_unit --value "ppm" --as str --parametertype-id 101 202
python update_any_key.py --in Rules_20251105.json --key data.translations --value '{"en":{"name":"Lead","ok":"NULL"}}' --as json

***add_sample_number.py***
python add_sample_number.py --to PDF_Reports/Report.pdf --label LIMS_Sample_ID --sample-nr ABC123456 --out output/Report_ID.pdf

***generate_fallback_xml.py***
python generate_fallback_xml.py --from XMLGBAFallBackQuery_7447.json --out ~/Desktop/pool_7447.xml

***convert_specs_csv_to_json.py***
python convert_specs_csv_to_json.py --from "Create Exim Specification from Batch Table .csv" --to specs_output.json --delim ";"
***convert_rules_csv_to_json.py***
python convert_rules_csv_to_json.py --from "Rules Templates - Microbiology_Template.csv" --to "rules_output.json" --delim ","

***export_rules_specs.py***
python export_rules_specs.py \
  --specs Specs_A.csv Specs_B.csv Specs_C.csv \
  --out-specs merged_specs.json
# rules
python export_rules_specs.py \
  --rules Rules_A.csv Rules_B.csv \
  --out-rules merged_rules.json

python export_rules_specs.py \
--specs Specs_A.csv Specs_B.csv \
--out-specs merged_specs.json \
--rules Rules_A.csv Rules_B.csv \
--out-rules merged_rules.json