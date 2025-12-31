Will read in bank statements from Nationwide, process and categorise then display

- One time only (I think it is re-runnable though)
sudo apt install git
sudo apt install keepass
sudo apt install dos2unix
sudo apt install libxcb-cursor0
sudo apt install sqlite3
./create_venv.sh

- Download statements 
Go to nationwide current account
click "last 12 months" button
then click Download Transactions
on linux this will go to the downloads folder

- Fix statement file
move file to local dir if you like - you just need to specify the relative path to process it
rename the file to remove spaces for ease of use
Remove the first few lines but leave the column titles
Remove all £ in the input file IMPORTANT!!!

- Run these after you have removed all the £ signs
source bankenv/bin/activate
python3 load_statement.py ./StatementDownloadYYYYMMDD-YYYYMMDD.csv
python3 categorise.py new_categories.csv
python3 display.py 

- you can query the database manually like this - semicolon is line terminator if you get in a mess
sqlite3 load_statement.db
list the tables : .tables 
show table def  : .schema <tablename>
show help       : .help
exit            : .quit

- tables in the database
transactions - raw transactions loaded by load_statement.py
categories   - patterns to match with raw transactions to categorise them - loaded by categorise.py
categorised  - also created by categorise.py for each row in transactions - linked on id - the category for that row
