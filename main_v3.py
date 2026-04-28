# Naver Title Checker — Parallel 3 Threads (ThreadPoolExecutor + Driver Pool)

import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import re

NUM_THREADS = 3

# XPath cho Place section
XPATH_PLACE_SECTION = '/html/body/div[3]/div[2]/div[1]/div[1]/div[3]/div[4]'
XPATH_PLACE_UL      = '/html/body/div[3]/div[2]/div[1]/div[1]/div[3]/div[4]/section/div/div[5]/ul'
XPATH_NEXT_BTN      = '/html/body/div[3]/div[2]/div[1]/div[1]/div[3]/div[4]/section/div/div[5]/div/a[2]'

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
        blockOrder.push({ titles: [] });
    }
    blockOrder[blockMap.get(ancestor)].titles.push(text);
});

return blockOrder.map(function(b) { return b.titles; });
"""


def find_target_in_groups(grouped, target):
    result = []
    for group in grouped:
        positions = [i + 1 for i, t in enumerate(group) if target in t]
        result.append(positions if positions else [0])
    return result


def build_list3(list2_grouped):
    seen = set()
    list3 = []
    for group in list2_grouped:
        for num in group:
            if num != 0 and num not in seen:
                seen.add(num)
                list3.append(num)
    return list3


class NaverTitleCheckerFinal:
    def __init__(self, root):
        self.root = root
        self.root.title("Naver Title Checker — Parallel 3 Threads")
        self.root.geometry("1200x1020")
        self.root.configure(bg='#e0e0e0')

        self.drivers = []
        self.driver_pool = None
        self.is_paused = threading.Event()
        self.is_paused.set()
        self.is_stopped = False
        self.completed_count = 0
        self.total_count = 0
        self.count_lock = threading.Lock()

        self.setup_ui()

    # ─────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────
    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#f2f2f2", fieldbackground="#f2f2f2", rowheight=25)

        main_frame = tk.Frame(self.root, padx=15, pady=15, bg='#e0e0e0')
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- INPUT & CONTROL ---
        top_frame = tk.Frame(main_frame, bg='#e0e0e0')
        top_frame.pack(fill=tk.X, side=tk.TOP)

        kw_frame = tk.Frame(top_frame, bg='#e0e0e0')
        kw_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(kw_frame, text="Danh sách Keywords:", font=('Arial', 10, 'bold'), bg='#e0e0e0').pack(anchor='w')
        self.txt_keywords = tk.Text(kw_frame, width=30, height=8, bg="white")
        self.txt_keywords.pack(fill=tk.BOTH, pady=5)

        ctrl_frame = tk.Frame(top_frame, padx=15, bg='#e0e0e0')
        ctrl_frame.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(ctrl_frame, text="Từ TARGET (Tìm trong Tiêu đề):", font=('Arial', 10, 'bold'), bg='#e0e0e0').pack(anchor='w')
        self.ent_target = tk.Entry(ctrl_frame, font=('Arial', 11), fg="#d32f2f")
        self.ent_target.insert(0, "스시도쿠")
        self.ent_target.pack(fill=tk.X, pady=5)

        # Số thread
        tk.Label(ctrl_frame, text=f"Số luồng song song: {NUM_THREADS}", font=('Arial', 9), bg='#e0e0e0', fg='#1565c0').pack(anchor='w')

        btn_grid = tk.Frame(ctrl_frame, bg='#e0e0e0')
        btn_grid.pack(pady=10)

        self.btn_run = tk.Button(btn_grid, text="▶ START", bg="#2e7d32", fg="white",
                                 font=('Arial', 9, 'bold'), width=10, command=self.start_thread)
        self.btn_run.grid(row=0, column=0, pady=2, padx=2)

        self.btn_pause = tk.Button(btn_grid, text="⏸ PAUSE", bg="#f57c00", fg="white",
                                   font=('Arial', 9, 'bold'), width=10, command=self.pause_process)
        self.btn_pause.grid(row=0, column=1, pady=2, padx=2)

        self.btn_resume = tk.Button(btn_grid, text="⏯ RESUME", bg="#0288d1", fg="white",
                                    font=('Arial', 9, 'bold'), width=10, command=self.resume_process)
        self.btn_resume.grid(row=1, column=0, pady=2, padx=2)

        self.btn_stop = tk.Button(btn_grid, text="⏹ STOP", bg="#c62828", fg="white",
                                  font=('Arial', 9, 'bold'), width=10, command=self.stop_process)
        self.btn_stop.grid(row=1, column=1, pady=2, padx=2)

        # Status bar
        self.lbl_status = tk.Label(ctrl_frame, text="Chờ lệnh...", font=('Arial', 9, 'italic'),
                                   bg='#e0e0e0', fg='#555')
        self.lbl_status.pack(anchor='w', pady=4)

        # --- BẢNG KẾT QUẢ ---
        table_frame = tk.Frame(main_frame, bg='#e0e0e0', pady=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(table_frame,
                                 columns=('key', 'place', 'rank', 'count', 'note'),
                                 show='headings', height=15)
        self.tree.heading('key',   text='Keyword (Key)')
        self.tree.heading('place', text='Place')
        self.tree.heading('rank',  text='Thứ hạng (Rank)')
        self.tree.heading('count', text='Đếm')
        self.tree.heading('note',  text='Ghi chú')
        self.tree.column('key',   width=230)
        self.tree.column('place', width=70,  anchor='center')
        self.tree.column('rank',  width=150, anchor='center')
        self.tree.column('count', width=70,  anchor='center')
        self.tree.column('note',  width=320)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        sc = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=sc.set)
        sc.pack(side=tk.RIGHT, fill=tk.Y)

        # --- SAO CHÉP ---
        copy_col_frame = tk.LabelFrame(main_frame, text=" Sao chép nhanh (Không kèm tên cột) ",
                                       bg='#e0e0e0', padx=10, pady=10)
        copy_col_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        tk.Button(copy_col_frame, text="Copy Keyword", bg="#546e7a", fg="white",
                  command=lambda: self.copy_specific_column(0, "Keyword")).grid(row=0, column=0, padx=5)
        tk.Button(copy_col_frame, text="Copy Place",   bg="#546e7a", fg="white",
                  command=lambda: self.copy_specific_column(1, "Place")).grid(row=0, column=1, padx=5)
        tk.Button(copy_col_frame, text="Copy Rank",    bg="#546e7a", fg="white",
                  command=lambda: self.copy_specific_column(2, "Rank")).grid(row=0, column=2, padx=5)
        tk.Button(copy_col_frame, text="Copy Đếm",     bg="#546e7a", fg="white",
                  command=lambda: self.copy_specific_column(3, "Đếm")).grid(row=0, column=3, padx=5)
        tk.Button(copy_col_frame, text="Copy Ghi chú", bg="#546e7a", fg="white",
                  command=lambda: self.copy_specific_column(4, "Ghi chú")).grid(row=0, column=4, padx=5)

        # --- CẬP NHẬT ---
        edit_frame = tk.LabelFrame(main_frame, text=" Cập nhật dữ liệu ", bg='#e0e0e0', padx=10, pady=10)
        edit_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(edit_frame, text="Rank:", bg='#e0e0e0').grid(row=0, column=0)
        self.ent_rank_input = tk.Entry(edit_frame, width=12)
        self.ent_rank_input.grid(row=0, column=1, padx=5)
        self.ent_rank_input.bind("<Return>", lambda e: self.update_data())
        tk.Label(edit_frame, text="Place:", bg='#e0e0e0').grid(row=0, column=2)
        self.ent_place_input = tk.Entry(edit_frame, width=8)
        self.ent_place_input.grid(row=0, column=3, padx=5)
        tk.Label(edit_frame, text="Ghi chú:", bg='#e0e0e0').grid(row=0, column=4)
        self.ent_note_input = tk.Entry(edit_frame, width=25)
        self.ent_note_input.grid(row=0, column=5, padx=5)
        tk.Button(edit_frame, text="CẬP NHẬT", bg="#455a64", fg="white",
                  command=self.update_data).grid(row=0, column=6, padx=5)
        tk.Button(edit_frame, text="순위밖", bg="#78909c", fg="white",
                  command=self.set_outside_rank).grid(row=0, column=7, padx=5)
        tk.Button(edit_frame, text="📋 COPY TOÀN BẢNG", bg="#1976d2", fg="white",
                  font=('Arial', 9, 'bold'), command=self.copy_table).grid(row=0, column=8, padx=5)

    # ─────────────────────────────────────────────
    # LOGIC
    # ─────────────────────────────────────────────
    def calculate_count_logic(self, rank_str):
        if not rank_str or "순위밖" in rank_str or "Đang" in rank_str or "✓" in rank_str:
            return ""
        try:
            clean_str = rank_str.replace("위", "").replace(" ", "")
            parts = clean_str.split(",")
            total_count = 0
            for part in parts:
                if "~" in part:
                    range_parts = part.split("~")
                    if len(range_parts) == 2:
                        start = int(re.sub(r'\D', '', range_parts[0]))
                        end   = int(re.sub(r'\D', '', range_parts[1]))
                        total_count += (end - start + 1)
                else:
                    only_num = re.sub(r'\D', '', part)
                    if only_num:
                        total_count += 1
            return total_count if total_count > 0 else ""
        except:
            return ""

    # ─────────────────────────────────────────────
    # SAO CHÉP / CẬP NHẬT
    # ─────────────────────────────────────────────
    def copy_specific_column(self, col_index, col_name):
        column_data = []
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            if len(values) > col_index:
                val = str(values[col_index]) if values[col_index] is not None else ""
                column_data.append(val)
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(column_data))
        self.root.update()
        messagebox.showinfo("Đã copy cột", f"Đã copy toàn bộ nội dung cột {col_name} vào clipboard!")

    def select_next_row(self):
        selected = self.tree.selection()
        if not selected:
            return
        next_item = self.tree.next(selected[-1])
        if next_item:
            self.tree.selection_set(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item)

    def set_outside_rank(self):
        for item in self.tree.selection():
            self.tree.set(item, column='rank',  value="순위밖")
            self.tree.set(item, column='count', value="")
        self.select_next_row()

    def copy_table(self):
        headers = ["Keyword", "Place", "Rank", "Đếm", "Ghi chú"]
        rows = [self.tree.item(item)['values'] for item in self.tree.get_children()]
        table_text = "\t".join(headers) + "\n"
        for row in rows:
            table_text += "\t".join(str(v) for v in row) + "\n"
        self.root.clipboard_clear()
        self.root.clipboard_append(table_text)
        self.root.update()
        messagebox.showinfo("Đã copy!", f"Đã copy {len(rows)} dòng vào clipboard!")

    def update_data(self):
        selected = self.tree.selection()
        if not selected:
            return
        rank_raw  = self.ent_rank_input.get().strip()
        place_raw = self.ent_place_input.get().strip()
        note_val  = self.ent_note_input.get().strip()

        rank_final = rank_raw
        if rank_raw == "0":
            rank_final = "순위밖"
        elif "," in rank_raw:
            parts = [f"{p.strip()}위" if p.strip().isdigit() else p.strip() for p in rank_raw.split(",")]
            rank_final = ", ".join(parts)
        elif rank_raw.isdigit():
            rank_final = f"{rank_raw}위"

        count_val = self.calculate_count_logic(rank_final)

        for item in selected:
            if rank_raw:
                self.tree.set(item, column='rank',  value=rank_final)
                self.tree.set(item, column='count', value=count_val)
            if place_raw:
                self.tree.set(item, column='place', value=place_raw)
            if note_val:
                self.tree.set(item, column='note',  value=note_val)

        self.ent_rank_input.delete(0, tk.END)
        self.ent_place_input.delete(0, tk.END)
        self.ent_note_input.delete(0, tk.END)
        self.select_next_row()

    # ─────────────────────────────────────────────
    # ĐIỀU KHIỂN
    # ─────────────────────────────────────────────
    def pause_process(self):
        self.is_paused.clear()
        self.lbl_status.config(text="⏸ Đã tạm dừng")

    def resume_process(self):
        self.is_paused.set()
        self.lbl_status.config(text="▶ Đang chạy...")

    def stop_process(self):
        self.is_stopped = True
        self.is_paused.set()   # unblock nếu đang pause
        self.lbl_status.config(text="⏹ Đã dừng")

    # ─────────────────────────────────────────────
    # SELENIUM — KHỞI TẠO DRIVER
    # ─────────────────────────────────────────────
    def _create_driver(self):
        opts = Options()
        opts.add_experimental_option("detach", True)
        opts.add_argument('--disable-blink-features=AutomationControlled')
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option('useAutomationExtension', False)
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=opts
        )
        driver.get("about:blank")
        return driver

    # ─────────────────────────────────────────────
    # SELENIUM — TÌM PLACE
    # ─────────────────────────────────────────────
    def search_place_on_current_tab(self, driver, target):
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, XPATH_PLACE_SECTION))
            )
        except:
            return 0, None

        cumulative = 0
        while True:
            time.sleep(1)
            try:
                ul = driver.find_element(By.XPATH, XPATH_PLACE_UL)
                li_list = ul.find_elements(By.XPATH, './li')
            except:
                break

            for li in li_list:
                try:
                    span = li.find_element(By.CSS_SELECTOR, 'span.TYaxT')
                    name = span.text.strip()
                except:
                    name = ""
                cumulative += 1
                if target in name:
                    return cumulative, span

            try:
                next_btn = driver.find_element(By.XPATH, XPATH_NEXT_BTN)
                if next_btn.get_attribute("aria-disabled") == "true":
                    break
                next_btn.click()
                time.sleep(2)
            except:
                break

        return 0, None

    # ─────────────────────────────────────────────
    # SELENIUM — XỬ LÝ 1 KEYWORD (chạy trong thread)
    # ─────────────────────────────────────────────
    def process_one_keyword(self, driver, kw, item_id, target):
        if self.is_stopped:
            return
        self.is_paused.wait()   # block nếu đang pause

        self.root.after(0, lambda id=item_id: self.tree.set(id, column='rank', value="Đang quét..."))

        # Mở tab mới trong driver này
        driver.execute_script("window.open('about:blank', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])

        time.sleep(random.uniform(3, 5))
        driver.get(f"https://search.naver.com/search.naver?query={kw}")
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except:
            pass

        time.sleep(4)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        # BƯỚC 1: TÌM PLACE
        place_rank, place_element = self.search_place_on_current_tab(driver, target)
        if place_rank > 0:
            self.root.after(0, lambda id=item_id, p=place_rank:
                            self.tree.set(id, column='place', value=str(p)))

        # BƯỚC 2: TÌM RANK (grouped)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        script_highlight_rank = f"""
        var target = "{target}";
        var firstFoundElement = null;
        var titleSelectors = [
            'span.sds-comps-text-type-headline1',
            'a[data-heatmap-target=".link"]',
            'a.total_tit', 'a.title_link', 'a.api_txt_lines.total_tit'
        ];
        titleSelectors.forEach(function(sel) {{
            document.querySelectorAll(sel).forEach(function(el) {{
                if (el.textContent.trim().includes(target)) {{
                    if (!firstFoundElement) {{ firstFoundElement = el; }}
                    el.style.backgroundColor = 'yellow';
                    el.style.color = 'black';
                    el.style.fontWeight = 'bold';
                    el.style.padding = '3px 6px';
                    el.style.borderRadius = '3px';
                    el.style.display = 'inline-block';
                }}
            }});
        }});
        if (firstFoundElement) {{
            var pos = firstFoundElement.getBoundingClientRect().top + window.pageYOffset;
            window.scrollTo({{ top: pos - 150, behavior: 'smooth' }});
            firstFoundElement.style.border = '3px solid red';
        }}
        """

        try:
            grouped        = driver.execute_script(SCRIPT_GET_TITLES_GROUPED) or []
            list2_grouped  = find_target_in_groups(grouped, target)
            list3          = build_list3(list2_grouped)

            if list3:
                def compress(nums):
                    groups = []
                    i = 0
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

                parts     = compress(list3)
                rank_str  = ", ".join(parts[:-1]) + (", " if len(parts) > 1 else "") + f"{parts[-1]}위"
                count_val = self.calculate_count_logic(rank_str)
                self.root.after(0, lambda id=item_id, r=rank_str:
                                self.tree.set(id, column='rank', value=r))
                self.root.after(0, lambda id=item_id, c=count_val:
                                self.tree.set(id, column='count', value=c))
            else:
                self.root.after(0, lambda id=item_id: self.tree.set(id, column='rank',  value="순위밖"))
                self.root.after(0, lambda id=item_id: self.tree.set(id, column='count', value=""))

            # BƯỚC 3: HIGHLIGHT & ĐỢI
            if place_rank > 0:
                try:
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                        place_element
                    )
                    driver.execute_script(
                        "arguments[0].style.border = '3px solid blue';"
                        "arguments[0].style.backgroundColor = 'lightgreen';",
                        place_element
                    )
                except:
                    pass
            elif list3:
                driver.execute_script(script_highlight_rank)

            time.sleep(10)

            if place_rank == 0 and not list3:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

        except Exception:
            self.root.after(0, lambda id=item_id: self.tree.set(id, column='rank', value="Lỗi"))

        # Cập nhật tiến độ (thread-safe)
        with self.count_lock:
            self.completed_count += 1
            done  = self.completed_count
            total = self.total_count

        self.root.after(0, lambda d=done, t=total:
                        self.lbl_status.config(text=f"✅ Tiến độ: {d}/{t}"))

        if done == total:
            self.root.after(0, lambda: messagebox.showinfo(
                "Hoàn thành", f"Đã quét xong {total} keywords!"))

    # ─────────────────────────────────────────────
    # CHẠY SONG SONG
    # ─────────────────────────────────────────────
    def run_parallel(self, items_data, target):
        """Chạy trong 1 background thread. Tạo pool driver, phân phối keywords."""

        # 1. Khởi tạo 3 Chrome instances
        self.root.after(0, lambda: self.lbl_status.config(
            text=f"🔄 Đang mở {NUM_THREADS} trình duyệt..."))
        self.drivers = []
        for i in range(NUM_THREADS):
            self.root.after(0, lambda i=i: self.lbl_status.config(
                text=f"🔄 Đang mở trình duyệt {i+1}/{NUM_THREADS}..."))
            d = self._create_driver()
            self.drivers.append(d)

        # 2. Đưa driver vào pool (Queue thread-safe)
        self.driver_pool = Queue()
        for d in self.drivers:
            self.driver_pool.put(d)

        self.root.after(0, lambda: self.lbl_status.config(
            text=f"▶ Bắt đầu quét — {NUM_THREADS} luồng song song"))

        # 3. Hàm worker: lấy driver từ pool → xử lý → trả lại pool
        def worker(kw, item_id):
            driver = self.driver_pool.get()    # chờ cho đến khi có driver trống
            try:
                self.process_one_keyword(driver, kw, item_id, target)
            finally:
                self.driver_pool.put(driver)   # luôn trả driver về pool

        # 4. ThreadPoolExecutor phân phối công việc
        with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            futures = {
                executor.submit(worker, kw, item_id): kw
                for kw, item_id in items_data
            }
            for future in as_completed(futures):
                # Lỗi chưa bắt bên trong sẽ bị bắt ở đây để không crash executor
                try:
                    future.result()
                except Exception as e:
                    print(f"[Worker error] {futures[future]}: {e}")

    # ─────────────────────────────────────────────
    # START
    # ─────────────────────────────────────────────
    def start_thread(self):
        keywords = self.txt_keywords.get("1.0", tk.END).strip().split('\n')
        target   = self.ent_target.get().strip()
        if not keywords or not target:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Keywords và Target!")
            return

        # Reset bảng
        for i in self.tree.get_children():
            self.tree.delete(i)

        items_data = []
        for kw in keywords:
            if kw.strip():
                item_id = self.tree.insert('', tk.END, values=(kw.strip(), "", "Đang chờ...", "", ""))
                items_data.append((kw.strip(), item_id))

        if not items_data:
            return

        self.is_stopped       = False
        self.is_paused.set()
        self.completed_count  = 0
        self.total_count      = len(items_data)

        # Chạy run_parallel trong 1 background thread riêng
        # (để không block UI khi khởi tạo 3 Chrome)
        threading.Thread(
            target=self.run_parallel,
            args=(items_data, target),
            daemon=True
        ).start()


if __name__ == "__main__":
    root = tk.Tk()
    app  = NaverTitleCheckerFinal(root)
    root.mainloop()

# ổn rồi, song song
