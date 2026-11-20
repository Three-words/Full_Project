
"""Окна добавления и редактирования записей."""
import customtkinter as ctk


class AddRecordWindow(ctk.CTkToplevel):
    TITLE, HEADER, ACTION = 'Добавление записи', 'Добавление новой записи', 'Добавить'

    #===== Открытие формы записи =====
    def __init__(self, parent, table_name, fields, on_action,
                 type_names=None, on_type_select=None):
        super().__init__(parent)
        self.entries, self.on_action = {}, on_action
        self.title(f'{self.TITLE}: {table_name}')
        self.geometry('520x550')
        self.minsize(450, 400)
        self.transient(parent)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.draw(fields, type_names, on_type_select)
        self.grab_set()
        self.focus()

    #===== Создание полей и кнопок =====
    def draw(self, fields, type_names, on_type_select):
        ctk.CTkLabel(self, text=self.HEADER, font=('Segoe UI', 18, 'bold')).grid(
            row=0, column=0, pady=(20, 10))
        form = ctk.CTkScrollableFrame(self)
        form.grid(row=1, column=0, sticky='nsew', padx=20, pady=10)
        if type_names is not None:
            frame = ctk.CTkFrame(form, fg_color='#273346', corner_radius=8)
            frame.pack(fill='x', pady=(0, 12))
            ctk.CTkLabel(frame, text='Вид изделия', font=('Segoe UI', 14, 'bold')).pack(
                anchor='w', padx=12, pady=(10, 6))
            self.type_menu = ctk.CTkOptionMenu(
                frame, values=['Ввод вручную', *type_names], command=on_type_select,
                height=36, dynamic_resizing=False)
            self.type_menu.pack(fill='x', padx=10, pady=(0, 10))
            self.type_menu.set('Выберите вид изделия')
        for name, hint, required in fields:
            row = ctk.CTkFrame(form, fg_color='transparent')
            row.pack(fill='x', pady=6)
            ctk.CTkLabel(row, text=name + (' *' if required else ''), width=150,
                         anchor='w').pack(side='left', padx=(0, 10))
            entry = ctk.CTkEntry(row, height=36, placeholder_text=hint)
            entry.pack(side='left', fill='x', expand=True)
            self.entries[name] = entry
        buttons = ctk.CTkFrame(self, fg_color='transparent')
        buttons.grid(row=2, column=0, sticky='ew', padx=20, pady=(5, 20))
        for title, command, color in self.buttons():
            ctk.CTkButton(buttons, text=title, command=command, fg_color=color).pack(
                side='left', fill='x', expand=True, padx=4)

    #===== Заполнение и блокировка полей =====
    def set_fields(self, values, disabled=False):
        for name, value in values.items():
            entry = self.entries.get(name)
            if entry is None:
                continue
            entry.configure(state='normal')
            entry.delete(0, 'end')
            if value is not None:
                entry.insert(0, str(value))
            if disabled:
                entry.configure(state='disabled')

    #===== Получение данных формы =====
    def get_values(self):
        return {name: entry.get().strip() for name, entry in self.entries.items()}

    #===== Кнопки создания записи =====
    def buttons(self):
        return ((self.ACTION, self.on_action, '#285DAC'),
                ('Отмена', self.destroy, '#344256'))


class EditRecordWindow(AddRecordWindow):
    TITLE, ACTION = 'Редактирование записи', 'Сохранить'

    #===== Открытие формы редактирования =====
    def __init__(self, parent, table_name, values, on_save, on_delete):
        self.record_id, self.on_delete = values['id'], on_delete
        self.HEADER = f'Редактирование записи\nID: {self.record_id}'
        super().__init__(parent, table_name,
                         [(name, '', False) for name in values if name != 'id'], on_save)
        self.set_fields({name: value for name, value in values.items() if name != 'id'})

    #===== Кнопки редактирования записи =====
    def buttons(self):
        return ((self.ACTION, self.on_action, '#285DAC'),
                ('Удалить', self.on_delete, '#B33A3A'),
                ('Отмена', self.destroy, '#344256'))
