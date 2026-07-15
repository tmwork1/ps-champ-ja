// data_en/ と data_jp/ の生成物に対する品質チェック。
// scripts/build-data-en.js -> scripts/translate-data.py を実行した後に使う。
// pokedex/pokedex_excluded/moves/learnsets が相互に矛盾なく対応しているか
// (1:1対応・宙に浮いた参照が無いか・en/jp間で内容が揃っているか)を検証する。
//
// Usage: node scripts/validate-data.js

const fs = require('fs');
const path = require('path');

const EN_DIR = path.join(__dirname, '..', 'data_en');
const JP_DIR = path.join(__dirname, '..', 'data_jp');
const LANGMAP_DIR = path.join(__dirname, '..', 'langmap');

function readJson(dir, name) {
	const filePath = path.join(dir, name);
	if (!fs.existsSync(filePath)) {
		console.error(`${filePath} が見つかりません。先に build-data-en.js / translate-data.py を実行してください。`);
		process.exit(1);
	}
	return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

// 技を1つも持たない(=このルールでは実質使用不可能な)種族のうち、既知のもの。
// アンノーン: 覚える技がめざめるパワー(現行仕様には無い)のみ。
// コスモッグ: 覚える技がすばやいツメ/テレポート(いずれも現行仕様には無い)のみ。
// これ以外に0件の種族が現れた場合は想定外なので FAIL 扱いにする。
const KNOWN_NO_LEARNSET = new Set(['unown', 'cosmog']);

let passCount = 0;
let failCount = 0;
let warnCount = 0;

function pass(label) {
	passCount++;
	console.log(`[PASS] ${label}`);
}

function fail(label, details) {
	failCount++;
	console.log(`[FAIL] ${label}`);
	if (details && details.length) {
		for (const d of details.slice(0, 20)) console.log(`         ${JSON.stringify(d)}`);
		if (details.length > 20) console.log(`         ...他 ${details.length - 20} 件`);
	}
}

function warn(label, details) {
	warnCount++;
	console.log(`[WARN] ${label}`);
	if (details && details.length) {
		for (const d of details.slice(0, 20)) console.log(`         ${JSON.stringify(d)}`);
		if (details.length > 20) console.log(`         ...他 ${details.length - 20} 件`);
	}
}

function check(label, badItems, {allow = new Set()} = {}) {
	const unexpected = badItems.filter(item => !allow.has(Array.isArray(item) ? item[0] : item));
	if (unexpected.length) fail(label, unexpected);
	else pass(label);
}

// --- データ読み込み ---
const enPokedex = readJson(EN_DIR, 'pokedex.json');
const enExcluded = readJson(EN_DIR, 'pokedex_excluded.json');
const enMoves = readJson(EN_DIR, 'moves.json');
const enLearnsets = readJson(EN_DIR, 'learnsets.json');

const jpPokedex = readJson(JP_DIR, 'pokedex.json');
const jpExcluded = readJson(JP_DIR, 'pokedex_excluded.json');
const jpMoves = readJson(JP_DIR, 'moves.json');
const jpLearnsets = readJson(JP_DIR, 'learnsets.json');

console.log('=== pokedex / pokedex_excluded の整合性 ===');

// pokedex と pokedex_excluded で showdown_id が重複していないか(排他的であるべき)。
function checkPartition(label, pokedex, excluded) {
	const ids = Object.values(pokedex).map(v => v.showdown_id);
	const exIds = Object.values(excluded).map(v => v.showdown_id);
	const overlap = ids.filter(id => exIds.includes(id));
	check(`${label}: pokedexとpokedex_excludedが重複していない`, overlap);
}
checkPartition('en', enPokedex, enExcluded);
checkPartition('jp', jpPokedex, jpExcluded);

console.log('\n=== pokedex ⇔ learnsets の対応 (en) ===');
{
	const pokedexIds = new Set(Object.values(enPokedex).map(v => v.showdown_id));
	const learnsetIds = new Set(Object.keys(enLearnsets));

	const orphanLearnsets = [...learnsetIds].filter(id => !pokedexIds.has(id));
	check('learnsetsのキーは全てpokedexに存在する', orphanLearnsets);

	const noLearnset = [...pokedexIds].filter(id => !learnsetIds.has(id));
	const unexpectedNoLearnset = noLearnset.filter(id => !KNOWN_NO_LEARNSET.has(id));
	if (unexpectedNoLearnset.length) fail('pokedexの全種族がlearnsetsを持つ(既知の例外を除く)', unexpectedNoLearnset);
	else if (noLearnset.length) warn('learnsetsを持たない種族(既知の例外)', noLearnset);
	else pass('pokedexの全種族がlearnsetsを持つ');

	const moveIds = new Set(Object.keys(enMoves));
	const badMoveRefs = [];
	for (const [sid, moveList] of Object.entries(enLearnsets)) {
		for (const moveId of moveList) if (!moveIds.has(moveId)) badMoveRefs.push([sid, moveId]);
	}
	check('learnsetsが参照する技は全てmoves.jsonに存在する', badMoveRefs);
}

console.log('\n=== pokedex ⇔ learnsets の対応 (jp) ===');
{
	const pokedexNames = new Set(Object.keys(jpPokedex));
	const learnsetNames = new Set(Object.keys(jpLearnsets));

	const orphanLearnsets = [...learnsetNames].filter(n => !pokedexNames.has(n));
	check('learnsetsのキーは全てpokedexに存在する', orphanLearnsets);

	const idBySid = new Map(Object.values(enPokedex).map(v => [v.showdown_id, v.showdown_name]));
	const jpSidByName = new Map(Object.entries(jpPokedex).map(([name, v]) => [name, v.showdown_id]));
	const noLearnset = [...pokedexNames].filter(n => !learnsetNames.has(n));
	const unexpectedNoLearnset = noLearnset.filter(n => !KNOWN_NO_LEARNSET.has(jpSidByName.get(n)));
	if (unexpectedNoLearnset.length) fail('pokedexの全種族がlearnsetsを持つ(既知の例外を除く)', unexpectedNoLearnset);
	else if (noLearnset.length) warn('learnsetsを持たない種族(既知の例外)', noLearnset);
	else pass('pokedexの全種族がlearnsetsを持つ');

	const moveNames = new Set(Object.keys(jpMoves));
	const badMoveRefs = [];
	for (const [name, moveList] of Object.entries(jpLearnsets)) {
		for (const moveName of moveList) if (!moveNames.has(moveName)) badMoveRefs.push([name, moveName]);
	}
	check('learnsetsが参照する技は全てmoves.jsonに存在する', badMoveRefs);
}

console.log('\n=== en ⇔ jp の対応 ===');
{
	// pokedex(採用分)+ pokedex_excluded(除外分) の showdown_id 集合は en/jp で完全一致するべき
	// (翻訳段階で種族が増減していないことの検証)。
	const enIds = new Set([
		...Object.values(enPokedex).map(v => v.showdown_id),
		...Object.values(enExcluded).map(v => v.showdown_id),
	]);
	const jpIds = new Set([
		...Object.values(jpPokedex).map(v => v.showdown_id),
		...Object.values(jpExcluded).map(v => v.showdown_id),
	]);
	const onlyInEn = [...enIds].filter(id => !jpIds.has(id));
	const onlyInJp = [...jpIds].filter(id => !enIds.has(id));
	check('en/jpの種族(showdown_id)集合が完全一致する(pokedex+excluded)', [...onlyInEn, ...onlyInJp]);

	// pokedexに採用されているか除外されているか、en/jpで判定が食い違っていないか。
	const enExcludedIds = new Set(Object.values(enExcluded).map(v => v.showdown_id));
	const jpExcludedIds = new Set(Object.values(jpExcluded).map(v => v.showdown_id));
	const onlyExcludedInEn = [...enExcludedIds].filter(id => !jpExcludedIds.has(id));
	const onlyExcludedInJp = [...jpExcludedIds].filter(id => !enExcludedIds.has(id));
	check('採用/除外の判定がen/jpで一致する', [...onlyExcludedInEn, ...onlyExcludedInJp]);

	// moves.json の showdown_id 集合も en/jp で一致するべき。
	const enMoveIds = new Set(Object.keys(enMoves));
	const jpMoveIds = new Set(Object.values(jpMoves).map(v => v.showdown_id));
	const onlyEnMoves = [...enMoveIds].filter(id => !jpMoveIds.has(id));
	const onlyJpMoves = [...jpMoveIds].filter(id => !enMoveIds.has(id));
	check('en/jpのmoves(showdown_id)集合が完全一致する', [...onlyEnMoves, ...onlyJpMoves]);

	// learnsets の内容(技の集合)も en/jp で一致するべき(和名を英名/idに変換して比較)。
	const jpNameToSid = new Map(Object.entries(jpPokedex).map(([name, v]) => [name, v.showdown_id]));
	const jpMoveNameToSid = new Map(Object.values(jpMoves).map(v => [v.showdown_name, v.showdown_id]));
	// jpMoveNameToSidはshowdown_nameキーではなく和名キーで引きたいので作り直す
	const jpMoveJpNameToSid = new Map(Object.entries(jpMoves).map(([jpName, v]) => [jpName, v.showdown_id]));

	const learnsetMismatches = [];
	for (const [jpName, jpMoveList] of Object.entries(jpLearnsets)) {
		const sid = jpNameToSid.get(jpName);
		if (!sid) continue; // 既に上のチェックでFAILしている
		const enMoveList = enLearnsets[sid];
		if (!enMoveList) continue;
		const enSet = new Set(enMoveList);
		const jpAsIds = new Set(jpMoveList.map(n => jpMoveJpNameToSid.get(n)).filter(Boolean));
		const onlyEn = enMoveList.filter(id => !jpAsIds.has(id));
		const onlyJp = [...jpAsIds].filter(id => !enSet.has(id));
		if (onlyEn.length || onlyJp.length) learnsetMismatches.push([sid, {onlyEn, onlyJp}]);
	}
	check('en/jpのlearnsetsの技集合が種族ごとに一致する', learnsetMismatches);
}

console.log('\n=== 進化チェーン(prevo/evos)の整合性 ===');
{
	// 除外(exclude=1)された種族が進化先/進化元として参照されたまま残っていないか。
	// (公式に固有名を持たないコスチューム違い等をexcludeした副作用で、他種族の
	//  evos/prevoが宙に浮くことがある。実害は無いが、把握のためWARNとして出す。)
	function checkEvoChain(label, pokedex) {
		const names = new Set(Object.keys(pokedex));
		const danglingPrevo = [];
		const danglingEvos = [];
		for (const [name, v] of Object.entries(pokedex)) {
			if (v.prevo && !names.has(v.prevo)) danglingPrevo.push([name, 'prevo', v.prevo]);
			for (const e of v.evos || []) if (!names.has(e)) danglingEvos.push([name, 'evos', e]);
		}
		const all = [...danglingPrevo, ...danglingEvos];
		if (all.length) warn(`${label}: prevo/evosが指す先がpokedexに存在しない(除外種族が進化先/元になっているケース)`, all);
		else pass(`${label}: prevo/evosの参照先は全てpokedexに存在する`);
	}
	checkEvoChain('en', enPokedex);
	checkEvoChain('jp', jpPokedex);

	// data_jp固有: prevo/evosが翻訳されずに英語のまま残っていないか。
	const isUntranslated = s => /^[A-Za-z0-9 '.\-]+$/.test(s);
	const untranslated = [];
	for (const [name, v] of Object.entries(jpPokedex)) {
		if (v.prevo && isUntranslated(v.prevo)) untranslated.push([name, 'prevo', v.prevo]);
		for (const e of v.evos || []) if (isUntranslated(e)) untranslated.push([name, 'evos', e]);
	}
	check('jp: prevo/evosが未翻訳(英語のまま)で残っていない', untranslated);
}

console.log('\n=== langmap/_form_langmap.csv の整合性 ===');
{
	function parseCsvLine(line) {
		const fields = [];
		let field = '';
		let inQuotes = false;
		for (let i = 0; i < line.length; i++) {
			const c = line[i];
			if (inQuotes) {
				if (c === '"') {
					if (line[i + 1] === '"') { field += '"'; i++; }
					else inQuotes = false;
				} else field += c;
			} else if (c === '"') {
				inQuotes = true;
			} else if (c === ',') {
				fields.push(field);
				field = '';
			} else {
				field += c;
			}
		}
		fields.push(field);
		return fields;
	}

	const csvPath = path.join(LANGMAP_DIR, '_form_langmap.csv');
	if (!fs.existsSync(csvPath)) {
		fail('langmap/_form_langmap.csv が見つかる', []);
	} else {
		let text = fs.readFileSync(csvPath, 'utf8');
		if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
		const lines = text.split(/\r?\n/).filter(l => l.length > 0);
		const header = parseCsvLine(lines[0]);
		const rows = lines.slice(1).map((line, i) => ({line: i + 2, fields: parseCsvLine(line)}));

		check('ヘッダーが想定通り', header.join(',') === 'exclude,showdown_name,baseForme,base_jp,final_jp' ? [] : [header]);

		const malformed = rows.filter(r => r.fields.length !== 5).map(r => [r.line, r.fields]);
		check('全行が5列である(カンマがクォートされずに列崩れしていない)', malformed);

		const badExclude = rows.filter(r => !['0', '1'].includes(r.fields[0])).map(r => [r.line, r.fields[0]]);
		check('exclude列が全て"0"か"1"である', badExclude);

		const names = rows.map(r => r.fields[1]);
		const nameCounts = new Map();
		for (const n of names) nameCounts.set(n, (nameCounts.get(n) || 0) + 1);
		const dupNames = [...nameCounts.entries()].filter(([, c]) => c > 1).map(([n]) => n);
		check('showdown_nameが重複していない', dupNames);

		// data_en側(採用分+除外分)でforme/baseFormeを持つ種族の集合と完全一致するべき。
		const normalizeName = s => s.normalize('NFC').replace(/’/g, "'");
		const expectedNames = new Set(
			[...Object.values(enPokedex), ...Object.values(enExcluded)]
				.filter(v => v.forme || v.baseForme)
				.map(v => normalizeName(v.showdown_name))
		);
		const csvNames = new Set(names.map(normalizeName));
		const missingFromCsv = [...expectedNames].filter(n => !csvNames.has(n));
		const extraInCsv = [...csvNames].filter(n => !expectedNames.has(n));
		check('data_enでforme/baseForme持ちの種族とCSVの行が完全一致する', [...missingFromCsv, ...extraInCsv]);

		// exclude=1の行のshowdown_idはdata_en/pokedex_excluded.jsonに、
		// exclude=0の行のshowdown_idはdata_en/pokedex.jsonに、それぞれ存在するべき。
		const enIdByName = new Map(
			[...Object.values(enPokedex), ...Object.values(enExcluded)]
				.map(v => [normalizeName(v.showdown_name), v])
		);
		const enExcludedNames = new Set(Object.values(enExcluded).map(v => normalizeName(v.showdown_name)));
		const enKeptNames = new Set(Object.values(enPokedex).map(v => normalizeName(v.showdown_name)));
		const mismatch = [];
		for (const r of rows) {
			const name = normalizeName(r.fields[1]);
			const exclude = r.fields[0];
			if (exclude === '1' && !enExcludedNames.has(name)) mismatch.push([name, 'exclude=1だがdata_en/pokedex_excluded.jsonに無い']);
			if (exclude === '0' && !enKeptNames.has(name)) mismatch.push([name, 'exclude=0だがdata_en/pokedex.jsonに無い']);
		}
		check('exclude列の値とdata_enでの採用/除外が一致する', mismatch);

		// 括弧の対応・連続括弧の未統合チェック(手動編集時のtypo検出用)。
		const parenIssues = [];
		for (const r of rows) {
			const finalJp = r.fields[4];
			const openCount = (finalJp.match(/\(/g) || []).length;
			const closeCount = (finalJp.match(/\)/g) || []).length;
			if (openCount !== closeCount) parenIssues.push([r.fields[1], finalJp, '括弧の対応が取れていない']);
			if (finalJp.includes(')(')) parenIssues.push([r.fields[1], finalJp, '連続括弧が未統合(カンマ区切りにすべき)']);
			if (finalJp.includes('（') || finalJp.includes('）')) parenIssues.push([r.fields[1], finalJp, '全角括弧が混入']);
		}
		check('final_jpの括弧表記が正しい(対応・半角・連続括弧の統合)', parenIssues);
	}
}

console.log('\n=== 値の形状チェック ===');
{
	function checkShape(label, pokedex) {
		const bad = [];
		for (const [name, v] of Object.entries(pokedex)) {
			const statKeys = ['hp', 'atk', 'def', 'spa', 'spd', 'spe'];
			const hasAllStats = statKeys.every(k => typeof v.baseStats[k] === 'number');
			if (!hasAllStats) bad.push([name, 'baseStatsが不正']);
			if (!Array.isArray(v.types) || v.types.length < 1 || v.types.length > 2) bad.push([name, 'typesが1〜2件でない']);
			if (!Array.isArray(v.abilities) || v.abilities.length < 1) bad.push([name, 'abilitiesが空']);
		}
		check(`${label}: baseStats/types/abilitiesの形状が正しい`, bad);
	}
	checkShape('en', enPokedex);
	checkShape('jp', jpPokedex);
}

console.log(`\n=== 結果: ${passCount} PASS / ${warnCount} WARN / ${failCount} FAIL ===`);
process.exit(failCount > 0 ? 1 : 0);
