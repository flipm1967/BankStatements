Will read in bank statements from Nationwide, process and categorise then display

- One time only (I think it is re-runnable though)
./create_venv.sh

- Download statements 
Go to nationwide current account
click "last 12 months" button
then click Download Transactions
on linux this will go to the downloads folder
move file to this dir if you like
rename the file to remove spaces for ease of use
Remove all £ in the input file IMPORTANT!!!

- Run these after you have removed all the £ signs
source bankenv/bin/activate
python3 load_statement.py ./StatementDownloadYYYYMMDD-YYYYMMDD.csv
python3 categorise.py new_categories.csv
python3 display.py 




