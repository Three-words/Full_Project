
"""Окно транспортной этикетки: только поля и получение введённого текста."""
import customtkinter as ctk
from Interface.InterfaceRecord import AddRecordWindow

#===== Настройки формы: подписи не используются как ключи данных =====
FIELDS = (('tkn', 'ТКН'), ('fnn', 'ФНН'), ('address', 'Адрес получателя'),
          ('place_number', 'Номер места'), ('place_count', 'Количество мест'),
          ('sender', 'Грузоотправитель'), ('recipient', 'Грузополучатель'),
          ('gross', 'Масса брутто, кг'), ('net', 'Масса нетто, кг'),
          ('dimensions', 'Габариты, см'))
WINDOW_SIZE = '540x620'


class GenerationWindow(AddRecordWindow):
    TITLE, HEADER, ACTION = 'Генерация кодов', 'Транспортная этикетка', 'Сгенерировать'

    #===== Создание формы; значения приходят из TemplateController =====
    def __init__(self, parent, record_id, values, on_generate, addresses, recipients):
        super().__init__(parent, f'Product ID {record_id}',
                         [(title, '', True) for _, title in FIELDS], on_generate)
        self.geometry(WINDOW_SIZE)
        for key, options in (('address', addresses), ('recipient', recipients)):
            title = dict(FIELDS)[key]
            entry = self.entries[title]
            combo = ctk.CTkComboBox(
                entry.master, values=options or [''], height=36,
                fg_color=entry.cget('fg_color'), border_color=entry.cget('border_color'),
                text_color=entry.cget('text_color'), button_color='#344256',
                button_hover_color='#46546A', dropdown_fg_color='#202938',
                dropdown_hover_color='#344256', dropdown_text_color='#E7EDF6')
            entry.destroy()
            combo.pack(side='left', fill='x', expand=True)
            combo.bind('<KeyRelease>', lambda event, w=combo, items=options:
                       self.filter_options(event, w, items))
            self.entries[title] = combo
        for key, title in FIELDS:
            value = values.get(key)
            if value is not None:
                entry = self.entries[title]
                if isinstance(entry, ctk.CTkComboBox):
                    entry.set(str(value))
                else:
                    entry.insert(0, str(value))
        self.entries['Габариты, см'].configure(state='disabled')

    #===== Чтение формы; вызывается из MainController.generate_transport =====
    def get_values(self):
        return {key: self.entries[title].get().strip() for key, title in FIELDS}

    #===== Поиск вариантов при наборе адреса или получателя =====
    @staticmethod
    def filter_options(event, combo, options):
        if event.keysym not in ('Up', 'Down', 'Return', 'Escape', 'Tab'):
            combo.configure(values=[value for value in options
                                    if combo.get().casefold() in value.casefold()] or [''])
