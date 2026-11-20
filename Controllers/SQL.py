
"""Запросы к PostgreSQL и операции с таблицами."""
from psycopg2 import sql


#===== Допустимые типы пользовательских столбцов =====
COLUMN_TYPES = {'INTEGER', 'BIGINT', 'DOUBLE PRECISION', 'NUMERIC', 'VARCHAR(255)',
                'TEXT', 'BOOLEAN', 'DATE', 'TIMESTAMP', 'XML', 'JSONB'}


class SQL:
    """Единственное место с запросами PostgreSQL, без знаний об интерфейсе."""

    #===== Безопасное имя таблицы =====
    @staticmethod
    def _table(table):
        return sql.Identifier('public', table)

    #===== Выполнение SQL-запроса =====
    @staticmethod
    def _query(bd, query, params=None, commit=False):
        bd.cursor.execute(query, params)
        if commit:
            bd.connection.commit()
        return bd.cursor

    #===== Получение списка таблиц =====
    @staticmethod
    def get_tables(bd):
        q = ("SELECT table_name FROM information_schema.tables WHERE table_schema='public' "
             "AND table_type='BASE TABLE' AND table_name NOT IN ('ProductSerialCounter','CargoSerialCounter') ORDER BY 1")
        return [row[0] for row in SQL._query(bd, q).fetchall()]

    #===== Получение данных таблицы с фильтрацией по категории =====
    @staticmethod
    def get_table_data(bd, table, category_id=None):
        condition = sql.SQL(' WHERE product_type_id=%s') if category_id is not None else sql.SQL('')
        query = sql.SQL('SELECT * FROM {}{} ORDER BY id').format(SQL._table(table), condition)
        cur = SQL._query(bd, query, (category_id,) if category_id is not None else None)
        return [c[0] for c in cur.description], cur.fetchall()

    #===== Получение записи по заданному полю =====
    @staticmethod
    def get_record(bd, table, value, columns=None, key='id'):
        if isinstance(columns, str):
            columns = (columns,)
        fields = sql.SQL(', ').join(map(sql.Identifier, columns)) if columns else sql.SQL('*')
        q = sql.SQL('SELECT {} FROM {} WHERE {}=%s').format(
            fields, SQL._table(table), sql.Identifier(key))
        cur = SQL._query(bd, q, (value,))
        row = cur.fetchone()
        return dict(zip((c[0] for c in cur.description), row)) if row else None

    #===== Получение обязательных столбцов =====
    @staticmethod
    def get_required_columns(bd, table):
        q = ("SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
             "AND table_name=%s AND is_nullable='NO' AND column_default IS NULL AND is_identity='NO'")
        return [r[0] for r in SQL._query(bd, q, (table,)).fetchall()]

    #===== Подсчёт изделий =====
    @staticmethod
    def get_product_count(bd):
        return SQL._query(bd, 'SELECT COUNT(*) FROM public."Product"').fetchone()[0]

    #===== Получение существующих видов изделий =====
    @staticmethod
    def get_product_types(bd):
        q = ('SELECT t.id,t."Product_name",t."UYAIS",t."FNN" FROM public."ProductType" t '
             'WHERE EXISTS (SELECT 1 FROM public."Product" p WHERE p.product_type_id=t.id) ORDER BY 2,t.id')
        return SQL._query(bd, q).fetchall()

    #===== Поиск или создание вида изделия с необязательным ФНН =====
    @staticmethod
    def get_or_create_product_type(bd, values):
        name, uyais, fnn = values
        values = (str(name), str(uyais), str(fnn) if fnn not in (None, '') else None)
        select = ('SELECT id FROM public."ProductType" WHERE '
                  '"Product_name"=%s AND "UYAIS"=%s AND "FNN" IS NOT DISTINCT FROM %s '
                  'ORDER BY id LIMIT 1')
        row = SQL._query(bd, select, values).fetchone()
        if row:
            return row[0]
        insert = ('INSERT INTO public."ProductType" ("Product_name","UYAIS","FNN") '
                  'VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id')
        row = SQL._query(bd, insert, values).fetchone()
        if not row:
            row = SQL._query(bd, select, values).fetchone()
        if not row:
            raise ValueError('Не удалось получить вид изделия')
        return row[0]

    #===== Получение справочника транслитерации =====
    @staticmethod
    def get_translations(bd):
        q = ('SELECT id,"Russian_Designation","Caps_Ruassian_Designation","Translate" '
             'FROM public."Translate" ORDER BY id')
        return SQL._query(bd, q).fetchall()

    #===== Следующий номер после максимального за указанный год =====
    @staticmethod
    def next_serial(bd, year, after=0):
        # Блокировка действует до COMMIT/ROLLBACK и защищает параллельное присвоение.
        SQL._query(bd, 'SELECT pg_advisory_xact_lock(%s, %s)', (4829161, year))
        query = """
            SELECT GREATEST(COALESCE(MAX("product_serial_number"::integer), 0), %s) + 1
            FROM public."Product"
            WHERE cargo_year = %s AND "product_serial_number" IS NOT NULL
        """
        number = SQL._query(bd, query, (after, year)).fetchone()[0]
        return number if number <= 99999 else None

    #===== Проверка будущего ТКН в рамках УЯИС =====
    @staticmethod
    def tkn_exists(bd, uyais, tkn):
        query = 'SELECT 1 FROM public."Product" WHERE "UYAIS"=%s AND "TKN"=%s LIMIT 1'
        return SQL._query(bd, query, (uyais, tkn)).fetchone() is not None

    #===== Поиск по одному или всем содержательным столбцам =====
    @staticmethod
    def search_records(bd, table, column, value, category_id=None):
        if column:
            columns = [column]
        else:
            meta = sql.SQL('SELECT * FROM {} LIMIT 0').format(SQL._table(table))
            cur = SQL._query(bd, meta)
            columns = [c[0] for c in cur.description if not c[0].lower().startswith('svg_')
                       and c[0] not in ('cargo_year', 'code_id', 'product_type_id')
                       and not c[0].endswith('_id')]
        if not columns:
            return []
        # Экранируем специальные символы LIKE: поиск идёт по буквальному фрагменту.
        pattern = '%' + value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        comparisons = sql.SQL(' OR ').join(
            sql.SQL('CAST({} AS TEXT) ILIKE %s').format(sql.Identifier(name))
            for name in columns)
        category = sql.SQL(' AND product_type_id=%s') if category_id is not None else sql.SQL('')
        query = sql.SQL('SELECT * FROM {} WHERE ({}){} ORDER BY id').format(
            SQL._table(table), comparisons, category)
        params = [pattern] * len(columns)
        if category_id is not None:
            params.append(category_id)
        return SQL._query(bd, query, params).fetchall()

    #===== Добавление записи =====
    @staticmethod
    def add_record(bd, table, values, commit=True):
        cols = list(values)
        q = sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING id').format(
            SQL._table(table), sql.SQL(', ').join(map(sql.Identifier, cols)),
            sql.SQL(', ').join(sql.Placeholder() for _ in cols))
        record_id = SQL._query(bd, q, list(values.values())).fetchone()[0]
        if commit:
            bd.connection.commit()
        return record_id

    #===== Изменение записи =====
    @staticmethod
    def update_record(bd, table, record_id, values, commit=True):
        if not values:
            return
        fields = sql.SQL(', ').join(sql.SQL('{}=%s').format(sql.Identifier(c)) for c in values)
        q = sql.SQL('UPDATE {} SET {} WHERE id=%s').format(SQL._table(table), fields)
        SQL._query(bd, q, [*values.values(), record_id], commit=commit)

    #===== Удаление записи =====
    @staticmethod
    def delete_record(bd, table, record_id, commit=True):
        q = sql.SQL('DELETE FROM {} WHERE id=%s').format(SQL._table(table))
        SQL._query(bd, q, (record_id,), commit=commit)

    #===== Удаление неиспользуемого вида изделия =====
    @staticmethod
    def delete_unused_type(bd, type_id):
        q = ('DELETE FROM public."ProductType" t WHERE t.id=%s AND NOT EXISTS '
             '(SELECT 1 FROM public."Product" p WHERE p.product_type_id=t.id)')
        SQL._query(bd, q, (type_id,))

    #===== Создание таблицы =====
    @staticmethod
    def create_table(bd, table, columns, commit=True):
        if any(c['type'] not in COLUMN_TYPES for c in columns):
            raise ValueError('Недопустимый тип столбца')
        fields = sql.SQL(', ').join(sql.SQL('{} {}{}').format(
            sql.Identifier(c['name']), sql.SQL(c['type']),
            sql.SQL(' UNIQUE' if c.get('unique') else '')) for c in columns)
        q = sql.SQL('CREATE TABLE {} (id SERIAL PRIMARY KEY, {})').format(SQL._table(table), fields)
        SQL._query(bd, q, commit=commit)

    #===== Добавление столбца =====
    @staticmethod
    def add_column(bd, table, column, data_type, commit=True):
        if data_type not in COLUMN_TYPES:
            raise ValueError('Недопустимый тип столбца')
        q = sql.SQL('ALTER TABLE {} ADD COLUMN {} {}').format(
            SQL._table(table), sql.Identifier(column), sql.SQL(data_type))
        SQL._query(bd, q, commit=commit)

    #===== Удаление столбца =====
    @staticmethod
    def delete_column(bd, table, column):
        q = sql.SQL('ALTER TABLE {} DROP COLUMN {}').format(SQL._table(table), sql.Identifier(column))
        SQL._query(bd, q, commit=True)

    #===== Удаление таблицы =====
    @staticmethod
    def delete_table(bd, table):
        if table in ('Product', 'ProductType', 'Codes', 'ProductSerialCounter', 'CargoSerialCounter'):
            raise ValueError('Системную таблицу удалять нельзя')
        SQL._query(bd, sql.SQL('DROP TABLE {}').format(SQL._table(table)), commit=True)

    #===== Создание столбца пользовательской этикетки в общей транзакции =====
    @staticmethod
    def ensure_custom_label_column(bd, column):
        if not column.startswith('SVG_Custom_') or len(column) > 63:
            raise ValueError('Недопустимое имя столбца этикетки')
        query = sql.SQL('ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} TEXT').format(
            SQL._table('Codes'), sql.Identifier(column))
        SQL._query(bd, query)

    #===== Сохранение этикеток изделия =====
    @staticmethod
    def save_product_codes(bd, product_id, code_id, labels):
        values = {'product_id': product_id, **labels}
        if code_id is None:
            code_id = SQL.add_record(bd, 'Codes', values, commit=False)
            SQL.update_record(bd, 'Product', product_id, {'code_id': code_id}, commit=False)
        else:
            SQL.update_record(bd, 'Codes', code_id, values, commit=False)
        return code_id
