Delta Topoliner 0.2.2

Распаковать в корень репозитория поверх, с заменой:

    C:\Users\Val\Documents\GitHub\topoliner

Папка .git не затрагивается.

Что изменилось по сравнению с 0.2.1 (замечания линтера каталога):

    убраны обработчики except Exception: pass
    убран повторный импорт MODE_INSERT и два неиспользуемых импорта
    добавлены тесты, которые ловят такие вещи до подачи в каталог

Файлы:

    topoliner\LICENSE            если ещё не добавлен из дельты 0.2.1
    topoliner\metadata.txt       версия 0.2.2
    topoliner\branding.py
    topoliner\geom_backend.py
    topoliner\i18n.py
    topoliner\topo_algorithm.py
    topoliner\topo_checks.py
    topoliner\audit_algorithms.py
    topoliner\simplify_algorithm.py
    topoliner\tests\test_i18n.py
    tools\*.py
    CHANGELOG.md
    PUBLISHING.md

Дальше:

    1. GitHub Desktop, Summary: Topoliner 0.2.2, Commit to main, Push origin
    2. Релиз с тегом v0.2.2, приложить topoliner.zip и topoliner_upload.zip
    3. На plugins.qgis.org загрузить topoliner_upload.zip
