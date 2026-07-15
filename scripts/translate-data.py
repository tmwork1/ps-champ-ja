# -*- coding: utf-8 -*-
"""data_en/ の英語データを langmap/ の言語テーブルで和訳し、data_jp/ に書き出す。

langmap/*.csv (https://github.com/tmwork1/poke-langmap 由来、リポジトリにはコミットしない)
は scripts/download-langmap.py で事前にダウンロードしておくこと。
langmap/_additional_langmap.csv は champions mod 独自の特性・アイテムなど、
poke-langmap に収録が無いものを手動で補う対応表(リポジトリにコミットする)。

対象: pokedex.json の name / types / abilities / prevo / evos / requiredItem
      moves.json の name / type
      learnsets.json のキー(種族)・値(技リスト)
方針: data_en/ のキー名・構造(weight/height・abilitiesの配列化・categoryの小文字化等)は
      scripts/build-data-en.js 側で既に整形済みのため、ここでは値の翻訳のみを行う。
      技ID・種族IDそのものは内部参照のため翻訳しない。
      learnsets.json はキーを showdown_id から pokedex.json のキーと同じ和名に、
      値の技IDをmoves.jsonで解決した和名に変換する。pokedex_excluded.json 送りになった
      フォルム(showdown_id)は pokedex.json 側に存在しないため learnsets.json からも除外する。
      forme/baseForme のいずれかを持つ種族(メガ進化・リージョンフォルム・ガラル/ヒスイ/
      パルデアの各フォルム、オーガポンの仮面違い、オドリドリ等の baseForme 付き基本フォルム等、
      単純な name_langmap.csv の対応表だけでは和名を組み立てられないすべてのポケモン)の和名は、
      langmap/_form_langmap.csv (exclude,showdown_name,baseForme,base_jp,final_jp のヘッダ付き
      CSV、手動管理・コミット対象)を必ず参照して解決する。フォルムが連なる場合
      (例: メロエッタ+キョダイのような "(A)(B)")は "(A,B)" のようにカンマ区切りで
      1つの括弧にまとめる。公式に固有の表示名を持たないコスチューム違い(コスプレピカチュウ、
      ビビヨンの模様違い等)や、対戦・図鑑上の価値が薄く代表1体のみ収録すれば十分なもの
      (ボス/タテヌシ勢、アルセウス/シルヴァディのタイプ違い、ゲノセクトのドライブ違い、
      ウッウの飲み込み形態違い)は final_jp をベースの和名と同じ値にしつつ、
      exclude列(必ず"0"か"1")を"1"にする。この exclude列は scripts/build-data-en.js が
      既に参照して data_en/pokedex.json から除外し data_en/pokedex_excluded.json に
      振り分け済みのため、ここでは data_en/pokedex_excluded.json 側を読み込んで和訳し、
      data_jp/pokedex.json には含めず data_jp/pokedex_excluded.json にのみ出力する。
      このCSVに無い組み合わせ(新種族追加など)は翻訳漏れとして一覧に出力し、ベースの和名を
      そのまま使う。
      abilities は data_en 側の {スロット: 特性名} オブジェクトから、data_jp 側では
      スロット情報を落として和名の配列に変換する。
      data_jp/pokedex.json は data_en/pokedex.json と同じくキーを表示名にするが、
      英名ではなく和名を使う点が異なる(showdown_id/showdown_name としてshowdownのid/nameを残す)。
      weightkg/heightmはweight/heightにリネームする。
      exclude列で除外指定されていないのに和名がフォルム間で重複する場合(CSV未収録の新規
      フォルム等への保険)も、最初に登場したものだけを残し、以降は同様に
      data_jp/pokedex_excluded.json (showdown_idキー、reason付き)に退避して
      data_jp/pokedex.json からは除外する。

Usage: python scripts/download-langmap.py && python scripts/translate-data.py
"""
import csv
import json
import os
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN_DIR = os.path.join(ROOT, 'data_en')
JP_DIR = os.path.join(ROOT, 'data_jp')
TRANSLATION_DIR = os.path.join(ROOT, 'langmap')


def load_csv(name):
    path = os.path.join(TRANSLATION_DIR, name)
    if not os.path.exists(path):
        print(f'langmap/{name} が見つかりません。先に scripts/download-langmap.py を実行してください。')
        sys.exit(1)
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        return header, list(reader)


# champions mod 独自の特性・アイテムなど、poke-langmap (公式ゲームの対応表) には存在しない
# ものを手動で補う対応表。langmap/_additional_langmap.csv (en,jp のヘッダ付きCSV) に
# 追記していく。ability/item 共通の名前空間として両方のテーブルにマージする。
def load_additional_table():
    path = os.path.join(TRANSLATION_DIR, '_additional_langmap.csv')
    if not os.path.exists(path):
        return {}
    table = {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if not row or not row[0]:
                continue
            en, jp = row[0], row[1]
            table[en] = normalize_fullwidth_alnum(jp)
    return table


# forme/baseForme のいずれかを持ち、name_langmap.csv の単純な対応表だけでは和名を
# 組み立てられない種族の和名は、この langmap/_form_langmap.csv
# (exclude,showdown_name,baseForme,base_jp,final_jp のヘッダ付きCSV) を必ず参照して解決する。
# showdown_name は data_en/pokedex.json のキーと同じ表示名で、PSの全species中で一意なため
# これ単体をキーにする(baseFormeの値自体は種族間で衝突しうる。例: "Normal"はアルセウス/
# シルヴァディ両方、"Hero"はザシアン/ザマゼンタ両方で使われる)。forme の値は showdown_name
# 自体に含まれておりCSV側では使わないため列を持たない。
# exclude列は必ず "0" か "1" で埋める。"1" は、公式に固有の表示名を持たないコスチューム違い
# (コスプレピカチュウ、ビビヨンの模様違い等)や、対戦上・図鑑上の価値が薄いためこのmodでは
# 代表1体のみ収録する形違い(ボス/タテヌシ勢、アルセウス/シルヴァディのタイプ違い、
# ゲノセクトのドライブ違い、ウッウの飲み込み形態違い等)を明示的にマークし、
# data_jp/pokedex.json からは除外して data_jp/pokedex_excluded.json 側にのみ出力する指示になる。
# 戻り値: showdown_name(NFC正規化済み) -> (final_jp, excluded: bool)
def load_form_table():
    path = os.path.join(TRANSLATION_DIR, '_form_langmap.csv')
    if not os.path.exists(path):
        print('langmap/_form_langmap.csv が見つかりません。')
        sys.exit(1)
    table = {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if not row:
                continue
            exclude, showdown_name, _base_forme, _base_jp, final_jp = row
            table[normalize_name(showdown_name)] = (final_jp, exclude == '1')
    return table


TYPE_JP = {
    'Normal': 'ノーマル', 'Fire': 'ほのお', 'Water': 'みず', 'Electric': 'でんき',
    'Grass': 'くさ', 'Ice': 'こおり', 'Fighting': 'かくとう', 'Poison': 'どく',
    'Ground': 'じめん', 'Flying': 'ひこう', 'Psychic': 'エスパー', 'Bug': 'むし',
    'Rock': 'いわ', 'Ghost': 'ゴースト', 'Dragon': 'ドラゴン', 'Dark': 'あく',
    'Steel': 'はがね', 'Fairy': 'フェアリー', 'Stellar': 'ステラ',
}

def build_species_table():
    _, rows = load_csv('name_langmap.csv')
    by_num = {}
    for row in rows:
        if not row[0]:
            continue
        en = row[2]
        # 英伊西で表記が割れる行は "Name (英語)Nome (イタリア語)..." のように連結されている。
        # 実際に必要なのは英語表記だけなので "(英語)" の手前を取り出す。
        if '(英語)' in en:
            en = en.split('(英語)')[0].strip()
        by_num.setdefault(int(row[0]), []).append((normalize_fullwidth_alnum(row[1]), normalize_name(en)))
    return by_num


def build_simple_table(filename):
    _, rows = load_csv(filename)
    table = {}
    for row in rows:
        jp, en = row[0], row[1]
        table[en] = normalize_fullwidth_alnum(jp)
    return table


def normalize_name(s):
    # PS側は "é" をNFD(結合分解形)、アポストロフィを "’" で持つことがあるため、
    # langmap/ 側(NFC・直立アポストロフィ)と比較できるようにそろえる。
    return unicodedata.normalize('NFC', s).replace('’', "'")


# langmap/ 側の和名に全角英数字が紛れているケース(例: "ポリゴン２")に備えて、
# data_jp/ に書き出す和名は英数字を半角に統一する(全角は半角に統一する方針)。
FULLWIDTH_ALNUM_TABLE = str.maketrans(
    '０１２３４５６７８９'
    'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
    'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
    '0123456789'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    'abcdefghijklmnopqrstuvwxyz',
)


def normalize_fullwidth_alnum(s):
    return s.translate(FULLWIDTH_ALNUM_TABLE)


def resolve_species_name(sid, name, num, forme, base_forme, species_by_num, unresolved, form_table):
    candidates = species_by_num.get(num, [])
    if not candidates:
        unresolved.append((sid, name, num, 'no base entry for dex num'))
        return name

    base_jp, base_en = candidates[0]

    if not forme and not base_forme:
        return base_jp

    # forme/baseForme のいずれかを持つ種族は langmap/_form_langmap.csv を必ず参照する。
    entry = form_table.get(normalize_name(name))
    if entry is not None:
        final_jp, _excluded = entry
        return final_jp
    unresolved.append((sid, name, num, f'no _form_langmap.csv entry for forme="{forme}" baseForme="{base_forme}"'))
    return base_jp


# 「特性名 (バリエーション)」形式のカッコ内は、対応する姿の和名タグに差し替える。
ABILITY_VARIANT_JP = {
    'Glastrier': 'はくば', 'Spectrier': 'こくば',  # じんばいったい
    'Teal': 'みどり', 'Wellspring': 'いど', 'Hearthflame': 'かまど', 'Cornerstone': 'いしずえ',  # おもかげやどし
}


def resolve_ability(en_name, ability_table, unresolved):
    if not en_name:
        return en_name
    if en_name in ability_table:
        return ability_table[en_name]
    if '(' in en_name and en_name.endswith(')'):
        base, paren = en_name[:en_name.index('(')].strip(), en_name[en_name.index('(') + 1:-1]
        base_jp = ability_table.get(base)
        if base_jp:
            paren_jp = ABILITY_VARIANT_JP.get(paren, paren)
            return f'{base_jp}({paren_jp})'
    unresolved.append(en_name)
    return en_name


def resolve_move(en_name, move_table, unresolved):
    if en_name in move_table:
        return move_table[en_name]
    normalized = normalize_name(en_name)
    for key, jp in move_table.items():
        if normalize_name(key) == normalized:
            return jp
    unresolved.append(en_name)
    return en_name


def main():
    os.makedirs(JP_DIR, exist_ok=True)

    species_by_num = build_species_table()
    form_table = load_form_table()
    additional_table = load_additional_table()
    ability_table = {**build_simple_table('ability_langmap.csv'), **additional_table}
    item_table = {**build_simple_table('item_langmap.csv'), **additional_table}
    move_table = {**build_simple_table('move_langmap.csv'), **additional_table}

    pokedex = json.load(open(os.path.join(EN_DIR, 'pokedex.json'), encoding='utf-8'))
    # scripts/build-data-en.js が langmap/_form_langmap.csv の exclude列を見て
    # data_en/pokedex.json から既に除外した種族(コスプレピカチュウ等)。ここでも和訳して
    # data_jp/pokedex_excluded.json に残す(data_jp/pokedex.json には含めない)。
    en_pokedex_excluded = json.load(open(os.path.join(EN_DIR, 'pokedex_excluded.json'), encoding='utf-8'))
    moves = json.load(open(os.path.join(EN_DIR, 'moves.json'), encoding='utf-8'))
    learnsets = json.load(open(os.path.join(EN_DIR, 'learnsets.json'), encoding='utf-8'))

    # 最終的に pokedex_excluded.json 送りになった種族(コスプレピカチュウ等の重複フォルム)は
    # data_jp/ の出力に含まれないため、その分の未解決 species/ability/item はログに出さない。
    # 1st pass の時点ではどの種族が除外されるか分からないので、いったん sid ごとに保持しておき、
    # 2nd pass で採用が確定した種族の分だけ最終的な unresolved_* に合流させる。
    unresolved_species_by_sid = {}
    unresolved_abilities = []
    unresolved_items = []
    unresolved_moves = []

    # 1st pass: 種族名を解決し、英語表示名 -> 和名 の対応表を作る (進化情報の変換に使う)
    # pokedex.json のキーは showdown_name(表示名)になったため、showdown_id が必要な箇所は
    # 辞書のキーではなく v['showdown_id'] を参照する。
    name_jp_by_en = {}
    for v in list(pokedex.values()) + list(en_pokedex_excluded.values()):
        sid = v['showdown_id']
        local_unresolved = []
        jp_name = resolve_species_name(
            sid, v['showdown_name'], v['num'], v['forme'], v['baseForme'], species_by_num, local_unresolved,
            form_table)
        if local_unresolved:
            unresolved_species_by_sid[sid] = local_unresolved[0][1:]
        name_jp_by_en[v['showdown_name']] = jp_name

    def build_entry(sid, v, unresolved_abilities, unresolved_items):
        item_jp = ''
        if v['requiredItem']:
            item_jp = item_table.get(v['requiredItem'])
            if item_jp is None:
                unresolved_items.append(v['requiredItem'])
                item_jp = v['requiredItem']

        return {
            'showdown_id': v['showdown_id'],
            'showdown_name': v['showdown_name'],
            'num': v['num'],
            'forme': v['forme'],
            'baseForme': v['baseForme'],
            'types': [TYPE_JP.get(t, t) for t in v['types']],
            'abilities': [
                resolve_ability(name, ability_table, unresolved_abilities)
                for name in v['abilities']
            ],
            'baseStats': v['baseStats'],
            'weight': v['weight'],
            'height': v['height'],
            'prevo': name_jp_by_en.get(v['prevo'], v['prevo']) if v['prevo'] else '',
            'evos': [name_jp_by_en.get(n, n) for n in v['evos']],
            'genderRatio': v['genderRatio'],
            'requiredItem': item_jp,
        }

    # 2nd pass: 和名をキーにpokedex_jpを組み立てる。
    # langmap/_form_langmap.csv の exclude列で明示的に除外指定された種族(コスプレピカチュウや
    # ビビヨンの模様違いなど、公式に固有の和名を持たないもの)は scripts/build-data-en.js が
    # 既に data_en/pokedex.json から取り除き data_en/pokedex_excluded.json 側に回しているため、
    # ここでの pokedex.values() には含まれない(下の en_pokedex_excluded ループで別途処理する)。
    # それでも和名が重複する場合(CSV未収録の新規フォルム等への保険)は、先に登場したものだけを
    # 残し、以降の重複を pokedex_excluded.json に記録して除外する。
    skipped_species = []
    pokedex_jp = {}
    pokedex_excluded = {}
    for v in pokedex.values():
        sid = v['showdown_id']
        jp_name = name_jp_by_en[v['showdown_name']]

        if jp_name in pokedex_jp:
            skipped_species.append((sid, v['showdown_name'], jp_name))
            pokedex_excluded[sid] = {
                **build_entry(sid, v, [], []),
                'name': jp_name,
                'reason': f'和名"{jp_name}"が既存エントリ(showdown_id={pokedex_jp[jp_name]["showdown_id"]})と重複',
            }
            continue

        pokedex_jp[jp_name] = build_entry(sid, v, unresolved_abilities, unresolved_items)

    # data_en/pokedex_excluded.json 側(exclude列による除外指定)も和訳して合流させる。
    for v in en_pokedex_excluded.values():
        sid = v['showdown_id']
        jp_name = name_jp_by_en[v['showdown_name']]
        pokedex_excluded[sid] = {
            **build_entry(sid, v, [], []),
            'name': jp_name,
            'reason': f'langmap/_form_langmap.csv の exclude列により除外指定(和名"{jp_name}")',
        }

    # 採用された(pokedex_jp に残った)種族の分だけ未解決speciesログに残す
    excluded_sids = {s for s, _, _ in skipped_species} | set(pokedex_excluded.keys())
    unresolved_species = [
        (sid, name, num, reason)
        for sid, (name, num, reason) in unresolved_species_by_sid.items()
        if sid not in excluded_sids
    ]

    # pokedex.json と同様、moves.json も和名をキーにする(showdown_id/showdown_name で元のidを保持)。
    moves_jp = {}
    mid_to_jp_name = {}
    for mid, v in moves.items():
        jp_name = resolve_move(v['showdown_name'], move_table, unresolved_moves)
        mid_to_jp_name[mid] = jp_name
        moves_jp[jp_name] = {
            **v,
            'type': TYPE_JP.get(v['type'], v['type']),
        }

    # learnsets.json: キーを showdown_id -> pokedex_jp のキー(和名)に、値を技ID -> moves_jp のキー(和名)に変換する。
    # pokedex_excluded 送りになった showdown_id(sid_to_jp_name に存在しない)は除外する。
    sid_to_jp_name = {v['showdown_id']: jp_name for jp_name, v in pokedex_jp.items()}
    learnsets_jp = {}
    for sid, move_ids in learnsets.items():
        jp_name = sid_to_jp_name.get(sid)
        if jp_name is None:
            continue
        learnsets_jp[jp_name] = [mid_to_jp_name[mid] for mid in move_ids]

    json.dump(pokedex_jp, open(os.path.join(JP_DIR, 'pokedex.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    json.dump(pokedex_excluded, open(os.path.join(JP_DIR, 'pokedex_excluded.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    json.dump(moves_jp, open(os.path.join(JP_DIR, 'moves.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    json.dump(learnsets_jp, open(os.path.join(JP_DIR, 'learnsets.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    print(f'pokedex: {len(pokedex_jp)} 件書き出し')
    print(f'pokedex_excluded: {len(pokedex_excluded)} 件書き出し')
    print(f'moves: {len(moves_jp)} 件書き出し')
    print(f'learnsets: {len(learnsets_jp)} 件書き出し')
    print()

    log_lines = []
    log_lines.append(f'[species] 未解決/ルール未収録 (ベース和名をそのまま使用): {len(unresolved_species)} 件')
    for sid, name, num, reason in unresolved_species:
        log_lines.append(f'  {sid}\t{name}\t#{num}\t{reason}')
    log_lines.append('')
    log_lines.append(f'[species] 和名キー衝突により除外: {len(skipped_species)} 件')
    for sid, name, jp_name in skipped_species:
        log_lines.append(f'  {sid}\t{name}\t-> {jp_name} (既存エントリと衝突)')
    log_lines.append('')
    log_lines.append(f'[ability] 未収録 (英語のまま): {len(unresolved_abilities)} 件')
    for name in sorted(set(unresolved_abilities)):
        log_lines.append(f'  {name}')
    log_lines.append('')
    log_lines.append(f'[item] 未収録 (英語のまま): {len(unresolved_items)} 件')
    for name in sorted(set(unresolved_items)):
        log_lines.append(f'  {name}')
    log_lines.append('')
    log_lines.append(f'[move] 未収録 (英語のまま): {len(unresolved_moves)} 件')
    for name in sorted(set(unresolved_moves)):
        log_lines.append(f'  {name}')

    log_path = os.path.join(JP_DIR, 'translate_unresolved.log')
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines) + '\n')

    print(f'[species] 未解決/ルール未収録: {len(unresolved_species)} 件')
    print(f'[species] 和名キー衝突により除外: {len(skipped_species)} 件')
    print(f'[ability] 未収録 (英語のまま): {len(unresolved_abilities)} 件')
    print(f'[item] 未収録 (英語のまま): {len(unresolved_items)} 件')
    print(f'[move] 未収録 (英語のまま): {len(unresolved_moves)} 件')
    print(f'詳細: {os.path.relpath(log_path, ROOT)}')


if __name__ == '__main__':
    main()
