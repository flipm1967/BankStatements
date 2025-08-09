import sys
import sqlite3
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QCheckBox, QLabel, QSizePolicy, QAbstractItemView
)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

DB_FILE = 'load_statement.db'

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
        main_layout = QVBoxLayout()

        self.category_label = QLabel("Click a segment or row to see transactions")
        main_layout.addWidget(self.category_label)

        chart_table_layout = QHBoxLayout()

        # Pie chart
        self.fig = Figure(figsize=(5, 5))
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ax = self.fig.add_subplot(111)
        chart_table_layout.addWidget(self.canvas, 3)

        # Category summary table
        self.category_table = QTableWidget()
        self.category_table.setColumnCount(2)
        self.category_table.setHorizontalHeaderLabels(["Category", "Amount"])
        self.category_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.category_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.category_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.category_table.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        chart_table_layout.addWidget(self.category_table, 1)

        main_layout.addLayout(chart_table_layout)

        # Transactions table
        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setColumnCount(4)
        headers = ["Date", "Transaction Type", "Description", "Paid Out" if self.is_paid_out else "Paid In"]
        self.table.setHorizontalHeaderLabels(headers)
        main_layout.addWidget(self.table, 3)

        self.setLayout(main_layout)

        self.canvas.mpl_connect('pick_event', self.on_pie_click)
        self.category_table.itemSelectionChanged.connect(self.on_category_table_click)

    def refresh(self):
        self.current_selected_category = None
        self.category_label.setText("Click a segment or row to see transactions")
        self.table.clearContents()
        self.table.setRowCount(0)
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

        self.grouped = self.df.groupby('category')[amount_col].sum().sort_values(ascending=False)
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
        for idx, (cat, size) in enumerate(zip(self.categories, self.sizes)):
            self.category_table.setItem(idx, 0, QTableWidgetItem(cat))
            self.category_table.setItem(idx, 1, QTableWidgetItem(f"{size:.2f}"))
        self.category_table.resizeColumnsToContents()

    def on_pie_click(self, event):
        wedge = event.artist
        if wedge not in self.wedges:
            return
        idx = self.wedges.index(wedge)
        category = self.categories[idx]
        self.select_category(category)

    def on_category_table_click(self):
        selected = self.category_table.selectedItems()
        if not selected:
            return
        category = selected[0].text()
        self.select_category(category)

    def select_category(self, category):
        if category == self.current_selected_category:
            return
        self.current_selected_category = category
        self.category_label.setText(f"Transactions in category: {category}")
        filtered = self.df[self.df['category'] == category]
        self.populate_table(filtered)

    def populate_table(self, df_filtered):
        amount_col = 'paid_out' if self.is_paid_out else 'paid_in'
        MAX_ROWS = 200
        if len(df_filtered) > MAX_ROWS:
            df_filtered = df_filtered.head(MAX_ROWS)

        self.table.setRowCount(len(df_filtered))
        for row_idx, (_, row) in enumerate(df_filtered.iterrows()):
            self.table.setItem(row_idx, 0, QTableWidgetItem(row['date']))
            self.table.setItem(row_idx, 1, QTableWidgetItem(row['transaction_type']))
            self.table.setItem(row_idx, 2, QTableWidgetItem(row['description']))
            self.table.setItem(row_idx, 3, QTableWidgetItem(f"{row[amount_col]:.2f}"))


class MainWindow(QWidget):
    def __init__(self, db_conn):
        super().__init__()
        self.db_conn = db_conn
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Bank Transactions Categorisation")
        layout = QHBoxLayout()

        left_layout = QVBoxLayout()
        self.checkbox = QCheckBox("Use full category (show subcategories)")
        self.checkbox.setChecked(True)
        left_layout.addWidget(self.checkbox)

        self.pie_out = PieChartWithTable(self.db_conn, is_paid_out=True, use_full_category=True)
        left_layout.addWidget(self.pie_out)

        layout.addLayout(left_layout)

        self.pie_in = PieChartWithTable(self.db_conn, is_paid_out=False, use_full_category=True)
        layout.addWidget(self.pie_in)

        self.setLayout(layout)
        self.checkbox.stateChanged.connect(self.on_checkbox_change)

    def on_checkbox_change(self):
        use_full = self.checkbox.isChecked()
        self.pie_out.use_full_category = use_full
        self.pie_out.refresh()


def main():
    app = QApplication(sys.argv)
    db_conn = sqlite3.connect(DB_FILE)
    main_win = MainWindow(db_conn)
    main_win.resize(1400, 800)
    main_win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

