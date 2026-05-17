import csv
import sys
import os


def read_csv_rows(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return [], []

        for r in reader:
            # skip empty rows
            if all((not c or c.strip() == '') for c in r):
                continue
            # skip comment lines where first column starts with '#'
            first = r[0].strip() if len(r) > 0 else ''
            if first.startswith('#'):
                continue
            # ensure row length matches header
            if len(r) < len(header):
                r = r + [''] * (len(header) - len(r))
            rows.append([c.strip() for c in r])

    return header, rows


def to_markdown_table(header, rows):
    cols = len(header)
    # compute column widths
    widths = [len(h) for h in header]
    for r in rows:
        for i in range(cols):
            widths[i] = max(widths[i], len(r[i]) if i < len(r) else 0)

    def pad(cell, i):
        return cell + ' ' * (widths[i] - len(cell))

    # header
    header_line = '| ' + ' | '.join(pad(header[i], i) for i in range(cols)) + ' |'
    # separator (left align)
    sep_line = '| ' + ' | '.join('-' * widths[i] for i in range(cols)) + ' |'
    lines = [header_line, sep_line]

    for r in rows:
        line = '| ' + ' | '.join(pad(r[i], i) for i in range(cols)) + ' |'
        lines.append(line)

    return '\n'.join(lines) + '\n'


def main():
    infile = sys.argv[1] if len(sys.argv) > 1 else 'categories.csv'
    outfile = sys.argv[2] if len(sys.argv) > 2 else 'categories.md'

    if not os.path.exists(infile):
        print(f"Error: '{infile}' not found")
        sys.exit(1)

    header, rows = read_csv_rows(infile)
    if not header:
        print('No data found in CSV')
        sys.exit(0)

    md = to_markdown_table(header, rows)

    with open(outfile, 'w', encoding='utf-8') as f:
        f.write('# Categories (generated from categories.csv)\n\n')
        f.write(md)

    print(f'Wrote {len(rows)} rows to {outfile}')


if __name__ == '__main__':
    main()
