FILE=$1
cat $FILE \
| iconv -f ISO-8859-1 -t UTF-8 \
| dos2unix \
| sed 's/£//g' \
| sed '/^$/d' \
| egrep -v "Account Name:|Account Balance:|Available Balance" \
> $FILE.preprocessed


