# -*- coding: utf-8 -*-
"""https://github.com/tmwork1/poke-langmap の csv/ から和訳対応表をダウンロードし、
langmap/ に保存する(langmap/*.csv はリポジトリにコミットしない。常に最新を取得する)。

scripts/translate-data.py の前提として実行する。

Usage: python scripts/download-langmap.py
"""
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATION_DIR = os.path.join(ROOT, 'langmap')

LANGMAP_BASE_URL = 'https://raw.githubusercontent.com/tmwork1/poke-langmap/main/csv'
LANGMAP_FILES = ['name_langmap.csv', 'ability_langmap.csv', 'item_langmap.csv', 'move_langmap.csv']


def main():
    os.makedirs(TRANSLATION_DIR, exist_ok=True)
    for name in LANGMAP_FILES:
        with urllib.request.urlopen(f'{LANGMAP_BASE_URL}/{name}') as res:
            body = res.read()
        with open(os.path.join(TRANSLATION_DIR, name), 'wb') as f:
            f.write(body)
    print(f'langmap: poke-langmap から {len(LANGMAP_FILES)} 件ダウンロード')


if __name__ == '__main__':
    main()
