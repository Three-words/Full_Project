
"""Окно просмотра этикетки или каталога SVG-шаблонов."""
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

BACKGROUND, PANEL = '#141A23', '#202938'


class SVGViewer(ctk.CTkToplevel):
    #===== Создание окна этикетки или каталога =====
    def __init__(self, parent, on_save=None, titles=None, on_select=None):
        root = parent.winfo_toplevel()
        super().__init__(root)
        self.withdraw()
        self.transient(root)
        self.configure(fg_color=BACKGROUND)
        self.photo = self.item = self.size = None
        catalog = titles is not None
        self.title('Шаблоны этикеток' if catalog else 'Просмотр этикетки')
        self.geometry('930x650' if catalog else '820x700')
        self.minsize(*(720, 500) if catalog else (480, 380))
        self.grid_columnconfigure(1 if catalog else 0, weight=1)
        self.grid_rowconfigure(0 if catalog else 1, weight=1)

        if catalog:
            sidebar = ctk.CTkScrollableFrame(self, width=255, fg_color=PANEL)
            sidebar.grid(row=0, column=0, sticky='nsew', padx=(12, 6), pady=12)
            ctk.CTkLabel(sidebar, text='Типы этикеток', font=('Segoe UI', 18, 'bold')).pack(
                anchor='w', padx=10, pady=(12, 14))
            self.buttons = []
            for index, title in enumerate(titles):
                button = ctk.CTkButton(sidebar, text=title, anchor='w', height=38,
                                       fg_color='transparent', hover_color='#315781',
                                       command=lambda i=index: on_select(i))
                button.pack(fill='x', padx=5, pady=3)
                self.buttons.append(button)

            area = ctk.CTkFrame(self, fg_color=PANEL)
            area.grid(row=0, column=1, sticky='nsew', padx=(6, 12), pady=12)
            area.grid_columnconfigure(0, weight=1)
            area.grid_rowconfigure(2, weight=1)
            self.heading = ctk.CTkLabel(area, text='', font=('Segoe UI', 20, 'bold'))
            self.heading.grid(row=0, column=0, sticky='w', padx=22, pady=(16, 4))
            self.info = ctk.CTkLabel(area, text='', text_color='#9BACBF')
            self.info.grid(row=1, column=0, sticky='w', padx=22)
            canvas_parent, canvas_row = area, 2
            ctk.CTkLabel(area, text='Исходный макет SVG · тестовые данные',
                         text_color='#9BACBF', font=('Segoe UI', 12)).grid(
                row=3, column=0, pady=(0, 12))
        else:
            self.protocol('WM_DELETE_WINDOW', self.withdraw)
            bar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
            bar.grid(row=0, column=0, sticky='ew')
            bar.grid_columnconfigure(0, weight=1)
            self.heading = ctk.CTkLabel(bar, text='Просмотр этикетки', anchor='w')
            self.heading.grid(row=0, column=0, sticky='ew', padx=16, pady=12)
            ctk.CTkButton(bar, text='Сохранить SVG', width=130,
                          command=on_save).grid(row=0, column=1, padx=12)
            canvas_parent, canvas_row = self, 1

        self.canvas = tk.Canvas(canvas_parent, bg='#17212F', highlightthickness=0)
        self.canvas.grid(row=canvas_row, column=0, sticky='nsew',
                         padx=14 if catalog else 8,
                         pady=(14, 6) if catalog else 8)
        self.canvas.bind('<ButtonPress-1>', lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind('<B1-Motion>', lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))

    #===== Отображение изображения на холсте =====
    def display(self, image, zoom):
        self.canvas.delete('preview_message')
        size = tuple(max(1, round(value * zoom)) for value in image.size)
        if size != self.size:
            picture = image.resize(size, Image.LANCZOS) if size != image.size else image
            self.photo = ImageTk.PhotoImage(picture, master=self)
            self.size = size
            if self.item is None:
                self.item = self.canvas.create_image(0, 0, image=self.photo)
            else:
                self.canvas.itemconfigure(self.item, image=self.photo)
        width = max(self.canvas.winfo_width(), size[0])
        height = max(self.canvas.winfo_height(), size[1])
        self.canvas.coords(self.item, width / 2, height / 2)
        self.canvas.configure(scrollregion=(0, 0, width, height))

    #===== Очистка холста при ошибке =====
    def clear(self, message=''):
        self.canvas.delete('all')
        self.item = self.photo = self.size = None
        if message:
            self.canvas.create_text(20, 20, text=message, anchor='nw',
                                    fill='#9BACBF', font=('Segoe UI', 13),
                                    tags='preview_message')

    #===== Выделение выбранного шаблона =====
    def set_selection(self, index, title, info):
        self.heading.configure(text=title)
        self.info.configure(text=info)
        for i, button in enumerate(self.buttons):
            button.configure(fg_color='#315781' if i == index else 'transparent')
