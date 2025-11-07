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
python update_spec_id.py --in Rules_20251105.json --spec-id 789 --out Rules_new.json
python update_spec_id.py --in Rules_20251105.json --spec-id 789 --inplace


**update_unit.py**
python update_unit.py --in Rules_20251105.json --unit "µg/kg" --out Rules_20251105_unit_ugkg.json
python update_unit.py --in Rules_20251105.json --unit "ppm" --parametertype-id 101 202
python update_unit.py --in Rules_20251105.json --unit "CFU/g" --only-missing
python update_unit.py --in Rules_20251105.json --clear --inplace
python update_unit.py --in Rules_20251105.json --unit "mg/kg"

**update_any_key.py**
python update_any_key.py --in Rules_20251105.json --key action --value "update" --as str --out Rules_20251105_action_update.json
python update_any_key.py --in Rules_20251105.json --key data.spec_id --value 789 --as int
python update_any_key.py --in Rules_20251105.json --key data.DDF_unit --value null --as null --inplace
python update_any_key.py --in Rules_20251105.json --key data.DDF_unit --value null --as null --inplace
python update_any_key.py --in Rules_20251105.json --key data.DDF_unit --value "mg/kg" --as str --only-missing
python update_any_key.py --in Rules_20251105.json --key data.DDF_unit --value "ppm" --as str --parametertype-id 101 202
python update_any_key.py --in Rules_20251105.json --key data.translations --value '{"en":{"name":"Lead","ok":"NULL"}}' --as json
