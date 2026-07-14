// Pokemon Showdown の champions mod から図鑑・技・覚える技のデータを、
// PS自身のオブジェクト構造のまま(リネームやフィルタなし)JSONとして data_raw/ に書き出す。
// CAP/Custom/Future/LGPE種族や isNonstandard な技も含め、全件をそのまま保存する。
// data_en/ への変換(除外・リネーム・PP再計算など)は scripts/build-data-en.js が担う。
//
// 実行前提: 隣ディレクトリに pokemon-showdown のチェックアウトがビルド済みで存在すること
// (このリポジトリと同じ親フォルダに `pokemon-showdown/` があり、`npm run build` 済みで
// dist/sim/dex.js が生成されている状態)。
//
// Usage: node scripts/extract-champions-raw.js [path/to/pokemon-showdown]

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

const outDir = path.join(__dirname, '..', 'data_raw');
fs.mkdirSync(outDir, {recursive: true});

function buildPokedex() {
	const pokedex = {};
	for (const species of dex.species.all()) {
		pokedex[species.id] = species;
	}
	return pokedex;
}

function buildMoves() {
	const moves = {};
	for (const move of dex.moves.all()) {
		moves[move.id] = move;
	}
	return moves;
}

// getLearnsetData() の species フィールドは pokedex.json と重複するSpeciesオブジェクトの
// 埋め込みになってしまう(循環参照ではないが丸ごと二重保存になる)ため、ここだけ間引く。
function buildLearnsets(pokedex) {
	const learnsets = {};
	for (const id of Object.keys(pokedex)) {
		const {species, ...data} = dex.species.getLearnsetData(id) || {};
		learnsets[id] = data;
	}
	return learnsets;
}

const pokedex = buildPokedex();
const moves = buildMoves();
const learnsets = buildLearnsets(pokedex);

fs.writeFileSync(path.join(outDir, 'pokedex.json'), JSON.stringify(pokedex, null, 2));
fs.writeFileSync(path.join(outDir, 'moves.json'), JSON.stringify(moves, null, 2));
fs.writeFileSync(path.join(outDir, 'learnsets.json'), JSON.stringify(learnsets, null, 2));

console.log(`pokedex: ${Object.keys(pokedex).length} 種(未フィルタ)`);
console.log(`moves: ${Object.keys(moves).length} 技(未フィルタ)`);
console.log(`learnsets: ${Object.keys(learnsets).length} 種分`);
