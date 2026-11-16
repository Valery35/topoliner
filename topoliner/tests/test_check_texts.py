# -*- coding: utf-8 -*-
"""
Деление на предложения в tools/check_texts.py.

16 ноября 2026 года проверка резала предложение по точке внутри адреса
и внутри номера версии, а закрывающая скобка уезжала в следующее
предложение. Средняя длина по файлам со ссылками выходила заниженной,
на пробе 3.4 вместо 6.7. Образцы лежат в tools/samples, длины в них
посчитаны вручную.

Тест смотрит на инструмент хранилища, а не плагина. В архиве плагина
папки tools нет, там тест пропускается.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, "tools")
SAMPLES = os.path.join(TOOLS, "samples")


@unittest.skipUnless(os.path.isfile(os.path.join(TOOLS, "check_texts.py")),
                     "tools/check_texts.py нет рядом")
class TestSentenceSplit(unittest.TestCase):

    def setUp(self):
        if TOOLS not in sys.path:
            sys.path.insert(0, TOOLS)
        import check_texts
        self.ct = check_texts

    def lengths(self, name):
        with open(os.path.join(SAMPLES, name), encoding="utf-8") as fh:
            body = self.ct.clean_markdown(fh.read())
        return self.ct.sentence_lengths(body), self.ct.sentence_stats(body)

    # Беда ядра measure.py (fe65aa4), а не ожидания: word_count дробит номер
    # версии «0.13.5» на три слова, и предложение выходит в 7 слов вместо 5.
    # Ожидание посчитано вручную и верно. Ждём исправления ядра. Когда его
    # исправят, тест даст неожиданный успех, и обёртку пора снять.
    @unittest.expectedFailure
    def test_link_and_version_stay_whole(self):
        # Значок не проза. Адрес ссылки не слово. 0.13.5 - одно слово.
        lengths, stats = self.lengths("sentences_links.md")
        self.assertEqual(lengths, [7, 8, 5])
        self.assertAlmostEqual(stats[0], 20 / 3.0, places=6)
        self.assertEqual(stats[1], 3)

    # Беда ядра measure.py (fe65aa4), а не ожидания: после «.)» перед цифрой
    # ядро предложение не делит, второе и третье сливаются в одно на 11 слов.
    # Закрывающая скобка после точки конец предложения не отменяет, прежнее
    # деление плагина это делало верно. Ждём исправления ядра, неожиданный
    # успех скажет, что обёртку пора снять.
    @unittest.expectedFailure
    def test_bracket_and_digit_start_a_sentence(self):
        # Закрывающая скобка остаётся при своём предложении, перед скобкой
        # и перед цифрой предложение делится.
        lengths, _stats = self.lengths("sentences_brackets.md")
        self.assertEqual(lengths, [5, 5, 6])

    def test_bold_entity_and_list_continuation(self):
        # Перед жирным словом предложение делится. «&nbsp;» - пробел, а не
        # склейка слов и не точка с запятой. Продолжение пункта перечня
        # с отступом остаётся в своём пункте.
        lengths, _stats = self.lengths("sentences_markup.md")
        self.assertEqual(lengths, [3, 4, 4, 10, 3])
        with open(os.path.join(SAMPLES, "sentences_markup.md"), encoding="utf-8") as fh:
            body = self.ct.clean_markdown(fh.read())
        problems = []
        self.ct.check_prose("sample", body, problems, lang="ru")
        self.assertEqual(problems, [])

    def test_findings_keep_their_lines(self):
        # Находки прежнего инструмента на образце остаются с теми же номерами
        # строк. «Кучку» ядро ловит по форме слова, прежний список её не знал.
        with open(os.path.join(SAMPLES, "findings.md"), encoding="utf-8") as fh:
            body = self.ct.clean_markdown(fh.read())
        problems = []
        self.ct.check_prose("findings.md", body, problems, lang="ru")
        found = sorted((place, reason.split(" ->")[0]) for place, _q, reason in problems)
        self.assertEqual(found, sorted([
            ("findings.md:4", "длинное тире"),
            ("findings.md:5", "точка с запятой"),
            ("findings.md:6", "двоеточие внутри строки"),
            ("findings.md:8", "стоп-слово"),
            ("findings.md:8", "стоп-слово"),
            ("findings.md:9", "стоп-слово"),
            ("findings.md:10", "«число» вместо «количества»"),
            ("findings.md:11", "двоеточие внутри строки"),
        ]))

    def test_product_terms_drop_a_core_stop_word(self):
        # Слово из списка исключений продукта находкой не считается. Список
        # заводит автор, сам тест слово туда не вносит, а подменяет список.
        problems = []
        self.ct.check_prose("t", "Мелочь исправлена.", problems, lang="ru")
        self.assertEqual(len(problems), 1)
        saved = self.ct.TERMS
        try:
            self.ct.TERMS = ("мелочь",)
            problems = []
            self.ct.check_prose("t", "Мелочь исправлена.", problems, lang="ru")
            self.assertEqual(problems, [])
        finally:
            self.ct.TERMS = saved

    def test_git_is_found_for_new(self):
        # Ключ --new берёт изменённые файлы из git. На рабочей машине git
        # стоит только в составе GitHub Desktop, прежний поиск его не видел.
        if not self.ct.git_path():
            self.skipTest("git на машине не найден")
        self.assertTrue(os.path.exists(self.ct.git_path()))


# Сумма копии ядра measure.py из agents-md-document-project, коммит fe65aa4.
# Сторож ловит правку копии у нас. Расхождение с источником он не ловит:
# источника при прогоне тестов нет. Новая версия ядра приходит копированием
# вместе с новой суммой здесь.
MEASURE_SHA256 = "9553d7cb4709b8f8caee7ab521dcde7db068497f7284d3546a1af3d714d87aab"


@unittest.skipUnless(os.path.isfile(os.path.join(TOOLS, "measure.py")),
                     "tools/measure.py нет рядом")
class TestMeasureCopy(unittest.TestCase):

    def test_core_copy_is_unchanged(self):
        import hashlib
        with open(os.path.join(TOOLS, "measure.py"), "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(digest, MEASURE_SHA256,
                         "tools/measure.py изменён. Ядро не правится у нас, "
                         "новая версия приносится копированием из источника.")


if __name__ == "__main__":
    unittest.main()
