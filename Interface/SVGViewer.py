
"""Окна просмотра SVG: только оформление и отображение изображения."""
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

BACKGROUND, PANEL = '#141A23', '#202938'


class SVGPreviewBase(ctk.CTkToplevel):
    #===== Общее окно и холст =====
    def __init__(self, parent):
        super().__init__(parent.winfo_toplevel())
        self.withdraw()
        self.transient(parent.winfo_toplevel())
        self.configure(fg_color=BACKGROUND)
        self.photo = self.item = self.size = None

    #===== Создание холста =====
    def create_canvas(self, parent):
        self.canvas = tk.Canvas(parent, bg='#17212F', highlightthickness=0)
        self.canvas.bind('<ButtonPress-1>', lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind('<B1-Motion>', lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        return self.canvas

    #===== Отображение готового изображения =====
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

    #===== Очистка холста =====
    def clear(self, message=''):
        self.canvas.delete('all')
        self.item = self.photo = self.size = None
        if message:
            self.canvas.create_text(20, 20, text=message, anchor='nw',
                                    fill='#9BACBF', font=('Segoe UI', 13),
                                    tags='preview_message')


class SVGViewer(SVGPreviewBase):
    #===== Окно отдельной этикетки =====
    def __init__(self, parent, on_save):
        super().__init__(parent)
        self.title('Просмотр этикетки')
        self.geometry('820x700')
        self.minsize(480, 380)
        self.protocol('WM_DELETE_WINDOW', self.withdraw)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        bar.grid(row=0, column=0, sticky='ew')
        bar.grid_columnconfigure(0, weight=1)
        self.heading = ctk.CTkLabel(bar, text='Просмотр этикетки', anchor='w')
        self.heading.grid(row=0, column=0, sticky='ew', padx=16, pady=12)
        ctk.CTkButton(bar, text='Сохранить SVG', width=130,
                      command=on_save).grid(row=0, column=1, padx=12)
        self.create_canvas(self).grid(row=1, column=0, sticky='nsew', padx=8, pady=8)


class TemplatesWindow(SVGPreviewBase):
    #===== Окно каталога этикеток =====
    def __init__(self, parent, titles, on_select):
        super().__init__(parent)
        self.title('Шаблоны этикеток')
        self.geometry('930x650')
        self.minsize(720, 500)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

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
        self.create_canvas(area).grid(row=2, column=0, sticky='nsew', padx=14, pady=(14, 6))
        ctk.CTkLabel(area, text='Исходный макет SVG · тестовые данные',
                     text_color='#9BACBF', font=('Segoe UI', 12)).grid(
            row=3, column=0, pady=(0, 12))

    #===== Обновление выбранного пункта и заголовка =====
    def set_selection(self, index, title, info):
        self.heading.configure(text=title)
        self.info.configure(text=info)
        for i, button in enumerate(self.buttons):
            button.configure(fg_color='#315781' if i == index else 'transparent')
