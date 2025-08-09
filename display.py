import sys
import sqlite3
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QCheckBox, QLabel, QSizePolicy, QRadioButton,
    QButtonGroup, QHeaderView
)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

DB_FILE = 'load_statement.db'

class NumericItem(QTableWidgetItem):
    def __init__(self, value):
        super().__init__(f"{value:.2f}")
        self.value = value

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            return self.value < other.value
        return super().__lt__(other)

class PieChartWithTable(QWidget):
    def __init__(self, db_conn, is_paid_out=True, use_full_category=True):
        super().__init__()
        self.db_conn = db_conn
        self.is_paid_out = is_paid_out
        self.use_full_category = use_full_category

        self.current_selected_category = None
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout()

        # Label above the table to show selected category
        self.category_label = QLabel("Click a segment to see transactions")
        layout.addWidget(self.category_label)

        # Pie chart canvas
        self.fig = Figure(figsize=(5, 5))
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ax = self.fig.add_subplot(111)

        # Horizontal layout for pie chart and category table
        chart_table_layout = QHBoxLayout()
        chart_table_layout.addWidget(self.canvas, 4)

        # Table for categories
        self.category_table = QTableWidget()
        self.category_table.setColumnCount(2)
        self.category_table.setHorizontalHeaderLabels(["Category", "Amount"])
        self.category_table.horizontalHeader().setStretchLastSection(True)
        self.category_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.category_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.category_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.category_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.category_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.category_table.setSortingEnabled(True)
        chart_table_layout.addWidget(self.category_table, 2)

        layout.addLayout(chart_table_layout)

        # Table for transactions
        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setColumnCount(4)
        headers = ["Date", "Transaction Type", "Description", "Paid Out" if self.is_paid_out else "Paid In"]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table, 3)

        self.setLayout(layout)

        # Connect events
        self.canvas.mpl_connect('pick_event', self.on_pie_click)
        self.category_table.cellClicked.connect(self.on_category_table_click)

    def refresh(self):
        self.current_selected_category = None
        self.table.clearContents()
        self.table.setRowCount(0)
        self.category_label.setText("Click a segment to see transactions")
        self.load_data()
        self.draw_pie()
        self.populate_category_table()

    def load_data(self):
        cursor = self.db_conn.cursor()
        amount_col = 'paid_out' if self.is_paid_out else 'paid_in'

        query = f'''
        SELECT t.id, t.date, t.transaction_type, t.description, t.{amount_col}, cg.category
        FROM transactions t
        LEFT JOIN categorised cg ON t.id = cg.transaction_id
        WHERE t.{amount_col} > 0
        '''
        cursor.execute(query)
        rows = cursor.fetchall()

        columns = ['id', 'date', 'transaction_type', 'description', amount_col, 'category']
        base_df = pd.DataFrame(rows, columns=columns)
        base_df['category'] = base_df['category'].fillna('Uncategorised')
        self.df = base_df.copy()

        if not self.use_full_category:
            self.df['category'] = self.df['category'].apply(lambda c: c.split(';')[0].strip())

        self.amount_col = amount_col
        self.grouped = self.df.groupby('category')[amount_col].sum()
        self.categories = self.grouped.index.tolist()
        self.sizes = self.grouped.values.tolist()

    def draw_pie(self):
        self.ax.clear()
        if not self.categories:
            self.ax.text(0.5, 0.5, "No data", ha='center', va='center')
            self.canvas.draw()
            return

        wedges, _, _ = self.ax.pie(
            self.sizes,
            labels=self.categories,
            autopct='%1.1f%%',
            startangle=140,
            wedgeprops={'picker': True}
        )
        self.wedges = wedges
        self.canvas.draw()

    def populate_category_table(self):
        self.category_table.setRowCount(len(self.categories))
        for i, (cat, amt) in enumerate(zip(self.categories, self.sizes)):
            self.category_table.setItem(i, 0, QTableWidgetItem(cat))
            self.category_table.setItem(i, 1, NumericItem(amt))

    def on_pie_click(self, event):
        wedge = event.artist
        if wedge not in self.wedges:
            return
        idx = self.wedges.index(wedge)
        category = self.categories[idx]
        self.select_category(category)

    def on_category_table_click(self, row, _col):
        category = self.category_table.item(row, 0).text()
        self.select_category(category)

    def select_category(self, category):
        if category == self.current_selected_category:
            return
        self.current_selected_category = category
        self.category_label.setText(f"Transactions in category: {category}")
        filtered = self.df[self.df['category'] == category]
        self.populate_transaction_table(filtered)

    def populate_transaction_table(self, df_filtered):
        self.table.setRowCount(min(len(df_filtered), 200))
        for row_idx, (_, row) in enumerate(df_filtered.head(200).iterrows()):
            self.table.setItem(row_idx, 0, QTableWidgetItem(row['date']))
            self.table.setItem(row_idx, 1, QTableWidgetItem(row['transaction_type']))
            self.table.setItem(row_idx, 2, QTableWidgetItem(row['description']))
            self.table.setItem(row_idx, 3, NumericItem(row[self.amount_col]))


class MainWindow(QWidget):
    def __init__(self, db_conn):
        super().__init__()
        self.db_conn = db_conn
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Bank Transactions Categorisation")
        main_layout = QVBoxLayout()

        # Top controls
        top_controls = QHBoxLayout()
        self.checkbox = QCheckBox("Use full category (show subcategories)")
        self.checkbox.setChecked(True)
        top_controls.addWidget(self.checkbox)

        self.radio_paid_out = QRadioButton("Show Paid Out")
        self.radio_paid_in = QRadioButton("Show Paid In")
        self.radio_paid_out.setChecked(True)

        self.radio_group = QButtonGroup()
        self.radio_group.addButton(self.radio_paid_out)
        self.radio_group.addButton(self.radio_paid_in)
        top_controls.addWidget(self.radio_paid_out)
        top_controls.addWidget(self.radio_paid_in)

        main_layout.addLayout(top_controls)

        # Chart container
        self.chart_container = QVBoxLayout()
        main_layout.addLayout(self.chart_container)

        self.setLayout(main_layout)

        # Create both charts
        self.pie_out = PieChartWithTable(self.db_conn, is_paid_out=True, use_full_category=True)
        self.pie_in = PieChartWithTable(self.db_conn, is_paid_out=False, use_full_category=True)

        self.chart_container.addWidget(self.pie_out)
        self.chart_container.addWidget(self.pie_in)

        self.pie_in.hide()

        # Connect signals
        self.checkbox.stateChanged.connect(self.on_checkbox_change)
        self.radio_paid_out.toggled.connect(self.on_radio_change)

    def on_checkbox_change(self):
        use_full = self.checkbox.isChecked()
        if self.radio_paid_out.isChecked():
            self.pie_out.use_full_category = use_full
            self.pie_out.refresh()
        else:
            self.pie_in.use_full_category = use_full
            self.pie_in.refresh()

    def on_radio_change(self):
        show_out = self.radio_paid_out.isChecked()
        self.pie_out.setVisible(show_out)
        self.pie_in.setVisible(not show_out)
        self.on_checkbox_change()  # Refresh the visible chart


def main():
    app = QApplication(sys.argv)
    db_conn = sqlite3.connect(DB_FILE)
    main_win = MainWindow(db_conn)
    main_win.resize(1400, 800)
    main_win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

