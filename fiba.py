import re
import os
import threading
import requests
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# 嘗試載入拖曳模組，若環境未安裝則降級為普通模式
try:
    from tkinterdnd2 import DND_TEXT, DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    TkinterDnD = None

class FibaDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FIBA 高解析原圖批次下載器")
        self.root.geometry("640x580")
        self.root.resizable(False, False)

        # 標題與說明
        header_frame = tk.Frame(root)
        header_frame.pack(fill="x", padx=15, pady=(15, 5))
        
        lbl_title = tk.Label(
            header_frame, 
            text="🏀 FIBA 原圖下載器", 
            font=("Microsoft JhengHei", 12, "bold")
        )
        lbl_title.pack(anchor="w")

        lbl_instruction = tk.Label(
            header_frame, 
            text="請貼上或【直接拖曳】FIBA 圖片網址 / 包含網址的文字檔至下方框內：", 
            font=("Microsoft JhengHei", 9),
            fg="#555555"
        )
        lbl_instruction.pack(anchor="w", pady=(2, 0))

        # 輸入文字框
        self.txt_urls = tk.Text(root, height=12, width=72, font=("Consolas", 9), undo=True)
        self.txt_urls.pack(padx=15, pady=5)

        # 註冊拖曳接收事件 (若模組可用)
        if DND_AVAILABLE and hasattr(self.root, 'drop_target_register'):
            try:
                self.txt_urls.drop_target_register(DND_TEXT, DND_FILES)
                self.txt_urls.dnd_bind('<<Drop>>', self.handle_drop)
            except Exception as e:
                print(f"拖曳綁定失敗: {e}")

        # 捷徑按鈕區塊
        frame_btn = tk.Frame(root)
        frame_btn.pack(fill="x", padx=15, pady=5)

        btn_clipboard = tk.Button(
            frame_btn, text="📋 從剪貼簿讀取網址", command=self.load_from_clipboard, bg="#e3f2fd"
        )
        btn_clipboard.pack(side="left", padx=(0, 5))

        btn_clear = tk.Button(
            frame_btn, text="清空內容", command=lambda: self.txt_urls.delete("1.0", tk.END)
        )
        btn_clear.pack(side="left")

        # 儲存目錄設定
        frame_path = tk.LabelFrame(root, text="儲存位置", font=("Microsoft JhengHei", 9))
        frame_path.pack(fill="x", padx=15, pady=10, ipady=5)

        self.entry_path = tk.Entry(frame_path, width=54)
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads", "FIBA_Photos")
        self.entry_path.insert(0, default_dir)
        self.entry_path.pack(side="left", padx=10)

        btn_browse = tk.Button(frame_path, text="瀏覽...", command=self.browse_folder)
        btn_browse.pack(side="left")

        # 下載執行按鈕
        self.btn_download = tk.Button(
            root, 
            text="🚀 開始解析並下載原圖", 
            font=("Microsoft JhengHei", 11, "bold"), 
            bg="#2e7d32", 
            fg="white", 
            activebackground="#1b5e20",
            activeforeground="white",
            command=self.start_download_thread
        )
        self.btn_download.pack(fill="x", padx=15, pady=10)

        # 狀態顯示與進度條
        status_text = "就緒" if not DND_AVAILABLE else "就緒 (支援拖曳 URL 或文字檔自動下載)"
        self.status_label = tk.Label(root, text=status_text, anchor="w", fg="#333333", font=("Microsoft JhengHei", 9))
        self.status_label.pack(fill="x", padx=15)

        self.progress = ttk.Progressbar(root, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=15, pady=(5, 15))

    def clean_fiba_url(self, url):
        """去除 FIBA 網址中的 w_1600 / c_fill / q_auto / f_auto 裁切參數以獲取高解析原圖"""
        url = url.strip()
        if not url:
            return ""
        # 移除 Cloudinary 縮圖及優化裁切參數
        cleaned = re.sub(r'/(?:w_\d+|c_\w+|q_\w+|f_\w+|h_\d+|dpr_[\d\.]+)(?=/)', '', url)
        # 清理多餘斜線
        cleaned = re.sub(r'(?<!:)/{2,}', '/', cleaned)
        return cleaned

    def extract_urls(self, text):
        """從混雜文字中擷取 HTTP/HTTPS 網址"""
        return re.findall(r'https?://[^\s\'"<>\(\)]+', text)

    def handle_drop(self, event):
        """處理拖曳事件"""
        dropped_data = event.data.strip()
        extracted_urls = []

        # 處理 Windows 拖曳路徑可能包含的大括號
        clean_path = dropped_data.strip('{}')
        
        # 若拖入的是本地檔案
        if os.path.isfile(clean_path):
            try:
                with open(clean_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    extracted_urls = self.extract_urls(content)
            except Exception as e:
                messagebox.showerror("錯誤", f"無法讀取拖入的檔案：{e}")
                return
        else:
            # 直接拖曳文字或網址
            extracted_urls = self.extract_urls(dropped_data)

        if extracted_urls:
            current_text = self.txt_urls.get("1.0", tk.END).strip()
            new_urls = "\n".join(extracted_urls)
            
            if current_text:
                self.txt_urls.insert(tk.END, f"\n{new_urls}")
            else:
                self.txt_urls.insert("1.0", new_urls)

            self.status_label.config(text=f"已拖入 {len(extracted_urls)} 筆網址，自動開始下載...", fg="#1565c0")
            self.start_download_thread()
        else:
            self.status_label.config(text="拖入的內容中找不到有效的 URL", fg="#d32f2f")

    def load_from_clipboard(self):
        """從剪貼簿讀取網址"""
        try:
            clipboard_text = self.root.clipboard_get()
            urls = self.extract_urls(clipboard_text)
            if urls:
                current_text = self.txt_urls.get("1.0", tk.END).strip()
                new_urls = "\n".join(urls)
                if current_text:
                    self.txt_urls.insert(tk.END, f"\n{new_urls}")
                else:
                    self.txt_urls.insert("1.0", new_urls)
                self.status_label.config(text=f"已匯入剪貼簿中的 {len(urls)} 筆網址", fg="#2e7d32")
            else:
                messagebox.showinfo("提示", "剪貼簿中未找到有效的 URL 網址。")
        except Exception:
            messagebox.showwarning("警告", "無法讀取剪貼簿內容。")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, folder)

    def start_download_thread(self):
        """啟用新執行緒處理下載，避免 GUI 凍結"""
        threading.Thread(target=self.process_downloads, daemon=True).start()

    def process_downloads(self):
        raw_text = self.txt_urls.get("1.0", tk.END).strip()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        if not lines:
            messagebox.showwarning("提示", "請先輸入、貼上或拖入 FIBA 圖片網址。")
            return

        save_dir = self.entry_path.get().strip()
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("錯誤", f"無法建立資料夾：{e}")
                return

        self.btn_download.config(state="disabled")
        self.progress["maximum"] = len(lines)
        self.progress["value"] = 0

        success_count = 0
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        for idx, raw_url in enumerate(lines, start=1):
            target_url = self.clean_fiba_url(raw_url)
            
            # 解析主檔名
            filename = target_url.split("/")[-1].split("?")[0]
            if not filename or not re.search(r'\.(jpg|jpeg|png|webp)$', filename, re.IGNORECASE):
                filename = f"fiba_photo_{idx}.jpg"

            save_path = os.path.join(save_dir, filename)

            try:
                self.status_label.config(text=f"下載中 ({idx}/{len(lines)}): {filename}", fg="#333333")
                resp = requests.get(target_url, headers=headers, timeout=20)
                if resp.status_code == 200:
                    with open(save_path, "wb") as f:
                        f.write(resp.content)
                    success_count += 1
                else:
                    print(f"HTTP 錯誤 {resp.status_code}: {target_url}")
            except Exception as e:
                print(f"下載失敗 {target_url}: {e}")

            self.progress["value"] = idx

        self.status_label.config(text=f"完成！成功下載 {success_count}/{len(lines)} 張原圖", fg="#1565c0")
        self.btn_download.config(state="normal")
        messagebox.showinfo("下載完成", f"成功下載 {success_count} 張原圖至：\n{save_dir}")

def main():
    # 判斷是否可用 TkinterDnD 視窗
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    app = FibaDownloaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()