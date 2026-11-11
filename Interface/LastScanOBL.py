"""Сканы текущего сеанса без вымышленных тестовых записей."""
import re
from datetime import datetime
import customtkinter as ctk


class LastScanOBL:
    def __init__(self, parent):
        self.parent, self.on_record_click = parent, None
        self.history, self.rows = [], []

    def draw(self):
        self.parent.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.parent, text='Последние сканирования',
                     font=('Segoe UI', 18, 'bold')).grid(
            row=0, column=0, sticky='w', padx=18, pady=(14, 7))
        self.list_frame = ctk.CTkFrame(self.parent, fg_color='transparent')
        self.list_frame.grid(row=1, column=0, sticky='nsew', padx=10)
        self.history_button = ctk.CTkButton(
            self.parent, text='Вся история сеанса', height=32,
            fg_color='transparent', border_width=1, border_color='#46546A',
            command=self.show_history)
        self.history_button.grid(row=2, column=0, sticky='ew', padx=14, pady=(5, 10))
        self.refresh()

    @staticmethod
    def preview(code):
        return re.sub(r'[\x00-\x1f]', '·', code)[:28]

    def add_scan(self, code):
        self.history.insert(0, (code, datetime.now().strftime('%d.%m.%Y %H:%M:%S')))
        self.refresh()

    def refresh(self):
        for row in self.rows:
            row.destroy()
        self.rows = []
        if not self.history:
            label = ctk.CTkLabel(self.list_frame, text='Пока нет сканирований',
                                 text_color='#8E9CAF')
            label.pack(anchor='w', padx=8)
            self.rows.append(label)
        for code, timestamp in self.history[:3]:
            row = ctk.CTkFrame(self.list_frame, fg_color='transparent')
            row.pack(fill='x', pady=2)
            label = ctk.CTkLabel(row, text=self.preview(code), anchor='w',
                                 font=('Segoe UI', 12, 'bold'))
            label.pack(side='left', fill='x', expand=True, padx=(8, 4))
            ctk.CTkLabel(row, text=timestamp[11:16], text_color='#8E9CAF').pack(
                side='right', padx=(4, 8))
            for widget in (row, label):
                widget.bind('<Button-1>', lambda _, value=code: self.open_record(value))
            self.rows.append(row)

    def show_history(self):
        window = ctk.CTkToplevel(self.parent)
        window.title('История сканирования — текущий сеанс')
        window.geometry('650x420')
        frame = ctk.CTkScrollableFrame(window)
        frame.pack(fill='both', expand=True, padx=12, pady=12)
        for code, when in self.history:
            ctk.CTkButton(frame, text=when + '  ' + self.preview(code), anchor='w',
                          fg_color='transparent', command=lambda value=code:
                          self.open_record(value)).pack(fill='x', pady=2)

    def open_record(self, code):
        if self.on_record_click:
            self.on_record_click(code)
