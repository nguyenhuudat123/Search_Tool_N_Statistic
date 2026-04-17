# full ok
# usingh


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
import re

class NaverTitleCheckerFinal:
    def __init__(self, root):
        self.root = root
        self.root.title("Naver Title Checker - Final Version (Enhanced)")
        self.root.geometry("1100x1000") 
        self.root.configure(bg='#e0e0e0') 

        self.driver = None
        self.is_paused = threading.Event()
        self.is_paused.set() 
        self.is_stopped = False
        
        self.setup_ui()

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#f2f2f2", fieldbackground="#f2f2f2", rowheight=25)
        
        main_frame = tk.Frame(self.root, padx=15, pady=15, bg='#e0e0e0')
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- PHẦN TRÊN: INPUT & CONTROL ---
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

        btn_grid = tk.Frame(ctrl_frame, bg='#e0e0e0')
        btn_grid.pack(pady=10)

        self.btn_run = tk.Button(btn_grid, text="▶ START", bg="#2e7d32", fg="white", font=('Arial', 9, 'bold'), width=10, command=self.start_thread)
        self.btn_run.grid(row=0, column=0, pady=2, padx=2)
        
        self.btn_pause = tk.Button(btn_grid, text="⏸ PAUSE", bg="#f57c00", fg="white", font=('Arial', 9, 'bold'), width=10, command=self.pause_process)
        self.btn_pause.grid(row=0, column=1, pady=2, padx=2)

        self.btn_resume = tk.Button(btn_grid, text="⏯ RESUME", bg="#0288d1", fg="white", font=('Arial', 9, 'bold'), width=10, command=self.resume_process)
        self.btn_resume.grid(row=1, column=0, pady=2, padx=2)

        self.btn_stop = tk.Button(btn_grid, text="⏹ STOP", bg="#c62828", fg="white", font=('Arial', 9, 'bold'), width=10, command=self.stop_process)
        self.btn_stop.grid(row=1, column=1, pady=2, padx=2)

        # --- PHẦN GIỮA: BẢNG ---
        table_frame = tk.Frame(main_frame, bg='#e0e0e0', pady=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(table_frame, columns=('key', 'rank', 'count', 'note'), show='headings', height=15)
        self.tree.heading('key', text='Keyword (Key)')
        self.tree.heading('rank', text='Thứ hạng (Rank)')
        self.tree.heading('count', text='Đếm') 
        self.tree.heading('note', text='Ghi chú')

        self.tree.column('key', width=250)
        self.tree.column('rank', width=150, anchor='center')
        self.tree.column('count', width=80, anchor='center') 
        self.tree.column('note', width=350)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        sc = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=sc.set)
        sc.pack(side=tk.RIGHT, fill=tk.Y)

        # --- PHẦN DƯỚI: SAO CHÉP TỪNG CỘT ---
        copy_col_frame = tk.LabelFrame(main_frame, text=" Sao chép nhanh (Không kèm tên cột) ", bg='#e0e0e0', padx=10, pady=10)
        copy_col_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=5)

        btn_copy_key = tk.Button(copy_col_frame, text="Copy Keyword", bg="#546e7a", fg="white", command=lambda: self.copy_specific_column(0, "Keyword"))
        btn_copy_key.grid(row=0, column=0, padx=5)

        btn_copy_rank = tk.Button(copy_col_frame, text="Copy Rank", bg="#546e7a", fg="white", command=lambda: self.copy_specific_column(1, "Rank"))
        btn_copy_rank.grid(row=0, column=1, padx=5)

        btn_copy_count = tk.Button(copy_col_frame, text="Copy Đếm", bg="#546e7a", fg="white", command=lambda: self.copy_specific_column(2, "Đếm"))
        btn_copy_count.grid(row=0, column=2, padx=5)

        btn_copy_note = tk.Button(copy_col_frame, text="Copy Ghi chú", bg="#546e7a", fg="white", command=lambda: self.copy_specific_column(3, "Ghi chú"))
        btn_copy_note.grid(row=0, column=3, padx=5)

        # --- PHẦN CUỐI: CẬP NHẬT DỮ LIỆU ---
        edit_frame = tk.LabelFrame(main_frame, text=" Cập nhật dữ liệu ", bg='#e0e0e0', padx=10, pady=10)
        edit_frame.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Label(edit_frame, text="Rank:", bg='#e0e0e0').grid(row=0, column=0)
        self.ent_rank_input = tk.Entry(edit_frame, width=12)
        self.ent_rank_input.grid(row=0, column=1, padx=5)
        self.ent_rank_input.bind("<Return>", lambda e: self.update_data())

        tk.Label(edit_frame, text="Ghi chú:", bg='#e0e0e0').grid(row=0, column=2)
        self.ent_note_input = tk.Entry(edit_frame, width=30)
        self.ent_note_input.grid(row=0, column=3, padx=5)

        btn_update = tk.Button(edit_frame, text="CẬP NHẬT", bg="#455a64", fg="white", command=self.update_data)
        btn_update.grid(row=0, column=4, padx=5)

        btn_outside = tk.Button(edit_frame, text="순위밖", bg="#78909c", fg="white", command=self.set_outside_rank)
        btn_outside.grid(row=0, column=5, padx=5)

        btn_copy_all = tk.Button(edit_frame, text="📋 COPY TOÀN BẢNG", bg="#1976d2", fg="white", font=('Arial', 9, 'bold'), command=self.copy_table)
        btn_copy_all.grid(row=0, column=6, padx=5)

    # --- HÀM LOGIC ĐẾM ---
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
                        end = int(re.sub(r'\D', '', range_parts[1]))
                        total_count += (end - start + 1)
                else:
                    only_num = re.sub(r'\D', '', part)
                    if only_num: total_count += 1
            return total_count if total_count > 0 else ""
        except: return ""

    # --- HÀM SAO CHÉP TỪNG CỘT ---
    def copy_specific_column(self, col_index, col_name):
        column_data = []
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            if len(values) > col_index:
                val = str(values[col_index]) if values[col_index] is not None else ""
                column_data.append(val)
        
        final_text = "\n".join(column_data)
        self.root.clipboard_clear()
        self.root.clipboard_append(final_text)
        self.root.update()
        messagebox.showinfo("Đã copy cột", f"Đã copy toàn bộ nội dung cột {col_name} vào clipboard!")

    # --- HÀM ĐIỀU KHIỂN ---
    def select_next_row(self):
        selected = self.tree.selection()
        if not selected: return
        next_item = self.tree.next(selected[-1])
        if next_item:
            self.tree.selection_set(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item)

    def set_outside_rank(self):
        for item in self.tree.selection():
            self.tree.set(item, column='rank', value="순위밖")
            self.tree.set(item, column='count', value="") 
        self.select_next_row()

    def copy_table(self):
        headers = ["Keyword", "Rank", "Đếm", "Ghi chú"]
        rows = []
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            rows.append(values)
        
        table_text = "\t".join(headers) + "\n"
        for row in rows:
            table_text += "\t".join(str(v) for v in row) + "\n"
        
        self.root.clipboard_clear()
        self.root.clipboard_append(table_text)
        self.root.update()
        messagebox.showinfo("Đã copy!", f"Đã copy {len(rows)} dòng vào clipboard!")

    def update_data(self):
        selected = self.tree.selection()
        if not selected: return
        rank_raw = self.ent_rank_input.get()
        note_val = self.ent_note_input.get()
        
        rank_final = rank_raw
        if rank_raw == "0": rank_final = "순위밖"
        elif "," in rank_raw:
            parts = [f"{p.strip()}위" if p.strip().isdigit() else p.strip() for p in rank_raw.split(",")]
            rank_final = ", ".join(parts)
        elif rank_raw.isdigit(): 
            rank_final = f"{rank_raw}위"

        count_val = self.calculate_count_logic(rank_final)

        for item in selected:
            if rank_raw: 
                self.tree.set(item, column='rank', value=rank_final)
                self.tree.set(item, column='count', value=count_val)
            if note_val: 
                self.tree.set(item, column='note', value=note_val)
        
        self.ent_rank_input.delete(0, tk.END)
        self.ent_note_input.delete(0, tk.END)
        self.select_next_row()

    def pause_process(self): self.is_paused.clear()
    def resume_process(self): self.is_paused.set()
    def stop_process(self):
        self.is_stopped = True
        self.is_paused.set()

    def start_thread(self):
        keywords = self.txt_keywords.get("1.0", tk.END).strip().split('\n')
        target = self.ent_target.get().strip()
        if not keywords or not target:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Keywords và Target!")
            return

        # Xử lý giao diện ở luồng chính trước khi khởi tạo luồng phụ
        for i in self.tree.get_children(): 
            self.tree.delete(i)
        
        self.items_data = [] # Lưu trữ item ID để truy xuất an toàn trong luồng phụ
        for kw in keywords:
            if kw.strip(): 
                item_id = self.tree.insert('', tk.END, values=(kw.strip(), "Đang chờ...", "", ""))
                self.items_data.append((kw.strip(), item_id))

        self.is_stopped = False
        self.is_paused.set()
        threading.Thread(target=self.run_automation, args=(self.items_data, target), daemon=True).start()

    def run_automation(self, items_data, target):
        if not self.driver:
            opts = Options()
            opts.add_experimental_option("detach", True)
            opts.add_argument('--disable-blink-features=AutomationControlled')
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option('useAutomationExtension', False)
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
            self.driver.get("about:blank")

        for kw, item_id in items_data:
            if self.is_stopped: break
            self.is_paused.wait()

            self.root.after(0, lambda id=item_id: self.tree.set(id, column='rank', value="Đang quét..."))

            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
            self.driver.execute_script("window.open('about:blank', '_blank');")
            self.driver.switch_to.window(self.driver.window_handles[-1])

            time.sleep(random.uniform(3, 5))
            self.driver.get(f"https://search.naver.com/search.naver?query={kw}")
            try: WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except: pass

            time.sleep(4)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)

            # ── BƯỚC 1: Lấy list1 (toàn bộ tiêu đề đã lọc) ──────────────────
            script_get_titles = """
            var titles = [];
            var seen = new Set();

            // Cách 1: selector UI mới Naver 2024+
            var spans = document.querySelectorAll('span.sds-comps-text-type-headline1');
            spans.forEach(function(span) {
                if (span.closest('#adbox, .sp_adbox, .ad_area, [class*="ad_"]')) return;
                var text = span.textContent.trim();
                if (text.endsWith('...') || text.endsWith('\u2026')) return;
                if (/^re\s*[:：]?\s*/i.test(text)) return;
                if (text.length < 6 || text.length > 150) return;
                if (text.indexOf('\ud568\uaed8 \ub9ce\uc774 \ucc3e\ub294') !== -1) return;
                if (text.indexOf('>') !== -1) return;
                if (text.indexOf('-') !== -1) return;
                if (text.indexOf('_') !== -1) return;
                if (!seen.has(text)) { seen.add(text); titles.push(text); }
            });

            // Fallback 1: attribute data-heatmap-target
            if (titles.length === 0) {
                document.querySelectorAll('a[data-heatmap-target=".link"]').forEach(function(a) {
                    if (a.closest('#adbox, .sp_adbox, .ad_area')) return;
                    var text = a.textContent.trim();
                    if (text.endsWith('...') || text.endsWith('\u2026')) return;
                    if (/^re\s*[:：]?\s*/i.test(text)) return;
                    if (text.length < 6 || text.length > 150) return;
                    if (text.indexOf('>') !== -1) return;
                    if (text.indexOf('-') !== -1) return;
                    if (text.indexOf('_') !== -1) return;
                    if (!seen.has(text)) { seen.add(text); titles.push(text); }
                });
            }

            // Fallback 2: selector UI cũ
            if (titles.length === 0) {
                document.querySelectorAll('a.total_tit, a.title_link, a.api_txt_lines.total_tit').forEach(function(a) {
                    var text = a.textContent.trim();
                    if (text.endsWith('...') || text.endsWith('\u2026')) return;
                    if (/^re\s*[:：]?\s*/i.test(text)) return;
                    if (text.length < 6 || text.length > 150) return;
                    if (text.indexOf('>') !== -1) return;
                    if (text.indexOf('-') !== -1) return;
                    if (text.indexOf('_') !== -1) return;
                    if (!seen.has(text)) { seen.add(text); titles.push(text); }
                });
            }

            return titles;
            """

            # ── BƯỚC 2: Highlight tiêu đề chứa target (tô vàng + scroll) ─────
            script_highlight = f"""
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
                list1 = self.driver.execute_script(script_get_titles) or []

                # ── BƯỚC 3: Tính list2 (vị trí tiêu đề chứa target) ──────────
                list2 = [i + 1 for i, title in enumerate(list1) if target in title]

                if list2:
                    # Rút gọn dãy liên tiếp >= 3 số thành dạng start~end
                    def compress(nums):
                        groups = []
                        i = 0
                        while i < len(nums):
                            j = i
                            while j + 1 < len(nums) and nums[j+1] == nums[j] + 1:
                                j += 1
                            if j - i >= 2:  # 3 số liên tiếp trở lên
                                groups.append(f"{nums[i]}~{nums[j]}")
                            else:
                                groups.extend(str(nums[k]) for k in range(i, j+1))
                            i = j + 1
                        return groups

                    parts = compress(list2)
                    rank_str = ", ".join(parts[:-1]) + (", " if len(parts) > 1 else "") + f"{parts[-1]}위"
                    count_val = self.calculate_count_logic(rank_str)
                    self.root.after(0, lambda id=item_id, r=rank_str: self.tree.set(id, column='rank', value=r))
                    self.root.after(0, lambda id=item_id, c=count_val: self.tree.set(id, column='count', value=c))
                    self.driver.execute_script(script_highlight)
                else:
                    self.root.after(0, lambda id=item_id: self.tree.set(id, column='rank', value="순위밖"))
                    self.root.after(0, lambda id=item_id: self.tree.set(id, column='count', value=""))

                time.sleep(5)

                if not list2:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])

            except Exception as e:
                self.root.after(0, lambda id=item_id: self.tree.set(id, column='rank', value="Lỗi"))

        self.root.after(0, lambda: messagebox.showinfo("Hoàn thành", f"Đã quét xong {len(items_data)} keywords!"))

if __name__ == "__main__":
    root = tk.Tk()
    app = NaverTitleCheckerFinal(root)
    root.mainloop()