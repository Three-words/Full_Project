
"""Состояние COM-сканера и кнопки управления."""
from pathlib import Path
import customtkinter as ctk
from PIL import Image


class ScannerOBL:
    def __init__(self, parent, card='#202938'):
        self.parent = parent
        self.status = ctk.StringVar(value='• Не подключен ')
        self.model = ctk.StringVar(value='Модель: —')
        self.port = ctk.StringVar(value='Порт: —')

    def draw(self):
        self.parent.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.parent, text='Сканер штрих-кодов',
                     font=('Segoe UI', 18, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', padx=18, pady=(14, 7))

        for row, variable, size, options in (
            (1, self.status, 12, {'text_color': '#EF6464', 'fg_color': '#3A252B',
                                  'corner_radius': 7, 'height': 25}),
            (2, self.model, 12, {'anchor': 'w', 'justify': 'left', 'wraplength': 165}),
            (3, self.port, 13, {'anchor': 'w'})
        ):
            label = ctk.CTkLabel(self.parent, textvariable=variable,
                                 font=('Segoe UI', size, 'bold'), **options)
            label.grid(row=row, column=0, sticky='w', padx=18,
                       pady=(0, 4) if row == 1 else 1)
            if row == 1:
                self.status_label = label

        path = Path(__file__).resolve().parent.parent / 'icons' / 'scanner1.png'
        if path.is_file():
            self.icon = ctk.CTkImage(Image.open(path), size=(85, 105))
            ctk.CTkLabel(self.parent, text='', image=self.icon).grid(
                row=1, column=1, rowspan=3, sticky='e', padx=(4, 14))

        frame = ctk.CTkFrame(self.parent, fg_color='transparent')
        frame.grid(row=4, column=0, columnspan=2, sticky='ew', padx=14, pady=(7, 10))
        style = {'height': 32, 'font': ('Segoe UI', 14, 'bold'),
                 'fg_color': 'transparent', 'hover_color': '#2A3546',
                 'border_width': 1, 'border_color': '#46546A',
                 'corner_radius': 6, 'text_color': '#E7EDF6'}
        for title, name in (('Тест сканера', 'test_button'),
                            ('Отключить', 'disconnect_button')):
            button = ctk.CTkButton(frame, text=title, **style)
            button.pack(side='left', fill='x', expand=True, padx=4)
            setattr(self, name, button)

    def set_info(self, connected, model='—', port='—'):
        color, bg = ('#4ADE80', '#20372D') if connected else ('#EF6464', '#3A252B')
        self.status.set('• Подключен ' if connected else '• Не подключен ')
        self.status_label.configure(text_color=color, fg_color=bg)
        self.model.set('Модель: ' + model)
        self.port.set('Порт: ' + port)
