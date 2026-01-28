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
move this to the DATA folder

- Fix statement file
We need to fix the encoding, blank lines, pound signs etc in the download
./preprocess.sh ../DATA/Statement...blah
this produces a .processed file in the same directory

- Run these after you have removed all the £ signs
source bankenv/bin/activate
python3 load_statement.py ../DATA/StatementDownloadYYYYMMDD-YYYYMMDD.csv.processed
python3 categorise.py categories.csv

- Show what is missed
python3 list_uncategorised.py 

- display the final results
>>> python3 display.py <<< WORK IN PROGRESS FOR v2

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
