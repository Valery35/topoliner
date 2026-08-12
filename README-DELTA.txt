Дельта Topoliner 0.2.1

Распаковать содержимое этого архива в корень репозитория, поверх, с заменой:

    C:\Users\Val\Documents\GitHub\topoliner

Папка .git не затрагивается: в архиве её нет и файлов из неё тоже.

Что меняется (6 файлов):

    topoliner\LICENSE          новый файл, ради него выпуск и делается:
                               каталог QGIS проверяет содержимое архива,
                               а не репозитория, и требует лицензию внутри
                               папки плагина
    topoliner\metadata.txt     версия 0.2.1
    tools\build_zip.py         сборка не соберёт архив без LICENSE внутри
                               плагина и сверит его с корневым
    tools\preflight.py         та же проверка до сборки
    tools\check_docs.py        проверка согласованности документации
    CHANGELOG.md               запись о 0.2.1
    PUBLISHING.md              обновлённый порядок публикации

После распаковки в GitHub Desktop:

    1. Убедиться, что показано 6 изменённых файлов и ветка main
    2. Summary: Topoliner 0.2.1
    3. Commit to main, затем Push origin
    4. На GitHub создать релиз с тегом v0.2.1 и приложить
       topoliner.zip и topoliner_upload.zip
    5. На plugins.qgis.org загрузить topoliner_upload.zip

Проверить у себя перед коммитом (необязательно, нужен Python):

    python tools\preflight.py
    python tools\check_docs.py
