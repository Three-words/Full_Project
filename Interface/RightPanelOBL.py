
"""Интерфейс правой панели: параметры, этикетки и примечания."""
import tkinter as tk
import customtkinter as ctk


class DetailsOBL:
    LABEL_NAMES = {
        'SVG_Uniq_Marker': 'Маркировка УИИ / ФНН',
        'SVG_UII': 'УИИ', 'SVG_FNN': 'ФНН',
        'SVG_Single_Item_Package': 'Упаковка изделия',
        'SVG_RE': 'Руководство по эксплуатации',
        'SVG_RO': 'Руководство по обслуживанию',
        'SVG_Passport': 'Паспорт изделия',
        'SVG_Military_Cargo_Transport_Unit': 'Транспортная этикетка',
    }

    def __init__(self, parent):
        self.parent = parent
        self.value_labels, self.attribute_rows = {}, []
        self.code_buttons, self.code_rows = {}, []

    #===== Заголовок и вкладки =====
    def draw(self):
        p = self.parent
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(2, weight=1)
        self.title = ctk.CTkLabel(p, text='Информация об изделии', anchor='w', font=('Segoe UI', 18, 'bold'))
        self.title.grid(row=0, column=0, sticky='ew', padx=(14, 38), pady=(10, 7))
        self.tabs = ctk.CTkSegmentedButton(
            p, values=['Общее', 'Коды'], height=32, font=('Segoe UI', 13, 'bold'),
            fg_color='#1A2534', selected_color='#315781', selected_hover_color='#3C6897',
            unselected_color='#253244', unselected_hover_color='#30435B')
        self.tabs.grid(row=1, column=0, sticky='ew', padx=10, pady=(0, 7))
        self.tabs.set('Общее')
        self.pages = {name: ctk.CTkScrollableFrame(p, fg_color='#17212F', corner_radius=8)
                      for name in ('Общее', 'Коды')}
        self.show_section('Общее')
        self.set_attributes(None)
        self.set_codes(None)

    def get_tab(self):
        return self.tabs.get()

    def set_title(self, value):
        self.title.configure(text=value or 'Информация об изделии')

    def show_section(self, name):
        for page in self.pages.values():
            page.grid_forget()
        self.pages[name].grid(row=2, column=0, sticky='nsew', padx=9, pady=(0, 9))

    @staticmethod
    def reset(page, message=None):
        for widget in page.winfo_children():
            widget.destroy()
        if message:
            ctk.CTkLabel(page, text=message, anchor='w', text_color='#9BACBF',
                         font=('Segoe UI', 13)).pack(fill='x', padx=10, pady=12)

    #===== Строки параметров с сохранением прокрутки =====
    def set_attributes(self, attributes):
        self.value_labels, self.attribute_rows = {}, []
        page = self.pages['Общее']
        self.reset(page, 'Выберите запись в таблице' if not attributes else None)
        if not attributes:
            return
        ctk.CTkLabel(page, text='Информация', anchor='w', text_color='#DCE6F3',
                     font=('Segoe UI', 12, 'bold')).pack(fill='x', padx=12, pady=(10, 7))
        for index, (name, value) in enumerate(attributes.items()):
            color = '#1C2A3B' if index % 2 == 0 else '#182536'
            row = ctk.CTkFrame(page, fg_color=color, corner_radius=5)
            row.pack(fill='x', padx=6, pady=(0, 3))
            row.grid_columnconfigure(0, weight=2, uniform='property')
            row.grid_columnconfigure(1, weight=3, uniform='property')
            left = tk.Label(row, text=str(name), width=1, wraplength=90, anchor='nw', justify='left',
                            font=('Segoe UI', 11), bg=color, fg='#A5B9D0', bd=0)
            right = tk.Label(row, text='—' if value is None or value == '' else str(value),
                             width=1, wraplength=120, anchor='nw', justify='left',
                             font=('Segoe UI', 12, 'bold'), bg=color, fg='#F2F6FC', bd=0)
            left.grid(row=0, column=0, sticky='nsew', padx=(10, 7), pady=9)
            right.grid(row=0, column=1, sticky='nsew', padx=(2, 8), pady=9)
            self.value_labels[name] = right
            self.attribute_rows.append((row, left, right))

    #===== Поле для редактирования =====
    @staticmethod
    def show_editor(label):
        entry = ctk.CTkEntry(label.master, height=30, fg_color='#253B54',
                             text_color='#FFFFFF', border_color='#5681B1', font=('Segoe UI', 12))
        entry.insert(0, '' if label.cget('text') == '—' else label.cget('text'))
        label.grid_remove()
        entry.grid(row=0, column=1, sticky='ew', padx=(2, 8), pady=6)
        entry.focus_set()
        entry.select_range(0, 'end')
        return entry

    @staticmethod
    def hide_editor(label, entry):
        if entry.winfo_exists():
            entry.destroy()
        if label.winfo_exists():
            label.grid()

    #===== Список сохранённых этикеток =====
    def set_codes(self, labels):
        self.code_buttons, self.code_rows = {}, []
        page = self.pages['Коды']
        message = 'Выберите изделие' if labels is None else 'Этикетки ещё не сформированы'
        self.reset(page, message if not labels else None)
        for name in labels or ():
            row = ctk.CTkFrame(page, fg_color='#1E2A3A', corner_radius=6)
            row.pack(fill='x', padx=4, pady=3)
            row.grid_columnconfigure(0, weight=1)
            caption = tk.Label(row, text=self.LABEL_NAMES.get(name, name), width=1,
                               wraplength=130, anchor='w', justify='left', bg='#1E2A3A',
                               fg='#F2F6FC', bd=0, font=('Segoe UI', 12, 'bold'))
            caption.grid(row=0, column=0, sticky='ew', padx=(9, 4), pady=10)
            button = ctk.CTkButton(row, text='Открыть', width=68, height=27,
                                   font=('Segoe UI', 11), fg_color='#305982')
            button.grid(row=0, column=1, sticky='e', padx=(0, 8), pady=7)
            self.code_buttons[name] = button
            self.code_rows.append((row, caption))


class NotesOBL:
    def __init__(self, parent):
        self.parent = parent

    #===== Поле примечаний =====
    def draw(self):
        p = self.parent
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(p, text='Примечания', font=('Segoe UI', 16, 'bold')).grid(
            row=0, column=0, sticky='w', padx=14, pady=(10, 5))
        self.editor = ctk.CTkTextbox(p, wrap='word', fg_color='#171F2B', font=('Segoe UI', 13))
        self.editor.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 7))
        self.save_button = ctk.CTkButton(p, text='Сохранить', height=30, fg_color='#285DAC')
        self.save_button.grid(row=2, column=0, sticky='ew', padx=10, pady=(0, 9))
        self.set_notes(None, False)

    def set_notes(self, value, enabled):
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end')
        if value is not None:
            self.editor.insert('1.0', str(value))
        self.editor.configure(state='normal' if enabled else 'disabled')
        self.save_button.configure(state='normal' if enabled else 'disabled')

    def get_notes(self):
        return self.editor.get('1.0', 'end-1c')
