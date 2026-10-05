import customtkinter as ctk

from Controllers.Connect import BD
from Controllers.Command import Commands
from Interface.ControlPanel import AdminControlPanel
from Interface.CenterOBL import CenterOBL
from Controllers.ControllerForPannel import ControllerForPannel


class App(ctk.CTk):

    # Инициализация главного окна и основных компонентов приложения
    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__()

        self.title("Code Studio")
        self.geometry("1400x850")
        self.minsize(1100, 650)
        self.configure(fg_color="#141A23")

        self.card = "#202938"
        self.connection_status = ctk.StringVar(value="Подключение...")

        for i, width in enumerate((210, 0, 280)):
            self.grid_columnconfigure(i, minsize=width, weight=i == 1)
        self.grid_rowconfigure(0, weight=1)

        self.create_layout()

        # Вот тут нужно будет сделать условие выбора панели для пользователя или для админа 
        self.control_panel = AdminControlPanel(
            self.left,
            self.connection_status
        )
        self.control_panel.draw()

        self.center_obl = CenterOBL(
            self.main_area,
            self.card
        )
        self.center_obl.draw()

        self.bd = BD(self)
        self.commands = Commands(self)

        self.panel_controller = ControllerForPannel(
            self.bd,
            self.control_panel,
            self.center_obl
        )

        self.bd.Connect_BD()

        if self.bd.open:
            self.panel_controller.load_tables()

        self.protocol(
            "WM_DELETE_WINDOW",
            self.commands.close_window
        )

    # Создание универсального блока интерфейса
    def area(self, parent, row, column, color=None):
        frame = ctk.CTkFrame(
            parent,
            fg_color=color or self.card,
            corner_radius=12
        )
        frame.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=4,
            pady=4
        )
        return frame

    # Создание основной разметки главного окна
    def create_layout(self):
        self.left = self.area(self, 0, 0)
        self.left.configure(width=210)
        self.left.grid_propagate(False)

        self.center = self.area(self, 0, 1, "transparent")
        self.center.grid_columnconfigure(0, weight=1)

        for row, weight in enumerate((12, 1)):
            self.center.grid_rowconfigure(row, weight=weight)

        self.main_area = self.area(self.center, 0, 0)
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(1, weight=1)

        self.bottom = self.area(self.center, 1, 0, "transparent")
        self.right = self.area(self, 0, 2, "transparent")

        self.right.configure(width=280)
        self.right.grid_propagate(False)

        self.bottom.grid_rowconfigure(0, weight=1)
        self.right.grid_columnconfigure(0, weight=1)

        for i in range(3):
            self.bottom.grid_columnconfigure(i, weight=1)
            self.right.grid_rowconfigure(i, weight=1)

            setattr(
                self,
                f"bottom_{i + 1}",
                self.area(self.bottom, 0, i)
            )

            setattr(
                self,
                f"right_{i + 1}",
                self.area(self.right, i, 0)
            )

    # Получение текущей таблицы из центральной области
    @property
    def table(self):
        return self.center_obl.table

    # Получение горизонтальной полосы прокрутки
    @property
    def scrollbar_x(self):
        return self.center_obl.scrollbar_x

    # Получение выбранного столбца поиска
    @property
    def search_column(self):
        return self.center_obl.search_column

    # Получение поля ввода поиска
    @property
    def search_entry(self):
        return self.center_obl.search_entry

    # Очистка текущей таблицы
    def clear_view(self):
        self.center_obl.clear_table()

    # Обновление статуса подключения к базе данных
    def set_status(self, text, color):
        self.connection_status.set(f"•  {text}")
        self.control_panel.status_label.configure(text_color=color)