#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3-Part Checker — Rank + Place Naver + Place Web
======================================================================
Mỗi phần chạy độc lập: Start / Stop / Pause / Resume riêng + chia luồng riêng.
3 phần có thể chạy đồng thời (mỗi phần mở Chrome riêng).

  Phần 1 — Rank + Đếm     : Naver search   (N luồng tùy chọn)
  Phần 2 — Place Naver    : Naver Place    (N luồng tùy chọn, Chrome minimize,
                                            đóng tab/cửa sổ sau khi xong)
  Phần 3 — Place Web      : thegangsa.xyz  (cố định 1 luồng, X giây/keyword)

Cài đặt: pip install selenium webdriver-manager
"""

import re
import time
import random
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager


# ══════════════════════════════════════════════════════════
#  HẰNG SỐ
# ══════════════════════════════════════════════════════════

MAX_THREADS     = 10
DEFAULT_THREADS = 3
P3_DEFAULT_WAIT = 4    # Giây chờ tối thiểu giữa các keyword Phần 3

# Naver Place panel XPath
XPATH_PLACE_SECTION = '/html/body/div[3]/div[2]/div[1]/div[1]/div[3]/div[4]'
XPATH_PLACE_UL      = '/html/body/div[3]/div[2]/div[1]/div[1]/div[3]/div[4]/section/div/div[5]/ul'
XPATH_NEXT_BTN      = '/html/body/div[3]/div[2]/div[1]/div[1]/div[3]/div[4]/section/div/div[5]/div/a[2]'

# thegangsa.xyz XPath (giao diện mới)
XG = {
    'id_in'      : '/html/body/div/div[4]/input[1]',
    'pw_in'      : '/html/body/div/div[4]/input[2]',
    'login_btn'  : '/html/body/div/div[4]/button',
    'aside'      : '/html/body/div[5]/aside',
    'menu'       : '/html/body/div[5]/aside/div[5]',
    'kw_in'      : '/html/body/div[5]/main/div[4]/div/div[3]/div[1]/div[2]/input',
    'kw_btn'     : '/html/body/div[5]/main/div[4]/div/div[3]/div[1]/div[2]/button',
    'exact_300'  : '/html/body/div[5]/main/div[4]/div/div[3]/div[1]/div[3]/div[1]/div[2]/button[3]',
    'name_in'    : '/html/body/div[5]/main/div[4]/div/div[3]/div[3]/div[3]/input',
    'name_btn'   : '/html/body/div[5]/main/div[4]/div/div[3]/div[3]/div[3]/button',
    'rank_span'  : '/html/body/div[5]/main/div[4]/div/div[3]/div[3]/div[4]/span[2]',
}


# ══════════════════════════════════════════════════════════
#  SCRIPT JS — lấy danh sách title theo nhóm (từ x7/x10)
# ══════════════════════════════════════════════════════════

SCRIPT_GET_TITLES_GROUPED = r"""
function isValidTitle(text) {
    if (!text) return false;
    if (text.endsWith('...') || text.endsWith('\u2026')) return false;
    if (/^re\s*[:\uFF1A]?\s*/i.test(text)) return false;
    if (text.length < 6 || text.length > 150) return false;
    if (text.indexOf('\ud568\uaed8 \ub9ce\uc774 \ucc3e\ub294') !== -1) return false;
    if (text.indexOf('>') !== -1) return false;
    if (text.indexOf('-') !== -1) return false;
    if (text.indexOf('_') !== -1) return false;
    return true;
}
function getSubkey(ancestor) {
    /* Tìm subkey (h2 hoặc h3) trong block.
       Block có subkey: ancestor > div > div > div[1] > ... > h2
       Block không có : không tồn tại h2/h3 nào trong ancestor.
       Lấy h2/h3 đầu tiên có text — đó là tiêu đề nhóm (인기글, 최신글...) */
    var headers = ancestor.querySelectorAll('h2, h3');
    for (var hi = 0; hi < headers.length; hi++) {
        var txt = headers[hi].textContent.trim();
        if (txt) return txt;
    }
    return '';
}
var mainContainer = null;
var xpathsToTry = [
    '/html/body/div[3]/div[2]/div[1]/div[1]',
    '/html/body/div[3]/div[2]/div[1]/div[2]',
    '/html/body/div[3]/div[2]/div[2]/div[1]'
];
for (var xi = 0; xi < xpathsToTry.length; xi++) {
    try {
        var xr = document.evaluate(xpathsToTry[xi], document, null,
            XPathResult.FIRST_ORDERED_NODE_TYPE, null);
        var node = xr.singleNodeValue;
        if (node && node.querySelectorAll('span.sds-comps-text-type-headline1').length > 0) {
            mainContainer = node; break;
        }
    } catch(e) {}
}
if (!mainContainer) return [];
var selectors = [
    'span.sds-comps-text-type-headline1',
    'a[data-heatmap-target=".link"]',
    'a.total_tit', 'a.title_link', 'a.api_txt_lines.total_tit'
];
var titleElements = [];
for (var si = 0; si < selectors.length; si++) {
    var els = mainContainer.querySelectorAll(selectors[si]);
    if (els.length > 0) { titleElements = Array.from(els); break; }
}
if (titleElements.length === 0) return [];
var blockOrder = [];
var blockMap = new WeakMap();
var seenText = new Set();
titleElements.forEach(function(el) {
    if (el.closest('#adbox, .sp_adbox, .ad_area, [class*="ad_"]')) return;
    var text = el.textContent.trim();
    if (!isValidTitle(text)) return;
    if (seenText.has(text)) return;
    seenText.add(text);
    var cur = el;
    var ancestor = null;
    while (cur && cur !== mainContainer) {
        if (cur.parentElement === mainContainer) { ancestor = cur; break; }
        cur = cur.parentElement;
    }
    if (!ancestor) return;
    if (!blockMap.has(ancestor)) {
        blockMap.set(ancestor, blockOrder.length);
        blockOrder.push({ titles: [], subkey: getSubkey(ancestor) });
    }
    blockOrder[blockMap.get(ancestor)].titles.push(text);
});
return blockOrder.map(function(b) { return { titles: b.titles, subkey: b.subkey }; });
"""


# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════

def find_target_in_groups(grouped, target):
    """grouped: list of {titles:[...], subkey:str}
    Trả về (list2, subkeys_found)
      list2        : [[pos...] or [0], ...]  — như cũ
      subkeys_found: list subkey của các block có chứa target (không trùng, giữ thứ tự)
    """
    list2, seen_sk, subkeys_found = [], set(), []
    for block in grouped:
        titles  = block['titles'] if isinstance(block, dict) else block
        subkey  = block.get('subkey', '') if isinstance(block, dict) else ''
        positions = [i + 1 for i, t in enumerate(titles) if target in t]
        list2.append(positions if positions else [0])
        if positions and subkey and subkey not in seen_sk:
            seen_sk.add(subkey)
            subkeys_found.append(subkey)
    return list2, subkeys_found


def build_list3(list2_grouped):
    seen, list3 = set(), []
    for group in list2_grouped:
        for num in group:
            if num != 0 and num not in seen:
                seen.add(num)
                list3.append(num)
    return list3


def compress(nums):
    groups, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        if j - i >= 2:
            groups.append(f"{nums[i]}~{nums[j]}")
        else:
            groups.extend(str(nums[k]) for k in range(i, j + 1))
        i = j + 1
    return groups


def calc_count(rank_str):
    if not rank_str or any(x in str(rank_str) for x in ['순위밖', 'Đang', '✓']):
        return ''
    try:
        clean = str(rank_str).replace('위', '').replace(' ', '')
        total = 0
        for part in clean.split(','):
            if '~' in part:
                a, b = part.split('~')
                total += int(re.sub(r'\D', '', b)) - int(re.sub(r'\D', '', a)) + 1
            elif re.sub(r'\D', '', part):
                total += 1
        return total if total > 0 else ''
    except Exception:
        return ''


def chunk_items(items, n):
    """Chia items thành n chunk liền nhau; phần dư phân vào các chunk đầu."""
    total = len(items)
    base, rem = divmod(total, n)
    chunks, idx = [], 0
    for i in range(n):
        size = base + (1 if i < rem else 0)
        chunks.append(items[idx:idx + size])
        idx += size
    return chunks


# ══════════════════════════════════════════════════════════
#  SECTION CONTROLLER — quản lý state 1 phần
# ══════════════════════════════════════════════════════════

class SectionCtl:
    STATE_IDLE    = 'idle'
    STATE_RUNNING = 'running'
    STATE_PAUSED  = 'paused'

    def __init__(self, name, app):
        self.name  = name
        self.app   = app
        self.state = self.STATE_IDLE

        self.stop_event  = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()   # mặc định = không pause

        self.drivers     = []
        self.driver_lock = threading.Lock()

        self.thread_progress  = {}   # {tid: [done, total]}
        self.progress_lock    = threading.Lock()
        self.completion_shown = False

    # ── State ────────────────────────────────────────
    def set_state(self, st):
        self.state = st
        self.app.root.after(0, lambda: self.app._refresh_buttons(self.name))

    def reset_for_run(self):
        self.stop_event.clear()
        self.pause_event.set()
        self.completion_shown = False
        with self.progress_lock:
            self.thread_progress = {}

    # ── Driver ───────────────────────────────────────
    def add_driver(self, drv):
        with self.driver_lock:
            self.drivers.append(drv)

    def remove_driver(self, drv):
        with self.driver_lock:
            try:    self.drivers.remove(drv)
            except ValueError: pass

    def kill_drivers(self):
        with self.driver_lock:
            drvs = list(self.drivers)
            self.drivers.clear()
        for d in drvs:
            try: d.quit()
            except Exception: pass

    # ── Control ──────────────────────────────────────
    def pause(self):
        if self.state == self.STATE_RUNNING:
            self.pause_event.clear()
            self.set_state(self.STATE_PAUSED)

    def resume(self):
        if self.state == self.STATE_PAUSED:
            self.pause_event.set()
            self.set_state(self.STATE_RUNNING)

    def stop(self):
        self.stop_event.set()
        self.pause_event.set()  # giải pause để thread thoát
        threading.Thread(target=self.kill_drivers, daemon=True).start()
        self.set_state(self.STATE_IDLE)

    # ── Sleep ngắt được ──────────────────────────────
    def isleep(self, seconds):
        """Sleep nhưng kiểm tra stop/pause định kỳ. Trả False nếu bị stop."""
        end = time.time() + seconds
        while time.time() < end:
            if self.stop_event.is_set():
                return False
            self.pause_event.wait()
            time.sleep(0.1)
        return True


# ══════════════════════════════════════════════════════════
#  APP
# ══════════════════════════════════════════════════════════

class App:

    def __init__(self, root: tk.Tk):
        self.root = root
        self._cdpath = None
        self._cdpath_lock = threading.Lock()

        self.p1 = SectionCtl('p1', self)
        self.p2 = SectionCtl('p2', self)
        self.p3 = SectionCtl('p3', self)

        root.title('3-Part Checker — Rank + Place Naver + Place Web')
        root.configure(bg='#e0e0e0')
        root.geometry('1280x980')
        root.minsize(1100, 760)
        root.protocol('WM_DELETE_WINDOW', self._on_close)

        self._build_ui()

    # ═════════════════════════════════════════════════════
    # BUILD UI
    # ═════════════════════════════════════════════════════
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', background='#f2f2f2',
                         fieldbackground='#f2f2f2', rowheight=25)

        main = tk.Frame(self.root, bg='#e0e0e0', padx=12, pady=10)
        main.pack(fill='both', expand=True)

        # ── ROW 1: Keywords + Target/ID/PW ────────────
        row1 = tk.Frame(main, bg='#e0e0e0')
        row1.pack(fill='x', pady=(0, 8))

        kw_wrap = tk.Frame(row1, bg='#e0e0e0')
        kw_wrap.pack(side='left', fill='both', expand=True)
        tk.Label(kw_wrap, text='Danh sách Keywords:',
                 font=('Arial', 10, 'bold'), bg='#e0e0e0').pack(anchor='w')
        self.txt_kw = tk.Text(kw_wrap, width=50, height=7,
                               bg='white', font=('Consolas', 10))
        self.txt_kw.pack(fill='both', expand=True, pady=4)

        info = tk.Frame(row1, bg='#e0e0e0', padx=18)
        info.pack(side='left', fill='y')

        tk.Label(info, text='Target / Name:',
                 font=('Arial', 10, 'bold'), bg='#e0e0e0').pack(anchor='w')
        self.v_target = tk.StringVar(value='스시도쿠')
        tk.Entry(info, textvariable=self.v_target,
                 font=('Arial', 11), fg='#d32f2f', width=28).pack(fill='x', pady=4)

        tk.Label(info, text='ID (thegangsa.xyz):',
                 font=('Arial', 10, 'bold'), bg='#e0e0e0').pack(anchor='w')
        self.v_id = tk.StringVar()
        tk.Entry(info, textvariable=self.v_id,
                 font=('Arial', 10), width=28).pack(fill='x', pady=4)

        tk.Label(info, text='Password:',
                 font=('Arial', 10, 'bold'), bg='#e0e0e0').pack(anchor='w')
        self.v_pw = tk.StringVar()
        tk.Entry(info, textvariable=self.v_pw, show='*',
                 font=('Arial', 10), width=28).pack(fill='x', pady=4)

        # ── ROW 2: 3 PANEL ĐIỀU KHIỂN ─────────────────
        row2 = tk.Frame(main, bg='#e0e0e0')
        row2.pack(fill='x', pady=(0, 8))

        self._build_panel(row2, 'p1', 'PHẦN 1 — Rank + Đếm',
                          'Naver search', '#1565c0', has_threads=True)
        self._build_panel(row2, 'p2', 'PHẦN 2 — Place Naver',
                          'Naver Place panel (Chrome ngầm)', '#6a1b9a',
                          has_threads=True)
        self._build_panel(row2, 'p3', 'PHẦN 3 — Place Web',
                          'thegangsa.xyz · 1 luồng', '#c62828',
                          has_threads=False, has_wait=True)

        # ── ROW 3: TREEVIEW ───────────────────────────
        tbl = tk.Frame(main, bg='#e0e0e0')
        tbl.pack(fill='both', expand=True, pady=(0, 4))

        self.tree = ttk.Treeview(
            tbl,
            columns=('key', 'rank', 'subkw', 'count', 'p_naver', 'p_web'),
            show='headings', height=15)

        self.tree.heading('key',     text='Keyword')
        self.tree.heading('rank',    text='Rank (P1)')
        self.tree.heading('subkw',   text='Sub Keyword')
        self.tree.heading('count',   text='Đếm')
        self.tree.heading('p_naver', text='Place Naver (P2)')
        self.tree.heading('p_web',   text='Place Web (P3)')

        self.tree.column('key',     width=230)
        self.tree.column('rank',    width=160, anchor='center')
        self.tree.column('subkw',   width=200, anchor='w')
        self.tree.column('count',   width=60,  anchor='center')
        self.tree.column('p_naver', width=130, anchor='center')
        self.tree.column('p_web',   width=130, anchor='center')

        sb = ttk.Scrollbar(tbl, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # ── ROW 4: COPY ───────────────────────────────
        copy_frame = tk.LabelFrame(
            main, text=' Sao chép nhanh (không kèm tên cột) ',
            bg='#e0e0e0', padx=10, pady=8)
        copy_frame.pack(fill='x', pady=(4, 2))

        copy_buttons = [
            ('Copy Keyword',      0, 'Keyword'),
            ('Copy Rank',         1, 'Rank'),
            ('Copy Sub Keyword',  2, 'Sub Keyword'),
            ('Copy Đếm',          3, 'Đếm'),
            ('Copy Place Naver',  4, 'Place Naver'),
            ('Copy Place Web',    5, 'Place Web'),
        ]
        for ci, (lbl, idx, name) in enumerate(copy_buttons):
            tk.Button(copy_frame, text=lbl, bg='#546e7a', fg='white',
                      font=('Arial', 9), width=15,
                      command=lambda i=idx, n=name: self._copy_col(i, n)
                      ).grid(row=0, column=ci, padx=4)

        tk.Button(copy_frame, text='📋 COPY TOÀN BẢNG',
                  bg='#1976d2', fg='white',
                  font=('Arial', 9, 'bold'), width=18,
                  command=self._copy_table).grid(row=0, column=len(copy_buttons), padx=8)

        # ── ROW 5: EDIT ───────────────────────────────
        edit = tk.LabelFrame(main, text=' Cập nhật thủ công ',
                              bg='#e0e0e0', padx=10, pady=8)
        edit.pack(fill='x', pady=(2, 0))

        tk.Label(edit, text='Rank:', bg='#e0e0e0').grid(row=0, column=0, padx=(4, 2))
        self.ent_rank = tk.Entry(edit, width=12)
        self.ent_rank.grid(row=0, column=1, padx=(0, 8))

        tk.Label(edit, text='Place Naver:', bg='#e0e0e0').grid(row=0, column=2, padx=(4, 2))
        self.ent_pnaver = tk.Entry(edit, width=8)
        self.ent_pnaver.grid(row=0, column=3, padx=(0, 8))

        tk.Label(edit, text='Place Web:', bg='#e0e0e0').grid(row=0, column=4, padx=(4, 2))
        self.ent_pweb = tk.Entry(edit, width=8)
        self.ent_pweb.grid(row=0, column=5, padx=(0, 8))

        self.ent_rank.bind('<Return>', lambda e: self._update_data())

        tk.Button(edit, text='CẬP NHẬT', bg='#455a64', fg='white',
                  command=self._update_data).grid(row=0, column=6, padx=4)
        tk.Button(edit, text='순위밖 (Rank)', bg='#78909c', fg='white',
                  command=self._set_outside).grid(row=0, column=7, padx=4)
        tk.Button(edit, text='Xóa bảng', bg='#9e9e9e', fg='white',
                  command=self._clear_table).grid(row=0, column=8, padx=4)

        # init button state cho 3 phần
        for name in ('p1', 'p2', 'p3'):
            self._refresh_buttons(name)

    def _build_panel(self, parent, name, title, subtitle, color,
                     has_threads, has_wait=False):
        frame = tk.LabelFrame(parent, bg='#e0e0e0', padx=8, pady=6,
                              labelanchor='n', font=('Arial', 9, 'bold'),
                              fg=color, text=f' {title} ')
        frame.pack(side='left', fill='both', expand=True, padx=4)

        tk.Label(frame, text=subtitle, font=('Arial', 8),
                 bg='#e0e0e0', fg='#555').pack(anchor='w')

        row_th = tk.Frame(frame, bg='#e0e0e0')
        row_th.pack(anchor='w', pady=(4, 4))
        if has_threads:
            tk.Label(row_th, text='Luồng:', font=('Arial', 9, 'bold'),
                     bg='#e0e0e0').pack(side='left')
            spin = tk.Spinbox(row_th, from_=1, to=MAX_THREADS, width=4,
                              font=('Arial', 10))
            spin.delete(0, 'end')
            spin.insert(0, str(DEFAULT_THREADS))
            spin.pack(side='left', padx=4)
            tk.Label(row_th, text=f'(1–{MAX_THREADS})',
                     font=('Arial', 8), bg='#e0e0e0', fg='#666').pack(side='left')
            setattr(self, f'spin_{name}', spin)
        elif has_wait:
            # Phần 3: input số giây chờ giữa các keyword
            tk.Label(row_th, text='Chờ/kw (giây):',
                     font=('Arial', 9, 'bold'), bg='#e0e0e0').pack(side='left')
            spin_w = tk.Spinbox(row_th, from_=4, to=120, width=4,
                                font=('Arial', 10))
            spin_w.delete(0, 'end')
            spin_w.insert(0, str(P3_DEFAULT_WAIT))
            spin_w.pack(side='left', padx=4)
            tk.Label(row_th, text='(min 4s)',
                     font=('Arial', 8), bg='#e0e0e0', fg='#666').pack(side='left')
            setattr(self, f'spin_{name}_wait', spin_w)
        else:
            tk.Label(row_th, text='Cố định 1 luồng',
                     font=('Arial', 9, 'italic'),
                     bg='#e0e0e0', fg='#666').pack(side='left')

        row_btn = tk.Frame(frame, bg='#e0e0e0')
        row_btn.pack(anchor='w', pady=4)

        btn_start  = tk.Button(row_btn, text='▶ START',  bg='#2e7d32',
                               fg='white', font=('Arial', 9, 'bold'), width=10,
                               command=lambda: self._on_start(name))
        btn_stop   = tk.Button(row_btn, text='⏹ STOP',   bg='#c62828',
                               fg='white', font=('Arial', 9, 'bold'), width=10,
                               command=lambda: self._on_stop(name))
        btn_pause  = tk.Button(row_btn, text='⏸ PAUSE',  bg='#f57c00',
                               fg='white', font=('Arial', 9, 'bold'), width=10,
                               command=lambda: self._on_pause(name))
        btn_resume = tk.Button(row_btn, text='⏯ RESUME', bg='#0288d1',
                               fg='white', font=('Arial', 9, 'bold'), width=10,
                               command=lambda: self._on_resume(name))
        btn_start .grid(row=0, column=0, padx=2, pady=2)
        btn_stop  .grid(row=0, column=1, padx=2, pady=2)
        btn_pause .grid(row=1, column=0, padx=2, pady=2)
        btn_resume.grid(row=1, column=1, padx=2, pady=2)

        setattr(self, f'btn_{name}_start',  btn_start)
        setattr(self, f'btn_{name}_stop',   btn_stop)
        setattr(self, f'btn_{name}_pause',  btn_pause)
        setattr(self, f'btn_{name}_resume', btn_resume)

        lbl_status = tk.Label(frame, text='Trạng thái: Chờ lệnh...',
                              font=('Consolas', 9), bg='#e0e0e0', fg='#333',
                              anchor='w', justify='left', wraplength=380)
        lbl_status.pack(anchor='w', fill='x', pady=(4, 0))
        setattr(self, f'lbl_{name}_status', lbl_status)

    # ═════════════════════════════════════════════════════
    # BUTTON STATE
    # ═════════════════════════════════════════════════════
    def _refresh_buttons(self, name):
        ctrl = getattr(self, name)
        st   = ctrl.state
        bs   = getattr(self, f'btn_{name}_start')
        bx   = getattr(self, f'btn_{name}_stop')
        bp   = getattr(self, f'btn_{name}_pause')
        br   = getattr(self, f'btn_{name}_resume')

        def s(b, on): b.config(state='normal' if on else 'disabled')

        if st == SectionCtl.STATE_IDLE:
            s(bs, True);  s(bx, False); s(bp, False); s(br, False)
        elif st == SectionCtl.STATE_RUNNING:
            s(bs, False); s(bx, True);  s(bp, True);  s(br, False)
        elif st == SectionCtl.STATE_PAUSED:
            s(bs, False); s(bx, True);  s(bp, False); s(br, True)

    def _set_status(self, name, msg):
        lbl = getattr(self, f'lbl_{name}_status')
        self.root.after(0, lambda t=f'Trạng thái: {msg}': lbl.config(text=t))

    # ═════════════════════════════════════════════════════
    # TREEVIEW HELPERS
    # ═════════════════════════════════════════════════════
    def _read_keywords(self):
        raw = self.txt_kw.get('1.0', 'end-1c')
        return [k.strip() for k in raw.split('\n') if k.strip()]

    def _ensure_rows(self, keywords):
        existing = {self.tree.item(i)['values'][0]: i
                    for i in self.tree.get_children()}
        items = []
        for kw in keywords:
            if kw in existing:
                items.append((kw, existing[kw]))
            else:
                iid = self.tree.insert('', 'end', values=(kw, '', '', '', '', ''))
                items.append((kw, iid))
        return items

    def _copy_col(self, idx, name):
        data = [str(self.tree.item(i)['values'][idx] or '')
                for i in self.tree.get_children()]
        self.root.clipboard_clear()
        self.root.clipboard_append('\n'.join(data))
        self.root.update()
        messagebox.showinfo('Đã copy', f'Đã copy cột {name}!')

    def _copy_table(self):
        headers = ['Keyword', 'Rank', 'Sub Keyword', 'Đếm', 'Place Naver', 'Place Web']
        rows = [self.tree.item(i)['values'] for i in self.tree.get_children()]
        txt = '\t'.join(headers) + '\n'
        for r in rows:
            txt += '\t'.join(str(v) for v in r) + '\n'
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.root.update()
        messagebox.showinfo('Đã copy!', f'Đã copy {len(rows)} dòng!')

    def _select_next(self):
        sel = self.tree.selection()
        if not sel: return
        nxt = self.tree.next(sel[-1])
        if nxt:
            self.tree.selection_set(nxt)
            self.tree.focus(nxt)
            self.tree.see(nxt)

    def _set_outside(self):
        for item in self.tree.selection():
            self.tree.set(item, 'rank',  '순위밖')
            self.tree.set(item, 'count', '')
        self._select_next()

    def _update_data(self):
        sel = self.tree.selection()
        if not sel: return
        rank_raw   = self.ent_rank.get().strip()
        pnaver_raw = self.ent_pnaver.get().strip()
        pweb_raw   = self.ent_pweb.get().strip()

        rank_final = rank_raw
        if rank_raw == '0':
            rank_final = '순위밖'
        elif ',' in rank_raw:
            parts = [f'{p.strip()}위' if p.strip().isdigit() else p.strip()
                     for p in rank_raw.split(',')]
            rank_final = ', '.join(parts)
        elif rank_raw.isdigit():
            rank_final = f'{rank_raw}위'

        count_val = calc_count(rank_final)

        for item in sel:
            if rank_raw:
                self.tree.set(item, 'rank',  rank_final)
                self.tree.set(item, 'count', count_val)
            if pnaver_raw:
                self.tree.set(item, 'p_naver', pnaver_raw)
            if pweb_raw:
                self.tree.set(item, 'p_web',   pweb_raw)

        for e in (self.ent_rank, self.ent_pnaver, self.ent_pweb):
            e.delete(0, 'end')
        self._select_next()

    def _clear_table(self):
        if not self.tree.get_children():
            return
        if not messagebox.askyesno('Xác nhận', 'Xóa toàn bộ bảng kết quả?'):
            return
        for i in self.tree.get_children():
            self.tree.delete(i)

    # ═════════════════════════════════════════════════════
    # ON_CLOSE
    # ═════════════════════════════════════════════════════
    def _on_close(self):
        for ctrl in (self.p1, self.p2, self.p3):
            ctrl.stop_event.set()
            ctrl.pause_event.set()
            threading.Thread(target=ctrl.kill_drivers, daemon=True).start()
        self.root.after(800, self.root.destroy)

    # ═════════════════════════════════════════════════════
    # DRIVER FACTORY
    # ═════════════════════════════════════════════════════
    def _ensure_cdpath(self):
        with self._cdpath_lock:
            if self._cdpath is None:
                self._cdpath = ChromeDriverManager().install()
            return self._cdpath

    def _make_driver(self, minimize=False):
        opts = Options()
        opts.add_experimental_option('detach', True)
        opts.add_argument('--disable-blink-features=AutomationControlled')
        opts.add_experimental_option('excludeSwitches', ['enable-automation'])
        opts.add_experimental_option('useAutomationExtension', False)
        if minimize:
            opts.add_argument('--window-position=10000,10000')
            opts.add_argument('--window-size=1280,800')
        driver = webdriver.Chrome(service=Service(self._cdpath), options=opts)
        if minimize:
            try: driver.minimize_window()
            except Exception: pass
        else:
            try: driver.maximize_window()
            except Exception: pass
        return driver

    # ═════════════════════════════════════════════════════
    # START / STOP / PAUSE / RESUME — router
    # ═════════════════════════════════════════════════════
    def _on_start(self, name):
        keywords = self._read_keywords()
        if not keywords:
            messagebox.showwarning('Cảnh báo', 'Chưa nhập keyword!'); return
        target = self.v_target.get().strip()
        if not target:
            messagebox.showwarning('Cảnh báo', 'Chưa nhập Target!'); return
        if name == 'p3':
            if not self.v_id.get().strip():
                messagebox.showwarning('Cảnh báo', 'Chưa nhập ID cho Phần 3!'); return
            if not self.v_pw.get().strip():
                messagebox.showwarning('Cảnh báo', 'Chưa nhập Password cho Phần 3!'); return

        items = self._ensure_rows(keywords)

        if name == 'p1':
            for _, iid in items:
                self.tree.set(iid, 'rank',  'Đang chờ...')
                self.tree.set(iid, 'subkw', '')
                self.tree.set(iid, 'count', '')
        elif name == 'p2':
            for _, iid in items:
                self.tree.set(iid, 'p_naver', 'Đang chờ...')
        elif name == 'p3':
            for _, iid in items:
                self.tree.set(iid, 'p_web', 'Đang chờ...')

        ctrl = getattr(self, name)
        ctrl.reset_for_run()
        ctrl.set_state(SectionCtl.STATE_RUNNING)
        self._set_status(name, '🔄 Đang chuẩn bị ChromeDriver...')

        if name == 'p1':
            n_threads = self._read_threads('p1')
            threading.Thread(target=self._bootstrap_p1,
                             args=(items, target, n_threads),
                             daemon=True).start()
        elif name == 'p2':
            n_threads = self._read_threads('p2')
            threading.Thread(target=self._bootstrap_p2,
                             args=(items, target, n_threads),
                             daemon=True).start()
        elif name == 'p3':
            wait_sec = self._read_p3_wait()
            threading.Thread(target=self._bootstrap_p3,
                             args=(items, target, wait_sec),
                             daemon=True).start()

    def _read_threads(self, name):
        try:
            n = int(getattr(self, f'spin_{name}').get())
            return max(1, min(n, MAX_THREADS))
        except Exception:
            return DEFAULT_THREADS

    def _read_p3_wait(self):
        try:
            v = int(self.spin_p3_wait.get())
            return max(4, v)   # tối thiểu 4s
        except Exception:
            return P3_DEFAULT_WAIT

    def _on_stop(self, name):
        getattr(self, name).stop()
        self._set_status(name, '⏹ Đã dừng')

    def _on_pause(self, name):
        getattr(self, name).pause()
        self._set_status(name, '⏸ Đã tạm dừng')

    def _on_resume(self, name):
        getattr(self, name).resume()
        self._set_status(name, '▶ Tiếp tục')

    # ═════════════════════════════════════════════════════
    # PHẦN 1 — Rank + Đếm  (Naver search)
    # ═════════════════════════════════════════════════════
    def _bootstrap_p1(self, items, target, n_threads):
        try:
            self._ensure_cdpath()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror('ChromeDriver lỗi', str(e)))
            self.p1.set_state(SectionCtl.STATE_IDLE); return

        ctrl = self.p1
        n = min(n_threads, len(items))
        chunks = chunk_items(items, n)

        with ctrl.progress_lock:
            ctrl.thread_progress = {tid: [0, len(c)] for tid, c in enumerate(chunks)}
        self._refresh_p_status('p1')

        for tid, chunk in enumerate(chunks):
            threading.Thread(target=self._worker_p1,
                             args=(tid, chunk, target, n),
                             daemon=True).start()
            time.sleep(0.7)

    def _worker_p1(self, tid, chunk, target, total_threads):
        ctrl = self.p1
        try:
            driver = self._make_driver(minimize=False)
            ctrl.add_driver(driver)
            if ctrl.stop_event.is_set():
                ctrl.remove_driver(driver)
                try: driver.quit()
                except Exception: pass
                return
            driver.get('about:blank')
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                'Lỗi Chrome P1', f'Thread {tid+1}: {e}'))
            for kw, iid in chunk:
                self.root.after(0, lambda i=iid: self.tree.set(i, 'rank', 'Lỗi driver'))
            with ctrl.progress_lock:
                ctrl.thread_progress[tid] = [len(chunk), len(chunk)]
            self._refresh_p_status('p1')
            self._check_done('p1', total_threads)
            return

        script_hl = f"""
        var target = "{target}";
        var firstFound = null;
        var sels = ['span.sds-comps-text-type-headline1','a[data-heatmap-target=".link"]',
                    'a.total_tit','a.title_link','a.api_txt_lines.total_tit'];
        sels.forEach(function(sel) {{
            document.querySelectorAll(sel).forEach(function(el) {{
                if (el.textContent.trim().includes(target)) {{
                    if (!firstFound) firstFound = el;
                    el.style.backgroundColor = 'yellow';
                    el.style.color = 'black';
                    el.style.fontWeight = 'bold';
                    el.style.padding = '3px 6px';
                    el.style.borderRadius = '3px';
                    el.style.display = 'inline-block';
                }}
            }});
        }});
        if (firstFound) {{
            var pos = firstFound.getBoundingClientRect().top + window.pageYOffset;
            window.scrollTo({{top: pos - 150, behavior: 'smooth'}});
            firstFound.style.border = '3px solid red';
        }}
        """

        for kw, iid in chunk:
            if ctrl.stop_event.is_set(): break
            ctrl.pause_event.wait()
            if ctrl.stop_event.is_set(): break

            self.root.after(0, lambda i=iid: self.tree.set(i, 'rank', 'Đang quét...'))

            has_result = False
            try:
                try:
                    driver.switch_to.new_window('tab')
                except Exception:
                    driver.execute_script("window.open('about:blank','_blank');")
                    driver.switch_to.window(driver.window_handles[-1])

                if not ctrl.isleep(random.uniform(2, 4)): break

                driver.get(f'https://search.naver.com/search.naver?query={kw}')

                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, 'body')))
                except Exception:
                    pass

                if not ctrl.isleep(4): break
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                if not ctrl.isleep(1): break
                driver.execute_script("window.scrollTo(0, 0);")
                if not ctrl.isleep(1): break

                try:
                    grouped = driver.execute_script(SCRIPT_GET_TITLES_GROUPED) or []
                    list2, subkeys_found = find_target_in_groups(grouped, target)
                    list3   = build_list3(list2)

                    if list3:
                        parts = compress(list3)
                        rank_str = (', '.join(parts[:-1]) +
                                    (', ' if len(parts) > 1 else '') +
                                    f'{parts[-1]}위')
                        count_v = calc_count(rank_str)
                        self.root.after(0, lambda i=iid, r=rank_str:
                                        self.tree.set(i, 'rank', r))
                        self.root.after(0, lambda i=iid, c=count_v:
                                        self.tree.set(i, 'count', c))
                        # Ghi subkey: nếu có → nối bằng ", "; không có → ' '
                        subkw_val = ', '.join(subkeys_found) if subkeys_found else ' '
                        self.root.after(0, lambda i=iid, s=subkw_val:
                                        self.tree.set(i, 'subkw', s))
                        has_result = True
                    else:
                        self.root.after(0, lambda i=iid:
                                        self.tree.set(i, 'rank', '순위밖'))
                        self.root.after(0, lambda i=iid:
                                        self.tree.set(i, 'count', ''))
                        self.root.after(0, lambda i=iid:
                                        self.tree.set(i, 'subkw', ' '))

                    driver.execute_script(script_hl)
                except Exception:
                    if not ctrl.stop_event.is_set():
                        self.root.after(0, lambda i=iid:
                                        self.tree.set(i, 'rank', 'Lỗi'))

                if has_result:
                    ctrl.isleep(10)
                else:
                    ctrl.isleep(2.5)
                    try:
                        driver.close()
                        if driver.window_handles:
                            driver.switch_to.window(driver.window_handles[0])
                    except Exception:
                        pass

            except Exception:
                if not ctrl.stop_event.is_set():
                    self.root.after(0, lambda i=iid:
                                    self.tree.set(i, 'rank', 'Lỗi'))

            with ctrl.progress_lock:
                ctrl.thread_progress[tid][0] += 1
            self._refresh_p_status('p1')

        self._check_done('p1', total_threads)

    # ═════════════════════════════════════════════════════
    # PHẦN 2 — Place Naver
    # ═════════════════════════════════════════════════════
    def _bootstrap_p2(self, items, target, n_threads):
        try:
            self._ensure_cdpath()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror('ChromeDriver lỗi', str(e)))
            self.p2.set_state(SectionCtl.STATE_IDLE); return

        ctrl = self.p2
        n = min(n_threads, len(items))
        chunks = chunk_items(items, n)

        with ctrl.progress_lock:
            ctrl.thread_progress = {tid: [0, len(c)] for tid, c in enumerate(chunks)}
        self._refresh_p_status('p2')

        for tid, chunk in enumerate(chunks):
            threading.Thread(target=self._worker_p2,
                             args=(tid, chunk, target, n),
                             daemon=True).start()
            time.sleep(0.7)

    def _worker_p2(self, tid, chunk, target, total_threads):
        ctrl = self.p2
        try:
            driver = self._make_driver(minimize=True)
            ctrl.add_driver(driver)
            if ctrl.stop_event.is_set():
                ctrl.remove_driver(driver)
                try: driver.quit()
                except Exception: pass
                return
            driver.get('about:blank')
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                'Lỗi Chrome P2', f'Thread {tid+1}: {e}'))
            for kw, iid in chunk:
                self.root.after(0, lambda i=iid: self.tree.set(i, 'p_naver', 'Lỗi driver'))
            with ctrl.progress_lock:
                ctrl.thread_progress[tid] = [len(chunk), len(chunk)]
            self._refresh_p_status('p2')
            self._check_done('p2', total_threads)
            return

        for kw, iid in chunk:
            if ctrl.stop_event.is_set(): break
            ctrl.pause_event.wait()
            if ctrl.stop_event.is_set(): break

            self.root.after(0, lambda i=iid: self.tree.set(i, 'p_naver', 'Đang quét...'))

            try:
                try:
                    driver.switch_to.new_window('tab')
                except Exception:
                    driver.execute_script("window.open('about:blank','_blank');")
                    driver.switch_to.window(driver.window_handles[-1])

                driver.get(f'https://search.naver.com/search.naver?query={kw}')
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, 'body')))
                except Exception:
                    pass

                if not ctrl.isleep(2): break
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                if not ctrl.isleep(1): break
                driver.execute_script("window.scrollTo(0, 0);")
                if not ctrl.isleep(1): break

                place_rank = self._search_place_naver(driver, target, ctrl)
                if ctrl.stop_event.is_set(): break

                val = str(place_rank) if place_rank > 0 else ' '
                self.root.after(0, lambda i=iid, v=val:
                                self.tree.set(i, 'p_naver', v))

            except Exception:
                if not ctrl.stop_event.is_set():
                    self.root.after(0, lambda i=iid:
                                    self.tree.set(i, 'p_naver', 'Lỗi'))

            try:
                driver.close()
                if driver.window_handles:
                    driver.switch_to.window(driver.window_handles[0])
            except Exception:
                pass

            with ctrl.progress_lock:
                ctrl.thread_progress[tid][0] += 1
            self._refresh_p_status('p2')

        try: driver.quit()
        except Exception: pass
        ctrl.remove_driver(driver)

        self._check_done('p2', total_threads)

    def _search_place_naver(self, driver, target, ctrl):
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, XPATH_PLACE_SECTION)))
        except Exception:
            return 0

        cumulative = 0
        while True:
            if ctrl.stop_event.is_set(): return 0
            ctrl.pause_event.wait()
            if not ctrl.isleep(1): return 0
            try:
                ul = driver.find_element(By.XPATH, XPATH_PLACE_UL)
                li_list = ul.find_elements(By.XPATH, './li')
            except Exception:
                break

            for li in li_list:
                try:
                    span = li.find_element(By.CSS_SELECTOR, 'span.TYaxT')
                    name = span.text.strip()
                except Exception:
                    name = ''
                cumulative += 1
                if target in name:
                    return cumulative

            try:
                next_btn = driver.find_element(By.XPATH, XPATH_NEXT_BTN)
                if next_btn.get_attribute('aria-disabled') == 'true':
                    break
                next_btn.click()
                if not ctrl.isleep(2): return 0
            except Exception:
                break

        return 0

    # ═════════════════════════════════════════════════════
    # PHẦN 3 — Place Web  (thegangsa.xyz — giao diện mới)
    # ═════════════════════════════════════════════════════
    def _bootstrap_p3(self, items, target, wait_sec):
        try:
            self._ensure_cdpath()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror('ChromeDriver lỗi', str(e)))
            self.p3.set_state(SectionCtl.STATE_IDLE); return

        ctrl = self.p3
        with ctrl.progress_lock:
            ctrl.thread_progress = {0: [0, len(items)]}
        self._refresh_p_status('p3')

        threading.Thread(target=self._worker_p3,
                         args=(items, target, wait_sec),
                         daemon=True).start()

    def _worker_p3(self, items, target, wait_sec):
        ctrl  = self.p3
        uid   = self.v_id.get().strip()
        pwd   = self.v_pw.get().strip()
        total = len(items)

        try:
            driver = self._make_driver(minimize=False)
            ctrl.add_driver(driver)
            if ctrl.stop_event.is_set():
                ctrl.remove_driver(driver)
                try: driver.quit()
                except Exception: pass
                return
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror('Lỗi Chrome P3', str(e)))
            ctrl.set_state(SectionCtl.STATE_IDLE); return

        def W(t=30): return WebDriverWait(driver, t)
        def loc(k):  return (By.XPATH, XG[k])

        def fill(key, text):
            el = W().until(EC.element_to_be_clickable(loc(key)))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            time.sleep(0.3)
            el.clear()
            el.send_keys(text)

        def click(key):
            el = W().until(EC.element_to_be_clickable(loc(key)))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            time.sleep(0.3)
            try:    el.click()
            except Exception: driver.execute_script("arguments[0].click();", el)

        try:
            driver.get('https://thegangsa.xyz/')
            self._set_status('p3', 'Đang tải trang...')

            fill('id_in', uid)
            fill('pw_in', pwd)
            click('login_btn')
            self._set_status('p3', 'Đang đăng nhập...')

            try:
                W(20).until(EC.presence_of_element_located(loc('aside')))
            except TimeoutException:
                self.root.after(0, lambda: messagebox.showerror(
                    'Đăng nhập thất bại',
                    'Sai ID hoặc mật khẩu thegangsa.xyz!'))
                self._mark_done_p3(); return

            if ctrl.stop_event.is_set(): return

            click('menu')
            W().until(EC.presence_of_element_located(loc('kw_in')))

            for seq, (kw, iid) in enumerate(items, 1):
                if ctrl.stop_event.is_set(): break
                ctrl.pause_event.wait()
                if ctrl.stop_event.is_set(): break

                self._set_status('p3', f'{seq}/{total}: {kw}')
                self.root.after(0, lambda i=iid: self.tree.set(i, 'p_web', '⏳'))

                try:
                    # ── Bước 1: Nhập keyword ──────────────────────
                    fill('kw_in', kw)
                    click('kw_btn')

                    # ── Bước 2: Click "Tìm kiếm chính xác 300" ───
                    click('exact_300')

                    # ── Bước 3: Chờ cố định 5s để web load ────────
                    if not ctrl.isleep(5): break

                    # ── Bước 4: Nhập tên cửa hàng ─────────────────
                    fill('name_in', target)
                    click('name_btn')

                    # ── Bước 5: Đọc kết quả từ span[2] ────────────
                    place_val = ' '
                    try:
                        span = W(10).until(
                            EC.presence_of_element_located(loc('rank_span')))
                        text = span.text.strip()
                        # Kiểm tra "không tìm thấy" → trả về khoảng trắng
                        if '찾을 수 없습니다' in text or not text:
                            place_val = ' '
                        else:
                            m = re.match(r'(\d+)', text)
                            place_val = m.group(1) if m else ' '
                    except TimeoutException:
                        place_val = ' '

                    self.root.after(0, lambda i=iid, v=place_val:
                                    self.tree.set(i, 'p_web', v))

                except Exception:
                    if not ctrl.stop_event.is_set():
                        self.root.after(0, lambda i=iid:
                                        self.tree.set(i, 'p_web', 'Lỗi'))

                with ctrl.progress_lock:
                    ctrl.thread_progress[0][0] += 1
                self._refresh_p_status('p3')

                # ── Chờ X giây trước khi sang keyword tiếp ────────
                if seq < total and not ctrl.stop_event.is_set():
                    self._set_status('p3',
                        f'{seq}/{total}: {kw} ✓ — chờ {wait_sec}s')
                    ctrl.isleep(wait_sec)

            self._mark_done_p3()

        except Exception as ex:
            if not ctrl.stop_event.is_set():
                msg = str(ex)
                self.root.after(0, lambda: messagebox.showerror('Lỗi P3', msg))
            self._mark_done_p3()

    def _mark_done_p3(self):
        ctrl = self.p3
        if not ctrl.completion_shown and not ctrl.stop_event.is_set():
            ctrl.completion_shown = True
            self._set_status('p3', '✓ Hoàn thành')
            self.root.after(0, lambda: messagebox.showinfo(
                'Phần 3', 'Phần 3 (Place Web) đã hoàn thành!'))
        ctrl.set_state(SectionCtl.STATE_IDLE)

    # ═════════════════════════════════════════════════════
    # PROGRESS HELPERS
    # ═════════════════════════════════════════════════════
    def _refresh_p_status(self, name):
        ctrl = getattr(self, name)
        with ctrl.progress_lock:
            snap = {tid: list(p) for tid, p in ctrl.thread_progress.items()}
        if not snap: return
        parts = []
        td = ta = 0
        for tid in sorted(snap.keys()):
            done, total = snap[tid]
            parts.append(f'[T{tid+1}] {done}/{total}')
            td += done; ta += total
        text = '  '.join(parts) + f'   ∑ {td}/{ta}'
        self._set_status(name, text)

    def _check_done(self, name, total_threads):
        ctrl = getattr(self, name)
        with ctrl.progress_lock:
            if len(ctrl.thread_progress) < total_threads:
                return
            all_done = all(p[0] >= p[1] for p in ctrl.thread_progress.values())
        if all_done and not ctrl.completion_shown and not ctrl.stop_event.is_set():
            ctrl.completion_shown = True
            total = sum(p[1] for p in ctrl.thread_progress.values())
            self._set_status(name, f'✓ Hoàn thành {total} keywords')
            label = {'p1': 'Phần 1 (Rank + Đếm)',
                     'p2': 'Phần 2 (Place Naver)'}[name]
            self.root.after(0, lambda n=label, t=total: messagebox.showinfo(
                'Hoàn thành', f'{n} đã xong {t} keywords!'))
            ctrl.set_state(SectionCtl.STATE_IDLE)


# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()