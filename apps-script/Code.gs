/**
 * 墨竹亭 光復店 耗損登記表 — 後端
 * 職責只有「存」與「取」，一律不算金額（金額在前端 calc.makeRecord() 算好才送上來）。
 */

var SS_NAME = '墨竹亭光復 耗損登記表';

var ITEM_COLS = ['品名', '品類', '單位', '單位成本', '停用', '更新時間'];
var LOSS_COLS = ['id', '日期', '店別', '品類', '品名', '耗損量', '單位', '單位成本',
  '金額', '原因', '原因說明', '備註', '建立時間', '作廢'];

/* ---------- 試算表：沒有就自己建 ---------- */

function ss_() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty('SS_ID');
  if (id) {
    try { return SpreadsheetApp.openById(id); } catch (e) { /* 被刪掉就重建 */ }
  }
  var ss = SpreadsheetApp.create(SS_NAME);
  props.setProperty('SS_ID', ss.getId());
  initSheet_(ss, 'items', ITEM_COLS);
  initSheet_(ss, 'loss', LOSS_COLS);
  initMeta_(ss);
  var first = ss.getSheetByName('工作表1') || ss.getSheetByName('Sheet1');
  if (first) ss.deleteSheet(first);
  return ss;
}

function initSheet_(ss, name, cols) {
  var sh = ss.getSheetByName(name) || ss.insertSheet(name);
  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, cols.length).setValues([cols]);
    sh.getRange(1, 1, 1, cols.length).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  return sh;
}

function initMeta_(ss) {
  var sh = ss.getSheetByName('meta') || ss.insertSheet('meta');
  if (!sh.getRange('A2').getValue()) {
    sh.getRange('A1').setValue('設定').setFontWeight('bold');
    sh.getRange('A2').setValue('config');
    sh.getRange('B2').setValue(JSON.stringify({ rev: 1 }));
  }
  return sh;
}

function sheet_(name, cols) {
  return initSheet_(ss_(), name, cols);
}

/* ---------- 以「表頭名稱」定位欄位，不寫死欄號 ---------- */

function readRows_(sh) {
  var last = sh.getLastRow();
  if (last < 2) return [];
  var width = sh.getLastColumn();
  var values = sh.getRange(1, 1, last, width).getValues();
  var head = values[0];
  var out = [];
  for (var r = 1; r < values.length; r++) {
    var o = {};
    for (var c = 0; c < head.length; c++) if (head[c] !== '') o[head[c]] = values[r][c];
    out.push(o);
  }
  return out;
}

function headerIndex_(sh) {
  var head = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  var idx = {};
  for (var i = 0; i < head.length; i++) if (head[i] !== '') idx[head[i]] = i;
  return idx;
}

function rowFrom_(obj, idx, width) {
  var row = new Array(width).fill('');
  for (var k in obj) if (idx.hasOwnProperty(k)) row[idx[k]] = obj[k];
  return row;
}

/* ---------- meta：務必保留不認得的欄位 ---------- */

function readMeta_() {
  var sh = initMeta_(ss_());
  var raw = sh.getRange('B2').getValue();
  if (!raw) return { rev: 1 };
  try { return JSON.parse(raw); } catch (e) { return { rev: 1 }; }
}

function writeMeta_(patch) {
  var sh = initMeta_(ss_());
  var cur = readMeta_();
  for (var k in patch) cur[k] = patch[k];   // 只覆蓋有給的鍵，其餘原封不動
  cur.rev = (Number(cur.rev) || 0) + 1;
  sh.getRange('B2').setValue(JSON.stringify(cur));
  return cur;
}

/* ---------- 四個 action ---------- */

function actBootstrap_() {
  var sh = sheet_('items', ITEM_COLS);
  return {
    items: normalizeItems_(readRows_(sh)),
    meta: readMeta_(),
    serverTime: new Date().toISOString(),
    ssUrl: ss_().getUrl()
  };
}

function normalizeItems_(rows) {
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    if (!r['品名']) continue;
    out.push({
      品名: String(r['品名']),
      品類: String(r['品類'] || ''),
      單位: String(r['單位'] || ''),
      單位成本: Number(r['單位成本']) || 0,
      停用: r['停用'] === true || String(r['停用']).toUpperCase() === 'TRUE',
      更新時間: r['更新時間'] ? String(r['更新時間']) : ''
    });
  }
  return out;
}

function actSaveItem_(item) {
  if (!item || !item['品名']) throw new Error('缺少品名');
  var sh = sheet_('items', ITEM_COLS);
  var idx = headerIndex_(sh);
  var width = sh.getLastColumn();
  var rows = readRows_(sh);
  var target = -1;
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i]['品名']) === String(item['品名'])) { target = i + 2; break; }
  }
  var rec = {
    品名: item['品名'], 品類: item['品類'] || '', 單位: item['單位'] || '',
    單位成本: Number(item['單位成本']) || 0,
    停用: item['停用'] === true, 更新時間: new Date().toISOString()
  };
  if (item.舊品名 && item.舊品名 !== item['品名']) {          // 改名
    for (var j = 0; j < rows.length; j++) {
      if (String(rows[j]['品名']) === String(item.舊品名)) { target = j + 2; break; }
    }
  }
  if (target > 0) sh.getRange(target, 1, 1, width).setValues([rowFrom_(rec, idx, width)]);
  else sh.appendRow(rowFrom_(rec, idx, width));
  return { items: normalizeItems_(readRows_(sh)) };
}

function actAddLoss_(records) {
  if (!records || !records.length) return { accepted: [], duplicated: [] };
  var sh = sheet_('loss', LOSS_COLS);
  var idx = headerIndex_(sh);
  var width = sh.getLastColumn();

  var seen = {};
  var last = sh.getLastRow();
  if (last >= 2) {
    var ids = sh.getRange(2, idx['id'] + 1, last - 1, 1).getValues();
    for (var i = 0; i < ids.length; i++) if (ids[i][0]) seen[String(ids[i][0])] = true;
  }

  var accepted = [], duplicated = [], batch = [];
  for (var r = 0; r < records.length; r++) {
    var rec = records[r];
    if (!rec || !rec.id) continue;
    if (seen[String(rec.id)]) { duplicated.push(rec.id); continue; }
    seen[String(rec.id)] = true;
    rec['建立時間'] = new Date().toISOString();
    if (rec['作廢'] === undefined) rec['作廢'] = false;
    batch.push(rowFrom_(rec, idx, width));
    accepted.push(rec.id);
  }
  if (batch.length) sh.getRange(sh.getLastRow() + 1, 1, batch.length, width).setValues(batch);
  return { accepted: accepted, duplicated: duplicated };
}

function actVoidLoss_(id) {
  var sh = sheet_('loss', LOSS_COLS);
  var idx = headerIndex_(sh);
  var last = sh.getLastRow();
  if (last < 2) return { ok: false };
  var ids = sh.getRange(2, idx['id'] + 1, last - 1, 1).getValues();
  for (var i = 0; i < ids.length; i++) {
    if (String(ids[i][0]) === String(id)) {
      sh.getRange(i + 2, idx['作廢'] + 1).setValue(true);   // 不刪列、不改數字
      return { ok: true, id: id };
    }
  }
  return { ok: false };
}

function actListLoss_(from, to) {
  var rows = readRows_(sheet_('loss', LOSS_COLS));
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    if (!r.id) continue;
    var d = fmtDate_(r['日期']);
    if (from && d < from) continue;
    if (to && d > to) continue;
    r['日期'] = d;
    r['耗損量'] = Number(r['耗損量']) || 0;
    r['單位成本'] = Number(r['單位成本']) || 0;
    r['金額'] = Number(r['金額']) || 0;
    r['作廢'] = r['作廢'] === true || String(r['作廢']).toUpperCase() === 'TRUE';
    out.push(r);
  }
  return { records: out };
}

// 試算表可能把 'YYYY-MM-DD' 存成 Date，取回時要轉回字串
function fmtDate_(v) {
  if (v instanceof Date) return Utilities.formatDate(v, 'Asia/Taipei', 'yyyy-MM-dd');
  return String(v || '').slice(0, 10);
}

/* ---------- 入口 ---------- */

function handle_(req) {
  switch (req.action) {
    case 'bootstrap': return actBootstrap_();
    case 'saveItem': return actSaveItem_(req.item);
    case 'addLoss': return actAddLoss_(req.records);
    case 'voidLoss': return actVoidLoss_(req.id);
    case 'listLoss': return actListLoss_(req.from, req.to);
    case 'ping': return { pong: true, serverTime: new Date().toISOString() };
    default: throw new Error('不認得的 action：' + req.action);
  }
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    var req = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    return json_({ ok: true, data: handle_(req) });
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err) });
  } finally {
    try { lock.releaseLock(); } catch (e2) { }
  }
}

function doGet(e) {
  try {
    var action = (e && e.parameter && e.parameter.action) || 'ping';
    return json_({ ok: true, data: handle_({ action: action, from: e.parameter.from, to: e.parameter.to }) });
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err) });
  }
}

/** 在編輯器手動跑一次就會建好試算表並回傳網址（部署前的煙霧測試） */
function setup() {
  var url = ss_().getUrl();
  Logger.log(url);
  return url;
}
