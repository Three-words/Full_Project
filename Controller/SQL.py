from psycopg2 import sql


class SQL:

    # Получение списка всех таблиц схемы public
    @staticmethod
    def get_tables(bd):
        bd.cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        return [row[0] for row in bd.cursor.fetchall()]

    # Получение названий столбцов и содержимого выбранной таблиц с сортировкой по id
    @staticmethod
    def get_table_data(bd, table_name):
        query = sql.SQL("SELECT * FROM {} ORDER BY {}").format(
            sql.Identifier("public", table_name),
            sql.Identifier("id")
        )

        bd.cursor.execute(query)
        columns = [column[0] for column in bd.cursor.description]

        return columns, bd.cursor.fetchall()

    
    # Поиск записей по выбранному столбцу и введённому тексту
    @staticmethod
    def search_records(bd, table_name, column_name, text):
        query = sql.SQL("""
            SELECT * FROM {}
            WHERE CAST({} AS TEXT) ILIKE %s
            ORDER BY {}
        """).format(
            sql.Identifier("public", table_name),
            sql.Identifier(column_name),
            sql.Identifier("id")
        )

        bd.cursor.execute(query, (f"%{text}%",))
        return bd.cursor.fetchall()

    # Добавление новой записи в таблицу
    @staticmethod
    def add_record(bd, table_name, values):
        columns = list(values)
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier("public", table_name),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(sql.Placeholder() * len(columns))
        )

        bd.cursor.execute(query, [values[col] for col in columns])
        bd.connection.commit()