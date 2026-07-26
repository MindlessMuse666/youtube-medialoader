import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import yt_dlp
import threading
import os
import certifi

def start_download():
    url = url_entry.get().strip()
    if not url:
        messagebox.showerror("Ошибка", "Введите ссылку")
        return

    download_type = type_var.get()
    quality = quality_var.get()

    ydl_opts = {
        'outtmpl': os.path.join(os.getcwd(), '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ca_cert': certifi.where(),
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'source_address': '0.0.0.0',
    }

    if download_type == "Аудио (MP3)":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '0',
            }],
        })
    else:
        if quality == "1080p":
            height = 1080
        elif quality == "720p":
            height = 720
        elif quality == "480p":
            height = 480
        else:
            height = 720
        ydl_opts.update({
            'format': f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best',
            'merge_output_format': 'mp4',
        })

    download_btn.config(state=tk.DISABLED)
    log_text.config(state=tk.NORMAL)
    log_text.delete(1.0, tk.END)
    log_text.insert(tk.END, "Начинаем загрузку...\n")
    log_text.config(state=tk.DISABLED)
    progress_bar['value'] = 0

    thread = threading.Thread(target=download_video, args=(url, ydl_opts))
    thread.start()

def download_video(url, opts):
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, "\n✅ Загрузка успешно завершена!")
        log_text.config(state=tk.DISABLED)
        progress_bar['value'] = 100
    except Exception as e:
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, f"\n❌ Ошибка: {e}\n")
        log_text.insert(tk.END, "Совет: попробуйте сменить VPN-сервер или отключить VPN вовсе.\n")
        log_text.insert(tk.END, "Если ошибка повторяется, запустите скрипт с параметром --no-check-certificate (уже добавлен).\n")
        log_text.config(state=tk.DISABLED)
    finally:
        download_btn.config(state=tk.NORMAL)

def progress_hook(d):
    if d['status'] == 'downloading':
        if 'total_bytes' in d:
            percent = (d['downloaded_bytes'] / d['total_bytes']) * 100
            progress_bar['value'] = percent
        elif 'total_bytes_estimate' in d:
            percent = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
            progress_bar['value'] = percent

        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, f"\rЗагрузка: {d.get('_percent_str', '')} | Скорость: {d.get('_speed_str', '')}")
        log_text.see(tk.END)
        log_text.config(state=tk.DISABLED)
    elif d['status'] == 'finished':
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, f"\n✅ Скачивание завершено. Начинается обработка...")
        log_text.config(state=tk.DISABLED)

# --- СОЗДАНИЕ ГРАФИЧЕСКОГО ИНТЕРФЕЙСА ---
root = tk.Tk()
root.title("YouTube Downloader")
root.geometry("600x500")
root.resizable(False, False)

# Поле для ввода ссылки
tk.Label(root, text="Ссылка на видео:").pack(pady=(10,0))
url_entry = tk.Entry(root, width=70)
url_entry.pack(pady=5)

# Рамка для выбора типа и качества
options_frame = tk.Frame(root)
options_frame.pack(pady=10)

tk.Label(options_frame, text="Тип:").grid(row=0, column=0, padx=5)
type_var = tk.StringVar(value="Видео (MP4)")
type_menu = ttk.Combobox(options_frame, textvariable=type_var, values=["Видео (MP4)", "Аудио (MP3)"], state="readonly", width=15)
type_menu.grid(row=0, column=1, padx=5)

tk.Label(options_frame, text="Качество:").grid(row=0, column=2, padx=5)
quality_var = tk.StringVar(value="720p")
quality_menu = ttk.Combobox(options_frame, textvariable=quality_var, values=["1080p", "720p", "480p"], state="readonly", width=10)
quality_menu.grid(row=0, column=3, padx=5)

# Кнопка "Скачать"
download_btn = tk.Button(root, text="Скачать", command=start_download, bg="lightblue", width=20)
download_btn.pack(pady=10)

# Прогресс-бар
progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
progress_bar.pack(pady=5)

# Лог-область
log_text = scrolledtext.ScrolledText(root, height=15, state=tk.DISABLED)
log_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

# --- ЗАПУСК ГЛАВНОГО ЦИКЛА ---
root.mainloop()