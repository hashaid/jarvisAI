import os
import sys
import subprocess
import threading
import time
import queue
import platform
import json
import pickle
from pathlib import Path
import re
import webbrowser
import pyautogui
import requests
import psutil
import datetime
import random
import winsound

# Проверка и установка numpy
try:
    import numpy as np
except ImportError:
    print("Установка numpy...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy"])
    import numpy as np

# Проверка и установка scikit-learn
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    print("Установка scikit-learn...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "scikit-learn"])
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

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
        'python-dateutil',
        'scikit-learn',
        'numpy'
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
    
    # Установка SAPI5 голосов для Windows
    if platform.system() == "Windows":
        print("Проверка голосовых движков...")
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Speech\Voices")
            voices_found = False
            for i in range(winreg.QueryInfoKey(key)[0]):
                voice_name = winreg.EnumKey(key, i)
                if "Russian" in voice_name:
                    voices_found = True
                    break
            
            if not voices_found:
                print("Русские голоса не найдены. Попробуйте установить их вручную через настройки Windows.")
        except:
            print("Не удалось проверить голосовые движки. Убедитесь, что установлены русские голоса SAPI5.")

# Установка зависимостей перед импортом остальных модулей
install_dependencies()

# Теперь импортируем остальные модули
import speech_recognition as sr
import pyttsx3
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, PhotoImage
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from dateutil.relativedelta import relativedelta

# ===== Конфигурация системы =====
CONFIG_FILE = "jarvis_config.json"
HISTORY_FILE = "jarvis_history.json"
NOTES_FILE = "jarvis_notes.txt"
KNOWLEDGE_FILE = "jarvis_knowledge.pkl"
PERSONALITY_FILE = "jarvis_personality.json"

# Загрузка конфигурации
def load_config():
    default_config = {
        "voice_rate": 185,
        "voice_pitch": 110,
        "hotword": "джарвис",
        "user_name": "Сэр",
        "ai_provider": "local",
        "deepseek_api_key": "",
        "learn_from_commands": True,
        "always_listen": True,
        "password": "jarvis",
        "sequence_mode": False,
        "sequence_commands": []
    }
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            user_config = json.load(f)
            # Объединение с дефолтными настройками для новых ключей
            for key, value in default_config.items():
                if key not in user_config:
                    user_config[key] = value
            return user_config
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

# ===== Локальный ИИ с обучением =====
class LocalAI:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()
        self.knowledge = []
        self.patterns = []
        self.responses = []
        self.load_knowledge()
        
        # Загрузка личности
        self.load_personality()
    
    def load_personality(self):
        default_personality = {
            "name": "Jarvis",
            "greetings": [
                "Приветствую, {user_name}. Чем могу быть полезен?",
                "Здравствуйте, {user_name}. Система готова к работе.",
                "Добрый день, {user_name}. Ожидаю ваших указаний."
            ],
            "farewells": [
                "До свидания, {user_name}. Всегда к вашим услугам.",
                "Завершаю работу. Обращайтесь, если понадоблюсь.",
                "Отключаю системы. До новых встреч."
            ],
            "jokes": [
                "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 == Dec 25!",
                "Сколько программистов нужно, чтобы поменять лампочку? Ни одного, это аппаратная проблема!",
                "Что говорит программист, когда ему нужно в туалет? 'Я пойду пофиксю баги'",
                "Почему программисты такие плохие водители? Потому что они всегда ищут баги на дороге!",
                "Как называют программиста, который не боится работы? Фуллстек!"
            ],
            "personality_traits": {
                "humor_level": 5,
                "formality_level": 7,
                "patience_level": 8
            }
        }
        
        try:
            with open(PERSONALITY_FILE, 'r') as f:
                self.personality = json.load(f)
        except:
            self.personality = default_personality
            with open(PERSONALITY_FILE, 'w') as f:
                json.dump(default_personality, f, indent=4)
    
    def save_personality(self):
        with open(PERSONALITY_FILE, 'w') as f:
            json.dump(self.personality, f, indent=4)
    
    def train(self, pattern, response):
        """Добавление нового знания в ИИ"""
        self.patterns.append(pattern.lower())
        self.responses.append(response)
        # Переобучаем векторизатор на всех шаблонах
        if self.patterns:
            self.vectorizer.fit(self.patterns)
        self.save_knowledge()
    
    def save_knowledge(self):
        """Сохранение знаний в файл"""
        knowledge = {
            "patterns": self.patterns,
            "responses": self.responses
        }
        with open(KNOWLEDGE_FILE, 'wb') as f:
            pickle.dump(knowledge, f)
    
    def load_knowledge(self):
        """Загрузка знаний из файла"""
        try:
            with open(KNOWLEDGE_FILE, 'rb') as f:
                knowledge = pickle.load(f)
                self.patterns = knowledge["patterns"]
                self.responses = knowledge["responses"]
                
                # Обучение векторизатора
                if self.patterns:
                    self.vectorizer.fit(self.patterns)
        except:
            # Начальные знания
            self.patterns = [
                "привет",
                "как дела",
                "что ты умеешь",
                "спасибо",
                "расскажи о себе"
            ]
            self.responses = [
                "Здравствуйте, {user_name}. Чем могу помочь?",
                "Всё функционирует в пределах нормы, {user_name}. Спасибо, что интересуетесь.",
                "Я могу выполнять различные команды: открывать приложения, искать информацию, управлять системой и многое другое. Спросите 'Что ты умеешь?' для подробностей.",
                "Всегда пожалуйста, {user_name}. Обращайтесь, если понадоблюсь.",
                "Я - Jarvis, ваш персональный ассистент. Моя задача - помогать вам в решении повседневных задач и управлении компьютером."
            ]
            # Обучаем векторизатор на начальных знаниях
            if self.patterns:
                self.vectorizer.fit(self.patterns)
            self.save_knowledge()
    
    def respond(self, query, user_name):
        """Генерация ответа на запрос"""
        # Проверка точных соответствий
        if query.lower() in self.patterns:
            idx = self.patterns.index(query.lower())
            return self.responses[idx].format(user_name=user_name)
        
        # Поиск похожих вопросов
        if self.patterns:
            query_vec = self.vectorizer.transform([query.lower()])
            pattern_vecs = self.vectorizer.transform(self.patterns)
            similarities = cosine_similarity(query_vec, pattern_vecs)
            max_idx = np.argmax(similarities)
            
            if similarities[0, max_idx] > 0.6:
                return self.responses[max_idx].format(user_name=user_name)
        
        # Генерация ответа на основе личности
        traits = self.personality["personality_traits"]
        
        if traits["humor_level"] > 7 and random.random() > 0.7:
            return random.choice(self.personality["jokes"])
        
        responses = [
            f"Понял вас, {user_name}. Но я еще учусь отвечать на такие вопросы.",
            f"Интересный вопрос, {user_name}. Пока я не могу на него ответить, но я запомню его для изучения.",
            f"Простите, {user_name}, я еще не научился отвечать на такие запросы.",
            f"Моя текущая версия не поддерживает ответ на этот вопрос, {user_name}."
        ]
        
        return random.choice(responses)

# Инициализация локального ИИ
local_ai = LocalAI()

# ===== ИИ-провайдеры =====
def ask_ai(prompt):
    """Запрос к ИИ"""
    if config["ai_provider"] == "deepseek" and config["deepseek_api_key"]:
        return ask_deepseek(prompt)
    else:
        return local_ai.respond(prompt, config["user_name"])

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
    try:
        engine = pyttsx3.init()
    except Exception as e:
        print(f"Ошибка инициализации pyttsx3: {e}")
        return None
    
    # Найдем лучший голос для Jarvis
    voices = engine.getProperty('voices')
    jarvis_voice = None
    
    # Приоритетные голоса (расширенный список)
    preferred_voices = [
        'david', 'hazel', 'mark', 'microsoft david', 
        'zira', 'igor', 'aleksandr', 'pavel', 'anat', 'milena'
    ]
    
    print("Доступные голоса:")
    for voice in voices:
        print(f" - {voice.name} (ID: {voice.id})")
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
            lang = getattr(voice, 'languages', None)
            if lang and ('ru' in lang[0].lower() or 'rus' in lang[0].lower()):
                engine.setProperty('voice', voice.id)
                print(f"Используется русский голос: {voice.name}")
                break
    
    # Настройки голоса для эффекта Jarvis
    engine.setProperty('rate', config["voice_rate"])
    engine.setProperty('volume', 1.0)
    try:
        engine.setProperty('pitch', config["voice_pitch"])
    except:
        print("Предупреждение: настройка pitch не поддерживается текущим голосовым движком")
    
    return engine

engine = None  # Будет инициализирован позже

def speak(text):
    """Озвучивание текста с эффектом Jarvis"""
    global engine
    if engine is None:
        try:
            engine = setup_jarvis_voice()
            if engine is None:
                print("Не удалось инициализировать голосовой движок")
                return
        except Exception as e:
            print(f"Ошибка инициализации голоса: {e}")
            return
    
    print(f"JARVIS: {text}")
    
    try:
        # Разделяем текст на фразы для естественности
        phrases = re.split('[,.]', text)
        for phrase in phrases:
            if phrase.strip():
                engine.say(phrase.strip())
        engine.runAndWait()
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

# ===== Фоновое прослушивание для горячего слова =====
class BackgroundListener(threading.Thread):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.running = True
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.0
        self.recognizer.energy_threshold = 3000
        self.recognizer.dynamic_energy_threshold = True
        self.microphone = sr.Microphone()
        self.daemon = True
    
    def run(self):
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            print("Фоновое прослушивание запущено...")
            
            while self.running:
                try:
                    audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=3)
                    text = self.recognizer.recognize_google(audio, language="ru-RU").lower()
                    if config["hotword"] in text:
                        self.callback(text)
                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except Exception as e:
                    if self.running:  # Игнорировать ошибки при остановке
                        print(f"Ошибка фонового прослушивания: {e}")
    
    def stop(self):
        self.running = False
        print("Фоновое прослушивание остановлено")

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
    return random.choice(local_ai.personality["jokes"])

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

def type_text(text):
    """Печать текста"""
    pyautogui.typewrite(text)
    return f"Напечатано: {text}"

def press_key(key):
    """Нажатие клавиши"""
    pyautogui.press(key)
    return f"Нажата клавиша: {key}"

def send_message(text):
    """Отправка сообщения"""
    pyautogui.typewrite(text)
    pyautogui.press("enter")
    return f"Сообщение отправлено: {text}"

def maximize_window():
    """Максимизация текущего окна"""
    pyautogui.hotkey('win', 'up')
    return "Текущее окно максимизировано"

def minimize_window():
    """Минимизация текущего окна"""
    pyautogui.hotkey('win', 'down')
    return "Текущее окно минимизировано"

def switch_window():
    """Переключение между окнами"""
    pyautogui.hotkey('alt', 'tab')
    return "Переключение между окнами"

def remember_this(text):
    """Запоминание информации"""
    fact = text.replace("запомни что", "").strip()
    local_ai.train(f"что такое {fact.split()[0]}", fact)
    return f"Запомнил: {fact}"

def search_files(filename):
    """Поиск файлов на компьютере"""
    try:
        # Для Windows
        if platform.system() == "Windows":
            result = subprocess.run(['dir', filename, '/s', '/b'], 
                                   capture_output=True, text=True, shell=True)
            files = result.stdout.splitlines()
            
            if files:
                return f"Найдены файлы:\n" + "\n".join(files[:5]) + ("\n..." if len(files) > 5 else "")
            else:
                return "Файлы не найдены"
        # Для Linux/MacOS
        else:
            result = subprocess.run(['find', '-name', filename], 
                                   capture_output=True, text=True)
            files = result.stdout.splitlines()
            
            if files:
                return f"Найдены файлы:\n" + "\n".join(files[:5]) + ("\n..." if len(files) > 5 else "")
            else:
                return "Файлы не найдены"
    except:
        return "Ошибка поиска файлов"

def play_activation_sound():
    """Звук активации Jarvis"""
    try:
        winsound.Beep(1000, 200)  # Высокий звук
        winsound.Beep(1200, 150)
    except:
        # Для не-Windows систем
        try:
            import os
            os.system('echo -e "\a"')
        except:
            pass

def play_deactivation_sound():
    """Звук деактивации Jarvis"""
    try:
        winsound.Beep(800, 200)  # Низкий звук
        winsound.Beep(600, 150)
    except:
        # Для не-Windows систем
        try:
            import os
            os.system('echo -e "\a"')
        except:
            pass

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
    
    # Если включено обучение, добавляем команду в ИИ
    if config["learn_from_commands"]:
        # Формируем ответ на основе предыдущих ответов
        response, _ = handle_command_internal(command, history.copy())
        local_ai.train(command, response)
    
    # Обработка команды
    return handle_command_internal(command, history)

def handle_command_internal(command, history):
    command_lower = command.lower()
    
    # Проверка на горячее слово
    if config["hotword"] and config["hotword"] in command_lower:
        command_lower = command_lower.replace(config["hotword"], "").strip()
    
    # Приветствие
    if any(word in command_lower for word in ["привет", "здравствуй", "добрый день"]):
        greeting = random.choice(local_ai.personality["greetings"])
        return greeting.format(user_name=config["user_name"]), history
    
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
            "карты": "https://maps.google.com",
            "яндекс": "https://yandex.ru",
            "соцсети": "https://facebook.com"
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
    
    # Печать текста
    elif "напечатай" in command_lower:
        text = command_lower.replace("напечатай", "").strip()
        if text:
            return type_text(text), history
        return "Что напечатать?", history
    
    # Отправка сообщения
    elif "отправь сообщение" in command_lower:
        text = command_lower.replace("отправь сообщение", "").strip()
        if text:
            return send_message(text), history
        return "Какое сообщение отправить?", history
    
    # Управление окнами
    elif "максимизируй окно" in command_lower:
        return maximize_window(), history
    
    elif "минимизируй окно" in command_lower:
        return minimize_window(), history
    
    elif "переключи окно" in command_lower:
        return switch_window(), history
    
    # Поиск файлов
    elif "найди файл" in command_lower:
        filename = command_lower.replace("найди файл", "").strip()
        if filename:
            return search_files(filename), history
        return "Какой файл найти?", history
    
    # Запоминание информации
    elif "запомни что" in command_lower:
        return remember_this(command_lower), history
    
    # Последовательность команд
    elif "начать последовательность команд" in command_lower:
        config["sequence_mode"] = True
        config["sequence_commands"] = []
        save_config(config)
        return "Режим последовательности команд активирован. Ожидаю команды...", history
    
    elif "завершить последовательность команд" in command_lower:
        config["sequence_mode"] = False
        save_config(config)
        return "Режим последовательности команд завершен.", history
    
    elif "отмени команду" in command_lower:
        if config["sequence_commands"]:
            removed = config["sequence_commands"].pop()
            save_config(config)
            return f"Команда '{removed}' отменена. Осталось команд: {len(config['sequence_commands'])}", history
        return "Нет команд для отмены.", history
    
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
            "- Отвечать на вопросы\n"
            "- Печатать текст\n"
            "- Отправлять сообщения\n"
            "- Управлять окнами\n"
            "- Искать файлы\n"
            "- Запоминать информацию\n"
            "- Выполнять последовательности команд\n"
            "- Отменять последнюю команду\n"
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
        farewell = random.choice(local_ai.personality["farewells"])
        return f"exit||{farewell.format(user_name=config['user_name'])}", history
    
    # Общие вопросы
    elif any(word in command_lower for word in ["почему", "как", "что", "кто", "где", "зачем"]):
        return ask_ai(command), history
    
    # Непонятная команда
    else:
        return ask_ai(command), history

# ===== Графический интерфейс Jarvis =====
class JarvisGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"J.A.R.V.I.S. - Just A Rather Very Intelligent System")
        self.root.geometry("900x700")
        self.root.configure(bg="#0a0a2a")
        
        # Инициализация голосового движка
        threading.Thread(target=self.initialize_voice, daemon=True).start()
        
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
        
        # Фоновое прослушивание
        self.background_listener = BackgroundListener(self.activate_from_hotword)
        if config.get("always_listen", True):  # Используем безопасное получение значения
            self.background_listener.start()
    
    def initialize_voice(self):
        """Инициализация голосового движка в фоновом потоке"""
        global engine
        try:
            engine = setup_jarvis_voice()
            self.message_queue.put(("console", "Голосовой движок успешно инициализирован"))
        except Exception as e:
            self.message_queue.put(("console", f"Ошибка инициализации голосового движка: {e}"))
    
    def create_widgets(self):
        # Главный фрейм
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Создаем Notebook (вкладки)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Вкладка 1: Консоль
        console_frame = ttk.Frame(self.notebook)
        self.notebook.add(console_frame, text="Консоль")
        
        # Вкладка 2: Заметки
        notes_frame = ttk.Frame(self.notebook)
        self.notebook.add(notes_frame, text="Заметки")
        
        # Вкладка 3: История
        history_frame = ttk.Frame(self.notebook)
        self.notebook.add(history_frame, text="История")
        
        # ===== Содержимое вкладки Консоль =====
        # Заголовок
        header_frame = ttk.Frame(console_frame)
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
        console_panel_frame = ttk.LabelFrame(console_frame, text=" Консоль системы ")
        console_panel_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Текстовое поле для вывода
        self.console = scrolledtext.ScrolledText(
            console_panel_frame, 
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
        control_frame = ttk.Frame(console_frame)
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
            text="🤖 Задать вопрос", 
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
        
        # ===== Содержимое вкладки Заметки =====
        # Текстовое поле для заметок
        self.notes_text = scrolledtext.ScrolledText(
            notes_frame,
            wrap=tk.WORD,
            bg="#000033",
            fg="#ffffff",
            insertbackground="#ffffff",
            font=("Arial", 11)
        )
        self.notes_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Загружаем заметки
        self.load_notes()
        
        # Кнопки
        notes_btn_frame = ttk.Frame(notes_frame)
        notes_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(
            notes_btn_frame,
            text="Сохранить",
            command=self.save_notes
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            notes_btn_frame,
            text="Обновить",
            command=self.load_notes
        ).pack(side=tk.RIGHT, padx=5)
        
        # ===== Содержимое вкладки История =====
        # Список истории
        self.history_list = tk.Listbox(
            history_frame,
            bg="#000033",
            fg="#00ff00",
            font=("Arial", 11),
            selectbackground="#0066cc",
            selectforeground="#ffffff",
            relief="flat"
        )
        scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_list.yview)
        self.history_list.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Загружаем историю
        self.load_history_list()
        
        # Кнопки
        history_btn_frame = ttk.Frame(history_frame)
        history_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(
            history_btn_frame,
            text="Обновить",
            command=self.load_history_list
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            history_btn_frame,
            text="Очистить",
            command=self.clear_history
        ).pack(side=tk.RIGHT, padx=5)
    
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
            
            # Проверка на режим последовательности
            if config.get("sequence_mode", False):
                config["sequence_commands"].append(command)
                save_config(config)
                response = f"Команда добавлена в последовательность. Текущее количество: {len(config['sequence_commands'])}"
                self.message_queue.put(("console", response))
                self.message_queue.put(("speak", response))
            else:
                self.message_queue.put(("process_command", command))
        else:
            self.message_queue.put(("console", "Не удалось распознать команду"))
            self.message_queue.put(("speak", "Повторите команду, сэр."))
    
    def activate_from_hotword(self, text):
        """Активация по горячему слову"""
        # Воспроизвести звук активации
        play_activation_sound()
        
        # Обновить статус
        self.message_queue.put(("status", "🔴 Активирован по голосу"))
        
        # Визуальная индикация
        self.header_label.configure(foreground="#ff0000")
        
        # Обработка команды
        self.message_queue.put(("console", text, "USER"))
        
        # Проверка на режим последовательности
        if config.get("sequence_mode", False):
            config["sequence_commands"].append(text)
            save_config(config)
            response = f"Команда добавлена в последовательность. Текущее количество: {len(config['sequence_commands'])}"
            self.message_queue.put(("console", response))
            self.message_queue.put(("speak", response))
        else:
            self.message_queue.put(("process_command", text))
        
        # Запланировать восстановление нормального состояния
        self.root.after(5000, self.deactivate_hotword_state)
    
    def deactivate_hotword_state(self):
        """Возврат к нормальному состоянию после активации"""
        # Восстановить анимацию заголовка
        self.animate_header()
        # Обновить статус
        self.message_queue.put(("status", "🟢 Ожидание команды"))
    
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
    
    def load_notes(self):
        """Загрузка заметок в интерфейс"""
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                notes = f.read()
            self.notes_text.delete(1.0, tk.END)
            self.notes_text.insert(tk.END, notes)
        except FileNotFoundError:
            pass
    
    def save_notes(self):
        """Сохранение заметок из интерфейса"""
        notes = self.notes_text.get(1.0, tk.END)
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            f.write(notes)
        self.message_queue.put(("console", "Заметки сохранены"))
        self.message_queue.put(("speak", "Заметки сохранены"))
    
    def load_history_list(self):
        """Загрузка истории команд в список"""
        self.history = load_history()
        self.history_list.delete(0, tk.END)
        if self.history["commands"]:
            for cmd in self.history["commands"]:
                timestamp = datetime.datetime.fromisoformat(cmd["timestamp"]).strftime("%Y-%m-%d %H:%M")
                self.history_list.insert(tk.END, f"{timestamp}: {cmd['command']}")
    
    def clear_history(self):
        """Очистка истории команд"""
        self.history = {"commands": []}
        save_history(self.history)
        self.history_list.delete(0, tk.END)
        self.message_queue.put(("console", "История команд очищена"))
        self.message_queue.put(("speak", "История команд очищена"))
    
    def open_settings(self):
        """Открыть окно настроек"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Настройки Jarvis")
        dialog.geometry("500x500")
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
        
        ttk.Label(frame, text="Ваше имя:", font=("Arial", 10)).grid(row=3, column=0, sticky="w", pady=5)
        self.user_name_var = tk.StringVar(value=config["user_name"])
        user_name_entry = ttk.Entry(frame, textvariable=self.user_name_var, width=20)
        user_name_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        
        ttk.Label(frame, text="AI провайдер:", font=("Arial", 10)).grid(row=4, column=0, sticky="w", pady=5)
        self.ai_provider_var = tk.StringVar(value=config["ai_provider"])
        ai_provider_combobox = ttk.Combobox(frame, textvariable=self.ai_provider_var, 
                                          values=["local", "deepseek"], width=18)
        ai_provider_combobox.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(frame, text="API ключ DeepSeek:", font=("Arial", 10)).grid(row=5, column=0, sticky="w", pady=5)
        self.api_key_var = tk.StringVar(value=config["deepseek_api_key"])
        api_key_entry = ttk.Entry(frame, textvariable=self.api_key_var, width=30)
        api_key_entry.grid(row=5, column=1, sticky="ew", padx=5, pady=5)
        
        self.learn_var = tk.BooleanVar(value=config.get("learn_from_commands", True))
        learn_check = ttk.Checkbutton(frame, text="Обучаться на моих командах", 
                                    variable=self.learn_var)
        learn_check.grid(row=6, column=0, columnspan=2, pady=5, sticky="w")
        
        self.always_listen_var = tk.BooleanVar(value=config.get("always_listen", True))
        always_listen_check = ttk.Checkbutton(frame, text="Всегда слушать горячее слово", 
                                            variable=self.always_listen_var)
        always_listen_check.grid(row=7, column=0, columnspan=2, pady=5, sticky="w")
        
        # Настройка пароля
        ttk.Label(frame, text="Пароль доступа:", font=("Arial", 10)).grid(row=8, column=0, sticky="w", pady=5)
        self.password_var = tk.StringVar(value=config.get("password", "jarvis"))
        password_entry = ttk.Entry(frame, textvariable=self.password_var, width=20, show="*")
        password_entry.grid(row=8, column=1, sticky="ew", padx=5, pady=5)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=9, column=0, columnspan=2, pady=15)
        
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
        config["user_name"] = self.user_name_var.get()
        config["ai_provider"] = self.ai_provider_var.get()
        config["deepseek_api_key"] = self.api_key_var.get()
        config["learn_from_commands"] = self.learn_var.get()
        config["always_listen"] = self.always_listen_var.get()
        config["password"] = self.password_var.get()
        save_config(config)
        
        # Переинициализация голоса
        global engine
        try:
            engine = setup_jarvis_voice()
        except Exception as e:
            self.message_queue.put(("console", f"Ошибка переинициализации голоса: {e}"))
        
        # Обновление фонового прослушивания
        if config["always_listen"]:
            if not hasattr(self, 'background_listener') or not self.background_listener.running:
                self.background_listener = BackgroundListener(self.activate_from_hotword)
                self.background_listener.start()
        else:
            if hasattr(self, 'background_listener') and self.background_listener.running:
                self.background_listener.stop()
        
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
        
        ttk.Label(frame, text="Задайте вопрос:", font=("Arial", 12)).pack(pady=5)
        
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
        question = self.ai_question.get(1.0, tk.END).strip()
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
            "Напечатай [текст] - Напечатать текст",
            "Отправь сообщение [текст] - Отправить сообщение",
            "Максимизируй окно - Максимизировать текущее окно",
            "Минимизируй окно - Минимизировать текущее окно",
            "Переключи окно - Переключить на следующее окно",
            "Найди файл [имя] - Поиск файла на компьютере",
            "Запомни что [факт] - Запомнить информацию",
            "Спроси у ИИ [вопрос] - Задать вопрос искусственному интеллекту",
            "История команд - Показать историю команд",
            "Начать последовательность команд - Активировать режим последовательности",
            "Завершить последовательность команд - Завершить режим последовательности",
            "Отмени команду - Отменить последнюю команду в последовательности",
            "Что ты умеешь? - Список команд",
            "Стоп - Завернение работы"
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
        
        if response.startswith("exit||"):
            farewell = response.split("||")[1]
            play_deactivation_sound()
            self.message_queue.put(("speak", farewell))
            self.message_queue.put(("exit",))
            return
        
        self.message_queue.put(("console", response))
        self.message_queue.put(("speak", response))

# ===== Запуск приложения =====
if __name__ == "__main__":
    # Скрываем консоль для Windows
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.WinDLL('kernel32')
            user32 = ctypes.WinDLL('user32')
            SW_HIDE = 0
            hWnd = kernel32.GetConsoleWindow()
            if hWnd:
                user32.ShowWindow(hWnd, SW_HIDE)
        except:
            pass

    root = tk.Tk()
    app = JarvisGUI(root)
    root.mainloop()