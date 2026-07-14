// Pokemon Showdown の champions mod から図鑑・技・覚える技の静的データを抽出し、
// 英語のフラットJSONとして data_en/ 以下に書き出す。
//
// 実行前提: 隣ディレクトリに pokemon-showdown のチェックアウトがビルド済みで存在すること
// (このリポジトリと同じ親フォルダに `pokemon-showdown/` があり、`npm run build` 済みで
// dist/sim/dex.js が生成されている状態)。
//
// Usage: node scripts/extract-champions.js [path/to/pokemon-showdown]

const fs = require('fs');
const path = require('path');

const psRoot = path.resolve(process.argv[2] || path.join(__dirname, '..', '..', 'pokemon-showdown'));
const dexPath = path.join(psRoot, 'dist', 'sim', 'dex.js');
if (!fs.existsSync(dexPath)) {
	console.error(`pokemon-showdown のビルド済み dex.js が見つかりません: ${dexPath}`);
	console.error('pokemon-showdown 側で `npm run build` を実行してから再試行してください。');
	process.exit(1);
}

const {Dex} = require(dexPath);
const dex = Dex.mod('champions');

// CAP(自作ポケモン)/Custom(ジョーク・映画等)/Future(未公式のメガ進化案)/LGPE(レッツゴー限定フォルム)
// は実在の図鑑データとして扱わない。null(現行)とPast(現行SVの図鑑には無いが実在)は残す。
const EXCLUDED_SPECIES_TAGS = new Set(['CAP', 'Custom', 'Future', 'LGPE']);

const outDir = path.join(__dirname, '..', 'data_en');
fs.mkdirSync(outDir, {recursive: true});

function buildPokedex() {
	const pokedex = {};
	for (const species of dex.species.all()) {
		if (EXCLUDED_SPECIES_TAGS.has(species.isNonstandard)) continue;

		pokedex[species.id] = {
			name: species.name,
			num: species.num,
			weight: species.weightkg,
			height: species.heightm,
			type_1: species.types[0] || '',
			type_2: species.types[1] || '',
			ability_1: species.abilities['0'] || '',
			ability_2: species.abilities['1'] || '',
			ability_3: species.abilities['H'] || '',
			hp: species.baseStats.hp,
			atk: species.baseStats.atk,
			def: species.baseStats.def,
			spa: species.baseStats.spa,
			spd: species.baseStats.spd,
			spe: species.baseStats.spe,
			pre_evolution: species.prevo ? [species.prevo] : [],
			post_evolution: species.evos || [],
		};
	}
	return pokedex;
}

// championsの生の pp フィールドは内部値で、実際にプレイヤーへ表示される最大PPは
// data/mods/champions/scripts.ts の calculatePP() が定義する変換式
// `noPPBoosts ? pp : (pp / 5 + 1) * 4` を通した値(8/12/16/20の4段階)になる。
function calculatePP(move) {
	return move.noPPBoosts ? move.pp : (move.pp / 5 + 1) * 4;
}

// champions は現行SVルールがベースなので、実際に使用可能な技(isNonstandard === null)のみを対象にする。
function buildMoves() {
	const moves = {};
	for (const move of dex.moves.all()) {
		if (move.isNonstandard !== null) continue;

		moves[move.id] = {
			name: move.name,
			type: move.type,
			category: move.category,
			pp: calculatePP(move),
			power: move.basePower || null,
			accuracy: move.accuracy === true ? null : move.accuracy,
			priority: move.priority,
			critical_rank: (move.critRatio || 1) - 1,
			target: move.target,
			multi_hit: move.multihit || null,
			flags: Object.keys(move.flags || {}).filter(k => move.flags[k]).sort(),
		};
	}
	return moves;
}

// megaやキョダイマックス等の battleOnly フォルムは、そのフォルム自体では技を覚えず
// 元の種族(baseSpecies)の覚える技をそのまま引き継ぐ(PSのチーム検証と同じ扱い)。
function collectRawLearnsetIds(id, seen = new Set()) {
	if (seen.has(id)) return new Set();
	seen.add(id);

	const data = dex.species.getLearnsetData(id);
	const ids = new Set(Object.keys((data && data.learnset) || {}));

	const species = dex.species.get(id);
	if (species.battleOnly) {
		const bases = Array.isArray(species.battleOnly) ? species.battleOnly : [species.battleOnly];
		for (const base of bases) {
			for (const moveId of collectRawLearnsetIds(dex.species.get(base).id, seen)) ids.add(moveId);
		}
	}
	return ids;
}

// 現行ルールで使える技だけに絞った上でのフォールバック判定。
// アローラ・ヒスイ等の地方フォルムは独自の learnset を持つため素通しするが、
// Arceusのタイプ違いやUnownの文字違い、Necrozmaの融合フォルムのように
// 自前の技が全て対象外(isNonstandard != null)で0件になってしまう場合だけ、
// 見た目違いの元になっている baseSpecies の技を借りてくる。
function resolveValidMoveIds(id, moves, seen = new Set()) {
	if (seen.has(id)) return [];
	seen.add(id);

	const ownIds = [...collectRawLearnsetIds(id)].filter(moveId => moveId in moves);
	if (ownIds.length) return ownIds;

	const species = dex.species.get(id);
	if (species.baseSpecies !== species.name) {
		const baseId = dex.species.get(species.baseSpecies).id;
		return resolveValidMoveIds(baseId, moves, seen);
	}
	return ownIds;
}

function buildLearnsets(pokedex, moves) {
	const learnsets = {};
	let droppedCount = 0;
	for (const id of Object.keys(pokedex)) {
		const rawIds = collectRawLearnsetIds(id);
		droppedCount += [...rawIds].filter(moveId => !(moveId in moves)).length;

		const moveIds = resolveValidMoveIds(id, moves).sort();
		if (moveIds.length) learnsets[id] = moveIds;
	}
	console.log(`[learnsets] 対象外(isNonstandard != null)の技への参照を ${droppedCount} 件除外しました。`);
	return learnsets;
}

const pokedex = buildPokedex();
const moves = buildMoves();
const learnsets = buildLearnsets(pokedex, moves);

fs.writeFileSync(path.join(outDir, 'pokedex.json'), JSON.stringify(pokedex, null, 2));
fs.writeFileSync(path.join(outDir, 'moves.json'), JSON.stringify(moves, null, 2));
fs.writeFileSync(path.join(outDir, 'learnsets.json'), JSON.stringify(learnsets, null, 2));

console.log(`pokedex: ${Object.keys(pokedex).length} 種`);
console.log(`moves: ${Object.keys(moves).length} 技`);
console.log(`learnsets: ${Object.keys(learnsets).length} 種分`);
