
"""Главный контроллер связывает события интерфейса с рабочими модулями."""
from functools import wraps
from tkinter import messagebox
from Controllers.RecordController import RecordController
from Controllers.RightPanelController import RightPanelController
from Controllers.ScannerController import ScannerController
from Controllers.TableController import TableController
from Interface.InterfaceGeneration import GenerationWindow
from Controllers.PreviewController import TemplatesController
from GenerateQR.TemplateController import TemplateController
from GenerateQR.QRController import QRController
from GenerateQR.DataMatrixController import DataMatrixController
from GenerateQR.PDF417Controller import PDF417Controller
from GenerateQR.Code128Controller import Code128Controller

#===== Настройки кнопки проверки кодов =====
VERIFY_COLORS = ('#22344C', '#256B49')
VERIFY_HOVER = ('#2B4D73', '#31865A')


#===== Общая обработка ошибок пользовательских команд =====
def report_errors(title):
    def decorate(method):
        @wraps(method)
        def execute(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except Exception as error:
                self.bd.connection.rollback()
                messagebox.showerror(title, str(error))
        return execute
    return decorate


class MainController:
    def __init__(self, bd, panel, center, quick, scanner, manual, details, notes):
        self.bd, self.panel, self.quick, self.manual = bd, panel, quick, manual
        self.parent = center.parent
        self.selected_record_id, self.verifier = None, False
        self.records = RecordController(bd, self.parent, self.refresh_table)
        self.table = TableController(bd, panel, center, self.select_record,
                                     self.records.open_edit_record)
        self.scanner = ScannerController(scanner, self.on_scanned, self.scanner_status)
        self.templates = TemplateController(bd, QRController(), DataMatrixController(),
                                            PDF417Controller(), Code128Controller())
        self.template_browser = TemplatesController(self.parent, self.templates.renderer)
        self.right_panel = RightPanelController(bd, self.records, self.table, details, notes,
                                               self.templates, self.parent)
        commands = {'products': lambda: self.table.select_table('Product'),
                    'categories': self.open_categories, 'templates': self.open_templates,
                    'add_record': self.add_record, 'generate': self.open_transport}
        for name, action in commands.items():
            panel.buttons[name].configure(command=action)
        panel.buttons['generate'].configure(state='disabled')
        manual.search_button.configure(command=lambda: self.table.find_product(manual.get_code()))
        for button, action in (('scan_button', self.toggle_verify),
                               ('generate_button', self.generate_labels),
                               ('save_button', self.right_panel.save_labels),
                               ('delete_button', self.delete_record)):
            getattr(quick, button).configure(command=action)
        quick.set_enabled(False)

    #===== Загрузка списка таблиц после подключения к БД =====
    def initialize(self):
        self.table.load_tables()

    @report_errors('Ошибка загрузки категорий')
    def open_categories(self):
        self.panel.show_categories(self.table.get_categories(), self.table.show_category)

    #===== Открытие каталога шаблонов =====
    def open_templates(self):
        self.template_browser.open()

    #===== Проверка сканером; вызывается кнопкой и ScannerController =====
    @report_errors('Ошибка проверки')
    def toggle_verify(self):
        if self.verifier:
            self.scanner.clear_codes()
        else:
            if self.selected_record_id is None:
                return messagebox.showwarning('Проверка', 'Выберите изделие')
            if not self.scanner.is_connected:
                return messagebox.showwarning('Проверка', 'Подключите сканер')
            self.scanner.load_codes(self.bd, self.selected_record_id)
        self.verifier = not self.verifier
        active = int(self.verifier)
        self.quick.scan_button.configure(text='Проверка: ВКЛ' if active else 'Сканер',
                                         fg_color=VERIFY_COLORS[active],
                                         hover_color=VERIFY_HOVER[active])
        self.quick.set_scan_status('waiting' if active else 'off')

    def on_scanned(self, code):
        self.manual.set_code(code)
        if not self.verifier:
            return
        try:
            label = self.scanner.check(code)
            state = 'success' if label else 'mismatch'
            self.quick.set_scan_status(state, label[4:] if label else '')
            self.scanner.play_sound(state)
        except Exception as error:
            self.quick.set_scan_status('error', str(error))

    def scanner_status(self, connected):
        self.panel.set_scanner_status(connected)
        if not connected and self.verifier:
            self.toggle_verify()

    #===== Выбор изделия и обновление правой панели; вызывается из TableController =====
    @report_errors('Ошибка записи')
    def select_record(self, table, record_id=None):
        selected = record_id if table == 'Product' else None
        if self.verifier and selected != self.selected_record_id:
            self.toggle_verify()
        self.selected_record_id = selected
        self.quick.set_enabled(selected is not None)
        self.panel.buttons['generate'].configure(state='normal' if selected is not None else 'disabled')
        if self.verifier:
            self.quick.scan_button.configure(fg_color=VERIFY_COLORS[1])
        record = self.records.get_record(table, record_id) if record_id is not None else None
        self.right_panel.show_record(table, record_id, record)

    def refresh_table(self):
        table, record_id = self.table.table_name, self.selected_record_id
        if table:
            self.table.load_table(table, record_id if table == 'Product' else None)
        self.table.update_products_count()

    #===== Генерация; TemplateController отвечает за данные и сохранение в БД =====
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

    @report_errors('Ошибка транспортной этикетки')
    def open_transport(self):
        if self.selected_record_id is None:
            return
        values, addresses, recipients = self.templates.get_transport_form(self.selected_record_id)
        window = GenerationWindow(self.parent, self.selected_record_id, values,
                                  lambda: self.generate_transport(window), addresses, recipients)

    def generate_transport(self, window):
        try:
            self.templates.save_transport(self.selected_record_id, window.get_values())
            window.destroy()
            self.refresh_table()
            messagebox.showinfo('Генерация', 'Транспортная этикетка сохранена в БД')
        except Exception as error:
            self.bd.connection.rollback()
            messagebox.showerror('Ошибка генерации', str(error), parent=window)

    #===== Записи: исполнение поручается RecordController =====
    def add_record(self):
        if self.table.table_name:
            self.records.open_add_record(self.table.table_name, tuple(self.table.columns))

    @report_errors('Ошибка удаления')
    def delete_record(self):
        record_id = self.selected_record_id
        if record_id is None or not messagebox.askyesno(
                'Удаление записи', f'Удалить изделие ID {record_id}?\nДействие нельзя отменить.',
                parent=self.parent):
            return
        self.records.delete_product(record_id, commit=True)
        self.refresh_table()
