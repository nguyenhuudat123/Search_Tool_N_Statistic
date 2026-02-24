import tkinter as tk
from tkinter import ttk, messagebox
import threading
import re
from scraper import NaverScraper

class NaverTitleCheckerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Naver Rank Tracker - Automation Tool (Python Final)")
        self.root.geometry("1150x1000") 
        self.root.configure(bg='#e0e0e0') 

        self.scraper = NaverScraper()
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

        # --- PHẦN TRÊN: INPUT ---
        top_frame = tk.Frame(main_frame, bg='#e0e0e0')
        top_frame.pack(fill=tk.X, side=tk.TOP)

        kw_frame = tk.Frame(top_frame, bg='#e0e0e0')
        kw_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(kw_frame, text="Danh sách Keywords:", font=('Arial', 10, 'bold'), bg='#e0e0e0').pack(anchor='w')
        self.txt_keywords = tk.Text(kw_frame, width=30, height=8, bg="white")
        self.txt_keywords.pack(fill=tk.BOTH, pady=5)

        ctrl_frame = tk.Frame(top_frame, padx=15, bg='#e0e0e0')
        ctrl_frame.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(ctrl_frame, text="Từ TARGET:", font=('Arial', 10, 'bold'), bg='#e0e0e0').pack(anchor='w')
        self.ent_target = tk.Entry(ctrl_frame, font=('Arial', 11), fg="#d32f2f")
        self.ent_target.insert(0, "스시도쿠")  
        self.ent_target.pack(fill=tk.X, pady=5)

        btn_grid = tk.Frame(ctrl_frame, bg='#e0e0e0')
        btn_grid.pack(pady=10)

        tk.Button(btn_grid, text="▶ START", bg="#2e7d32", fg="white", font=('Arial', 9, 'bold'), width=10, command=self.start_thread).grid(row=0, column=0, pady=2, padx=2)
        tk.Button(btn_grid, text="⏸ PAUSE", bg="#f57c00", fg="white", font=('Arial', 9, 'bold'), width=10, command=self.pause_process).grid(row=0, column=1, pady=2, padx=2)
        tk.Button(btn_grid, text="⏯ RESUME", bg="#0288d1", fg="white", font=('Arial', 9, 'bold'), width=10, command=self.resume_process).grid(row=1, column=0, pady=2, padx=2)
        tk.Button(btn_grid, text="⏹ STOP", bg="#c62828", fg="white", font=('Arial', 9, 'bold'), width=10, command=self.stop_process).grid(row=1, column=1, pady=2, padx=2)

        # --- PHẦN GIỮA: BẢNG ---
        table_frame = tk.Frame(main_frame, bg='#e0e0e0', pady=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(table_frame, columns=('key', 'rank', 'count', 'note'), show='headings', height=15)
        self.tree.heading('key', text='Keyword')
        self.tree.heading('rank', text='Rank')
        self.tree.heading('count', text='Count') 
        self.tree.heading('note', text='Note')
        self.tree.column('key', width=250)
        self.tree.column('rank', width=150, anchor='center')
        self.tree.column('count', width=80, anchor='center') 
        self.tree.column('note', width=350)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        sc = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=sc.set)
        sc.pack(side=tk.RIGHT, fill=tk.Y)

        # Gán sự kiện nhấp đúp để chỉnh sửa trực tiếp trên bảng
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # --- PHẦN DƯỚI CÙNG: ĐIỀU KHIỂN SAO CHÉP & CẬP NHẬT ---
        copy_col_frame = tk.LabelFrame(main_frame, text=" Sao chép nhanh ", bg='#e0e0e0', padx=10, pady=10)
        copy_col_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        
        tk.Button(copy_col_frame, text="Copy Keyword", bg="#546e7a", fg="white", command=lambda: self.copy_specific_column(0, "Keyword")).grid(row=0, column=0, padx=5)
        tk.Button(copy_col_frame, text="Copy Rank", bg="#546e7a", fg="white", command=lambda: self.copy_specific_column(1, "Rank")).grid(row=0, column=1, padx=5)
        tk.Button(copy_col_frame, text="Copy Đếm", bg="#546e7a", fg="white", command=lambda: self.copy_specific_column(2, "Đếm")).grid(row=0, column=2, padx=5)
        tk.Button(copy_col_frame, text="Copy Ghi chú", bg="#546e7a", fg="white", command=lambda: self.copy_specific_column(3, "Ghi chú")).grid(row=0, column=3, padx=5)

        edit_frame = tk.LabelFrame(main_frame, text=" Cập nhật dữ liệu ", bg='#e0e0e0', padx=10, pady=10)
        edit_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(edit_frame, text="Rank:", bg='#e0e0e0').grid(row=0, column=0)
        self.ent_rank_input = tk.Entry(edit_frame, width=12)
        self.ent_rank_input.grid(row=0, column=1, padx=5)
        self.ent_rank_input.bind("<Return>", lambda e: self.update_data())
        
        tk.Label(edit_frame, text="Ghi chú:", bg='#e0e0e0').grid(row=0, column=2)
        self.ent_note_input = tk.Entry(edit_frame, width=30)
        self.ent_note_input.grid(row=0, column=3, padx=5)
        
        tk.Button(edit_frame, text="CẬP NHẬT", bg="#455a64", fg="white", command=self.update_data).grid(row=0, column=4, padx=5)
        tk.Button(edit_frame, text="순위밖", bg="#78909c", fg="white", command=self.set_outside_rank).grid(row=0, column=5, padx=5)
        tk.Button(edit_frame, text="📋 COPY TOÀN BẢNG", bg="#1976d2", fg="white", font=('Arial', 9, 'bold'), command=self.copy_table).grid(row=0, column=6, padx=5)
        tk.Button(edit_frame, text="🗑 XÓA TẤT CẢ", bg="#d32f2f", fg="white", font=('Arial', 9, 'bold'), command=self.clear_all_data).grid(row=0, column=7, padx=5)

    # --- TÍNH NĂNG CHỈNH SỬA TRỰC TIẾP TRÊN BẢNG (INLINE EDITING) ---
    def on_tree_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell": 
            return
        
        column = self.tree.identify_column(event.x)
        if column != "#2":  # Chỉ cho phép sửa đổi cột Rank (Index 2)
            return 
        
        item_id = self.tree.identify_row(event.y)
        x, y, width, height = self.tree.bbox(item_id, column)
        
        current_values = self.tree.item(item_id, 'values')
        current_val = current_values[1] if len(current_values) > 1 else ""
        
        entry = tk.Entry(self.tree, justify='center', font=('Arial', 10))
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, current_val)
        entry.select_range(0, tk.END)
        entry.focus_set()
        
        def save_edit(event=None):
            try:
                new_val = entry.get().strip()
            except tk.TclError:
                return # Tránh lỗi widget đã bị hủy
                
            if not new_val:
                self.tree.set(item_id, column='rank', value="")
                self.tree.set(item_id, column='count', value="")
                entry.destroy()
                return

            # Thuật toán định dạng Rank giống C#
            rank_final = new_val
            if new_val == "0": 
                rank_final = "순위밖"
            elif "," in new_val:
                parts = [f"{p.strip()}위" if p.strip().isdigit() else p.strip() for p in new_val.split(",")]
                rank_final = ", ".join(parts)
            elif new_val.isdigit(): 
                rank_final = f"{new_val}위"
                
            count_val = self.calculate_count_logic(rank_final)
            
            self.tree.set(item_id, column='rank', value=rank_final)
            self.tree.set(item_id, column='count', value=count_val)
            entry.destroy()

        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", save_edit)
        entry.bind("<Escape>", lambda e: entry.destroy())

    # --- TÍNH NĂNG XÓA TẤT CẢ ---
    def clear_all_data(self):
        res = messagebox.askyesno("Xác nhận dọn dẹp hệ thống", 
                                  "Bạn có chắc chắn muốn xóa toàn bộ danh sách Keywords và kết quả trong bảng không?\n\nHành động này không thể hoàn tác.",
                                  default=messagebox.NO)
        if res:
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.txt_keywords.delete("1.0", tk.END)
            self.ent_rank_input.delete(0, tk.END)
            self.ent_note_input.delete(0, tk.END)
            self.txt_keywords.focus_set()

    # --- CÁC TÍNH NĂNG XỬ LÝ DỮ LIỆU ---
    def calculate_count_logic(self, rank_str):
        if not rank_str or "순위밖" in rank_str or "Đang" in rank_str or "✓" in rank_str or "Lỗi" in rank_str: 
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
            return str(total_count) if total_count > 0 else ""
        except: return ""

    def update_data(self):
        selected = self.tree.selection()
        if not selected: return
        rank_raw = self.ent_rank_input.get()
        note_val = self.ent_note_input.get()
        
        rank_final = "순위밖" if rank_raw == "0" else (", ".join([f"{p.strip()}위" if p.strip().isdigit() else p.strip() for p in rank_raw.split(",")]) if "," in rank_raw else (f"{rank_raw}위" if rank_raw.isdigit() else rank_raw))
        count_val = self.calculate_count_logic(rank_final)

        for item in selected:
            if rank_raw: 
                self.tree.set(item, column='rank', value=rank_final)
                self.tree.set(item, column='count', value=count_val)
            if note_val:
                self.tree.set(item, column='note', value=note_val)
                
        self.ent_rank_input.delete(0, tk.END)
        self.select_next_row()

    def set_outside_rank(self):
        for item in self.tree.selection():
            self.tree.set(item, column='rank', value="순위밖")
            self.tree.set(item, column='count', value="") 
        self.select_next_row()

    def select_next_row(self):
        selected = self.tree.selection()
        if not selected: return
        next_item = self.tree.next(selected[-1])
        if next_item:
            self.tree.selection_set(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item)

    def copy_specific_column(self, col_index, col_name):
        column_data = []
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            val = str(values[col_index]) if len(values) > col_index and values[col_index] is not None else ""
            column_data.append(val)
        
        final_text = "\n".join(column_data)
        self.root.clipboard_clear()
        self.root.clipboard_append(final_text)
        self.root.update()
        messagebox.showinfo("Đã copy cột", f"Đã copy toàn bộ nội dung cột {col_name} vào clipboard!")

    def copy_table(self):
        headers = ["Keyword", "Rank", "Count", "Note"]
        rows = [headers]
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            rows.append([str(v) if v is not None else "" for v in values])
        
        table_text = "\n".join(["\t".join(row) for row in rows])
        self.root.clipboard_clear()
        self.root.clipboard_append(table_text)
        self.root.update()
        messagebox.showinfo("Đã copy!", f"Đã copy {len(rows)-1} dòng vào clipboard!")

    # --- ĐIỀU KHIỂN LUỒNG & SELENIUM ---
    def pause_process(self): self.is_paused.clear()
    def resume_process(self): self.is_paused.set()
    def stop_process(self):
        self.is_stopped = True
        self.is_paused.set()

    def update_ui_safe(self, item_id, column, rank_val, count_val=None):
        self.root.after(0, lambda: self.tree.set(item_id, column=column, value=rank_val))
        if count_val is not None:
            self.root.after(0, lambda: self.tree.set(item_id, column='count', value=count_val))

    def on_scraping_finished(self, total_items):
        self.root.after(0, lambda: messagebox.showinfo("Hoàn thành", f"Đã quét xong {total_items} keywords!"))

    def check_is_stopped(self):
        return self.is_stopped

    def start_thread(self):
        keywords = self.txt_keywords.get("1.0", tk.END).strip().split('\n')
        target = self.ent_target.get().strip()
        if not keywords or not target:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Keywords và Target!")
            return

        for i in self.tree.get_children(): self.tree.delete(i)
        
        items_data = []
        for kw in keywords:
            if kw.strip(): 
                item_id = self.tree.insert('', tk.END, values=(kw.strip(), "Đang chờ...", "", ""))
                items_data.append((kw.strip(), item_id))

        self.is_stopped = False
        self.is_paused.set()
        
        threading.Thread(
            target=self.scraper.run_automation, 
            args=(items_data, target, self.is_paused, self.check_is_stopped, self.update_ui_safe, self.on_scraping_finished), 
            daemon=True
        ).start()

    def on_close(self):
        self.stop_process()
        self.scraper.quit_driver()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = NaverTitleCheckerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()