"""Пример «плохой» работы: типичные ошибки первокурсника.

Файл специально насыщен антипаттернами для демонстрации анализатора:
голый except, изменяемый аргумент по умолчанию, затенение builtins,
global, == None, отсутствие докстрингов и перегруженная функция.
"""

result_storage = None


def process(data, accumulator=[]):
    # TODO: переписать нормально
    global result_storage
    try:
        for item in data:
            accumulator.append(int(item))
    except:
        accumulator = []
    result_storage = accumulator
    return accumulator


def list(data):
    return data == None


def prepare_report(records, limit):
    # одна функция делает сразу всё: фильтрацию, сортировку, форматирование
    filtered = []
    for record in records:
        if record.get("score") > limit:
            filtered.append(record)
    sorted_records = sorted(filtered, key=lambda r: r.get("score", 0))
    formatted = []
    for record in sorted_records:
        line = ""
        if record.get("title") is not None:
            line = line + record["title"] + " — "
        else:
            line = line + "без названия — "
        line = line + str(record.get("score"))
        formatted.append(line)
    total = 0
    for record in sorted_records:
        total = total + record.get("score", 0)
    header = "отчёт из " + str(len(formatted)) + " записей"
    return header + "\n" + "\n".join(formatted) + "\nитого: " + str(total)
