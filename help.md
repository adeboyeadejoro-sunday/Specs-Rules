**export_specs_rules.py**

python export_specs_rules.py --specs /Users/adeboye/projects/specs_rules/Specs.csv --rules /Users/adeboye/projects/specs_rules/Rules.csv --out /Users/adeboye/projects/specs_rules/output

python export_specs_rules.py \
  --specs /Users/adeboye/projects/specs_rules/Specs.csv \
  --rules /Users/adeboye/projects/specs_rules/Rules.csv \
  --out /Users/adeboye/projects/specs_rules/output

python export_specs_rules.py \
  --specs /Users/adeboye/projects/specs_rules/Specs.csv \
  --out /Users/adeboye/projects/specs_rules/output

python export_specs_rules.py \
  --rules /Users/adeboye/projects/specs_rules/Rules.csv \
  --out /Users/adeboye/projects/specs_rules/output



**update_spec_id.py**
python update_spec_id.py --in Rules_20251105.json --spec-id 789
python update_spec_id.py --in Rules_20251105.json --spec-id 789 --out Rules_new.json
python update_spec_id.py --in Rules_20251105.json --spec-id 789 --inplace
