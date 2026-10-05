import customtkinter as ctk


class AddRecordWindow(ctk.CTkToplevel):

    # Инициализация окна добавления записи
    def __init__(self, parent, table_name, fields, on_add):
        super().__init__(parent)

        self.entries = {}
        self.on_add = on_add

        self.title(f"Добавление записи: {table_name}")
        self.geometry("520x550")
        self.minsize(450, 400)
        self.transient(parent)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.draw(fields)

        self.grab_set()
        self.focus()

    # Отрисовка интерфейса окна
    def draw(self, fields):
        ctk.CTkLabel(
            self,
            text="Добавление новой записи",
            font=("Segoe UI", 18, "bold")
        ).grid(row=0, column=0, pady=(20, 10))

        form = ctk.CTkScrollableFrame(self)
        form.grid(
            row=1, column=0,
            sticky="nsew",
            padx=20, pady=10
        )

        for name, hint in fields:
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=6)

            ctk.CTkLabel(
                row,
                text=name,
                width=150,
                anchor="w"
            ).pack(side="left", padx=(0, 10))

            entry = ctk.CTkEntry(
                row,
                height=36,
                placeholder_text=hint
            )
            entry.pack(side="left", fill="x", expand=True)

            self.entries[name] = entry

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(
            row=2, column=0,
            sticky="ew",
            padx=20, pady=(5, 20)
        )

        ctk.CTkButton(
            buttons,
            text="Добавить",
            command=self.on_add,
            fg_color="#285DAC"
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(
            buttons,
            text="Отмена",
            command=self.destroy,
            fg_color="#344256"
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

    # Получение введённых пользователем значений
    def get_values(self):
        return {
            name: entry.get().strip()
            for name, entry in self.entries.items()
        }