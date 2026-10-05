from pathlib import Path

import customtkinter as ctk
from PIL import Image


class ControlPanelUser:
    SECTIONS = (
        ("ИЗДЕЛИЯ", (
            ("products", "Изделия"),
            ("categories", "Категории"),
            ("warehouse", "Склады"),
        )),
        ("СКАНИРОВАНИЕ", (
            ("scanner", "Сканер"),
            ("history", "История"),
        )),
        ("ГЕНЕРАЦИЯ КОДОВ", (
            ("generate", "Генерация кодов"),
            ("templates", "Шаблоны"),
            ("new_template", "Новый шаблон"),
        )),
        ("СИСТЕМА", (
            ("users", "Пользователи"),
            ("settings", "Настройки"),
            ("log", "Журнал изменений"),
        )),
    )

    # Инициализация панели
    def __init__(self, parent, status_var):
        self.parent, self.status_var = parent, status_var
        self.buttons = {}
        self.products_count = ctk.IntVar(value=0)
        self.scanner_status_label = None
        self.icons = self.load_icons(
            name for _, items in self.SECTIONS for name, _ in items
        )

    # Загрузка иконок
    def load_icons(self, names):
        path = Path(__file__).resolve().parent.parent / "icons"
        return {
            name: ctk.CTkImage(Image.open(path / f"{name}.png"), size=(22, 22))
            for name in names
        }

    # Отрисовка панели
    def draw(self):
        self.draw_title(self.parent)
        for title, buttons in self.SECTIONS:
            self.draw_section(self.parent, title, buttons)
        self.draw_status(self.parent)

    # Отрисовка заголовка
    def draw_title(self, parent):
        ctk.CTkLabel(
            parent, text="Панель управления",
            font=("Segoe UI", 18, "bold")
        ).pack(anchor="w", padx=14, pady=(20, 15))

    # Отрисовка раздела
    def draw_section(self, parent, title, buttons):
        ctk.CTkLabel(
            parent, text=title,
            font=("Segoe UI", 12, "bold"),
            text_color="#7F8EA3"
        ).pack(anchor="w", padx=14, pady=(11, 4))

        for name, text in buttons:
            self.draw_button(parent, name, text)

    # Создание кнопки панели
    def draw_button(self, parent, name, text, state="normal"):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=7, pady=1)

        self.buttons[name] = ctk.CTkButton(
            row, text=text, image=self.icons[name],
            compound="left", anchor="w", height=38,
            font=("Segoe UI", 14, "bold"),
            fg_color="transparent", hover_color="#2A3546",
            text_color="#E7EDF6", corner_radius=6, state=state
        )
        self.buttons[name].pack(side="left", fill="x", expand=True)

        if name == "products":
            ctk.CTkLabel(
                row, textvariable=self.products_count,
                width=28, height=22,
                font=("Segoe UI", 12, "bold"),
                fg_color="#344256",
                text_color="#E7EDF6",
                corner_radius=11
            ).pack(side="right", padx=4)

        elif name == "scanner":
            self.scanner_status_label = ctk.CTkLabel(
                row, text="●", width=28,
                font=("Segoe UI", 18),
                text_color="#EF6464"
            )
            self.scanner_status_label.pack(side="right", padx=4)

    # Отрисовка статуса подключения
    def draw_status(self, parent):
        self.status_label = ctk.CTkLabel(
            parent, textvariable=self.status_var,
            font=("Segoe UI", 12),
            text_color="#EF6464", anchor="w"
        )
        self.status_label.pack(
            side="bottom", fill="x",
            padx=14, pady=(10, 18)
        )

    # Изменение статуса сканера
    def set_scanner_status(self, connected):
        self.scanner_status_label.configure(
            text_color="#4ADE80" if connected else "#EF6464"
        )


class AdminControlPanel(ControlPanelUser):
    ADMIN_BUTTONS = (
        ("add_table", "Добавить таблицу"),
        ("delete_table", "Удалить таблицу"),
        ("add_record", "Добавить запись"),
        ("add_column", "Добавить столбец"),
        ("delete_column", "Удалить столбец"),
    )

    # Инициализация административной панели
    def __init__(self, parent, status_var):
        super().__init__(parent, status_var)
        self.icons.update(
            self.load_icons(name for name, _ in self.ADMIN_BUTTONS)
        )

    # Отрисовка административной панели
    def draw(self):
        status = ctk.CTkFrame(
            self.parent, fg_color="#202938", corner_radius=0
        )
        status.pack(side="bottom", fill="x")
        self.draw_status(status)

        scroll = ctk.CTkScrollableFrame(
            self.parent, fg_color="transparent", corner_radius=0,
            scrollbar_button_color="#344256",
            scrollbar_button_hover_color="#46546A"
        )
        scroll.pack(fill="both", expand=True)

        self.draw_title(scroll)
        self.draw_admin_section(scroll)

        for title, buttons in self.SECTIONS:
            self.draw_section(scroll, title, buttons)

    # Отрисовка блока редактирования таблиц
    def draw_admin_section(self, parent):
        ctk.CTkLabel(
            parent, text="РЕДАКТИРОВАНИЕ ТАБЛИЦ",
            font=("Segoe UI", 12, "bold"),
            text_color="#7F8EA3"
        ).pack(anchor="w", padx=14, pady=(5, 6))

        self.table_menu = ctk.CTkOptionMenu(
            parent, values=["Выбрать таблицу"], height=38,
            fg_color="#151F2D", button_color="#285DAC",
            dropdown_fg_color="#202938",
            dynamic_resizing=False
        )
        self.table_menu.pack(fill="x", padx=14, pady=(0, 5))
        self.table_menu.set("Выбрать таблицу")

        for name, text in self.ADMIN_BUTTONS:
            self.draw_button(
                parent, name, text,
                "normal" if name == "add_table" else "disabled"
            )