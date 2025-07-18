import os
import sys
import subprocess
import threading
import time
import queue
import platform
import json
from pathlib import Path

# Автоматическая установка всех зависимостей
def install_dependencies():
    required_packages = [
        'speechrecognition',
        'pyttsx3',
        'pyautogui',
        'requests',
        'psutil',
        'pillow',
        'pycaw',
        'comtypes',
        'pyaudio',
        'python-dateutil'
    ]
    
    print("Установка необходимых зависимостей...")
    for package in required_packages:
        try:
            __import__(package.split('==')[0])
            print(f"{package} уже установлен")
        except ImportError:
            print(f"Установка {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"{package} успешно установлен")
            except Exception as e:
                print(f"Ошибка установки {package}: {e}")
    
    # Дополнительная проверка для pyaudio
    try:
        import pyaudio
    except ImportError:
        print("Попытка установки PyAudio...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "PyAudio"])
        except:
            print("Не удалось установить PyAudio. Голосовые команды недоступны.")

# Установка зависимостей перед импортом остальных модулей
install_dependencies()

# Теперь импортируем остальные модули
import speech_recognition as sr
import pyttsx3
import webbrowser
import pyautogui
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, PhotoImage
import requests
import psutil
import datetime
import random
import re
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from dateutil.relativedelta import relativedelta

# ===== Конфигурация системы =====
CONFIG_FILE = "jarvis_config.json"
HISTORY_FILE = "jarvis_history.json"
NOTES_FILE = "jarvis_notes.txt"

# Загрузка конфигурации
def load_config():
    default_config = {
        "voice_rate": 185,
        "voice_pitch": 110,
        "hotword": "джарвис",
        "ai_provider": "deepseek",
        "deepseek_api_key": "sk-9b2c0e0d7d2845c1b8c7f1a6e6f8a3c0"
    }
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return default_config

# Сохранение конфигурации
def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Загрузка истории команд
def load_history():
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"commands": []}

# Сохранение истории команд
def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=4)

# Загрузка конфигурации
config = load_config()

# ===== ИИ-провайдеры =====
def ask_ai(prompt):
    """Запрос к ИИ"""
    if config["ai_provider"] == "deepseek":
        return ask_deepseek(prompt)
    else:
        return "ИИ-провайдер не настроен"

def ask_deepseek(prompt):
    """Запрос к DeepSeek AI"""
    headers = {
        "Authorization": f"Bearer {config['deepseek_api_key']}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Ты Jarvis - интеллектуальный ассистент. Отвечай кратко и по делу."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post("https://api.deepseek.com/chat/completions", 
                                headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Ошибка AI: {str(e)}"

# ===== Улучшенная настройка голоса Jarvis =====
def setup_jarvis_voice():
    engine = pyttsx3.init()
    
    # Найдем лучший голос для Jarvis
    voices = engine.getProperty('voices')
    jarvis_voice = None
    
    # Приоритетные голоса (расширенный список)
    preferred_voices = [
        'david', 'hazel', 'mark', 'microsoft david', 
        'zira', 'igor', 'aleksandr', 'pavel', 'anat', 'milena'
    ]
    
    for voice in voices:
        for name in preferred_voices:
            if name in voice.name.lower():
                jarvis_voice = voice.id
                print(f"Найден голос Jarvis: {voice.name}")
                break
        if jarvis_voice:
            break
    
    if jarvis_voice:
        engine.setProperty('voice', jarvis_voice)
    else:
        print("Используется стандартный голос")
        # Попробуем установить русский голос
        for voice in voices:
            if 'russian' in voice.languages or 'ru' in voice.languages:
                engine.setProperty('voice', voice.id)
                break
    
    # Настройки голоса для эффекта Jarvis
    engine.setProperty('rate', config["voice_rate"])
    engine.setProperty('volume', 1.0)
    engine.setProperty('pitch', config["voice_pitch"])
    
    return engine

engine = setup_jarvis_voice()

def speak(text):
    """Озвучивание текста с эффектом Jarvis"""
    print(f"JARVIS: {text}")
    
    try:
        # Разделяем текст на фразы для естественности
        phrases = re.split('[,.]', text)
        for phrase in phrases:
            if phrase.strip():
                engine.say(phrase.strip())
                engine.runAndWait()
                time.sleep(0.12)  # Короткая пауза между фразами
    except Exception as e:
        print(f"Ошибка синтеза речи: {e}")

# ===== Улучшенное распознавание речи =====
def setup_recognizer():
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 1.2
    recognizer.energy_threshold = 3000
    recognizer.dynamic_energy_threshold = True
    return recognizer

recognizer = setup_recognizer()

def listen():
    """Улучшенное распознавание речи"""
    try:
        with sr.Microphone() as source:
            print("Калибровка микрофона...")
            recognizer.adjust_for_ambient_noise(source, duration=1.2)
            
            print("Слушаю...")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            try:
                text = recognizer.recognize_google(audio, language="ru-RU")
                print(f"Вы: {text}")
                return text.lower()
            except sr.UnknownValueError:
                return ""
            except sr.RequestError as e:
                print(f"Ошибка сервиса распознавания: {e}")
                return "Ошибка сети. Проверьте интернет-соединение."
    except Exception as e:
        print(f"Ошибка микрофона: {e}")
        return "Ошибка микрофона. Проверьте подключение."

# ===== Расширенные функции Jarvis =====
def open_website(url):
    webbrowser.open(url)
    return f"Открываю {url.split('//')[-1].split('/')[0]}"

def system_info():
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot_time
    uptime_str = str(uptime).split('.')[0]
    
    return (f"Статус системы:\n"
            f"• CPU: {cpu_percent}%\n"
            f"• Память: {memory.percent}%\n"
            f"• Диск: {disk.percent}%\n"
            f"• Время работы: {uptime_str}")

def close_app(app_name):
    app_name_lower = app_name.lower()
    closed = []
    for proc in psutil.process_iter(['name', 'pid']):
        if proc.info['name'] and app_name_lower in proc.info['name'].lower():
            try:
                proc.kill()
                closed.append(proc.info['name'])
            except:
                pass
    
    if closed:
        return f"Закрыто приложений: {', '.join(closed)}"
    return f"Не удалось найти приложение: {app_name}"

def set_alarm(minutes):
    def alarm():
        time.sleep(minutes * 60)
        speak("Время вышло! Будильник сработал.")
    threading.Thread(target=alarm, daemon=True).start()
    return f"Будильник установлен на {minutes} минут"

def write_note(note):
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}: {note}\n")
    return "Заметка сохранена"

def read_notes():
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            notes = f.read()
        return "Последние заметки:\n" + notes if notes else "Заметок нет"
    except FileNotFoundError:
        return "Файл заметок не найден"

def create_folder(folder_name):
    desktop = Path.home() / "Desktop"
    folder_path = desktop / folder_name
    folder_path.mkdir(exist_ok=True)
    return f"Папка '{folder_name}' создана на рабочем столе"

def search_wikipedia(query):
    webbrowser.open(f"https://ru.wikipedia.org/wiki/{query}")
    return f"Ищу '{query}' в Википедии"

def open_app(app_name):
    apps = {
        "калькулятор": "calc.exe",
        "блокнот": "notepad.exe",
        "проводник": "explorer.exe",
        "браузер": "chrome.exe",
        "telegram": "telegram.exe",
        "discord": "discord.exe",
        "spotify": "spotify.exe",
        "word": "winword.exe",
        "excel": "excel.exe",
        "powerpoint": "powerpnt.exe",
        "paint": "mspaint.exe",
        "steam": "steam.exe",
        "vscode": "code.exe",
        "whatsapp": "whatsapp.exe",
        "skype": "skype.exe",
        "zoom": "zoom.exe"
    }
    
    app_name_lower = app_name.lower()
    
    # Поиск по ключевым словам
    for key, value in apps.items():
        if key in app_name_lower:
            try:
                os.startfile(value)
                return f"Открываю {key}, сэр."
            except:
                pass
    
    # Попробуем найти на рабочем столе
    desktop_path = Path.home() / "Desktop"
    for file in desktop_path.iterdir():
        if app_name_lower in file.name.lower() and (file.suffix in ['.lnk', '.exe']):
            try:
                os.startfile(file)
                return f"Открываю {file.stem}."
            except:
                pass
    
    return f"Не удалось найти приложение: {app_name}"

def system_command(cmd):
    commands = {
        "выключи компьютер": "shutdown /s /t 30",
        "перезагрузи компьютер": "shutdown /r /t 30",
        "режим сна": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
        "заблокируй компьютер": "rundll32.exe user32.dll,LockWorkStation"
    }
    
    if cmd in commands:
        os.system(commands[cmd])
        return "Выполняю команду."
    
    return "Неизвестная системная команда."

def get_time():
    current_time = time.strftime("%H:%M")
    return f"Сейчас {current_time}"

def get_date():
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    now = datetime.datetime.now()
    return f"Сегодня {now.day} {months[now.month]} {now.year} года"

def tell_joke():
    jokes = [
        "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 == Dec 25!",
        "Сколько программистов нужно, чтобы поменять лампочку? Ни одного, это аппаратная проблема!",
        "Что говорит программист, когда ему нужно в туалет? 'Я пойду пофиксю баги'",
        "Почему программисты такие плохие водители? Потому что они всегда ищут баги на дороге!",
        "Как называют программиста, который не боится работы? Фуллстек!"
    ]
    return random.choice(jokes)

def set_volume(level):
    """Установка громкости системы"""
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        
        # Конвертируем уровень от 0 до 100 в диапазон от 0.0 до 1.0
        volume_level = level / 100.0
        volume.SetMasterVolumeLevelScalar(volume_level, None)
        return f"Громкость установлена на {level}%"
    except:
        return "Не удалось изменить громкость"

def get_weather(city="Москва"):
    try:
        response = requests.get(f"http://wttr.in/{city}?format=%C+%t+%w")
        if response.status_code == 200:
            weather_data = response.text.split()
            condition = weather_data[0]
            temperature = weather_data[1]
            wind = weather_data[2]
            return f"Погода в {city}: {condition}, {temperature}, ветер {wind}"
        return "Не удалось получить данные о погоде"
    except:
        return "Ошибка подключения к сервису погоды"

# ===== Расширенный обработчик команд =====
def handle_command(command, history):
    if not command:
        return "Не расслышал команду, повторите.", history
    
    command_lower = command.lower()
    
    # Добавляем команду в историю
    history["commands"].append({
        "command": command,
        "timestamp": datetime.datetime.now().isoformat()
    })
    save_history(history)
    
    # Проверка на горячее слово
    if config["hotword"] and config["hotword"] in command_lower:
        command_lower = command_lower.replace(config["hotword"], "").strip()
    
    # Приветствие
    if any(word in command_lower for word in ["привет", "здравствуй", "добрый день"]):
        return "Здравствуйте, сэр. Чем могу помочь?", history
    
    # Системные команды
    elif any(cmd in command_lower for cmd in ["выключи компьютер", "перезагрузи компьютер", "режим сна", "заблокируй компьютер"]):
        for cmd in ["выключи компьютер", "перезагрузи компьютер", "режим сна", "заблокируй компьютер"]:
            if cmd in command_lower:
                return system_command(cmd), history
    
    # Системная информация
    elif "статус системы" in command_lower or "системная информация" in command_lower:
        return system_info(), history
    
    # Создание скриншота
    elif "сделай скриншот" in command_lower or "скриншот" in command_lower:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"jarvis_screenshot_{timestamp}.png"
        pyautogui.screenshot(filename)
        return f"Скриншот сохранён как {filename}", history
    
    # Открытие веб-сайтов
    elif "открой сайт" in command_lower or "открой" in command_lower:
        sites = {
            "youtube": "https://youtube.com",
            "google": "https://google.com",
            "github": "https://github.com",
            "wikipedia": "https://wikipedia.org",
            "почту": "https://gmail.com",
            "новости": "https://news.google.com",
            "переводчик": "https://translate.google.com",
            "карты": "https://maps.google.com"
        }
        
        for site_name, site_url in sites.items():
            if site_name in command_lower:
                return open_website(site_url), history
        
        return "Какой сайт открыть?", history
    
    # Открытие приложения
    elif any(word in command_lower for word in ["открой", "запусти"]):
        app_name = re.sub(r'открой|запусти', '', command_lower).strip()
        if app_name:
            return open_app(app_name), history
        return "Какое приложение открыть?", history
    
    # Закрытие приложения
    elif any(word in command_lower for word in ["закрой", "выключи"]):
        app_name = re.sub(r'закрой|выключи', '', command_lower).strip()
        if app_name:
            return close_app(app_name), history
        return "Какое приложение закрыть?", history
    
    # Поиск в интернете
    elif "найди в интернете" in command_lower or "найди" in command_lower:
        query = re.sub(r'найди в интернете|найди', '', command_lower).strip()
        if query:
            webbrowser.open(f"https://www.google.com/search?q={query}")
            return f"Ищу '{query}' в Google.", history
        return "Что искать?", history
    
    # Погода
    elif "погода" in command_lower:
        city_match = re.search(r'погода в ([\w\s]+)', command_lower)
        city = "Москва"
        if city_match:
            city = city_match.group(1)
        return get_weather(city), history
    
    # Создание папки
    elif "создай папку" in command_lower:
        folder_name = re.sub(r'создай папку', '', command_lower).strip()
        if folder_name:
            return create_folder(folder_name), history
        return "Как назвать папку?", history
    
    # Запись заметки
    elif "запиши заметку" in command_lower:
        note = re.sub(r'запиши заметку', '', command_lower).strip()
        if note:
            return write_note(note), history
        return "Что записать в заметку?", history
    
    # Чтение заметок
    elif "прочитай заметки" in command_lower:
        return read_notes(), history
    
    # Установка будильника
    elif "поставь будильник" in command_lower:
        time_match = re.search(r'на (\d+) минут', command_lower)
        minutes = 10
        if time_match:
            minutes = int(time_match.group(1))
        return set_alarm(minutes), history
    
    # Время
    elif "который час" in command_lower or "время" in command_lower:
        return get_time(), history
    
    # Дата
    elif "какое сегодня число" in command_lower or "дата" in command_lower:
        return get_date(), history
    
    # Шутка
    elif "расскажи анекдот" in command_lower or "пошути" in command_lower:
        return tell_joke(), history
    
    # Громкость
    elif "установи громкость" in command_lower:
        try:
            level = int(re.search(r'\d+', command_lower).group())
            level = max(0, min(100, level))
            return set_volume(level), history
        except:
            return "Укажите уровень громкости от 0 до 100", history
    
    # Вопрос к ИИ
    elif "спроси у ии" in command_lower or "задай вопрос ии" in command_lower:
        question = re.sub(r'спроси у ии|задай вопрос ии', '', command_lower).strip()
        if question:
            return ask_ai(question), history
        return "Что спросить у ИИ?", history
    
    # Помощь
    elif "что ты умеешь" in command_lower or "список команд" in command_lower:
        return (
            "Я могу выполнять различные команды:\n"
            "- Открывать приложения и сайты\n"
            "- Искать информацию в интернете\n"
            "- Показывать погоду\n"
            "- Делать скриншоты\n"
            "- Управлять системой (выключение, перезагрузка)\n"
            "- Создавать папки и заметки\n"
            "- Устанавливать будильники\n"
            "- Рассказывать анекдоты\n"
            "- Управлять громкостью\n"
            "- Отвечать на вопросы с помощью ИИ\n"
            "- И многое другое. Просто спросите!"
        ), history
    
    # История команд
    elif "история команд" in command_lower:
        if history["commands"]:
            last_commands = "\n".join([f"{i+1}. {cmd['command']} ({cmd['timestamp']})" 
                                     for i, cmd in enumerate(history["commands"][-5:])])
            return f"Последние команды:\n{last_commands}", history
        return "История команд пуста", history
    
    # Остановка работы
    elif any(word in command_lower for word in ["стоп", "выход", "закончи", "пока"]):
        return "exit", history
    
    # Общие вопросы к ИИ
    elif any(word in command_lower for word in ["почему", "как", "что", "кто", "где", "зачем"]):
        return ask_ai(command), history
    
    # Непонятная команда
    else:
        return "Я не понял команду. Попробуйте ещё раз.", history

# ===== Графический интерфейс Jarvis =====
class JarvisGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("J.A.R.V.I.S. - Just A Rather Very Intelligent System")
        self.root.geometry("900x700")
        self.root.configure(bg="#0a0a2a")
        
        # Загрузка истории
        self.history = load_history()
        
        # Очередь для обмена сообщениями
        self.message_queue = queue.Queue()
        
        # Стиль Jarvis
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TFrame', background='#0a0a2a')
        self.style.configure('TButton', background='#0066cc', foreground='white', 
                            font=('Arial', 10, 'bold'), borderwidth=0)
        self.style.map('TButton', background=[('active', '#0088ff')])
        self.style.configure('TLabel', background='#0a0a2a', foreground='#00aaff')
        self.style.configure('TEntry', fieldbackground='#000033', foreground='white')
        
        # Иконка приложения
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "jarvis_icon.png")
            if os.path.exists(icon_path):
                self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
        except:
            pass
        
        # Создание виджетов
        self.create_widgets()
        
        # Запуск приветствия
        self.speak_later("Система активирована. Готов к работе, сэр.")
        
        # Запуск проверки очереди
        self.root.after(100, self.process_queue)
        
    def create_widgets(self):
        # Главный фрейм
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Заголовок
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=10)
        
        # Анимированный заголовок
        self.header_label = ttk.Label(
            header_frame, 
            text="J.A.R.V.I.S.", 
            font=("Arial", 28, "bold"),
            foreground="#00ccff"
        )
        self.header_label.pack()
        self.animate_header()
        
        # Статусная строка
        self.status_var = tk.StringVar(value="🟢 Система активна")
        status_bar = ttk.Label(
            header_frame, 
            textvariable=self.status_var, 
            font=("Arial", 10, "bold"),
            foreground="#00ff00"
        )
        status_bar.pack(fill=tk.X, pady=5)
        
        # Панель консоли
        console_frame = ttk.LabelFrame(main_frame, text=" Консоль системы ")
        console_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Текстовое поле для вывода
        self.console = scrolledtext.ScrolledText(
            console_frame, 
            wrap=tk.WORD, 
            bg="#000033", 
            fg="#00ffff", 
            insertbackground="#00ffff", 
            font=("Consolas", 11),
            relief="flat",
            borderwidth=2,
            highlightbackground="#0066cc"
        )
        self.console.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.console.insert(tk.END, "> Инициализация системы...\n")
        self.console.insert(tk.END, "> Подключение к аудиоинтерфейсу...\n")
        self.console.insert(tk.END, "> J.A.R.V.I.S. готов к работе\n")
        self.console.configure(state=tk.DISABLED)
        
        # Панель управления
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        # Кнопки
        self.voice_btn = ttk.Button(
            control_frame, 
            text="🎤 Голосовая команда", 
            command=self.start_listening,
            width=20
        )
        self.voice_btn.pack(side=tk.LEFT, padx=5)
        
        self.commands_btn = ttk.Button(
            control_frame, 
            text="❓ Список команд", 
            command=self.show_commands,
            width=15
        )
        self.commands_btn.pack(side=tk.LEFT, padx=5)
        
        self.ai_btn = ttk.Button(
            control_frame, 
            text="🤖 Задать вопрос ИИ", 
            command=self.ask_ai_dialog,
            width=15
        )
        self.ai_btn.pack(side=tk.LEFT, padx=5)
        
        self.settings_btn = ttk.Button(
            control_frame, 
            text="⚙️ Настройки", 
            command=self.open_settings,
            width=15
        )
        self.settings_btn.pack(side=tk.LEFT, padx=5)
        
        self.exit_btn = ttk.Button(
            control_frame, 
            text="⏹ Выключить", 
            command=self.root.destroy,
            width=15
        )
        self.exit_btn.pack(side=tk.RIGHT, padx=5)
        
    def animate_header(self):
        """Анимация заголовка в стиле Jarvis"""
        colors = ["#00ccff", "#00aaff", "#0088ff", "#0066cc", "#0088ff", "#00aaff"]
        current_color = self.header_label.cget("foreground")
        
        if current_color in colors:
            current_index = colors.index(current_color)
            next_index = (current_index + 1) % len(colors)
            next_color = colors[next_index]
        else:
            next_color = colors[0]
        
        self.header_label.configure(foreground=next_color)
        self.root.after(300, self.animate_header)
        
    def update_console(self, text, sender="JARVIS"):
        """Обновление консоли системы"""
        self.console.configure(state=tk.NORMAL)
        prefix = "> ВЫ: " if sender == "USER" else "> JARVIS: "
        self.console.insert(tk.END, prefix + text + "\n")
        self.console.see(tk.END)
        self.console.configure(state=tk.DISABLED)
    
    def speak_later(self, text):
        """Озвучивание текста в отдельном потоке"""
        threading.Thread(target=speak, args=(text,), daemon=True).start()
    
    def start_listening(self):
        """Запуск прослушивания"""
        self.status_var.set("🔴 Запись...")
        self.voice_btn.configure(state=tk.DISABLED)
        threading.Thread(target=self.process_voice_command, daemon=True).start()
    
    def process_voice_command(self):
        """Обработка голосовой команды"""
        command = listen()
        self.message_queue.put(("status", "🟢 Система активна"))
        self.message_queue.put(("enable_button", self.voice_btn))
        
        if command:
            self.message_queue.put(("console", command, "USER"))
            self.message_queue.put(("process_command", command))
        else:
            self.message_queue.put(("console", "Не удалось распознать команду"))
            self.message_queue.put(("speak", "Повторите команду, сэр."))
    
    def process_queue(self):
        """Обработка сообщений из очереди"""
        try:
            while not self.message_queue.empty():
                message = self.message_queue.get_nowait()
                
                if message[0] == "status":
                    self.status_var.set(message[1])
                elif message[0] == "enable_button":
                    message[1].configure(state=tk.NORMAL)
                elif message[0] == "console":
                    if len(message) == 3:
                        self.update_console(message[1], message[2])
                    else:
                        self.update_console(message[1])
                elif message[0] == "speak":
                    self.speak_later(message[1])
                elif message[0] == "process_command":
                    self.process_command(message[1])
                elif message[0] == "exit":
                    self.root.destroy()
        except queue.Empty:
            pass
        
        self.root.after(100, self.process_queue)
    
    def open_settings(self):
        """Открыть окно настроек"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Настройки Jarvis")
        dialog.geometry("500x400")
        dialog.configure(bg="#0a0a2a")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="Скорость речи:", font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=5)
        self.speed_var = tk.IntVar(value=config["voice_rate"])
        speed_scale = tk.Scale(frame, from_=100, to=300, orient="horizontal", 
                              variable=self.speed_var, bg="#0a0a2a", fg="#00ccff",
                              highlightthickness=0)
        speed_scale.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        ttk.Label(frame, text="Тон голоса:", font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=5)
        self.pitch_var = tk.IntVar(value=config["voice_pitch"])
        pitch_scale = tk.Scale(frame, from_=50, to=150, orient="horizontal", 
                              variable=self.pitch_var, bg="#0a0a2a", fg="#00ccff",
                              highlightthickness=0)
        pitch_scale.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        
        ttk.Label(frame, text="Горячее слово:", font=("Arial", 10)).grid(row=2, column=0, sticky="w", pady=5)
        self.hotword_var = tk.StringVar(value=config["hotword"])
        hotword_entry = ttk.Entry(frame, textvariable=self.hotword_var, width=20)
        hotword_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        
        ttk.Label(frame, text="API ключ DeepSeek:", font=("Arial", 10)).grid(row=3, column=0, sticky="w", pady=5)
        self.api_key_var = tk.StringVar(value=config["deepseek_api_key"])
        api_key_entry = ttk.Entry(frame, textvariable=self.api_key_var, width=30)
        api_key_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=15)
        
        ttk.Button(
            btn_frame,
            text="Сохранить",
            command=lambda: self.save_settings(dialog)
        ).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(
            btn_frame,
            text="Отмена",
            command=dialog.destroy
        ).pack(side=tk.RIGHT, padx=10)
    
    def save_settings(self, dialog):
        """Сохранение настроек"""
        config["voice_rate"] = self.speed_var.get()
        config["voice_pitch"] = self.pitch_var.get()
        config["hotword"] = self.hotword_var.get()
        config["deepseek_api_key"] = self.api_key_var.get()
        save_config(config)
        
        # Переинициализация голоса
        global engine
        engine = setup_jarvis_voice()
        
        messagebox.showinfo("Настройки", "Настройки успешно сохранены!")
        dialog.destroy()
    
    def ask_ai_dialog(self):
        """Диалог для вопроса к ИИ"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Вопрос к ИИ")
        dialog.geometry("500x300")
        dialog.configure(bg="#0a0a2a")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="Задайте вопрос ИИ:", font=("Arial", 12)).pack(pady=5)
        
        self.ai_question = tk.Text(
            frame,
            height=6,
            bg="#000033",
            fg="#ffffff",
            insertbackground="#ffffff",
            font=("Arial", 11)
        )
        self.ai_question.pack(fill=tk.BOTH, expand=True, pady=5)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(
            btn_frame,
            text="Отправить",
            command=lambda: self.submit_ai_question(dialog)
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame,
            text="Отмена",
            command=dialog.destroy
        ).pack(side=tk.RIGHT, padx=5)
    
    def submit_ai_question(self, dialog):
        """Отправка вопроса к ИИ"""
        question = self.ai_question.get("1.0", tk.END).strip()
        if question:
            self.update_console(question, "USER")
            threading.Thread(
                target=self.process_ai_question, 
                args=(question, dialog),
                daemon=True
            ).start()
        else:
            messagebox.showwarning("Пустой вопрос", "Пожалуйста, введите вопрос")
    
    def process_ai_question(self, question, dialog):
        """Обработка вопроса к ИИ"""
        response = ask_ai(question)
        self.message_queue.put(("console", response))
        self.message_queue.put(("speak", response))
        dialog.destroy()
    
    def show_commands(self):
        """Показать список команд"""
        commands = [
            "Привет - Приветствие",
            "Открой [приложение] - Запуск приложения",
            "Закрой [приложение] - Закрытие приложения",
            "Открой сайт [название] - Открытие веб-сайта",
            "Найди в интернете [запрос] - Поиск в Google",
            "Погода [город] - Погода в указанном городе",
            "Сделай скриншот - Сохранение скриншота",
            "Статус системы - Информация о системе",
            "Создай папку [имя] - Создание папки на рабочем столе",
            "Запиши заметку [текст] - Сохранение заметки",
            "Прочитай заметки - Просмотр сохраненных заметок",
            "Поставь будильник - Установка будильника",
            "Расскажи анекдот - Рассказать шутку",
            "Который час? - Текущее время",
            "Какое сегодня число? - Текущая дата",
            "Установи громкость [0-100] - Установка уровня громкости",
            "Выключи компьютер - Выключение ПК",
            "Перезагрузи компьютер - Перезагрузка ПК",
            "Спроси у ИИ [вопрос] - Задать вопрос искусственному интеллекту",
            "История команд - Показать историю команд",
            "Что ты умеешь? - Список команд",
            "Стоп - Завершение работы"
        ]
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Доступные команды")
        dialog.geometry("600x400")
        dialog.configure(bg="#0a0a2a")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(
            frame, 
            yscrollcommand=scrollbar.set,
            bg="#000033", 
            fg="#00ffff", 
            font=("Arial", 11),
            selectbackground="#0066cc",
            relief="flat",
            highlightthickness=0
        )
        
        for cmd in commands:
            listbox.insert(tk.END, cmd)
        
        listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        ttk.Button(
            dialog, 
            text="Закрыть", 
            command=dialog.destroy
        ).pack(pady=10)
    
    def process_command(self, command):
        """Обработка команды"""
        response, self.history = handle_command(command, self.history)
        
        if response == "exit":
            self.message_queue.put(("speak", "Завершение работы системы. До свидания, сэр."))
            self.message_queue.put(("exit",))
            return
        
        self.message_queue.put(("console", response))
        self.message_queue.put(("speak", response))

# ===== Запуск приложения =====
if __name__ == "__main__":
    root = tk.Tk()
    app = JarvisGUI(root)
    
    # Проверка микрофона
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        if p.get_device_count() < 1:
            app.message_queue.put(("console", "> ВНИМАНИЕ: Микрофон не найден. Голосовые команды недоступны"))
            app.message_queue.put(("speak", "Внимание: микрофон не обнаружен. Используйте текстовые команды."))
        p.terminate()
    except ImportError:
        app.message_queue.put(("console", "> ВНИМАНИЕ: PyAudio не установлен. Голосовые команды недоступны"))
        app.message_queue.put(("speak", "Внимание: микрофон недоступен. Используйте текстовые команды."))
    
    root.mainloop()