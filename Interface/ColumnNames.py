
COLUMN_NAMES = {
    "id": "ID",
    "product_name": "Наименование изделия",
    "uyais": "УЯИС", "uii": "УИИ", "tkn": "ТКН",
    "organization_code": "Код организации",
    "issuance_agency_code": "Код агентства выдачи",
    "decimal_number": "Децимальный номер",
    "fnn": "ФНН", "serial_number": "Серийный номер",
    "unique_product_designation": "Уникальное обозначение изделия",
    "product_identification_code": "Идентификационный код изделия",
    "transport_unit_identifier": "Идентификатор транспортной единицы",
    "registration_date": "Дата регистрации изделия",
    "items_per_package": "Число изделий в упаковке",
    "cargo_place_count": "Количество мест груза",
    "cargo_place_number": "Номер места груза",
    "gross_weight": "Масса брутто", "net_weight": "Масса нетто",
    "width": "Ширина", "height": "Высота", "depth": "Глубина",
    "address": "Адрес", "re": "Руководство по эксплуатации",
    "ro": "Руководство по обслуживанию", "passport": "Паспорт",
    "code_id": "ID набора кодов",
    "svg_fnn": "SVG ФНН", "svg_uii": "SVG УИИ",
    "svg_uniq_marker": "SVG уникальной маркировки",
    "svg_re": "SVG РЭ", "svg_ro": "SVG РО",
    "svg_passport": "SVG паспорта",
    "svg_single_item_package": "SVG упаковки изделия",
    "svg_military_cargo_transport_unit": "SVG транспортной единицы",
    "notes": "Примечания",
    "xml": "XML",
    "russian_designation": "Русская буква",
    "caps_russian_designation": "Заглавная русская буква",
    "translate": "Транслит", "name_of_organization": "Название организации",
    "issuing_agency_code": "Код агентства выдачи",
    "code_organization": "Код организации", "caps_ruassian_designation": "Большая буква",
    "product_serial_number":"Номер груза", "name_docs" : "Вид документа", "identifiers" : "Идентификатор"
}

def display_name(column):
    return COLUMN_NAMES.get(column.lower(), column)
