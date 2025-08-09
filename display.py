import sys
import sqlite3
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QCheckBox, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

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
        layout.addWidget(self.canvas, 4)

        # Table for transactions
        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setColumnCount(4)
        headers = ["Date", "Transaction Type", "Description", "Paid Out" if self.is_paid_out else "Paid In"]
        self.table.setHorizontalHeaderLabels(headers)
        layout.addWidget(self.table, 3)

        self.setLayout(layout)

        # Connect click event on pie wedges
        self.canvas.mpl_connect('pick_event', self.on_pie_click)

    def refresh(self):
        self.current_selected_category = None
        self.table.clearContents()
        self.table.setRowCount(0)
        self.category_label.setText("Click a segment to see transactions")
        self.load_data()
        self.draw_pie()

    def load_data(self):
        print(f"[DEBUG] Loading data with use_full_category={self.use_full_category}")
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

        self.df = pd.DataFrame(rows, columns=['id', 'date', 'transaction_type', 'description', amount_col, 'category'])
        self.df['category'] = self.df['category'].fillna('Uncategorised')

        if not self.use_full_category:
            print(f"[DEBUG] Use MAIN category")
            self.df['category'] = self.df['category'].apply(lambda c: c.split(';')[0].strip())
        else:
            print(f"[DEBUG] Use SUB category")            

        self.grouped = self.df.groupby('category')[amount_col].sum()
        self.categories = self.grouped.index.tolist()
        self.sizes = self.grouped.values.tolist()
        print(f"[DEBUG] Categories after grouping: {self.categories}")

    def draw_pie(self):
        self.ax.clear()
        if not self.categories:
            self.ax.text(0.5, 0.5, "No data", ha='center', va='center')
            self.canvas.draw()
            return

        wedges, texts, autotexts = self.ax.pie(
            self.sizes,
            labels=self.categories,
            autopct='%1.1f%%',
            startangle=140,
            wedgeprops={'picker': True}
        )
        self.wedges = wedges
        self.canvas.draw()

    def on_pie_click(self, event):
        # event.artist is the wedge clicked
        wedge = event.artist
        if wedge not in self.wedges:
            return
        idx = self.wedges.index(wedge)
        category = self.categories[idx]

        if category == self.current_selected_category:
            # Same segment clicked again; do nothing
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

        # Left pie chart and table for paid_out
        left_layout = QVBoxLayout()
        self.checkbox = QCheckBox("Use full category (show subcategories)")
        self.checkbox.setChecked(True)
        left_layout.addWidget(self.checkbox)

        self.pie_out = PieChartWithTable(self.db_conn, is_paid_out=True, use_full_category=True)
        left_layout.addWidget(self.pie_out)

        layout.addLayout(left_layout)

        # Right pie chart and table for paid_in (no checkbox, always full categories)
        self.pie_in = PieChartWithTable(self.db_conn, is_paid_out=False, use_full_category=True)
        layout.addWidget(self.pie_in)

        self.setLayout(layout)

        # Connect checkbox event
        self.checkbox.stateChanged.connect(self.on_checkbox_change)

    def on_checkbox_change(self, state):
        use_full = (state == Qt.CheckState.Checked)
        print(f"[DEBUG] Checkbox changed, use_full_category={use_full}")
        self.pie_out.use_full_category = use_full
        self.pie_out.refresh()

        # For paid_in pie, always show full category (or adapt if you want)
        self.pie_in.refresh()


def main():
    app = QApplication(sys.argv)

    # Connect to your SQLite DB (replace 'your_database.db' with your DB filename)
    db_conn = sqlite3.connect('load_statement.db')

    main_win = MainWindow(db_conn)
    main_win.resize(1200, 700)
    main_win.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()

