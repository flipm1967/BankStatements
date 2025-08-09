Will read in bank statements from Nationwide, process and categorise then display

1) One time only (I think it is re-runnable though)
./create_venv.sh

2) Run these
source bankenv/bin/activate
python3 load_statement.py ../DATA/StatementDownload20240808-20250808.csv
python3 categorise.py new_categories.csv
python3 display.py 




