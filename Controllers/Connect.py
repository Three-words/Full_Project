import psycopg2


class BD:
    open = False

    def __init__(self, window=None):
        self.window = window
        self.connection = None
        self.cursor = None

    def Connect_BD(self):
        try:
            self.connection = psycopg2.connect(
                host="localhost",
                user="postgres",
                password="admin12345",
                dbname="AR_Instructions",
                port=5432
            )

            self.cursor = self.connection.cursor()
            self.open = True

            self.window.set_status(
                "Подключено к БД",
                "#4ADE80"
            )

        except Exception:
            self.open = False

            self.window.set_status(
                "Нет подключения к БД",
                "#EF6464"
            )

    def Disconnect_BD(self):
        try:
            if self.cursor is not None:
                self.cursor.close()
                self.cursor = None

            if self.connection is not None:
                self.connection.close()
                self.connection = None

            self.open = False

        except Exception:
            pass