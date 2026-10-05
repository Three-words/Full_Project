import customtkinter as ctk
from tksheet import Sheet


class ColumnsMenu:

    def __init__(self, parent, card="#202938"):
        self.parent, self.card = parent, card
        self.popup, self.on_apply = None, None
        self.columns, self.selection = [], {}

    # Обновление списка столбцов
    def set_columns(self, columns):
        self.columns = columns
        self.selection = {
            col: ctk.BooleanVar(value=True)
            for col in columns
        }

    # Открытие / закрытие меню
    def toggle(self, button):
        self.close() if self.popup else self.open(button)

    # Открытие меню
    def open(self, button):
        self.parent.update_idletasks()
        y = button.winfo_rooty() - self.parent.winfo_rooty() + button.winfo_height() + 5

        height = min(
            min(210, max(65, len(self.columns) * 36)) + 165,
            max(190, self.parent.winfo_height() - y - 8)
        )

        self.popup = ctk.CTkFrame(
            self.parent, width=280, height=height,
            fg_color=self.card, border_width=1,
            border_color="#46546A", corner_radius=10
        )
        self.popup.pack_propagate(False)

        ctk.CTkLabel(
            self.popup, text="Отображаемые столбцы",
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w", padx=15, pady=(10, 6))

        frame = ctk.CTkScrollableFrame(self.popup, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=8)

        for col in self.columns:
            ctk.CTkCheckBox(
                frame, text=col, variable=self.selection[col],
                font=("Segoe UI", 13), checkbox_width=21,
                checkbox_height=21, fg_color="#285DAC"
            ).pack(anchor="w", fill="x", padx=6, pady=4)

        self.draw_buttons((
            ("Выбрать все", lambda: self.select_all(True), "#344256"),
            ("Снять все", lambda: self.select_all(False), "#344256")
        ), (8, 4))

        self.error = ctk.CTkLabel(
            self.popup, text="", height=18, text_color="#EF6464"
        )
        self.error.pack()

        self.draw_buttons((
            ("Применить", self.apply, "#285DAC"),
            ("Отмена", self.close, "#344256")
        ))

        self.popup.place(relx=1, x=-8, y=y, anchor="ne")
        self.popup.lift()

    # Отрисовка кнопок
    def draw_buttons(self, buttons, pady=(0, 10)):
        frame = ctk.CTkFrame(self.popup, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=pady)

        for text, command, color in buttons:
            ctk.CTkButton(
                frame, text=text, command=command,
                fg_color=color, width=105, height=30
            ).pack(side="left", fill="x", expand=True, padx=4)

    # Выбор / снятие всех столбцов
    def select_all(self, value):
        for var in self.selection.values():
            var.set(value)

    # Применение выбранных столбцов
    def apply(self):
        columns = [col for col in self.columns if self.selection[col].get()]

        if not columns:
            self.error.configure(text="Выберите хотя бы один столбец")
            return

        if self.on_apply:
            self.on_apply(columns)

        self.close()

    # Закрытие меню
    def close(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None


class CenterOBL:

    def __init__(self, parent, card="#202938"):
        self.parent, self.card = parent, card
        self.grid_color = "#46546A"
        self.table = None
        self.columns, self.widths = [], {}
        self.columns_menu = ColumnsMenu(parent, card)

    # Отрисовка центральной области
    def draw(self):
        self.draw_search()


    # ==================== ТАБЛИЦА ====================

    # Отрисовка таблицы
    def show_table(self, columns, rows, widths):
        self.clear_table()

        self.columns = list(columns)
        self.widths = dict(zip(columns, widths))

        self.search_column.configure(values=columns)
        self.search_column.set(columns[0] if columns else "Столбец")
        self.columns_menu.set_columns(columns)
        self.columns_button.configure(state="normal" if columns else "disabled")

        self.table = Sheet(
            self.parent,
            data=[list(row) for row in rows],
            headers=columns,
            show_row_index=False,
            show_top_left=False,
            default_row_height=40,
            default_header_height=42,
            align="center",
            header_align="center",
            table_bg=self.card,
            table_fg="#E2E8F0",
            table_grid_fg=self.grid_color,
            header_bg="#344256",
            header_fg="white",
            header_grid_fg=self.grid_color,
            header_border_fg=self.grid_color,
            alternate_color="#2A3546",
            frame_bg=self.card,
            outline_thickness=0
        )

        self.table.font(("Segoe UI", 14, "normal"))
        self.table.header_font(("Segoe UI", 14, "bold"))

        for i, width in enumerate(widths):
            self.table.column_width(i, width=width, redraw=False)

        self.table.enable_bindings(
            "single_select",
            "arrowkeys",
            "column_width_resize",
            "double_click_column_resize"
        )

        self.table.grid(
            row=1, column=0, columnspan=2,
            sticky="nsew", padx=12, pady=(0, 12)
        )
        self.table.refresh()

    # Обновление строк
    def set_data(self, rows):
        if self.table:
            self.table.set_sheet_data(
                [list(row) for row in rows],
                reset_col_positions=False,
                reset_row_positions=True,
                redraw=True
            )

    # Изменение отображаемых столбцов
    def display_columns(self, columns):
        if not self.table:
            return

        if len(columns) == len(self.columns):
            self.table.display_columns("all", redraw=False)
        else:
            indexes = [self.columns.index(col) for col in columns]

            self.table.display_columns(
                indexes,
                all_columns_displayed=False,
                reset_col_positions=True,
                redraw=False
            )

        for i, col in enumerate(columns):
            self.table.column_width(
                i,
                width=self.widths[col],
                redraw=False
            )

        self.table.refresh()

    # Очистка таблицы
    def clear_table(self):
        if self.table:
            self.table.destroy()
            self.table = None


    # ==================== ПАНЕЛЬ ПОИСКА ====================

    # Отрисовка панели поиска
    def draw_search(self):
        search = ctk.CTkFrame(self.parent, fg_color="transparent")
        search.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        search.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            search, text="Поиск по:", font=("Segoe UI", 12)
        ).grid(row=0, column=0, padx=(0, 6))

        self.search_column = ctk.CTkOptionMenu(
            search, values=["Столбец"], width=110, height=34,
            fg_color="#151F2D", button_color="#285DAC",
            dropdown_fg_color=self.card, dynamic_resizing=False
        )
        self.search_column.grid(row=0, column=1, padx=(0, 6))

        self.search_entry = ctk.CTkEntry(
            search, height=34, placeholder_text="Введите значение"
        )
        self.search_entry.grid(row=0, column=2, sticky="ew", padx=(0, 6))

        buttons = (
            ("find_button", "Найти", "#285DAC", 64, {}),
            ("reset_button", "Сброс", "#344256", 64, {}),
            ("columns_button", "Столбцы ▾", "#344256", 112, {
                "hover_color": "#46546A",
                "state": "disabled",
                "command": lambda: self.columns_menu.toggle(self.columns_button)
            })
        )

        for col, (name, text, color, width, options) in enumerate(buttons, 3):
            button = ctk.CTkButton(
                search, text=text, width=width,
                height=34, fg_color=color, **options
            )
            button.grid(row=0, column=col, padx=(0, 6) if col < 5 else 0)
            setattr(self, name, button)