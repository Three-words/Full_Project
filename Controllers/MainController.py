
"""Точка сборки приложения: соединяет независимые подсистемы и их события."""
from functools import wraps
from psycopg2.errors import UniqueViolation
import copy
from tkinter import messagebox

from Controllers.RecordController import RecordController, TYPE_FIELDS
from Controllers.RecordFormController import RecordFormController
from Controllers.RightPanelController import RightPanelController
from Controllers.ScannerController import ScannerController
from Controllers.TableController import TableController
from Controllers.PreviewController import PreviewController
from Controllers.CustomTemplateController import CustomTemplateController
from Interface.CustomTemplateWindow import CustomTemplateWindow
from Interface.InterfaceGeneration import GenerationWindow
from GenerateQR.TemplateController import TemplateController

VERIFY_COLORS = ('#22344C', '#256B49')
VERIFY_HOVER = ('#2B4D73', '#31865A')


#===== Отображение ошибок команд без остановки интерфейса =====
def report_errors(title):
    def decorate(method):
        @wraps(method)
        def execute(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except Exception as error:
                self.bd.connection.rollback()
                messagebox.showerror(title, str(error), parent=self.parent)
        return execute
    return decorate


class MainController:
    #===== Создание подсистем и подключение пользовательских команд =====
    def __init__(self, bd, panel, center, quick, scanner, manual, details, notes):
        self.bd, self.parent, self.panel, self.quick, self.manual = bd, center.parent, panel, quick, manual
        self.selected_record_id = None
        self.records = RecordController(bd)
        self.forms = RecordFormController(self.parent, self.records.form_data,
                                          self.records.document_names, TYPE_FIELDS, self.add_record_data,
                                          self.update_record_data, self.delete_record_data)
        self.table = TableController(bd, panel, center, self.select_record, self.forms.open_edit)
        self.scanner = ScannerController(scanner, self.on_scanned, self.scanner_status)
        self.templates = TemplateController(bd)
        self.template_browser = PreviewController(
            self.parent, self.templates.preview_label,
            lambda: self.custom_templates.service.all_templates(), self.preview_custom)
        self.svg_preview = PreviewController(self.parent)
        self.custom_templates = CustomTemplateController(bd)
        self.details = details
        self.right_panel = RightPanelController(
            details, notes, self.parent, self.update_attribute, self.update_notes,
            self.templates.load_saved_labels, self.svg_preview.open,
            self.templates.export_saved_labels)

        commands = {'products': lambda: self.table.select_table('Product'),
                    'categories': self.open_categories, 'templates': self.template_browser.open_catalog,
                    'add_record': self.open_add_record, 'generate': self.open_generation_menu,
                    'new_template': self.open_template_editor}
        for name, action in commands.items():
            panel.buttons[name].configure(command=action)
        panel.buttons['generate'].configure(state='disabled')
        manual.search_button.configure(command=lambda: self.table.find_product(manual.get_code()))
        for button, action in (('scan_button', self.toggle_verify),
                               ('generate_button', self.generate_labels),
                               ('save_button', self.right_panel.save_labels),
                               ('delete_button', self.delete_selected)):
            getattr(quick, button).configure(command=action)
        center.assign_cargo_button.configure(command=self.assign_cargo_number)
        quick.set_enabled(False)
        self.refresh_custom_names()

    #===== Начальная загрузка таблиц =====
    def initialize(self):
        self.table.load_tables()

    #===== Отображение доступных категорий =====
    @report_errors('Ошибка категорий')
    def open_categories(self):
        self.panel.show_categories(self.table.get_categories(), self.table.show_category)

    #===== Запуск операции записи с единой транзакцией =====
    def write(self, action, *args):
        try:
            result = action(*args)
            self.bd.connection.commit()
            return result
        except UniqueViolation as error:
            self.bd.connection.rollback()
            names = {
                'uq_product_cargo_year': 'Номер груза уже используется в этом году',
                'uq_product_uyais_serial': 'Этот серийный номер уже используется для данного УЯИС',
                'uq_product_uyais_uii': 'Этот УИИ уже используется для данного УЯИС',
                'uq_product_uyais_tkn': 'Этот ТКН уже используется для данного УЯИС'}
            raise ValueError(names.get(error.diag.constraint_name, str(error))) from error
        except Exception:
            self.bd.connection.rollback()
            raise

    #===== Обновление таблицы после изменения состава записей =====
    def refresh_table(self):
        if self.table.table_name:
            self.table.load_table(self.table.table_name,
                                  self.selected_record_id if self.table.table_name == 'Product' else None)
        self.table.update_products_count()

    #===== Синхронизация выбора изделия с правой панелью =====
    @report_errors('Ошибка выбора записи')
    def select_record(self, table, record_id=None):
        selected = record_id if table == 'Product' else None
        if self.scanner.verifying and selected != self.selected_record_id:
            self.toggle_verify()
        self.selected_record_id = selected
        self.quick.set_enabled(selected is not None)
        record = self.records.get_record(table, record_id) if record_id is not None else None
        self.table.view.assign_cargo_button.configure(
            state='normal' if selected is not None and record and
            record.get('product_serial_number') is None else 'disabled')
        self.panel.buttons['generate'].configure(state='normal' if selected is not None else 'disabled')
        self.right_panel.show_record(table, record_id, record)

    #===== Присвоение номера груза выбранному изделию =====
    @report_errors('Ошибка присвоения номера груза')
    def assign_cargo_number(self):
        if self.selected_record_id is None:
            return
        number = self.write(self.records.assign_cargo_number, self.selected_record_id)
        self.refresh_table()
        messagebox.showinfo('Номер груза', 'Присвоен номер {}'.format(number),
                            parent=self.parent)

    #===== Сохранение атрибута с точечной синхронизацией таблицы =====
    def update_attribute(self, record_id, column, value):
        self.write(self.records.update_product, record_id, {column: value})
        record = self.records.get_record('Product', record_id)
        self.table.update_row(record)
        if record_id == self.selected_record_id:
            self.table.view.assign_cargo_button.configure(
                state='normal' if record.get('product_serial_number') is None else 'disabled')
        return record

    #===== Сохранение примечаний без перестроения интерфейса =====
    def update_notes(self, record_id, content):
        self.write(self.records.save_notes, record_id, content)
        self.table.update_row({'id': record_id, 'Notes': content or None})

    #===== Открытие формы добавления в активную таблицу =====
    def open_add_record(self):
        if self.table.table_name:
            self.forms.open_add(self.table.table_name, tuple(self.table.columns))

    #===== Добавление записи из формы =====
    def add_record_data(self, table, values, selected_type=None):
        self.write(self.records.add_record, table, values, selected_type)
        self.refresh_table()

    #===== Изменение записи из формы =====
    def update_record_data(self, table, record_id, values):
        self.write(self.records.update_record, table, record_id, values)
        self.refresh_table()

    #===== Удаление записи из формы =====
    def delete_record_data(self, table, record_id):
        self.write(self.records.delete_record, table, record_id)
        self.refresh_table()

    #===== Удаление выбранного изделия кнопкой быстрого действия =====
    @report_errors('Ошибка удаления')
    def delete_selected(self):
        record_id = self.selected_record_id
        if record_id is None or not messagebox.askyesno(
                'Удаление записи', f'Удалить изделие ID {record_id}?\nДействие нельзя отменить.',
                parent=self.parent):
            return
        self.delete_record_data('Product', record_id)

    #===== Переключение проверки отсканированных кодов =====
    @report_errors('Ошибка проверки')
    def toggle_verify(self):
        active = self.scanner.toggle_verify(self.bd, self.selected_record_id)
        if active is None:
            return
        i = int(active)
        self.quick.scan_button.configure(text='Проверка: ВКЛ' if active else 'Сканер',
                                         fg_color=VERIFY_COLORS[i], hover_color=VERIFY_HOVER[i])
        self.quick.set_scan_status('waiting' if active else 'off')

    #===== Передача отсканированного кода полю и проверке =====
    def on_scanned(self, code):
        self.manual.set_code(code)
        if self.scanner.verifying:
            try:
                state, detail = self.scanner.verify(code)
                self.quick.set_scan_status(state, detail)
            except Exception as error:
                self.quick.set_scan_status('error', str(error))

    #===== Обработка отключения сканера =====
    def scanner_status(self, connected):
        self.panel.set_scanner_status(connected)
        if not connected:
            if self.scanner.verifying:
                self.scanner.toggle_verify(self.bd, self.selected_record_id)
            self.quick.scan_button.configure(text='Сканер', fg_color=VERIFY_COLORS[0],
                                             hover_color=VERIFY_HOVER[0])
            self.quick.set_scan_status('off')

    #===== Генерация кодов выбранного изделия =====
    @report_errors('Ошибка генерации')
    def generate_labels(self):
        if self.selected_record_id is None:
            return
        labels = self.templates.generate_product_labels(self.selected_record_id, self.parent)
        text = f'Сгенерировано и сохранено в базе данных: {len(labels)} кодов'
        if self.templates.skipped:
            text += '\n\nНе удалось создать:\n' + '\n'.join(self.templates.skipped)
        self.right_panel.refresh_codes()
        (messagebox.showwarning if self.templates.skipped else messagebox.showinfo)('Генерация', text)

    #===== Меню транспортной этикетки и пользовательских шаблонов =====
    @report_errors('Ошибка выбора этикетки')
    def open_generation_menu(self):
        if self.selected_record_id is None:
            return
        names = self.custom_templates.service.all_templates()
        choices = [(None, 'Транспортная этикетка')]
        choices += [(name, 'Шаблон: ' + name) for name in names]
        self.panel.show_popup(self.panel.buttons['generate'], choices,
                              self.choose_generation, below=True)

    #===== Выбор способа генерации =====
    def choose_generation(self, name):
        if name is None:
            self.open_transport()
        else:
            self.generate_custom(name)

    #===== Генерация и сохранение пользовательской этикетки =====
    @report_errors('Ошибка пользовательской этикетки')
    def generate_custom(self, name):
        if self.selected_record_id is None:
            return
        self.templates.save_custom(self.custom_templates.service, name, self.selected_record_id)
        self.refresh_custom_names()
        self.right_panel.refresh_codes()
        messagebox.showinfo('Генерация', 'Этикетка «{}» сохранена в БД'.format(name),
                            parent=self.parent)

    #===== Демонстрационный просмотр без выбора изделия =====
    def preview_custom(self, name):
        template = self.custom_templates.service.all_templates().get(name)
        if template is None:
            raise ValueError('Шаблон не найден')
        return self.custom_templates.service.render(copy.deepcopy(template)), None

    #===== Обновление подписей сохранённых пользовательских этикеток =====
    def refresh_custom_names(self):
        self.details.LABEL_NAMES.update({
            self.templates.custom_column(name): name
            for name in self.custom_templates.service.all_templates()})

    #===== Открытие транспортной формы =====
    @report_errors('Ошибка транспортной этикетки')
    def open_transport(self):
        if self.selected_record_id is None:
            return
        values, addresses, recipients = self.templates.get_transport_form(self.selected_record_id)
        window = GenerationWindow(self.parent, self.selected_record_id, values,
                                  lambda: self.generate_transport(window), addresses, recipients)

    #===== Сохранение транспортной этикетки =====
    def generate_transport(self, window):
        try:
            self.templates.save_transport(self.selected_record_id, window.get_values())
            window.destroy()
            self.refresh_table()
            messagebox.showinfo('Генерация', 'Транспортная этикетка сохранена в БД')
        except Exception as error:
            self.bd.connection.rollback()
            messagebox.showerror('Ошибка генерации', str(error), parent=window)

    #===== Открытие конструктора пользовательских этикеток =====
    @report_errors('Ошибка конструктора')
    def open_template_editor(self):
        CustomTemplateWindow(self.parent, self.custom_templates, self.svg_preview.open,
                             self.selected_record_id)
