import customtkinter as ctk


class AddTableWindow(ctk.CTkToplevel):
    TYPES = {
        "Целое число": "INTEGER",
        "Большое целое": "BIGINT",
        "Дробное число": "DOUBLE PRECISION",
        "Точное дробное": "NUMERIC",
        "Строка": "VARCHAR(255)",
        "Текст": "TEXT",
        "Логическое": "BOOLEAN",
        "Дата": "DATE",
        "Дата и время": "TIMESTAMP",
        "SVG": "TEXT",
        "XML": "XML",
        "JSON": "JSONB"
    }

    def __init__(self, parent, data_types, on_create):
        super().__init__(parent)
        self.columns, self.on_create = [], on_create
        self.title("Создание таблицы")
        self.geometry("700x550")
        self.minsize(620, 450)
        self.transient(parent)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.draw()
        self.add_column()
        self.grab_set()
        self.focus()

    # ==================== ИНТЕРФЕЙС ====================

    def draw(self):
        ctk.CTkLabel(self, text="Создание новой таблицы",
                     font=("Segoe UI", 18, "bold")
                     ).grid(row=0, column=0, columnspan=2, pady=(20, 10))

        ctk.CTkLabel(self, text="Название таблицы", width=150, anchor="w"
                     ).grid(row=1, column=0, padx=(20, 10), pady=10)

        self.table_name = ctk.CTkEntry(self, placeholder_text="Введите название")
        self.table_name.grid(row=1, column=1, sticky="ew", padx=(0, 20), pady=10)

        self.columns_frame = ctk.CTkScrollableFrame(self)
        self.columns_frame.grid(row=2, column=0, columnspan=2,
                                sticky="nsew", padx=20, pady=10)

        ctk.CTkButton(self, text="+ Добавить столбец",
                      command=self.add_column, fg_color="#344256"
                      ).grid(row=3, column=0, columnspan=2,
                             sticky="ew", padx=20, pady=5)

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=4, column=0, columnspan=2, sticky="ew",
                   padx=20, pady=(5, 20))

        for text, command, color in (
            ("Создать", self.on_create, "#285DAC"),
            ("Отмена", self.destroy, "#344256")
        ):
            ctk.CTkButton(frame, text=text, command=command, fg_color=color
                          ).pack(side="left", fill="x", expand=True, padx=4)

    # ==================== СТОЛБЦЫ ====================

    def add_column(self):
        row = ctk.CTkFrame(self.columns_frame, fg_color="#151F2D")
        row.pack(fill="x", pady=4)

        name = ctk.CTkEntry(row, placeholder_text="Название столбца")
        name.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=8)

        data_type = ctk.CTkOptionMenu(row, values=list(self.TYPES), width=165)
        data_type.pack(side="left", padx=4)

        unique = ctk.BooleanVar()
        ctk.CTkCheckBox(row, text="Уникальный", variable=unique, width=115
                        ).pack(side="left", padx=6)

        column = (row, name, data_type, unique)
        self.columns.append(column)

        ctk.CTkButton(
            row, text="×", width=35, fg_color="#B33A3A",
            command=lambda: (self.columns.remove(column), row.destroy())
        ).pack(side="left", padx=(4, 8))

    # ==================== ДАННЫЕ ====================

    def get_values(self):
        return {
            "table_name": self.table_name.get().strip(),
            "columns": [
                {"name": name.get().strip(),
                 "type": self.TYPES[data_type.get()],
                 "unique": unique.get()}
                for _, name, data_type, unique in self.columns
                if name.get().strip()
            ]
        }

class AddColumnWindow(ctk.CTkToplevel):
    """Небольшая универсальная форма добавления столбца."""

    def __init__(self, parent, on_create):
        super().__init__(parent)
        self.title('Добавление столбца')
        self.geometry('390x220')
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.name = ctk.CTkEntry(self, placeholder_text='Имя столбца')
        self.name.pack(fill='x', padx=20, pady=(25, 12))
        self.type = ctk.CTkOptionMenu(self, values=list(AddTableWindow.TYPES))
        self.type.pack(fill='x', padx=20)
        ctk.CTkButton(self, text='Добавить', command=lambda: on_create(
            self.name.get().strip(), AddTableWindow.TYPES[self.type.get()], self)).pack(
            fill='x', padx=20, pady=18)
