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

    def test_link_and_version_stay_whole(self):
        # Значок не проза. Адрес ссылки не слово. 0.13.5 - одно слово.
        lengths, stats = self.lengths("sentences_links.md")
        self.assertEqual(lengths, [7, 8, 5])
        self.assertAlmostEqual(stats[0], 20 / 3.0, places=6)
        self.assertEqual(stats[1], 3)

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
        self.ct.check_prose("sample", body, problems)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
