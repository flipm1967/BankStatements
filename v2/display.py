import sqlite3
import json
import os
from datetime import datetime
from collections import defaultdict, OrderedDict

import plotly.graph_objects as go

DB_FILE = 'load_statement.db'
OUTPUT_FILE = 'display.html'

COLOR_PALETTE = [
    '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3',
    '#FF6692', '#B6E880', '#FF97FF', '#FECB52', '#2CA02C', '#d62728',
    '#9467BD', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
]


def parse_month(date_text):
    if not date_text:
        return ''
    date_text = date_text.strip()
    for fmt in ('%Y-%m-%d', '%Y%m%d', '%Y-%m', '%Y/%m/%d', '%d/%m/%Y'):
        try:
            dt = datetime.strptime(date_text[:10], fmt)
            return dt.strftime('%Y-%m')
        except ValueError:
            continue
    if len(date_text) >= 7:
        return date_text[:7]
    return date_text


def load_transactions(db_file):
    with sqlite3.connect(db_file) as conn:
        cur = conn.cursor()
        cur.execute(
            '''
            SELECT t.date, c.main_category, c.sub1, t.description, t.paid_in, t.paid_out
            FROM transactions t
            JOIN categorised c ON c.transaction_id = t.id
            ORDER BY t.date
            '''
        )
        return cur.fetchall()


def build_aggregates(rows):
    months = OrderedDict()
    data = defaultdict(lambda: defaultdict(float))
    detail_map = defaultdict(lambda: defaultdict(list))
    all_main_categories = []
    all_sub1 = []

    for date_text, main_category, sub1, description, paid_in, paid_out in rows:
        month = parse_month(date_text)
        if month == '':
            continue
        if month not in months:
            months[month] = None
        main_category = main_category or 'Uncategorised'
        sub1 = sub1 or '(no sub1)'
        amount = (paid_in or 0.0) - (paid_out or 0.0)

        key = (main_category, sub1)
        data[key][month] += amount
        detail_map[month][sub1].append({
            'date': date_text,
            'description': description or '',
            'main_category': main_category,
            'sub1': sub1,
            'amount': amount,
        })
        if main_category not in all_main_categories:
            all_main_categories.append(main_category)
        if sub1 not in all_sub1:
            all_sub1.append(sub1)

    return list(months.keys()), all_main_categories, all_sub1, data, detail_map


def format_month_label(month):
    try:
        dt = datetime.strptime(month, '%Y-%m')
        return dt.strftime('%B %Y')
    except ValueError:
        return month


def choose_color(sub1, palette):
    return palette[hash(sub1) % len(palette)]


def build_figure(months, data, all_sub1):
    traces = []
    trace_info = []
    month_labels = [format_month_label(m) for m in months]

    for (main_category, sub1), month_map in sorted(data.items()):
        y = [month_map.get(m, 0.0) for m in months]
        color = choose_color(sub1, COLOR_PALETTE)
        trace = go.Bar(
            x=months,
            y=y,
            name=sub1,
            marker_color=color,
            customdata=[[main_category, sub1, m] for m in months],
            hovertemplate='<b>%{x}</b><br>%{customdata[0]} / %{customdata[1]}<br>Amount: %{y:$,.2f}<extra></extra>',
        )
        traces.append(trace)
        trace_info.append({'main_category': main_category, 'sub1': sub1})

    fig = go.Figure(data=traces)
    fig.update_layout(
        barmode='relative',
        title='Monthly transaction summary by sub1 category',
        xaxis_title='Month',
        yaxis_title='Net amount (paid_in - paid_out)',
        legend_title='sub1 category',
        hovermode='closest',
        template='plotly_white',
        xaxis=dict(
            tickmode='array',
            tickvals=months,
            ticktext=month_labels,
            tickangle=-45,
        ),
    )
    fig.update_layout(margin=dict(l=40, r=20, t=80, b=100))
    return fig, trace_info


def make_html(fig, trace_info, main_categories, detail_map):
    plot_div = fig.to_html(full_html=False, include_plotlyjs=True, div_id='display_plot')
    checkbox_html = ''.join([f'<label><input type="checkbox" class="main-toggle" data-main="{mc}" checked> {mc}</label>' for mc in main_categories])
    script = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Bank Statements Display</title>
<style>
 body { font-family: Arial, sans-serif; margin: 20px; }
 .controls { margin-bottom: 16px; }
 .controls label { margin-right: 12px; }
 #detail-panel { margin-top: 32px; }
 table { border-collapse: collapse; width: 100%; margin-top: 8px; }
 th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
 th { background: #f2f2f2; }
 .note { color: #555; margin-top: 8px; }
</style>
</head>
<body>
<h1>Bank Statement Dashboard</h1>
<div class="controls">
  <strong>Toggle main_category:</strong><br />
  """ + checkbox_html + """
</div>
<div id="plot-container">
  """ + plot_div + """
</div>
<div id="detail-panel">
  <h2>Detail table</h2>
  <p class="note">Click a coloured bar segment to show transactions for that month and sub1 category.</p>
  <div id="detail-title">No data selected.</div>
  <table id="detail-table">
    <thead>
      <tr><th>Date</th><th>Main category</th><th>sub1</th><th>Description</th><th>Amount</th></tr>
    </thead>
    <tbody></tbody>
  </table>
</div>
<script>
const mainCategoryToTraces = {};
const traceInfo = """ + json.dumps(trace_info) + """;
const detailMap = """ + json.dumps(detail_map) + """;

traceInfo.forEach((info, idx) => {
    if (!mainCategoryToTraces[info.main_category]) {
        mainCategoryToTraces[info.main_category] = [];
    }
    mainCategoryToTraces[info.main_category].push(idx);
});

function updateVisibility() {
    const checkboxes = document.querySelectorAll('.main-toggle');
    const visible = [];
    const hidden = [];

    checkboxes.forEach(cb => {
        const main = cb.dataset.main;
        const indices = mainCategoryToTraces[main] || [];
        if (cb.checked) {
            visible.push(...indices);
        } else {
            hidden.push(...indices);
        }
    });

    const currentVisibility = document.getElementById('display_plot').data.map(trace => trace.visible);
    const newVisibility = currentVisibility.map((vis, idx) => {
        if (hidden.includes(idx)) return false;
        return true;
    });
    Plotly.restyle('display_plot', 'visible', newVisibility);
}

document.querySelectorAll('.main-toggle').forEach(cb => cb.addEventListener('change', updateVisibility));

const plotElement = document.getElementById('display_plot');
plotElement.on('plotly_click', function(event) {
    if (!event.points || !event.points.length) {
        return;
    }
    const point = event.points[0];
    const month = String(point.customdata[2] || point.x);
    const sub1 = String(point.customdata[1] || point.data.name);
    const mainCategory = String(point.customdata[0] || '');
    const monthGroup = detailMap[month] || detailMap[month.trim()] || detailMap[String(month).trim()];

    let rows = [];
    if (monthGroup) {
        rows = monthGroup[sub1] || monthGroup[sub1.trim()] || [];
        if (!rows.length) {
            const sub1Keys = Object.keys(monthGroup);
            const lower = sub1.toLowerCase().trim();
            const match = sub1Keys.find(key => key.toLowerCase().trim() === lower);
            if (match) {
                rows = monthGroup[match] || [];
            }
        }
    }
    if (mainCategory && rows.length) {
        rows = rows.filter(r => String(r.main_category) === mainCategory);
    }

    const tbody = document.querySelector('#detail-table tbody');
    tbody.innerHTML = '';
    rows.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${row.date}</td>
          <td>${row.main_category}</td>
          <td>${row.sub1}</td>
          <td>${row.description}</td>
          <td>${row.amount.toFixed(2)}</td>
        `;
        tbody.appendChild(tr);
    });
    const title = document.getElementById('detail-title');
    title.textContent = rows.length
      ? `Transactions for ${sub1} in ${month} (${rows.length} rows)`
      : `No transactions found for ${sub1} in ${month}.`;
});
</script>
</body>
</html>
"""
    return script


def main():
    if not os.path.exists(DB_FILE):
        raise FileNotFoundError(f'Missing database: {DB_FILE}')

    rows = load_transactions(DB_FILE)
    months, main_categories, all_sub1, data, detail_map = build_aggregates(rows)
    if not months:
        raise SystemExit('No transaction months found in database.')

    fig, trace_info = build_figure(months, data, all_sub1)
    html = make_html(fig, trace_info, main_categories, detail_map)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'Wrote interactive dashboard to {OUTPUT_FILE}')
    print('Open this file in a browser to view the monthly stacked bar chart and details table.')


if __name__ == '__main__':
    main()
