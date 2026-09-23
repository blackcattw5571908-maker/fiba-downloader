import re
import os
import io
import threading
import requests
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_TEXT, DND_FILES, TkinterDnD
from PIL import Image, ImageOps

class FibaDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FIBA 原圖下載器 (支援 1920x1080 統一尺寸)")
        self.root.geometry("620x620")
        self.root.resizable(False, False)

        # 1. 介面說明
        lbl_instruction = tk.Label(
            root, 
            text="請貼上或【直接拖曳】FIBA 圖片網址 / 文字檔至下方框內：", 
            font=("Microsoft JhengHei", 10, "bold")
        )
        lbl_instruction.pack(anchor="w", padx=15, pady=(15, 5))

        # 2. 輸入文字框
        self.txt_urls = tk.Text(root, height=10, width=70, font=("Consolas", 9))
        self.txt_urls.pack(padx=15, pady=5)

        # 註冊拖曳
        self.txt_urls.drop_target_register(DND_TEXT, DND_FILES)
        self.txt_urls.dnd_bind('<<Drop>>', self.handle_drop)

        # 3. 按鈕區塊
        frame_btn = tk.Frame(root)
        frame_btn.pack(fill="x", padx=15, pady=5)

        btn_clipboard = tk.Button(
            frame_btn, text="📋 從剪貼簿匯入網址", command=self.load_from_clipboard, bg="#e1f5fe"
        )
        btn_clipboard.pack(side="left", padx=(0, 5))

        btn_clear = tk.Button(
            frame_btn, text="清空內容", command=lambda: self.txt_urls.delete("1.0", tk.END)
        )
        btn_clear.pack(side="left")

        # 4. 尺寸轉換設定區塊
        frame_resize = tk.LabelFrame(root, text="圖片尺寸統一選項", font=("Microsoft JhengHei", 9, "bold"), padx=10, pady=5)
        frame_resize.pack(fill="x", padx=15, pady=5)

        self.var_enable_resize = tk.BooleanVar(value=True)
        chk_resize = tk.Checkbutton(
            frame_resize, 
            text="強制轉換為 1920x1080 (全高清規格)", 
            variable=self.var_enable_resize,
            font=("Microsoft JhengHei", 9)
        )
        chk_resize.pack(anchor="w")

        frame_mode = tk.Frame(frame_resize)
        frame_mode.pack(fill="x", pady=2)
        
        tk.Label(frame_mode, text="處理方式：", font=("Microsoft JhengHei", 9)).pack(side="left")
        
        self.var_resize_mode = tk.StringVar(value="pad")
        rb_pad = tk.Radiobutton(
            frame_mode, text="黑邊補滿 (保持完整不裁切)", value="pad", variable=self.var_resize_mode, font=("Microsoft JhengHei", 9)
        )
        rb_pad.pack(side="left", padx=5)

        rb_crop = tk.Radiobutton(
            frame_mode, text="滿版裁切 (無黑邊，自動置中裁切)", value="crop", variable=self.var_resize_mode, font=("Microsoft JhengHei", 9)
        )
        rb_crop.pack(side="left", padx=5)

        # 5. 儲存目錄設置
        frame_path = tk.Frame(root)
        frame_path.pack(fill="x", padx=15, pady=10)

        tk.Label(frame_path, text="儲存位置：", font=("Microsoft JhengHei", 9)).pack(side="left")
        self.entry_path = tk.Entry(frame_path, width=44)
        self.entry_path.insert(0, os.path.join(os.path.expanduser("~"), "Downloads"))
        self.entry_path.pack(side="left", padx=5)

        btn_browse = tk.Button(frame_path, text="瀏覽...", command=self.browse_folder)
        btn_browse.pack(side="left")

        # 6. 下載按鈕
        self.btn_download = tk.Button(
            root, 
            text="🚀 開始下載原圖並處理", 
            font=("Microsoft JhengHei", 11, "bold"), 
            bg="#4caf50", 
            fg="white", 
            command=self.start_download_thread
        )
        self.btn_download.pack(fill="x", padx=15, pady=10)

        # 7. 狀態顯示與進度條
        self.status_label = tk.Label(root, text="就緒 (可拖曳 URL / 檔案，預設輸出 1920x1080)", anchor="w", fg="gray")
        self.status_label.pack(fill="x", padx=15)

        self.progress = ttk.Progressbar(root, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=15, pady=(5, 15))

    def clean_fiba_url(self, url):
        """全面清除 FIBA/Cloudinary 圖片的所有縮放裁切參數"""
        url = url.strip()
        if not url:
            return ""
        
        # 移除網址路徑中包含的所有 Cloudinary 轉換參數
        cleaned = re.sub(r'/(?:[a-z]_[^/]+,?)+/', '/', url)
        # 移除 Query 參數
        cleaned = cleaned.split('?')[0]
        # 修復連續斜線
        cleaned = re.sub(r'([^:]/)/+', r'\1', cleaned)
        return cleaned

    def process_image_resize(self, image_bytes):
        """將圖片調整為 1920x1080"""
        img = Image.open(io.BytesIO(image_bytes))
        
        # 轉為 RGB 模式 (避開 RGBA/P 模式無法直接轉存 JPG 的問題)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        target_size = (1920, 1080)
        mode = self.var_resize_mode.get()

        if mode == "crop":
            # 滿版裁切：以中心點縮放並裁切掉多餘部分
            processed_img = ImageOps.fit(img, target_size, Image.Resampling.LANCZOS)
        else:
            # 黑邊補滿：維持原圖比例，等比縮放後置中放入 1920x1080 黑色背景
            img.thumbnail(target_size, Image.Resampling.LANCZOS)
            processed_img = Image.new("RGB", target_size, (0, 0, 0))
            offset = ((1920 - img.width) // 2, (1080 - img.height) // 2)
            processed_img.paste(img, offset)

        output = io.BytesIO()
        processed_img.save(output, format="JPEG", quality=95)
        return output.getvalue()

    def get_unique_filepath(self, save_dir, filename):
        """防覆蓋檔名處置"""
        base_name, ext = os.path.splitext(filename)
        if not ext:
            ext = ".jpg"
        
        save_path = os.path.join(save_dir, f"{base_name}{ext}")
        counter = 1
        
        while os.path.exists(save_path):
            save_path = os.path.join(save_dir, f"{base_name}_({counter}){ext}")
            counter += 1
            
        return save_path

    def handle_drop(self, event):
        dropped_data = event.data.strip()
        extracted_urls = []

        clean_path = dropped_data.strip('{}')
        if os.path.isfile(clean_path):
            try:
                with open(clean_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    extracted_urls = re.findall(r'https?://[^\s]+', content)
            except Exception as e:
                messagebox.showerror("錯誤", f"讀取拖曳檔案失敗：{e}")
                return
        else:
            extracted_urls = re.findall(r'https?://[^\s]+', dropped_data)

        if extracted_urls:
            current_text = self.txt_urls.get("1.0", tk.END).strip()
            new_urls = "\n".join(extracted_urls)
            if current_text:
                self.txt_urls.insert(tk.END, f"\n{new_urls}")
            else:
                self.txt_urls.insert("1.0", new_urls)

            self.status_label.config(text=f"偵測到拖曳網址 {len(extracted_urls)} 筆，準備自動下載...", fg="green")
            self.start_download_thread()
        else:
            self.status_label.config(text="拖入的內容中未找到有效的 HTTP/HTTPS 網址", fg="red")

    def load_from_clipboard(self):
        try:
            clipboard_text = self.root.clipboard_get()
            urls = re.findall(r'https?://[^\s]+', clipboard_text)
            if urls:
                current_text = self.txt_urls.get("1.0", tk.END).strip()
                new_urls = "\n".join(urls)
                if current_text:
                    self.txt_urls.insert(tk.END, f"\n{new_urls}")
                else:
                    self.txt_urls.insert("1.0", new_urls)
                self.status_label.config(text=f"已從剪貼簿自動匯入 {len(urls)} 筆網址", fg="green")
            else:
                messagebox.showinfo("提示", "剪貼簿中未偵測到有效的 URL 網址。")
        except Exception:
            messagebox.showwarning("警告", "無法讀取剪貼簿內容。")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, folder)

    def start_download_thread(self):
        threading.Thread(target=self.process_downloads, daemon=True).start()

    def process_downloads(self):
        raw_text = self.txt_urls.get("1.0", tk.END).strip()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        if not lines:
            messagebox.showwarning("提示", "請輸入或拖入至少一個 FIBA 網址。")
            return

        save_dir = self.entry_path.get().strip()
        if not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)

        self.btn_download.config(state="disabled")
        self.progress["maximum"] = len(lines)
        self.progress["value"] = 0

        success_count = 0
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        for idx, raw_url in enumerate(lines, start=1):
            target_url = self.clean_fiba_url(raw_url)
            filename = target_url.split("/")[-1].split("?")[0]
            if not filename or not re.search(r'\.(jpg|jpeg|png|webp)$', filename, re.IGNORECASE):
                filename = f"fiba_img_{idx}.jpg"

            save_path = self.get_unique_filepath(save_dir, filename)

            try:
                display_name = os.path.basename(save_path)
                self.status_label.config(text=f"正在下載 ({idx}/{len(lines)}): {display_name}", fg="black")
                
                resp = requests.get(target_url, headers=headers, timeout=15)
                if resp.status_code != 200:
                    resp = requests.get(raw_url, headers=headers, timeout=15)

                if resp.status_code == 200:
                    img_bytes = resp.content
                    
                    # 是否調整尺寸為 1920x1080
                    if self.var_enable_resize.get():
                        try:
                            img_bytes = self.process_image_resize(img_bytes)
                        except Exception as e_resize:
                            print(f"轉檔 1920x1080 失敗，降級存為原檔: {e_resize}")

                    with open(save_path, "wb") as f:
                        f.write(img_bytes)
                    success_count += 1
            except Exception as e:
                print(f"下載失敗 {target_url}: {e}")

            self.progress["value"] = idx

        self.status_label.config(text=f"完成！成功下載 {success_count}/{len(lines)} 張圖片", fg="blue")
        self.btn_download.config(state="normal")
        messagebox.showinfo("下載完成", f"已成功下載 {success_count} 張圖片至:\n{save_dir}")

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = FibaDownloaderApp(root)
    root.mainloop()
