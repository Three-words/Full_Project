from tkinter import messagebox, font

from Controllers.SQL import SQL
from Interface.InterfaceRecord import AddRecordWindow


class ControllerForPannel:
    TABLE_BUTTONS = ("delete_table", "add_record", "add_column", "delete_column")

    # ==================== ИНИЦИАЛИЗАЦИЯ ====================

    def __init__(self, bd, panel, center):
        self.bd, self.panel, self.center = bd, panel, center
        self.table_name = None
        self.columns, self.visible_columns, self.rows = [], [], []

        panel.table_menu.configure(command=self.select_table)
        panel.buttons["add_record"].configure(command=self.open_add_record)

        center.find_button.configure(command=self.search)
        center.reset_button.configure(command=self.reset_search)
        center.search_entry.bind("<Return>", lambda _: self.search())
        center.columns_menu.on_apply = self.apply_columns


    # ==================== ПАНЕЛЬ УПРАВЛЕНИЯ ====================

    def load_tables(self):
        try:
            tables = SQL.get_tables(self.bd)
            self.panel.table_menu.configure(values=tables or ["Нет таблиц"])
            self.panel.table_menu.set("Выбрать таблицу" if tables else "Нет таблиц")
        except Exception as error:
            self.show_error("Не удалось получить список таблиц", error)

    def select_table(self, table_name):
        if table_name in ("Выбрать таблицу", "Нет таблиц"):
            return

        try:
            columns, rows = SQL.get_table_data(self.bd, table_name)

            self.table_name = table_name
            self.columns = self.visible_columns = list(columns)
            self.rows = self.prepare_rows(rows)

            self.center.show_table(
                columns,
                self.rows,
                self.column_widths(columns, self.rows)
            )

            for name in self.TABLE_BUTTONS:
                self.panel.buttons[name].configure(state="normal")

        except Exception as error:
            self.show_error("Не удалось загрузить таблицу", error)


    # ==================== ДОБАВЛЕНИЕ ЗАПИСИ ====================

    def open_add_record(self):
        if not self.table_name:
            return

        fields = [
            (col, f"Введите {col}")
            for col in self.columns
            if col != "id"
        ]

        window = AddRecordWindow(
            self.center.parent,
            self.table_name,
            fields,
            lambda: self.add_record(window)
        )

    def add_record(self, window):
        try:
            values = {
                col: value
                for col, value in window.get_values().items()
                if value
            }

            SQL.add_record(self.bd, self.table_name, values)
            window.destroy()
            self.select_table(self.table_name)

        except Exception as error:
            self.show_error("Не удалось добавить запись", error)


    # ==================== ЦЕНТРАЛЬНАЯ ТАБЛИЦА ====================

    def search(self):
        if not self.table_name:
            return

        text = self.center.search_entry.get().strip()

        if not text:
            return self.reset_search()

        try:
            rows = SQL.search_records(
                self.bd,
                self.table_name,
                self.center.search_column.get(),
                text
            )

            self.fill_table(
                self.prepare_rows(rows)
            )

        except Exception as error:
            self.show_error("Не удалось выполнить поиск", error)

    def reset_search(self):
        self.center.search_entry.delete(0, "end")
        self.fill_table(self.rows)

    def apply_columns(self, columns):
        self.visible_columns = columns
        self.center.display_columns(columns)

    def fill_table(self, rows):
        self.center.set_data(rows)

    @staticmethod
    def prepare_rows(rows):
        return [
            [
                "" if value is None
                else "[SVG]" if isinstance(value, str) and "<svg" in value[:200]
                else str(value)
                for value in row
            ]
            for row in rows
        ]

    @staticmethod
    def column_widths(columns, rows):
        regular = font.Font(family="Segoe UI", size=14)
        bold = font.Font(family="Segoe UI", size=14, weight="bold")

        return [
            max(
                [bold.measure(col)]
                + [regular.measure(row[i]) for row in rows]
            ) + 40
            for i, col in enumerate(columns)
        ]


    # ==================== СЛУЖЕБНЫЕ МЕТОДЫ ====================

    @staticmethod
    def show_error(text, error):
        messagebox.showerror("Ошибка", f"{text}:\n{error}")