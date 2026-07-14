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
      フォルム違い(メガ/リージョンフォルム等)の和名は、公式で確立している組み合わせのみ
      FORM_RULES に明記して合成する。未収録の組み合わせ(コスチューム違いなど、実際のゲームでも
      固有の表示名を持たないもの)はベースの和名をそのまま使い、翻訳漏れとして一覧に出力する。
      基本フォルムであっても baseForme(例: オドリドリの"Baile")を持つ種族は同じ仕組みで
      「ベース和名(フォルム)」に合成する対象になる(単純な無印名にはしない)。
      abilities は data_en 側の {スロット: 特性名} オブジェクトから、data_jp 側では
      スロット情報を落として和名の配列に変換する。
      data_jp/pokedex.json は data_en と異なりキーを和名にする(showdown_id/showdown_name
      としてshowdownのid/nameを残す)。weightkg/heightmはweight/heightにリネームする。
      和名がフォルム間で重複する場合(コスプレピカチュウ、ビビヨンの模様違いなど、公式に
      固有の和名を持たないもの)は最初に登場したフォルムだけを残し、以降は
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
# ものを手動で補う対応表。langmap/_additional_langmap.csv (英語,和名 のヘッダ無しCSV) に
# 追記していく。ability/item 共通の名前空間として両方のテーブルにマージする。
def load_additional_table():
    path = os.path.join(TRANSLATION_DIR, '_additional_langmap.csv')
    if not os.path.exists(path):
        return {}
    table = {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        for row in csv.reader(f):
            if not row or not row[0]:
                continue
            en, jp = row[0], row[1]
            table[en] = normalize_fullwidth_alnum(jp)
    return table


TYPE_JP = {
    'Normal': 'ノーマル', 'Fire': 'ほのお', 'Water': 'みず', 'Electric': 'でんき',
    'Grass': 'くさ', 'Ice': 'こおり', 'Fighting': 'かくとう', 'Poison': 'どく',
    'Ground': 'じめん', 'Flying': 'ひこう', 'Psychic': 'エスパー', 'Bug': 'むし',
    'Rock': 'いわ', 'Ghost': 'ゴースト', 'Dragon': 'ドラゴン', 'Dark': 'あく',
    'Steel': 'はがね', 'Fairy': 'フェアリー', 'Stellar': 'ステラ',
}

# (num, PS名の "-" 以降の部分) -> {base} をベース和名として展開するテンプレート
FORM_RULES = {
    # メガシンカ
    'Mega': 'メガ{base}',
    'Mega-X': 'メガ{base}X',
    'Mega-Y': 'メガ{base}Y',
    'Mega-Z': 'メガ{base}Z',
    # キョダイマックス
    'Gmax': '{base}(キョダイ)',
    'Low-Key-Gmax': '{base}(ロー)(キョダイ)',
    'Rapid-Strike-Gmax': '{base}(れんげき)(キョダイ)',
    # リージョンフォルム
    'Alola': '{base}(アローラ)',
    'Alola-Totem': '{base}(アローラ)(ボス)',
    'Galar': '{base}(ガラル)',
    'Galar-Zen': '{base}(ガラル)(ダルマ)',
    'Hisui': '{base}(ヒスイ)',
    'Paldea': '{base}(パルデア)',
    'Paldea-Combat': '{base}(パルデア闘)',
    'Paldea-Blaze': '{base}(パルデア炎)',
    'Paldea-Aqua': '{base}(パルデア水)',
    # ボスポケモン(タテヌシ)
    'Totem': '{base}(ボス)',
    'Busted': '{base}(ばれたすがた)',
    'Busted-Totem': '{base}(ばれたすがた)(ボス)',
    # 原始回帰・オリジン・れいじゅう
    'Primal': '{base}(ゲンシカイキ)',
    'Origin': '{base}(オリジン)',
    'Therian': '{base}(れいじゅう)',
    'Zen': '{base}(ダルマ)',
    # デオキシス
    'Attack': '{base}(アタック)',
    'Defense': '{base}(ディフェンス)',
    'Speed': '{base}(スピード)',
    # ミノムッチ/ミノマダム
    'Sandy': '{base}(すなち)',
    'Trash': '{base}(ゴミ)',
    # ロトム(接頭)
    'Heat': 'ヒート{base}',
    'Wash': 'ウォッシュ{base}',
    'Frost': 'フロスト{base}',
    'Fan': 'スピン{base}',
    'Mow': 'カット{base}',
    # キュレム(接頭)
    'White': 'ホワイト{base}',
    'Black': 'ブラック{base}',
    # バスラオ
    'Blue-Striped': '{base}(あお)',
    'White-Striped': '{base}(しろ)',
    # ケルディオ
    'Resolute': '{base}(かくご)',
    # ゲノセクト(ドライブ)
    'Douse': '{base}(ダウズドライブ)',
    'Shock': '{base}(ショックドライブ)',
    'Burn': '{base}(バーンドライブ)',
    'Chill': '{base}(チルドライブ)',
    # エーフィ/ブラッキー枠ではなくアギルダー
    'Blade': '{base}(ブレード)',
    # シェイミ
    'Sky': '{base}(スカイ)',
    # ネクロズマ
    'Dusk-Mane': '{base}(たそがれ)',
    'Dawn-Wings': '{base}(あかつき)',
    'Ultra': '{base}(ウルトラネクロズマ)',
    # ジガルデ
    '10%': '{base}(10%)',
    'Complete': '{base}(パーフェクト)',
    # フーパ
    'Unbound': '{base}(ときはなたれし)',
    # ウッウ
    'Gulping': '{base}(うのみ)',
    'Gorging': '{base}(まるのみ)',
    # コオリッポ
    'Noice': '{base}(ナイス)',
    # モルペコ
    'Hangry': '{base}(はらぺこ)',
    # ムゲンダイナ
    'Eternamax': '{base}(ムゲンダイマックス)',
    # ウルサルーナ
    'Bloodmoon': '{base}(アカツキ)',
    # イッカネズミ
    'Four': '{base}(よにんかぞく)',
    # パーモット
    'Hero': '{base}(ヒーロー)',
    # シャリタツ
    'Droopy': '{base}(たれた)',
    'Stretchy': '{base}(のびた)',
    # コレクレー→パオジアン等は対象外(番号なし)
    # ドゥドゥ
    'Three-Segment': '{base}(みつくびがた)',
    # オーガポン
    'Wellspring': '{base}(いど)',
    'Hearthflame': '{base}(かまど)',
    'Cornerstone': '{base}(いしずえ)',
    'Teal-Tera': '{base}(テラスタル)',
    'Wellspring-Tera': '{base}(いど)(テラスタル)',
    'Hearthflame-Tera': '{base}(かまど)(テラスタル)',
    'Cornerstone-Tera': '{base}(いしずえ)(テラスタル)',
    # テラパゴス
    'Terastal': '{base}(テラスタル)',
    'Stellar': '{base}(ステラ)',
    # ニャオニクス
    'F-Mega': 'メガ{base}(メス)',
    'M-Mega': 'メガ{base}(オス)',
    # 性別で見た目が変わる種族共通
    'F': '{base}(メス)',
    # ポワルン
    'Sunny': '{base}(たいよう)',
    'Rainy': '{base}(あまみず)',
    'Snowy': '{base}(ゆきぐも)',
    # フラエッテ
    'Eternal': '{base}(えいえん)',
    # メロエッタ
    'Pirouette': '{base}(ステップ)',
    # バケッチャ/パンプジン
    'Small': '{base}(ちいさい)',
    'Large': '{base}(おおきい)',
    'Super': '{base}(とくだい)',
    # ストリンダー
    'Low-Key': '{base}(ロー)',
    # ウーラオス
    'Rapid-Strike': '{base}(れんげき)',
    # メテノ
    'Meteor': '{base}(りゅうせい)',
    # ザルード
    'Dada': '{base}(ダディ)',
    # コレクレー
    'Roaming': '{base}(あるくすがた)',
}

# メテノのコア色(色による固有名は無く公式表記は全色共通で「コア」)
MINIOR_CORE_COLORS = {'Orange', 'Yellow', 'Green', 'Blue', 'Indigo', 'Violet'}

# num を限定しないと衝突するもの (num, suffix) -> template
# suffixは差分フォルムでは forme、基本フォルムでは baseForme の値がそのまま入る
# (例: オドリドリの基本フォルムは forme="" だが baseForme="Baile" を持つ)。
FORM_RULES_BY_NUM = {
    (646, 'White'): 'ホワイト{base}',
    (646, 'Black'): 'ブラック{base}',
    (898, 'Ice'): '{base}(はくば)',       # バドレックス(白馬)
    (898, 'Shadow'): '{base}(こくば)',    # バドレックス(黒馬)
    (493, 'Ice'): '{base}(こおり)',       # アルセウス: タイプ違いに公式固有名はないため意訳
    (773, 'Ice'): '{base}(こおり)',       # シルヴァディ: 同上
    (745, 'Midnight'): '{base}(まよなか)',  # ルガルガン(まよなかのすがた)
    (745, 'Dusk'): '{base}(たそがれ)',      # ルガルガン(たそがれのすがた)
    # ザシアン/ザマゼンタの基本フォルム(baseForme="Hero")はパフュートンの
    # 'Hero'(ヒーロー)FORM_RULESと英語表記が衝突するため num限定で上書きする。
    (888, 'Hero'): '{base}(れきせん)',
    (889, 'Hero'): '{base}(れきせん)',
    # オドリドリ(基本フォルム含む4スタイル。公式のスタイル名から「スタイル」を除いた形で表記)
    (741, 'Baile'): '{base}(めらめら)',
    (741, 'Pom-Pom'): '{base}(ぱちぱち)',
    (741, "Pa'u"): '{base}(ふらふら)',
    (741, 'Sensu'): '{base}(まいまい)',
    # ヨワシ(基本フォルム含む2すがた)
    (746, 'Solo'): '{base}(たんどく)',
    (746, 'School'): '{base}(むれ)',
    # イキリンコ(基本フォルム含む4色。公式に固有名は無いコスチューム違いのため色名を意訳)
    (931, 'Green'): '{base}(グリーン)',
    (931, 'Blue'): '{base}(ブルー)',
    (931, 'Yellow'): '{base}(イエロー)',
    (931, 'White'): '{base}(ホワイト)',
}
for _t_en, _t_jp in TYPE_JP.items():
    if _t_en != 'Ice':
        FORM_RULES_BY_NUM[(493, _t_en)] = '{base}(' + _t_jp + ')'  # アルセウス
        FORM_RULES_BY_NUM[(773, _t_en)] = '{base}(' + _t_jp + ')'  # シルヴァディ
for _color in MINIOR_CORE_COLORS:
    FORM_RULES_BY_NUM[(774, _color)] = '{base}(コア)'  # メテノ: コア状態は色によらず表記共通

# ベースの英名からの単純な差分では表現できない特殊ケース (species id -> 和名)
ID_OVERRIDES = {
    'nidoranf': 'ニドラン♀',
    'nidoranm': 'ニドラン♂',
    'greninjaash': 'サトシゲッコウガ',
    'zaciancrowned': 'ザシアン(けんのおう)',
    'zamazentacrowned': 'ザマゼンタ(たてのおう)',
    'pichuspikyeared': 'ギザみみピチュー',
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


def resolve_species_name(sid, name, num, forme, base_forme, species_by_num, unresolved):
    if sid in ID_OVERRIDES:
        return ID_OVERRIDES[sid]

    candidates = species_by_num.get(num, [])
    if not candidates:
        unresolved.append((sid, name, num, 'no base entry for dex num'))
        return name

    base_jp, base_en = candidates[0]

    # 差分フォルムは forme、基本フォルムは(baseFormeを持つ場合のみ)baseForme を
    # 合成対象のサフィックスとして扱う。どちらも無ければ基本フォルムの和名をそのまま使う。
    suffix = forme or base_forme
    if not suffix:
        return base_jp

    if (num, suffix) in FORM_RULES_BY_NUM:
        template = FORM_RULES_BY_NUM[(num, suffix)]
        if template is None:
            return base_jp
        return template.format(base=base_jp)

    template = FORM_RULES.get(suffix)
    if template:
        return template.format(base=base_jp)

    unresolved.append((sid, name, num, f'no form rule for suffix "{suffix}"'))
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
    additional_table = load_additional_table()
    ability_table = {**build_simple_table('ability_langmap.csv'), **additional_table}
    item_table = {**build_simple_table('item_langmap.csv'), **additional_table}
    move_table = {**build_simple_table('move_langmap.csv'), **additional_table}

    pokedex = json.load(open(os.path.join(EN_DIR, 'pokedex.json'), encoding='utf-8'))
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
    name_jp_by_en = {}
    for sid, v in pokedex.items():
        local_unresolved = []
        jp_name = resolve_species_name(
            sid, v['showdown_name'], v['num'], v['forme'], v['baseForme'], species_by_num, local_unresolved)
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

    # 2nd pass: 和名をキーにpokedex_jpを組み立てる。コスプレピカチュウやビビヨンの模様違いなど
    # 公式に固有の和名を持たないフォルムは和名が重複するため、先に登場したものだけを残し、
    # 以降の重複は pokedex_excluded.json に理由付きで記録して除外する。
    skipped_species = []
    pokedex_jp = {}
    pokedex_excluded = {}
    for sid, v in pokedex.items():
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

    # 採用された(pokedex_jp に残った)種族の分だけ未解決speciesログに残す
    unresolved_species = [
        (sid, name, num, reason)
        for sid, (name, num, reason) in unresolved_species_by_sid.items()
        if sid not in {s for s, _, _ in skipped_species}
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
