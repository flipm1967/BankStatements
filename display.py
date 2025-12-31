import sys
import sqlite3
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QCheckBox, QLabel, QSizePolicy, QRadioButton, QButtonGroup, QHeaderView
)
from PyQt6.QtCore import Qt, QAbstractTableModel
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

DB_FILE = 'load_statement.db'

class PandasModel(QAbstractTableModel):
    def __init__(self, df):
        super().__init__()
        self._df = df

    def rowCount(self, parent=None):
        return len(self._df)

    def columnCount(self, parent=None):
        return len(self._df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = self._df.iloc[index.row(), index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(value, float):
                return f"{value:.2f}"
            return str(value)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._df.columns[section]
        else:
            return str(section + 1)

    def sort(self, column, order):
        colname = self._df.columns[column]
        ascending = order == Qt.SortOrder.AscendingOrder
        self.layoutAboutToBeChanged.emit()
        self._df.sort_values(colname, ascending=ascending, inplace=True)
        self._df.reset_index(drop=True, inplace=True)
        self.layoutChanged.emit()


class PieChartWithTable(QWidget):
    def __init__(self, db_conn, is_paid_out=True, use_full_category=True):
        super().__init__()
        self.db_conn = db_conn
        self.is_paid_out = is_paid_out
        self.use_full_category = use_full_category
        self.essential_filter = 'ALL'  # 'ALL', 'Y', 'N'

        self.df = pd.DataFrame()
        self.current_selected_category = None
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout()

        self.category_label = QLabel("Click a segment to see transactions")
        layout.addWidget(self.category_label)

        self.fig = Figure(figsize=(5, 5))
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ax = self.fig.add_subplot(111)

        chart_table_layout = QHBoxLayout()
        chart_table_layout.addWidget(self.canvas, 4)

        self.category_table = QTableView()
        self.category_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.category_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        chart_table_layout.addWidget(self.category_table, 2)

        layout.addLayout(chart_table_layout)

        self.table = QTableView()
        self.table.setSortingEnabled(True)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.table, 3)

        self.setLayout(layout)

        self.canvas.mpl_connect('pick_event', self.on_pie_click)
        self.category_table.clicked.connect(self.on_category_table_click)

    def refresh(self):
        self.current_selected_category = None
        self.category_label.setText("Click a segment to see transactions")
        self.load_data()
        self.draw_pie()
        self.populate_category_table()
        self.table.setModel(None)

    def load_data(self):
        cursor = self.db_conn.cursor()
        amount_col = 'paid_out' if self.is_paid_out else 'paid_in'
        query = f'''
            SELECT t.id, t.date, t.transaction_type, t.description, t.{amount_col}, cg.category, cg.essential
            FROM transactions t
            LEFT JOIN categorised cg ON t.id = cg.transaction_id
            WHERE t.{amount_col} > 0
        '''
        # apply essential filter (treat NULL as 'N')
        if self.essential_filter == 'Y':
            query = query.strip() + f" AND COALESCE(cg.essential,'N') = 'Y'"
        elif self.essential_filter == 'N':
            query = query.strip() + f" AND COALESCE(cg.essential,'N') = 'N'"
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = ['id', 'date', 'transaction_type', 'description', amount_col, 'category', 'essential']
        df = pd.DataFrame(rows, columns=columns)
        df['category'] = df['category'].fillna('Uncategorised')
        df['essential'] = df['essential'].fillna('N')
        if not self.use_full_category:
            df['category'] = df['category'].apply(lambda c: c.split(';')[0].strip())
        self.df = df
        self.amount_col = amount_col
        self.grouped = self.df.groupby('category')[amount_col].sum().sort_values(ascending=False)

    def draw_pie(self):
        self.ax.clear()
        if self.grouped.empty:
            self.ax.text(0.5, 0.5, "No data", ha='center', va='center')
            self.canvas.draw()
            return
        wedges, _, _ = self.ax.pie(
            self.grouped.values,
            labels=self.grouped.index,
            autopct='%1.1f%%',
            startangle=140,
            wedgeprops={'picker': True}
        )
        self.wedges = wedges
        self.categories = self.grouped.index.tolist()
        self.canvas.draw()

    def populate_category_table(self):
        cat_df = pd.DataFrame({
            "Category": self.grouped.index,
            "Amount": self.grouped.values
        })
        self.category_model = PandasModel(cat_df)
        self.category_table.setModel(self.category_model)
        self.category_table.setSortingEnabled(True)

    def on_pie_click(self, event):
        wedge = event.artist
        if wedge not in self.wedges:
            return
        idx = self.wedges.index(wedge)
        category = self.categories[idx]
        self.select_category(category)

    def on_category_table_click(self, index):
        # Convert the view index to model index in case of sorting
        model_index = self.category_table.model().index(index.row(), 0)
        category = self.category_table.model().data(model_index, Qt.ItemDataRole.DisplayRole)
        self.select_category(category)

    def select_category(self, category):
        if category == self.current_selected_category:
            return
        self.current_selected_category = category
        self.category_label.setText(f"Transactions in category: {category}")
        filtered = self.df[self.df['category'] == category]
        tx_df = filtered[['date', 'transaction_type', 'description', self.amount_col, 'essential']].copy()
        tx_df.columns = ["Date", "Transaction Type", "Description", "Amount", "Essential"]
        model = PandasModel(tx_df)
        self.table.setModel(model)
        self.table.resizeColumnsToContents()

    def set_essential_filter(self, mode):
        # mode: 'ALL', 'Y', 'N'
        if mode not in ('ALL', 'Y', 'N'):
            return
        self.essential_filter = mode
        self.refresh()


class MainWindow(QWidget):
    def __init__(self, db_conn):
        super().__init__()
        self.db_conn = db_conn
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Bank Transactions Categorisation")
        main_layout = QVBoxLayout()

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

        # Essential filter radio buttons
        self.essential_label = QLabel("Essential filter:")
        top_controls.addWidget(self.essential_label)
        self.essential_all = QRadioButton("All")
        self.essential_yes = QRadioButton("Essential only")
        self.essential_no = QRadioButton("Non-essential only")
        self.essential_all.setChecked(True)
        self.essential_group = QButtonGroup()
        self.essential_group.addButton(self.essential_all)
        self.essential_group.addButton(self.essential_yes)
        self.essential_group.addButton(self.essential_no)
        top_controls.addWidget(self.essential_all)
        top_controls.addWidget(self.essential_yes)
        top_controls.addWidget(self.essential_no)

        main_layout.addLayout(top_controls)

        self.chart_container = QVBoxLayout()
        main_layout.addLayout(self.chart_container)

        self.setLayout(main_layout)

        self.pie_out = PieChartWithTable(self.db_conn, is_paid_out=True, use_full_category=True)
        self.pie_in = PieChartWithTable(self.db_conn, is_paid_out=False, use_full_category=True)

        self.chart_container.addWidget(self.pie_out)
        self.chart_container.addWidget(self.pie_in)
        self.pie_in.hide()

        self.checkbox.stateChanged.connect(self.on_checkbox_change)
        self.radio_paid_out.toggled.connect(self.on_radio_change)
        self.essential_all.toggled.connect(self.on_essential_change)
        self.essential_yes.toggled.connect(self.on_essential_change)
        self.essential_no.toggled.connect(self.on_essential_change)

        # initialise filter state on pies
        self.pie_out.set_essential_filter('ALL')
        self.pie_in.set_essential_filter('ALL')

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
        self.on_checkbox_change()

    def on_essential_change(self):
        if self.essential_all.isChecked():
            mode = 'ALL'
        elif self.essential_yes.isChecked():
            mode = 'Y'
        else:
            mode = 'N'
        # apply to both pie widgets
        self.pie_out.set_essential_filter(mode)
        self.pie_in.set_essential_filter(mode)


def main():
    app = QApplication(sys.argv)
    db_conn = sqlite3.connect(DB_FILE)
    main_win = MainWindow(db_conn)
    main_win.resize(1400, 800)
    main_win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

