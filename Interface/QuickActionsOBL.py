
"""Быстрые действия и ненавязчивые уведомления о проверке кодов."""
from pathlib import Path

import customtkinter as ctk
from PIL import Image


class QuickActionsOBL:
    ACTIONS = (('generate_button', 'Генерация', 'generateQR.png'),
               ('scan_button', 'Сканер', 'scanner.png'),
               ('save_button', 'Сохранить', 'save.png'))

    def __init__(self, parent):
        self.parent = parent
        self.toast = self.toast_job = None
        project = Path(__file__).resolve().parent.parent
        folder = project / 'icons'
        self.icons = {}
        for name, _, file in self.ACTIONS:
            path = folder / file
            if path.is_file():
                image = Image.open(path)
                self.icons[name] = ctk.CTkImage(image.crop(image.getbbox()), size=(18, 18))

    def draw(self):
        self.parent.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(self.parent, text='Быстрые действия',
                     font=('Segoe UI', 18, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', padx=18, pady=(14, 7))

        for i, (name, title, _) in enumerate(self.ACTIONS):
            button = ctk.CTkButton(
                self.parent, text=title, image=self.icons.get(name),
                compound='top', height=54, font=('Segoe UI', 13, 'bold'),
                fg_color='#22344C', hover_color='#2B4D73',
                border_color='#356DA8', border_width=1, corner_radius=7)
            if i == 2:
                button.grid(row=2, column=0, columnspan=2,
                            sticky='ew', padx=18, pady=4)
            else:
                button.grid(row=1, column=i, sticky='nsew', pady=4,
                            padx=(18, 5) if i == 0 else (5, 18))
            setattr(self, name, button)

        self.delete_button = ctk.CTkButton(
            self.parent, text='Удалить запись', height=32,
            font=('Segoe UI', 13, 'bold'), border_width=1, corner_radius=7,
            fg_color='#38282D', hover_color='#563038',
            border_color='#74404A', text_color='#F08A94')
        self.delete_button.grid(row=3, column=0, columnspan=2,
                                sticky='ew', padx=18, pady=(4, 12))
        self.set_enabled(False)

    def set_enabled(self, enabled):
        state = 'normal' if enabled else 'disabled'
        color = '#22344C' if enabled else '#2A3443'
        for name, _, _ in self.ACTIONS:
            getattr(self, name).configure(state=state, fg_color=color)
        self.delete_button.configure(
            state=state, fg_color='#38282D' if enabled else '#2A282C')

    def hide_scan_status(self):
        if self.toast_job is not None:
            self.parent.after_cancel(self.toast_job)
            self.toast_job = None
        if self.toast is not None:
            self.toast.destroy()
            self.toast = None

    def set_scan_status(self, state, detail=''):
        """Краткое уведомление без блокировки интерфейса и кнопки OK."""
        self.hide_scan_status()
        messages = {
            'success': ('✓', 'Код совпадает', 'Этикетка: ' + detail, '#4ADE80'),
            'mismatch': ('✕', 'Код не совпадает',
                         'Не найден у выбранного изделия', '#F08A94'),
            'error': ('!', 'Ошибка проверки', detail or 'Не удалось проверить код', '#F7BC70')
        }
        if state not in messages:
            return

        symbol, title, description, color = messages[state]
        root = self.parent.winfo_toplevel()
        x = root.winfo_rootx() + root.winfo_width() - 333
        y = root.winfo_rooty() + root.winfo_height() - 93
        self.toast = ctk.CTkToplevel(root, fg_color='#192633')
        self.toast.withdraw()
        self.toast.overrideredirect(True)
        self.toast.transient(root)
        self.toast.geometry('315x75+{}+{}'.format(x, y))
        panel = ctk.CTkFrame(self.toast, fg_color='#192633', border_color=color,
                             border_width=1, corner_radius=10)
        panel.pack(fill='both', expand=True)
        panel.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(panel, text=symbol, width=32, font=('Segoe UI', 24, 'bold'),
                     text_color=color).grid(row=0, column=0, rowspan=2, padx=(12, 6))
        ctk.CTkLabel(panel, text=title, height=23,
                     font=('Segoe UI', 14, 'bold'), text_color='#F2F5FA',
                     anchor='w').grid(row=0, column=1, sticky='ew', pady=(10, 0))
        ctk.CTkLabel(panel, text=description[:80], height=22,
                     font=('Segoe UI', 11), text_color='#AFBDCE',
                     anchor='w').grid(row=1, column=1, sticky='ew',
                                      padx=(0, 8), pady=(0, 8))
        self.toast.deiconify()
        self.toast.lift(root)
        self.toast_job = self.parent.after(2800, self.hide_scan_status)
