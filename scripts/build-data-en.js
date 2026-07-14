// data_raw/ (Pokemon Showdown のオブジェクトをそのまま保存したもの) を、
// ps-champ-ja 用の英語フラットJSONに変換して data_en/ に書き出す。
// pokemon-showdown のチェックアウトには依存しない(data_raw/ さえあれば実行できる)。
//
// Usage: node scripts/build-data-en.js

const fs = require('fs');
const path = require('path');

const rawDir = path.join(__dirname, '..', 'data_raw');
const outDir = path.join(__dirname, '..', 'data_en');

function readRaw(name) {
	const filePath = path.join(rawDir, name);
	if (!fs.existsSync(filePath)) {
		console.error(`data_raw/${name} が見つかりません。先に scripts/extract-champions-raw.js を実行してください。`);
		process.exit(1);
	}
	return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

const rawPokedex = readRaw('pokedex.json');
const rawMoves = readRaw('moves.json');
const rawLearnsets = readRaw('learnsets.json');

// species.battleOnly / species.baseSpecies はPSの生データでは表示名(name)で持たれているため、
// name -> id の対応表を作っておく(pokemon-showdown の toID() には依存しない)。
const idByName = new Map();
for (const species of Object.values(rawPokedex)) {
	idByName.set(species.name, species.id);
}

fs.mkdirSync(outDir, {recursive: true});

// CAP(自作ポケモン)/Custom(ジョーク・映画等)/Future(未公式のメガ進化案)/LGPE(レッツゴー限定フォルム)
// は実在の図鑑データとして扱わない。null(現行)とPast(現行SVの図鑑には無いが実在)は残す。
const EXCLUDED_SPECIES_TAGS = new Set(['CAP', 'Custom', 'Future', 'LGPE']);

// PSの生データ(species)のキー名・構造はリネーム/整形せずそのまま残し、
// 対戦に不要なキー(タマゴグループ・使用率ランク等)だけを落とす(pick)。
const POKEDEX_KEYS = [
	'name', 'num', 'forme', 'types', 'abilities', 'baseStats',
	'weightkg', 'heightm', 'prevo', 'evos', 'genderRatio', 'requiredItem',
];

function buildPokedex() {
	const pokedex = {};
	for (const species of Object.values(rawPokedex)) {
		if (EXCLUDED_SPECIES_TAGS.has(species.isNonstandard)) continue;

		const entry = {};
		for (const key of POKEDEX_KEYS) entry[key] = species[key];
		pokedex[species.id] = entry;
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
	for (const move of Object.values(rawMoves)) {
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

	const data = rawLearnsets[id];
	const ids = new Set(Object.keys((data && data.learnset) || {}));

	const species = rawPokedex[id];
	if (species && species.battleOnly) {
		const bases = Array.isArray(species.battleOnly) ? species.battleOnly : [species.battleOnly];
		for (const base of bases) {
			for (const moveId of collectRawLearnsetIds(idByName.get(base), seen)) ids.add(moveId);
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

	const species = rawPokedex[id];
	if (species.baseSpecies !== species.name) {
		const baseId = idByName.get(species.baseSpecies);
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
