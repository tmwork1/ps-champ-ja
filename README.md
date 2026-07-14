# ps-champ-ja

Pokemon Showdown の `champions` mod の図鑑・技・覚える技データを、対戦に必要なスキーマへ
整形した上で日本語訳したデータセット。

> 本プロジェクトは株式会社ポケモン・任天堂・株式会社ゲームフリークとは無関係の非公式（fan-made）
> プロジェクトです。
>
> This is an unofficial, fan-made project and is not affiliated with, endorsed by, or sponsored by
> Nintendo, Game Freak, or The Pokémon Company.

## データの出典

- `data_raw/` `data_en/`: [Pokemon Showdown](https://github.com/smogon/pokemon-showdown) の
  `champions` mod から抽出
- `langmap/*.csv`(リポジトリには含めず、`scripts/download-langmap.py` で
  [tmwork1/poke-langmap](https://github.com/tmwork1/poke-langmap) からダウンロードする)
  および、それを用いて生成した `data_jp/`: [ポケモンWiki](https://wiki.pokemonwiki.com/)
  の外国語名一覧等を出典とする和名対応表([CC BY-NC-SA 3.0](https://wiki.pokemonwiki.com/wiki/%E3%83%9D%E3%82%B1%E3%83%A2%E3%83%B3Wiki:%E8%91%97%E4%BD%9C%E6%A8%A9))
- `jpoke/`: 自作の [jpoke](https://github.com/tmwork1/jpoke) プロジェクトの和名データを再利用

## ライセンス

コードとデータでライセンスを分けています(CC BY-NC-SA はコードへの適用が非推奨のため)。

- `scripts/`: [MIT](./LICENSE)
- `data_raw/` `data_en/` `data_jp/` `jpoke/`: [CC BY-NC-SA 4.0](./LICENSE-DATA)

ポケモンの名称・種族値等のゲームデータ自体の権利は任天堂・株式会社ゲームフリーク・
株式会社ポケモンに帰属します。上記ライセンスが及ぶのは本リポジトリの構成・変換スクリプト・
翻訳対応表の部分のみです。
