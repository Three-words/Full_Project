"""Русские обозначения и английские идентификаторы из одного JSON-файла."""
import json
import re
from functools import lru_cache
from pathlib import Path

NAMES_FILE = Path(__file__).resolve().parents[1] / 'JSON' / 'ColumnNames.json'


#===== Чтение таблиц переводов и пользовательских названий =====
@lru_cache(maxsize=1)
def read_names():
    if not NAMES_FILE.is_file():
        raise FileNotFoundError('Не найден файл сопоставлений: {}'.format(NAMES_FILE))
    data = json.loads(NAMES_FILE.read_text(encoding='utf-8'))
    keys = ('tables', 'columns', 'words', 'letters')
    if any(not isinstance(data.get(key), dict) for key in keys):
        raise ValueError('В ColumnNames.json нужны разделы: ' + ', '.join(keys))
    return data


#===== Сохранение новых подписей без потери словарей =====
def write_names(data):
    keys = ('tables', 'columns', 'words', 'letters')
    if any(not isinstance(data.get(key), dict) for key in keys):
        raise ValueError('Некорректная структура ColumnNames.json')
    temp = NAMES_FILE.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(NAMES_FILE)
    read_names.cache_clear()


#===== Преобразование названия в английский идентификатор БД =====
def english_name(name):
    name = name.strip()
    if not name:
        raise ValueError('Укажите название')
    if not re.search('[А-Яа-яЁё]', name):
        if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', name):
            raise ValueError('Английское имя может содержать только буквы, цифры и _')
        return name
    data = read_names()
    result = []
    for word in re.findall('[A-Za-zА-Яа-яЁё0-9]+', name):
        translated = data['words'].get(word.casefold())
        if translated is None:
            translated = ''.join(data['letters'].get(char, char) for char in word.casefold())
            translated = translated[:1].upper() + translated[1:]
        result.append(translated)
    value = '_'.join(result)
    if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', value):
        raise ValueError('Не удалось преобразовать название: ' + name)
    if len(value.encode('utf-8')) > 63:
        raise ValueError('Название слишком длинное для PostgreSQL (максимум 63 символа)')
    return value


#===== Русское обозначение таблицы =====
def table_name(name):
    return read_names()['tables'].get(name, name)


#===== Восстановление имени таблицы в PostgreSQL =====
def real_table(name):
    return next((key for key, title in read_names()['tables'].items() if title == name), name)


#===== Русское обозначение столбца =====
def display_name(column):
    return read_names()['columns'].get(column.lower(), column)
