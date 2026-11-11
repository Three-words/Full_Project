
from psycopg2 import sql


class SQL:
    """Единственное место с запросами PostgreSQL, без знаний об интерфейсе."""

    @staticmethod
    def _table(table):
        return sql.Identifier('public', table)

    @staticmethod
    def _query(bd, query, params=None, commit=False):
        bd.cursor.execute(query, params)
        if commit:
            bd.connection.commit()
        return bd.cursor

    @staticmethod
    def get_tables(bd):
        q = ("SELECT table_name FROM information_schema.tables WHERE table_schema='public' "
             "AND table_type='BASE TABLE' AND table_name<>'ProductSerialCounter' ORDER BY 1")
        return [row[0] for row in SQL._query(bd, q).fetchall()]

    @staticmethod
    def get_table_data(bd, table):
        cur = SQL._query(bd, sql.SQL('SELECT * FROM {} ORDER BY id').format(SQL._table(table)))
        return [c[0] for c in cur.description], cur.fetchall()

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

    @staticmethod
    def get_required_columns(bd, table):
        q = ("SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
             "AND table_name=%s AND is_nullable='NO' AND column_default IS NULL AND is_identity='NO'")
        return [r[0] for r in SQL._query(bd, q, (table,)).fetchall()]

    @staticmethod
    def get_data_types(bd):
        q = ("SELECT DISTINCT format_type(oid,NULL) FROM pg_type WHERE typtype IN ('b','e') "
             "AND typnamespace IN (SELECT oid FROM pg_namespace WHERE nspname IN ('pg_catalog','public')) ORDER BY 1")
        return [r[0] for r in SQL._query(bd, q).fetchall()]

    @staticmethod
    def get_product_count(bd):
        return SQL._query(bd, 'SELECT COUNT(*) FROM public."Product"').fetchone()[0]

    @staticmethod
    def get_product_types(bd):
        q = ('SELECT t.id,t."Product_name",t."UYAIS",t."FNN" FROM public."ProductType" t '
             'WHERE EXISTS (SELECT 1 FROM public."Product" p WHERE p.product_type_id=t.id) ORDER BY 2,t.id')
        return SQL._query(bd, q).fetchall()

    @staticmethod
    def get_or_create_product_type(bd, values):
        q = ('INSERT INTO public."ProductType" ("Product_name","UYAIS","FNN") VALUES (%s,%s,%s) '
             'ON CONFLICT ("Product_name","UYAIS","FNN") DO NOTHING RETURNING id')
        row = SQL._query(bd, q, values).fetchone()
        if row is None:
            q = ('SELECT id FROM public."ProductType" WHERE '
                 '"Product_name"=%s AND "UYAIS"=%s AND "FNN"=%s')
            row = SQL._query(bd, q, values).fetchone()
        if not row:
            raise ValueError('Не удалось получить вид изделия')
        return row[0]

    @staticmethod
    def get_translations(bd):
        q = ('SELECT id,"Russian_Designation","Caps_Ruassian_Designation","Translate" '
             'FROM public."Translate" ORDER BY id')
        return SQL._query(bd, q).fetchall()

    @staticmethod
    def next_serial(bd, year):
        q = ('SELECT COALESCE(MAX("product_serial_number"::integer), 0) + 1 '
             'FROM public."Product" WHERE RIGHT("TKN", 7) LIKE %s '
             'AND "product_serial_number" ~ \'^[0-9]{5}$\'')
        return SQL._query(bd, q, (str(year)[-1] + '______',)).fetchone()[0]

    @staticmethod
    def search_records(bd, table, column, value):
        q = sql.SQL('SELECT * FROM {} WHERE CAST({} AS TEXT) ILIKE %s ORDER BY id').format(
            SQL._table(table), sql.Identifier(column))
        return SQL._query(bd, q, ('%' + value + '%',)).fetchall()

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

    @staticmethod
    def update_record(bd, table, record_id, values, commit=True):
        if not values:
            return
        fields = sql.SQL(', ').join(sql.SQL('{}=%s').format(sql.Identifier(c)) for c in values)
        q = sql.SQL('UPDATE {} SET {} WHERE id=%s').format(SQL._table(table), fields)
        SQL._query(bd, q, [*values.values(), record_id], commit=commit)

    @staticmethod
    def delete_record(bd, table, record_id, commit=True):
        q = sql.SQL('DELETE FROM {} WHERE id=%s').format(SQL._table(table))
        SQL._query(bd, q, (record_id,), commit=commit)

    @staticmethod
    def delete_unused_type(bd, type_id):
        q = ('DELETE FROM public."ProductType" t WHERE t.id=%s AND NOT EXISTS '
             '(SELECT 1 FROM public."Product" p WHERE p.product_type_id=t.id)')
        SQL._query(bd, q, (type_id,))

    @staticmethod
    def create_table(bd, table, columns):
        allowed = {'INTEGER', 'BIGINT', 'DOUBLE PRECISION', 'NUMERIC', 'VARCHAR(255)',
                   'TEXT', 'BOOLEAN', 'DATE', 'TIMESTAMP', 'XML', 'JSONB'}
        if any(c['type'] not in allowed for c in columns):
            raise ValueError('Недопустимый тип столбца')
        fields = sql.SQL(', ').join(sql.SQL('{} {}{}').format(
            sql.Identifier(c['name']), sql.SQL(c['type']),
            sql.SQL(' UNIQUE' if c.get('unique') else '')) for c in columns)
        q = sql.SQL('CREATE TABLE {} (id SERIAL PRIMARY KEY, {})').format(SQL._table(table), fields)
        SQL._query(bd, q, commit=True)

    @staticmethod
    def add_column(bd, table, column, data_type):
        if data_type not in {'INTEGER', 'BIGINT', 'DOUBLE PRECISION', 'NUMERIC',
                             'VARCHAR(255)', 'TEXT', 'BOOLEAN', 'DATE', 'TIMESTAMP', 'XML', 'JSONB'}:
            raise ValueError('Недопустимый тип столбца')
        q = sql.SQL('ALTER TABLE {} ADD COLUMN {} {}').format(
            SQL._table(table), sql.Identifier(column), sql.SQL(data_type))
        SQL._query(bd, q, commit=True)

    @staticmethod
    def delete_column(bd, table, column):
        q = sql.SQL('ALTER TABLE {} DROP COLUMN {}').format(SQL._table(table), sql.Identifier(column))
        SQL._query(bd, q, commit=True)

    @staticmethod
    def delete_table(bd, table):
        if table in ('Product', 'ProductType', 'Codes', 'ProductSerialCounter'):
            raise ValueError('Системную таблицу удалять нельзя')
        SQL._query(bd, sql.SQL('DROP TABLE {}').format(SQL._table(table)), commit=True)

    @staticmethod
    def save_product_codes(bd, product_id, code_id, labels):
        values = {'product_id': product_id, **labels}
        if code_id is None:
            code_id = SQL.add_record(bd, 'Codes', values, commit=False)
            SQL.update_record(bd, 'Product', product_id, {'code_id': code_id}, commit=False)
        else:
            SQL.update_record(bd, 'Codes', code_id, values, commit=False)
        return code_id
