
import customtkinter as ctk
from tkinter import messagebox


class AddRecordWindow(ctk.CTkToplevel):
    TITLE, HEADER, ACTION = "Добавление записи", "Добавление новой записи", "Добавить"

    def __init__(self, parent, table_name, fields, on_action,
                 type_names=None, on_type_select=None):
        super().__init__(parent)
        self.entries, self.on_action = {}, on_action
        self.title(f"{self.TITLE}: {table_name}")
        self.geometry("520x550")
        self.minsize(450, 400)
        self.transient(parent)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.draw(fields, type_names, on_type_select)
        self.grab_set()
        self.focus()

    def draw(self, fields, type_names, on_type_select):
        ctk.CTkLabel(self, text=self.HEADER, font=("Segoe UI", 18, "bold")
                     ).grid(row=0, column=0, pady=(20, 10))

        form = ctk.CTkScrollableFrame(self)
        form.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        if type_names is not None:
            frame = ctk.CTkFrame(form, fg_color="#273346", corner_radius=8)
            frame.pack(fill="x", pady=(0, 12))

            ctk.CTkLabel(frame, text="Вид изделия", font=("Segoe UI", 14, "bold")
                         ).pack(anchor="w", padx=12, pady=(10, 6))

            self.type_menu = ctk.CTkOptionMenu(
                frame, values=["Ввод вручную", *type_names],
                command=on_type_select, height=36, dynamic_resizing=False
            )
            self.type_menu.pack(fill="x", padx=10, pady=(0, 10))
            self.type_menu.set("Выберите вид изделия")

        for name, hint, required in fields:
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=6)

            ctk.CTkLabel(row, text=f"{name} *" if required else name,
                         width=150, anchor="w").pack(side="left", padx=(0, 10))

            entry = ctk.CTkEntry(row, height=36, placeholder_text=hint)
            entry.pack(side="left", fill="x", expand=True)
            self.entries[name] = entry

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(5, 20))

        for text, command, color in self.buttons():
            ctk.CTkButton(frame, text=text, command=command, fg_color=color
                          ).pack(side="left", fill="x", expand=True, padx=4)

    def set_fields(self, values, disabled=False):
        for name, value in values.items():
            entry = self.entries.get(name)
            if entry is None:
                continue
            entry.configure(state="normal")
            entry.delete(0, "end")
            if value is not None:
                entry.insert(0, str(value))
            if disabled:
                entry.configure(state="disabled")

    def get_values(self):
        return {name: entry.get().strip() for name, entry in self.entries.items()}

    def buttons(self):
        return ((self.ACTION, self.on_action, "#285DAC"),
                ("Отмена", self.destroy, "#344256"))


class EditRecordWindow(AddRecordWindow):
    TITLE, ACTION = "Редактирование записи", "Сохранить"

    def __init__(self, parent, table_name, values, on_save, on_delete):
        self.record_id, self.on_delete = values["id"], on_delete
        self.HEADER = f"Редактирование записи\nID: {self.record_id}"
        super().__init__(parent, table_name,
                         [(name, "", False) for name in values if name != "id"], on_save)
        self.set_fields({name: value for name, value in values.items() if name != "id"})

    def buttons(self):
        return ((self.ACTION, self.on_action, "#285DAC"),
                ("Удалить", self.confirm_delete, "#B33A3A"),
                ("Отмена", self.destroy, "#344256"))

    def confirm_delete(self):
        if messagebox.askyesno("Удаление записи",
                               f"Удалить запись ID: {self.record_id}?", parent=self):
            self.on_delete()
