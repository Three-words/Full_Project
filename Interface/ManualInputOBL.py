
"""Поле ручного ввода кода и кнопка поиска."""
import customtkinter as ctk


class ManualInputOBL:
    def __init__(self, parent):
        self.parent = parent

    def draw(self):
        self.parent.grid_columnconfigure(0, weight=1)
        self.parent.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(self.parent, text='Ручной ввод кода',
                     font=('Segoe UI', 18, 'bold')).grid(
            row=0, column=0, sticky='w', padx=18, pady=(14, 7))
        ctk.CTkLabel(self.parent, text='Введите код вручную, если сканер недоступен',
                     font=('Segoe UI', 12), text_color='#7F8EA3').grid(
            row=1, column=0, sticky='w', padx=18, pady=(0, 10))

        field = ctk.CTkFrame(self.parent, height=42,
                             fg_color='#151F2D', corner_radius=7)
        field.grid(row=2, column=0, sticky='ew', padx=18)
        field.grid_columnconfigure(0, weight=1)
        self.code_entry = ctk.CTkEntry(
            field, placeholder_text='Введите код...', height=40,
            font=('Segoe UI', 13), fg_color='transparent', border_width=0)
        self.code_entry.grid(row=0, column=0, sticky='ew', padx=(5, 0))
        ctk.CTkLabel(field, text='⌨', width=38, font=('Segoe UI', 18),
                     text_color='#9AA8BA').grid(row=0, column=1, padx=(0, 4))

        self.search_button = ctk.CTkButton(
            self.parent, text='Найти изделие', height=32,
            font=('Segoe UI', 14, 'bold'), fg_color='transparent',
            hover_color='#2A3546', border_width=1,
            border_color='#46546A', corner_radius=6, text_color='#E7EDF6')
        self.search_button.grid(row=5, column=0, sticky='ew', padx=14, pady=(7, 10))

    def get_code(self):
        return self.code_entry.get().strip()

    def set_code(self, code):
        self.code_entry.delete(0, 'end')
        self.code_entry.insert(0, code)
