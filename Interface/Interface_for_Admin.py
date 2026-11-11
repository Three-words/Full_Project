
"""Главное окно Code Studio. Логика приложения находится в контроллерах."""
import tkinter as tk
import customtkinter as ctk

from Controllers.Connect import BD
from Controllers.MainController import MainController
from Interface.ControlPanel import AdminControlPanel
from Interface.CenterOBL import CenterOBL
from Interface.ScannerOBL import ScannerOBL
from Interface.ManualInputOBL import ManualInputOBL
from Interface.LastScanOBL import LastScanOBL
from Interface.QuickActionsOBL import QuickActionsOBL
from Interface.RightPanelOBL import DetailsOBL, NotesOBL

RIGHT_WIDTH = 392


class App(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode('dark')
        super().__init__()
        self.title('Code Studio')
        self.geometry('1400x850')
        self.minsize(1100, 650)
        self.configure(fg_color='#141A23')
        self.card = '#202938'
        self.connection_status = ctk.StringVar(value='Подключение...')
        self.grid_columnconfigure(0, minsize=210)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, minsize=RIGHT_WIDTH)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, minsize=220)
        self.create_layout()

        self.control_panel = self.create_view(AdminControlPanel, self.left, self.connection_status)
        self.center_obl = self.create_view(CenterOBL, self.main_area, self.card)
        self.scanner_obl = self.create_view(ScannerOBL, self.bottom_1, self.card)
        self.manual_input = self.create_view(ManualInputOBL, self.bottom_2)
        self.last_scan = self.create_view(LastScanOBL, self.bottom_3)
        self.details = self.create_view(DetailsOBL, self.right_1)
        self.notes = self.create_view(NotesOBL, self.right_2)
        self.quick_actions = self.create_view(QuickActionsOBL, self.right_3)

        self.close_right = ctk.CTkButton(self.right_1, text='×', width=25, height=25,
                                         font=('Segoe UI', 18), fg_color='transparent',
                                         hover_color='#34465D')
        self.close_right.place(relx=1, x=-10, y=9, anchor='ne')
        self.close_right.lift()

        self.bd = BD(self)
        self.controller = MainController(
            self.bd, self.control_panel, self.center_obl, self.quick_actions,
            self.scanner_obl, self.manual_input, self.details, self.notes)
        self.controller.right_panel.bind_layout(self.panes, self.right, self.open_right, self.close_right)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bd.Connect_BD()
        if self.bd.open:
            self.controller.initialize()

    @staticmethod
    def create_view(view, parent, *args):
        widget = view(parent, *args)
        widget.draw()
        return widget

    def area(self, parent, row, column, color=None):
        frame = ctk.CTkFrame(parent, fg_color=color or self.card, corner_radius=12)
        frame.grid(row=row, column=column, sticky='nsew', padx=4, pady=4)
        return frame

    #===== Размещение панелей =====
    def create_layout(self):
        self.left = self.area(self, 0, 0)
        self.left.grid_configure(rowspan=2)
        self.left.configure(width=210)
        self.left.grid_propagate(False)

        self.workspace = ctk.CTkFrame(self, fg_color='transparent')
        self.workspace.grid(row=0, column=1, columnspan=2, sticky='nsew', padx=(4, 0), pady=(4, 0))
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(0, weight=1)
        self.panes = tk.PanedWindow(self.workspace, orient='horizontal', sashwidth=7,
                                    showhandle=False, bg='#344256', bd=0)
        self.panes.grid(row=0, column=0, sticky='nsew')

        self.open_right = tk.Canvas(self.workspace, width=38, height=168, bg='#141A23',
                                    bd=0, highlightthickness=0, cursor='hand2')
        self.open_right.create_polygon(
            8, 8, 28, 8, 34, 8, 34, 16, 34, 148, 34, 156, 28, 156,
            8, 156, 3, 156, 3, 148, 3, 16, 3, 8, smooth=True,
            fill='#30445D', outline='#53749A', width=1, tags='tab')
        self.open_right.create_text(19, 82, text='Свойства', angle=270,
                                    font=('Segoe UI', 11, 'bold'), fill='#F2F6FC')

        self.center = ctk.CTkFrame(self.panes, fg_color='transparent')
        self.right = ctk.CTkFrame(self.panes, fg_color='transparent', width=RIGHT_WIDTH)
        self.panes.add(self.center, minsize=420, stretch='always')
        self.panes.add(self.right, minsize=240, width=RIGHT_WIDTH, stretch='never')
        for frame in (self.center, self.right):
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_rowconfigure(0, weight=1)

        self.main_area = self.area(self.center, 0, 0)
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(1, weight=1)
        self.right.grid_rowconfigure(1, minsize=190)
        self.right_1, self.right_2 = self.area(self.right, 0, 0), self.area(self.right, 1, 0)
        self.right_2.configure(height=190)
        self.right_2.grid_propagate(False)

        self.bottom = self.area(self, 1, 1, 'transparent')
        self.bottom.configure(height=220)
        self.bottom.grid_propagate(False)
        self.bottom.grid_rowconfigure(0, weight=1)
        for col in range(3):
            self.bottom.grid_columnconfigure(col, weight=1, uniform='bottom')
        self.bottom_1, self.bottom_2, self.bottom_3 = (
            self.area(self.bottom, 0, col) for col in range(3))

        self.right_3 = self.area(self, 1, 2)
        self.right_3.grid_propagate(False)

    def set_status(self, text, color):
        self.connection_status.set('•  ' + text)
        self.control_panel.status_label.configure(text_color=color)

    def close(self):
        self.controller.scanner.disconnect()
        self.bd.Disconnect_BD()
        self.destroy()
