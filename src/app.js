// 墨竹亭 光復店 耗損登記表
// 設計約束：金額只在 calc.makeRecord() 算一次；歷史金額永不重算；品項一律用「名稱」當 key。

var STORE_NAME = '墨竹亭光復';

var CATEGORIES = ['肉類', '海鮮', '蔬菜', '豆製品・加工品', '乾貨・南北貨', '調味料', '飲品・酒水', '包材・耗材', '其他'];
var REASONS = ['報廢', '過期', '備料失誤', '客訴重做', '試菜', '盤點差異', '其他'];

/* ---------- calc：全部純函式，不碰 DOM ---------- */
var calc = (function () {

  function pad(n, w) { var s = String(n); while (s.length < w) s = '0' + s; return s; }

  function ymd(d) {
    return d.getFullYear() + '-' + pad(d.getMonth() + 1, 2) + '-' + pad(d.getDate(), 2);
  }

  // 格式：L-<YYYYMMDDHHmmss>-<8 碼小寫英數>　例：L-20260801143005-k3f9d2xa
  function newId(now) {
    var d = now || new Date();
    var t = '' + d.getFullYear() + pad(d.getMonth() + 1, 2) + pad(d.getDate(), 2) +
      pad(d.getHours(), 2) + pad(d.getMinutes(), 2) + pad(d.getSeconds(), 2);
    var chars = 'abcdefghijklmnopqrstuvwxyz0123456789', r = '';
    for (var i = 0; i < 8; i++) r += chars.charAt(Math.floor(Math.random() * chars.length));
    return 'L-' + t + '-' + r;
  }

  // 全專案唯一一處把耗損量乘上單位成本的地方
  function makeRecord(input, item, now) {
    var d = now || new Date();
    var qty = Number(input.耗損量);
    var cost = Number(item.單位成本);
    var amount = Math.round(qty * cost * 100) / 100;
    return {
      id: input.id || newId(d),
      日期: input.日期,
      店別: STORE_NAME,
      品類: input.品類 || item.品類,
      品名: item.品名,
      耗損量: qty,
      單位: item.單位,
      單位成本: cost,
      金額: amount,
      原因: input.原因,
      原因說明: input.原因說明 || '',
      備註: input.備註 || '',
      建立時間: d.toISOString(),
      作廢: false
    };
  }

  function inRange(rec, from, to) {
    if (from && rec.日期 < from) return false;
    if (to && rec.日期 > to) return false;
    return true;
  }

  function live(records, from, to) {
    var out = [];
    for (var i = 0; i < records.length; i++) {
      var r = records[i];
      if (r.作廢 === true) continue;
      if (!inRange(r, from, to)) continue;
      out.push(r);
    }
    return out;
  }

  function rank(records, field) {
    var map = {}, total = 0;
    for (var i = 0; i < records.length; i++) {
      var r = records[i], k = r[field] || '（未填）';
      if (!map[k]) map[k] = { 名稱: k, 金額: 0, 筆數: 0 };
      map[k].金額 = Math.round((map[k].金額 + r.金額) * 100) / 100;
      map[k].筆數 += 1;
      total = Math.round((total + r.金額) * 100) / 100;
    }
    var list = [];
    for (var k2 in map) if (map.hasOwnProperty(k2)) list.push(map[k2]);
    list.sort(function (a, b) { return b.金額 - a.金額; });
    for (var j = 0; j < list.length; j++) {
      list[j].佔比 = total ? Math.round(list[j].金額 / total * 1000) / 10 : 0;
    }
    return list;
  }

  function daily(records, from, to) {
    var map = {};
    for (var i = 0; i < records.length; i++) {
      map[records[i].日期] = Math.round(((map[records[i].日期] || 0) + records[i].金額) * 100) / 100;
    }
    var out = [], cur = new Date(from + 'T00:00:00'), end = new Date(to + 'T00:00:00');
    while (cur <= end) {
      var key = ymd(cur);
      out.push({ 日期: key, 金額: map[key] || 0 });
      cur.setDate(cur.getDate() + 1);
    }
    return out;
  }

  // 統計一律直接加總每筆存下的「金額」，不回頭查成本表重算
  function summarize(records, from, to) {
    var rows = live(records, from, to), total = 0;
    for (var i = 0; i < rows.length; i++) total = Math.round((total + rows[i].金額) * 100) / 100;
    return {
      總金額: total,
      筆數: rows.length,
      按品類: rank(rows, '品類'),
      按品名: rank(rows, '品名'),
      按原因: rank(rows, '原因'),
      每日: (from && to) ? daily(rows, from, to) : []
    };
  }

  function dateRange(kind, todayStr) {
    var t = new Date(todayStr + 'T00:00:00');
    if (kind === 'today') return { from: todayStr, to: todayStr };
    if (kind === 'week') {
      var wd = (t.getDay() + 6) % 7; // 週一為第一天
      var s = new Date(t); s.setDate(t.getDate() - wd);
      return { from: ymd(s), to: todayStr };
    }
    if (kind === 'month') {
      return { from: ymd(new Date(t.getFullYear(), t.getMonth(), 1)), to: todayStr };
    }
    return { from: todayStr, to: todayStr };
  }

  function shift(dateStr, n) {
    var x = new Date(dateStr + 'T00:00:00');
    x.setDate(x.getDate() + n);
    return ymd(x);
  }

  function days(from, to) {
    return Math.round((new Date(to + 'T00:00:00') - new Date(from + 'T00:00:00')) / 86400000) + 1;
  }

  // 上一個同樣長度的期間（本期 vs 上期用）
  function prevRange(from, to) {
    var len = days(from, to);
    var pTo = shift(from, -1);
    return { from: shift(pTo, -(len - 1)), to: pTo };
  }

  var CSV_COLS = ['id', '日期', '店別', '品類', '品名', '耗損量', '單位', '單位成本', '金額', '原因', '原因說明', '備註', '建立時間'];

  function csv(records) {
    function esc(v) {
      v = (v === undefined || v === null) ? '' : String(v);
      return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    }
    var lines = [CSV_COLS.join(',')];
    for (var i = 0; i < records.length; i++) {
      var row = [];
      for (var j = 0; j < CSV_COLS.length; j++) row.push(esc(records[i][CSV_COLS[j]]));
      lines.push(row.join(','));
    }
    return '﻿' + lines.join('\r\n');   // BOM：Excel 開才不亂碼
  }

  function money(n) {
    var v = Math.round(Number(n) * 100) / 100;
    return '$' + v.toLocaleString('zh-TW', { maximumFractionDigits: 2 });
  }

  return {
    ymd: ymd, newId: newId, makeRecord: makeRecord, live: live,
    rank: rank, daily: daily, summarize: summarize, dateRange: dateRange, money: money,
    shift: shift, days: days, prevRange: prevRange, csv: csv, CSV_COLS: CSV_COLS
  };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { calc: calc, CATEGORIES: CATEGORIES, REASONS: REASONS, STORE_NAME: STORE_NAME };
}

/* ---------- 雲端設定 ---------- */
// Apps Script Web App（部署 v1）。改了要重 build。
var API_URL = 'https://script.google.com/macros/s/AKfycbzpCW2ZwSjX14D0Ry5rMnNmoaBr52VHDKWKiQlUjSW0zy1jdJGlaeRicgsvWn-LQqdNKA/exec';
var SYNC_DAYS = 120;   // 開頁時抓回最近幾天的紀錄

/* ---------- store：localStorage（雲端的快取＋待送佇列） ---------- */
var store = {
  K_ITEMS: 'mztloss.items',
  K_LOSS: 'mztloss.loss',
  K_QUEUE: 'mztloss.queue',
  read: function (k) {
    try { return JSON.parse(localStorage.getItem(k) || '[]'); } catch (e) { return []; }
  },
  write: function (k, v) {
    try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; }
  },
  items: function () { return store.read(store.K_ITEMS); },
  saveItems: function (v) { return store.write(store.K_ITEMS, v); },
  loss: function () { return store.read(store.K_LOSS); },
  saveLoss: function (v) { return store.write(store.K_LOSS, v); },
  queue: function () { return store.read(store.K_QUEUE); },
  saveQueue: function (v) { return store.write(store.K_QUEUE, v); }
};

/* ---------- api：只負責送出與取回，不做任何計算 ---------- */
var api = {
  post: function (payload) {
    return new Promise(function (resolve, reject) {
      var done = false;
      var timer = setTimeout(function () {
        if (!done) { done = true; reject(new Error('連線逾時')); }
      }, 20000);
      fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain;charset=utf-8' },  // 用 text/plain 避開 CORS 預檢
        body: JSON.stringify(payload)
      }).then(function (r) { return r.json(); }).then(function (j) {
        if (done) return;
        done = true; clearTimeout(timer);
        if (j && j.ok) resolve(j.data); else reject(new Error((j && j.error) || '伺服器錯誤'));
      }).catch(function (err) {
        if (done) return;
        done = true; clearTimeout(timer);
        reject(err);
      });
    });
  }
};

/* ---------- UI ---------- */
if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', function () {

  var $ = function (id) { return document.getElementById(id); };
  var items = store.items();
  var records = store.loss();
  var pending = store.queue();   // 還沒送上雲端的動作
  var picked = null;      // 目前選中的成本表品項
  var newMode = false;    // 打了成本表沒有的品名
  var editingName = null; // 成本設定頁正在編輯哪一筆

  function toast(msg, bad) {
    var t = $('toast');
    t.textContent = msg;
    t.className = 'toast' + (bad ? ' bad' : '');
    t.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.hidden = true; }, 2200);
  }

  /* --- 同步：待送佇列 --- */
  var flushing = false;
  var okTimer = null;

  function syncUI(justSynced) {
    var bar = $('sync');
    if (pending.length) {
      bar.hidden = false;
      bar.className = 'sync';
      $('sync-text').textContent = '有 ' + pending.length + ' 筆還沒上傳' + (flushing ? '，上傳中…' : '');
      return;
    }
    if (justSynced) {
      bar.hidden = false;
      bar.className = 'sync ok';
      $('sync-text').textContent = '已全部上傳到雲端';
      clearTimeout(okTimer);
      okTimer = setTimeout(function () { bar.hidden = true; }, 2500);
      return;
    }
    bar.hidden = true;
  }

  function enqueue(job) {
    pending.push(job);
    store.saveQueue(pending);
    syncUI();
    flush(true);
  }

  function flush(silent) {
    if (flushing || !pending.length) { syncUI(); return Promise.resolve(); }
    flushing = true;
    syncUI();
    var job = pending[0], p;
    if (job.kind === 'loss') p = api.post({ action: 'addLoss', records: [job.rec] });
    else if (job.kind === 'void') p = api.post({ action: 'voidLoss', id: job.id });
    else p = api.post({ action: 'saveItem', item: job.item });

    return p.then(function () {
      pending.shift();                    // 只有真的成功才移除
      store.saveQueue(pending);
      flushing = false;
      if (pending.length) return flush(silent);
      syncUI(true);
    }).catch(function (err) {
      flushing = false;
      syncUI();
      if (!silent) toast('上傳失敗：' + err.message, true);
    });
  }

  $('sync-btn').addEventListener('click', function () { flush(false); });
  window.addEventListener('online', function () { flush(true); });

  /* --- 開頁：先用快取畫面，再跟雲端對齊 --- */
  function boot() {
    api.post({ action: 'bootstrap' }).then(function (d) {
      items = d.items || [];
      store.saveItems(items);
      renderCost();
      var to = calc.ymd(new Date());
      return api.post({ action: 'listLoss', from: calc.shift(to, -SYNC_DAYS), to: to });
    }).then(function (d) {
      var seen = {};
      (d.records || []).forEach(function (r) { seen[r.id] = true; });
      var localOnly = records.filter(function (r) { return !seen[r.id]; });   // 還沒上傳的別被蓋掉
      records = (d.records || []).concat(localOnly);
      store.saveLoss(records);
      renderToday();
      if (document.querySelector('.page.is-on').id === 'page-stat') renderStat();
    }).catch(function () {
      // 離線或後端還沒授權：安靜地用本機快取，不打擾現場
    });
    flush(true);
  }

  function fillSelect(el, list, placeholder) {
    el.innerHTML = '';
    if (placeholder) {
      var o = document.createElement('option');
      o.value = ''; o.textContent = placeholder; o.disabled = true; o.selected = true;
      el.appendChild(o);
    }
    list.forEach(function (v) {
      var op = document.createElement('option');
      op.value = v; op.textContent = v;
      el.appendChild(op);
    });
  }

  function findItem(name) {
    for (var i = 0; i < items.length; i++) if (items[i].品名 === name) return items[i];
    return null;
  }

  /* --- 分頁切換 --- */
  Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (btn) {
    btn.addEventListener('click', function () {
      Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) { b.classList.remove('is-on'); });
      Array.prototype.forEach.call(document.querySelectorAll('.page'), function (p) { p.classList.remove('is-on'); });
      btn.classList.add('is-on');
      $('page-' + btn.dataset.tab).classList.add('is-on');
      if (btn.dataset.tab === 'stat') renderStat();
      window.scrollTo(0, 0);
    });
  });

  /* --- 登記頁 --- */
  fillSelect($('f-cat'), CATEGORIES, '選品類');
  fillSelect($('f-reason'), REASONS, '選原因');
  fillSelect($('c-cat'), CATEGORIES, '選品類');
  $('f-date').value = calc.ymd(new Date());

  function setNewMode(on) {
    newMode = on;
    $('f-unit').readOnly = !on;
    $('f-cost').readOnly = !on;
    $('f-unit').placeholder = on ? '包' : '—';
    $('f-cost').placeholder = on ? '單價' : '—';
    $('f-newhint').hidden = !on;
  }

  function applyItem(it) {
    picked = it;
    setNewMode(false);
    $('f-cat').value = it.品類;
    $('f-unit').value = it.單位;
    $('f-cost').value = it.單位成本;
    calcAmount();
  }

  function clearPicked() {
    picked = null;
    $('f-unit').value = '';
    $('f-cost').value = '';
    calcAmount();
  }

  function calcAmount() {
    var qty = Number($('f-qty').value);
    var cost = Number($('f-cost').value);
    var amt = (qty > 0 && cost > 0) ? Math.round(qty * cost * 100) / 100 : 0;
    $('f-amount').textContent = calc.money(amt);
  }

  function closeAc() { $('ac-list').hidden = true; $('ac-list').innerHTML = ''; }

  $('f-name').addEventListener('input', function () {
    var q = this.value.trim();
    var exact = findItem(q);
    if (exact && !exact.停用) { applyItem(exact); } else { clearPicked(); }
    if (!q) { closeAc(); setNewMode(false); return; }

    var hits = items.filter(function (it) {
      return !it.停用 && it.品名.indexOf(q) >= 0;      // 停用品項不進提示（兩條路之一）
    }).slice(0, 8);

    setNewMode(!exact && hits.length === 0);

    if (!hits.length) { closeAc(); return; }
    var ul = $('ac-list');
    ul.innerHTML = '';
    hits.forEach(function (it) {
      var li = document.createElement('li');
      li.innerHTML = '<span>' + it.品名 + '</span><small>' + it.品類 + ' · ' + calc.money(it.單位成本) + '/' + it.單位 + '</small>';
      li.addEventListener('mousedown', function (e) {
        e.preventDefault();
        $('f-name').value = it.品名;
        applyItem(it);
        closeAc();
        $('f-qty').focus();
      });
      ul.appendChild(li);
    });
    ul.hidden = false;
  });
  $('f-name').addEventListener('blur', function () { setTimeout(closeAc, 150); });
  $('f-qty').addEventListener('input', calcAmount);
  $('f-cost').addEventListener('input', calcAmount);

  $('f-reason').addEventListener('change', function () {
    var other = this.value === '其他';
    $('f-reasonnote-wrap').hidden = !other;
    $('f-reasonnote').required = other;
  });

  $('log-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var name = $('f-name').value.trim();
    var qty = Number($('f-qty').value);
    if (!name) return toast('請填品名', true);
    if (!(qty > 0)) return toast('耗損量要大於 0', true);
    if (!$('f-cat').value) return toast('請選品類', true);
    if (!$('f-reason').value) return toast('請選原因', true);

    var item = findItem(name);
    if (!item) {
      var unit = $('f-unit').value.trim();
      var cost = Number($('f-cost').value);
      if (!unit || !(cost > 0)) { setNewMode(true); return toast('新品項要補單位與單位成本', true); }
      item = { 品名: name, 品類: $('f-cat').value, 單位: unit, 單位成本: cost, 停用: false, 更新時間: new Date().toISOString() };
      items.push(item);
      store.saveItems(items);
      enqueue({ kind: 'item', item: item });
      renderCost();
      toast('已把「' + name + '」加進成本表');
    } else if (item.停用) {
      return toast('這個品項已停用，請先到成本設定啟用', true);
    }

    var rec = calc.makeRecord({
      日期: $('f-date').value,
      品類: $('f-cat').value,
      耗損量: qty,
      原因: $('f-reason').value,
      原因說明: $('f-reasonnote').value.trim(),
      備註: $('f-memo').value.trim()
    }, item);

    records.push(rec);
    store.saveLoss(records);
    enqueue({ kind: 'loss', rec: rec });     // id 在 makeRecord 產一次，之後永不重產
    renderToday();

    $('f-name').value = ''; $('f-qty').value = ''; $('f-memo').value = '';
    $('f-reasonnote').value = ''; $('f-reasonnote-wrap').hidden = true;
    $('f-cat').selectedIndex = 0; $('f-reason').selectedIndex = 0;
    clearPicked(); setNewMode(false);
    toast('已登記 ' + rec.品名 + '　' + calc.money(rec.金額));
    $('f-name').focus();
  });

  function renderToday() {
    var day = $('f-date').value || calc.ymd(new Date());
    var todayStr = calc.ymd(new Date());
    var rows = records.filter(function (r) { return r.日期 === day; })
      .sort(function (a, b) { return a.建立時間 < b.建立時間 ? 1 : -1; });

    document.querySelector('.today-head h2').textContent =
      (day === todayStr ? '今天這幾筆' : day.slice(5).replace('-', '/') + ' 這幾筆');

    var sum = calc.summarize(rows, day, day);
    $('today-sum').textContent = calc.money(sum.總金額);

    var ul = $('today-list');
    ul.innerHTML = '';
    rows.forEach(function (r) {
      var li = document.createElement('li');
      if (r.作廢) li.className = 'is-void';
      var main = document.createElement('div');
      main.className = 'rec-main';
      main.innerHTML = '<div class="rec-name">' + r.品名 + '</div>' +
        '<div class="rec-sub">' + r.耗損量 + ' ' + r.單位 + ' · ' + r.原因 +
        (r.原因說明 ? '（' + r.原因說明 + '）' : '') + '</div>';
      var amt = document.createElement('div');
      amt.className = 'rec-amt';
      amt.textContent = calc.money(r.金額);
      li.appendChild(main); li.appendChild(amt);
      if (!r.作廢) {
        // 兩段式點按取代 confirm()：LINE 等內嵌瀏覽器的原生對話框不可靠
        var b = document.createElement('button');
        b.className = 'void'; b.type = 'button'; b.textContent = '作廢';
        var armed = false, timer = null;
        b.addEventListener('click', function () {
          if (!armed) {
            armed = true;
            b.textContent = '確定作廢？';
            b.classList.add('armed');
            timer = setTimeout(function () {
              armed = false; b.textContent = '作廢'; b.classList.remove('armed');
            }, 6000);
            return;
          }
          clearTimeout(timer);
          r.作廢 = true;            // 不刪列、不改原始數字，統計一律排除
          store.saveLoss(records);
          enqueue({ kind: 'void', id: r.id });
          renderToday();
          toast('已作廢 ' + r.品名);
        });
        li.appendChild(b);
      }
      ul.appendChild(li);
    });
    $('today-empty').hidden = rows.length > 0;
    $('today-empty').textContent = (day === todayStr ? '今天還沒有登記。' : '這一天沒有紀錄。');
  }
  $('f-date').addEventListener('change', renderToday);

  /* --- 成本設定頁 --- */
  function resetCostForm() {
    editingName = null;
    $('cost-title').textContent = '新增品項';
    $('c-save').textContent = '儲存品項';
    $('c-cancel').hidden = true;
    $('cost-form').reset();
    $('c-cat').selectedIndex = 0;
  }

  $('c-cancel').addEventListener('click', resetCostForm);

  $('cost-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var name = $('c-name').value.trim();
    var cost = Number($('c-cost').value);
    var unit = $('c-unit').value.trim();
    if (!name || !unit || !(cost > 0) || !$('c-cat').value) return toast('每一欄都要填', true);

    var dup = findItem(name);
    if (dup && dup.品名 !== editingName) return toast('「' + name + '」已經在成本表裡了', true);

    if (editingName) {
      var old = findItem(editingName);
      var prevName = old.品名;
      old.品名 = name; old.品類 = $('c-cat').value; old.單位 = unit;
      old.單位成本 = cost; old.更新時間 = new Date().toISOString();
      enqueue({ kind: 'item', item: { 品名: name, 品類: old.品類, 單位: unit, 單位成本: cost, 停用: !!old.停用, 舊品名: prevName } });
      toast('已更新（舊紀錄金額不變）');
    } else {
      var fresh = { 品名: name, 品類: $('c-cat').value, 單位: unit, 單位成本: cost, 停用: false, 更新時間: new Date().toISOString() };
      items.push(fresh);
      enqueue({ kind: 'item', item: fresh });
      toast('已新增 ' + name);
    }
    store.saveItems(items);
    resetCostForm();
    renderCost();
  });

  $('c-search').addEventListener('input', renderCost);

  function renderCost() {
    var q = $('c-search').value.trim();
    var rows = items.filter(function (it) {
      return !q || it.品名.indexOf(q) >= 0 || it.品類.indexOf(q) >= 0;
    }).sort(function (a, b) { return a.品類 === b.品類 ? (a.品名 > b.品名 ? 1 : -1) : (a.品類 > b.品類 ? 1 : -1); });

    var ul = $('cost-list');
    ul.innerHTML = '';
    rows.forEach(function (it) {
      var li = document.createElement('li');
      if (it.停用) li.className = 'is-off';
      var main = document.createElement('div');
      main.className = 'rec-main';
      main.innerHTML = '<div class="rec-name">' + it.品名 + (it.停用 ? ' <span class="tag tag-off">已停用</span>' : '') + '</div>' +
        '<div class="rec-sub"><span class="tag">' + it.品類 + '</span>' + calc.money(it.單位成本) + ' / ' + it.單位 + '</div>';
      var edit = document.createElement('button');
      edit.className = 'item-act'; edit.type = 'button'; edit.textContent = '修改';
      edit.addEventListener('click', function () {
        editingName = it.品名;
        $('cost-title').textContent = '修改品項';
        $('c-save').textContent = '儲存修改';
        $('c-cancel').hidden = false;
        $('c-name').value = it.品名; $('c-cat').value = it.品類;
        $('c-unit').value = it.單位; $('c-cost').value = it.單位成本;
        window.scrollTo(0, 0);
      });
      var off = document.createElement('button');
      off.className = 'item-act off'; off.type = 'button'; off.textContent = it.停用 ? '啟用' : '停用';
      off.addEventListener('click', function () {
        it.停用 = !it.停用;
        it.更新時間 = new Date().toISOString();
        store.saveItems(items);
        enqueue({ kind: 'item', item: { 品名: it.品名, 品類: it.品類, 單位: it.單位, 單位成本: it.單位成本, 停用: it.停用 } });
        renderCost();
        toast(it.停用 ? '已停用 ' + it.品名 : '已啟用 ' + it.品名);
      });
      li.appendChild(main); li.appendChild(edit); li.appendChild(off);
      ul.appendChild(li);
    });
    $('cost-empty').hidden = rows.length > 0 || !!q;
  }

  /* --- 統計頁 --- */
  var statKind = 'week';

  Array.prototype.forEach.call(document.querySelectorAll('#s-seg button'), function (b) {
    b.addEventListener('click', function () {
      Array.prototype.forEach.call(document.querySelectorAll('#s-seg button'), function (x) { x.classList.remove('on'); });
      b.classList.add('on');
      statKind = b.dataset.k;
      $('s-custom').hidden = statKind !== 'custom';
      if (statKind === 'custom' && !$('s-from').value) {
        var m = calc.dateRange('month', calc.ymd(new Date()));
        $('s-from').value = m.from; $('s-to').value = m.to;
      }
      renderStat();
    });
  });
  $('s-from').addEventListener('change', renderStat);
  $('s-to').addEventListener('change', renderStat);

  function statRange() {
    if (statKind === 'custom') {
      var f = $('s-from').value, t = $('s-to').value;
      if (!f || !t) return null;
      return f <= t ? { from: f, to: t } : { from: t, to: f };
    }
    return calc.dateRange(statKind, calc.ymd(new Date()));
  }

  var itemRankOpen = false;

  function fillRank(el, list, limit) {
    el.innerHTML = '';
    var top = list.length ? list[0].金額 : 0;
    var shown = (limit && list.length > limit) ? list.slice(0, limit) : list;
    shown.forEach(function (r) {
      var li = document.createElement('li');
      li.innerHTML =
        '<div class="r-top"><span class="r-name">' + r.名稱 + '</span><span class="r-amt">' + calc.money(r.金額) + '</span></div>' +
        '<div class="r-sub">' + r.佔比 + '%　' + r.筆數 + ' 筆</div>' +
        '<div class="r-bar"><i style="width:' + (top ? Math.max(2, r.金額 / top * 100) : 0) + '%"></i></div>';
      el.appendChild(li);
    });
    if (limit && list.length > limit) {
      var more = document.createElement('li');
      more.innerHTML = '<button type="button" class="more">顯示全部 ' + list.length + ' 項</button>';
      more.querySelector('button').addEventListener('click', function () {
        itemRankOpen = true;
        renderStat();
      });
      el.appendChild(more);
    }
  }

  function renderStat() {
    var rg = statRange();
    if (!rg) return;
    var sum = calc.summarize(records, rg.from, rg.to);
    var pv = calc.prevRange(rg.from, rg.to);
    var prev = calc.summarize(records, pv.from, pv.to);

    $('s-range').textContent = rg.from.slice(5).replace('-', '/') +
      (rg.from === rg.to ? '' : '–' + rg.to.slice(5).replace('-', '/'));
    $('s-total').textContent = calc.money(sum.總金額);
    $('s-count').textContent = sum.筆數 + ' 筆';

    var d = Math.round((sum.總金額 - prev.總金額) * 100) / 100;
    $('s-delta').textContent = prev.總金額 === 0
      ? (sum.總金額 ? '上期沒有紀錄' : '')
      : '上期 ' + calc.money(prev.總金額) + '（' + (d >= 0 ? '+' : '') + calc.money(d).replace('$', '') + '）';

    // 每日走勢（只有一天就不畫，否則會變成一整塊實心色塊）
    $('s-chartblock').hidden = sum.每日.length < 2;
    var chart = $('s-chart'), max = 0;
    sum.每日.forEach(function (x) { if (x.金額 > max) max = x.金額; });
    chart.innerHTML = '';
    sum.每日.forEach(function (x) {
      var bar = document.createElement('div');
      bar.style.height = max ? Math.max(2, x.金額 / max * 100) + '%' : '2px';
      if (x.金額 > 0) bar.className = 'has';
      bar.title = x.日期 + '　' + calc.money(x.金額);
      chart.appendChild(bar);
    });
    $('s-axis-a').textContent = rg.from.slice(5).replace('-', '/');
    $('s-axis-b').textContent = rg.to.slice(5).replace('-', '/');

    fillRank($('s-cat'), sum.按品類);
    fillRank($('s-item'), sum.按品名, itemRankOpen ? 0 : 10);   // 品名可能上百項，先給前 10
    fillRank($('s-reason'), sum.按原因);

    var none = sum.筆數 === 0;
    $('s-empty').hidden = !none;
    Array.prototype.forEach.call(document.querySelectorAll('#page-stat .block'), function (b) {
      b.hidden = none || (b.id === 's-chartblock' && sum.每日.length < 2);
    });
    document.querySelector('#page-stat .btn-pair').hidden = none;
  }

  $('s-csv').addEventListener('click', function () {
    var rg = statRange();
    if (!rg) return;
    var rows = calc.live(records, rg.from, rg.to);   // 作廢的不匯出
    if (!rows.length) return toast('這段期間沒有資料', true);
    var blob = new Blob([calc.csv(rows)], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '耗損_' + rg.from + '_' + rg.to + '.csv';
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    toast('已匯出 ' + rows.length + ' 筆');
  });

  $('s-print').addEventListener('click', function () { window.print(); });

  renderToday();
  renderCost();
  syncUI();
  boot();
});
