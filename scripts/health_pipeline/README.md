# IDD harmonisation pipeline
pip install -r requirements.txt
bash run_all.sh data/Data out          # harmonise -> checks -> one HTML report per stakeholder
python mock_test.py data/Data --fast   # automated mock test -> mock_test/mock_test_report.html
Add a stakeholder: copy config/stakeholders/public_health_expert.json and edit it.
Classify a new disease: add a line to config/pathogen_class.csv.

## Quarto version of the report
report_public_health_expert.qmd rebuilds the same report with Quarto (same numbers as report.py).
Needs Quarto (https://quarto.org) plus: pip install jupyter matplotlib jinja2
bash run_all.sh data/Data out                          # creates out/harmonised.parquet etc.
quarto render report_public_health_expert.qmd          # -> report_public_health_expert.html
Another output folder: quarto render report_public_health_expert.qmd -P out:my_out
