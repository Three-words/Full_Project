"""COM-сканер: подключение, чтение, проверка сохранённых кодов."""
import sys
from pathlib import Path
from time import monotonic
from tkinter import messagebox
import serial
from serial.tools import list_ports
from Controllers.SQL import SQL

#===== Параметры сканера и звуков =====
BAUD_RATE, READ_TIMEOUT = 9600, 0
SCAN_END_DELAY, POLL_INTERVAL = 0.2, 50  # Секунды и миллисекунды.
SCANNER_WORDS = ('scanner', 'barcode', 'honeywell', 'zebra', 'datalogic', 'newland', 'ch340')
SOUND_FILES = {'success': 'Yes.mp3', 'mismatch': 'No.mp3'}

if sys.platform == 'win32':
    from ctypes import windll


class ScannerController:
    #===== Инициализация COM-порта и звуков =====
    def __init__(self, view, on_code, on_status_change):
        self.view, self.on_code, self.on_status_change = view, on_code, on_status_change
        self.ser = self.poll_job = None
        self.buffer, self.last_read, self.codes = b'', 0, {}
        self.verifying = False
        self.mci = windll.winmm.mciSendStringW if sys.platform == 'win32' else None
        self.sounds = {}
        if self.mci:
            folder = Path(__file__).resolve().parent.parent / 'sounds'
            for state, filename in SOUND_FILES.items():
                path, alias = folder / filename, 'code_studio_' + state
                if path.is_file() and not self.mci(
                        f'open "{path}" type mpegvideo alias {alias}', None, 0, None):
                    self.sounds[state] = alias
        view.test_button.configure(command=self.test_scanner)
        view.disconnect_button.configure(command=self.disconnect, state='disabled')

    #===== Проверка состояния подключения =====
    @property
    def is_connected(self):
        return bool(self.ser and self.ser.is_open)

    #===== Определение COM-порта сканера =====
    @staticmethod
    def find_port(ports):
        for port in ports:
            info = ' '.join(str(value or '') for value in
                            (port.product, port.description, port.manufacturer)).lower()
            if any(word in info for word in SCANNER_WORDS):
                return port
        return ports[0] if len(ports) == 1 else None

    #===== Подключение и проверка сканера =====
    def test_scanner(self):
        self.disconnect()
        ports = list(list_ports.comports())
        if not ports:
            return messagebox.showwarning('Сканер', 'COM-порты не обнаружены')
        port = self.find_port(ports)
        if port is None:
            return messagebox.showwarning('Сканер', 'Не удалось определить COM-порт сканера')
        try:
            self.ser = serial.Serial(port.device, BAUD_RATE, timeout=READ_TIMEOUT)
            self.set_status(True, port.product or port.description or 'Неизвестно', port.device)
            self.read_port()
        except (serial.SerialException, OSError) as error:
            self.disconnect()
            messagebox.showerror('Ошибка подключения', str(error))

    #===== Чтение данных с COM-порта =====
    def read_port(self):
        self.poll_job = None
        if not self.is_connected:
            return
        try:
            if self.ser.in_waiting:
                self.buffer += self.ser.read(self.ser.in_waiting)
                self.last_read = monotonic()
            if self.buffer and monotonic() - self.last_read >= SCAN_END_DELAY:
                code = self.buffer.decode('utf-8', errors='replace').rstrip('\r\n')
                self.buffer = b''
                if code:
                    self.on_code(code)
        except (serial.SerialException, OSError) as error:
            self.disconnect()
            return messagebox.showerror('Ошибка сканера', str(error))
        self.poll_job = self.view.parent.after(POLL_INTERVAL, self.read_port)

    #===== Обновление интерфейса при подключении и отключении =====
    def set_status(self, connected, model='—', port='—'):
        self.view.set_info(connected, model, port)
        self.on_status_change(connected)
        self.view.disconnect_button.configure(state='normal' if connected else 'disabled')

    #===== Отключение сканера =====
    def disconnect(self):
        if self.poll_job is not None:
            self.view.parent.after_cancel(self.poll_job)
            self.poll_job = None
        if self.is_connected:
            self.ser.close()
        self.ser, self.buffer = None, b''
        self.verifying = False
        self.codes.clear()
        self.set_status(False)

    #===== Загрузка кодов изделия для проверки =====
    def load_codes(self, bd, product_id):
        product = SQL.get_record(bd, 'Product', product_id, 'code_id')
        if not product or product['code_id'] is None:
            raise ValueError('У изделия отсутствуют сохранённые коды')
        codes = SQL.get_record(bd, 'Codes', product['code_id'], 'Payloads') or {}
        payloads = codes.get('Payloads') or {}
        self.codes = {bytes.fromhex(value): name for name, variants in payloads.items()
                      for value in variants}
        if not self.codes:
            raise ValueError('Данные кодов не сохранены. Сгенерируйте этикетки.')

    #===== Включение и выключение проверки кодов =====
    def toggle_verify(self, bd, product_id):
        if self.verifying:
            self.verifying = False
            self.codes.clear()
            return False
        if product_id is None:
            messagebox.showwarning('Проверка', 'Выберите изделие')
            return None
        if not self.is_connected:
            messagebox.showwarning('Проверка', 'Подключите сканер')
            return None
        self.load_codes(bd, product_id)
        self.verifying = True
        return True

    #===== Проверка кода и воспроизведение звукового сигнала =====
    def verify(self, scanned):
        label = self.codes.get(scanned.encode('utf-8').rstrip(b'\r\n'))
        state = 'success' if label else 'mismatch'
        self.play_sound(state)
        return state, label[4:] if label else ''

    #===== Воспроизведение звука результата проверки =====
    def play_sound(self, state):
        alias = self.sounds.get(state)
        if alias:
            for sound in self.sounds.values():
                self.mci('stop ' + sound, None, 0, None)
            self.mci(f'play {alias} from 0', None, 0, None)
            
    #===== Завершение работы COM-порта и освобождение звуков Windows =====
    def shutdown(self):
        try:
            self.disconnect()
        finally:
            if self.mci:
                for alias in self.sounds.values():
                    self.mci('stop ' + alias, None, 0, None)
                    self.mci('close ' + alias, None, 0, None)
                self.sounds.clear()
