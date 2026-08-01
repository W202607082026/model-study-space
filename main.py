import asyncio
import io
import json
import os
import re
from edge_tts import Communicate

# ===================== KIVY 导入 =====================
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.audio import SoundLoader
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.properties import StringProperty, ListProperty, NumericProperty, BooleanProperty

# ===================== 平台路径自适应 =====================
try:
    from android.storage import app_storage_path
    ANDROID_PLATFORM = True
    BASE_PATH = app_storage_path()
except ImportError:
    ANDROID_PLATFORM = False
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(BASE_PATH, "wordbook_data.json")
CORPUS_NAMES = [
    "初中_合并.json",
    "高中_合并.json",
    "四级_合并.json",
    "六级_合并.json",
    "考研_合并.json",
    "托福_合并.json",
    "SAT_合并.json"
]

# ===================== 自定义高亮文本控件（模拟Tk Text tag高亮） =====================
class HighlightTextDisplay(TextInput):
    highlight_target = StringProperty("")
    highlight_color_running = (1, 1, 0.3, 0.4)    # 黄色 朗读中
    highlight_color_stop = (0.3, 0.6, 1, 0.4)     # 蓝色 停止标记

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.readonly = True
        self.bind(text=self.refresh_highlight, highlight_target=self.refresh_highlight)

    def refresh_highlight(self, *args):
        self.canvas.after.clear()
        target = self.highlight_target.strip()
        if not target:
            return
        txt = self.text
        idx = txt.find(target)
        if idx == -1:
            return
        with self.canvas.after:
            if App.get_running_app().root.running_play:
                Color(*self.highlight_color_running)
            else:
                Color(*self.highlight_color_stop)
            rect = Rectangle()
            # 简易字符位置映射，手机端够用；如需精准可扩展文本布局计算
            line_height = self.line_height
            char_w = self.font_size * 0.58
            x0 = self.x + self.padding[0] + idx * char_w
            y0 = self.top - self.padding[1]
            rect.pos = (x0, y0 - line_height)
            rect.size = (len(target)*char_w, line_height)

# ===================== 主程序布局 =====================
class MainUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = 6
        self.padding = [8,8,8,8]

        # 播放状态机
        self.running_play = False
        self.global_audio_stop = False
        self.play_speed = 1.0
        self.current_corpus = []
        self.search_result_list = []
        self.now_highlight_word = ""
        self.wordbook = self.load_wordbook_data()

        # TTS音色
        self.voice_name = "zh-CN-YunyangNeural"
        self.build_ui()
        self.async_loop = asyncio.get_event_loop()

    def build_ui(self):
        # 顶部栏：题库选择、加载、搜索
        top_bar = BoxLayout(size_hint_y=0.09, spacing=4)
        self.spinner_corpus = Spinner(text="选择题库", values=CORPUS_NAMES)
        btn_load = Button(text="加载题库", size_hint_x=0.22)
        btn_load.bind(on_press=self.load_corpus_file)
        self.txt_search = TextInput(hint_text="输入单词搜索", size_hint_x=0.35)
        btn_search = Button(text="搜索", size_hint_x=0.15)
        btn_search.bind(on_press=self.do_search)
        top_bar.add_widget(self.spinner_corpus)
        top_bar.add_widget(btn_load)
        top_bar.add_widget(self.txt_search)
        top_bar.add_widget(btn_search)
        self.add_widget(top_bar)

        # 文本显示区域（核心高亮控件）
        self.display_area = HighlightTextDisplay(font_size=16)
        self.add_widget(self.display_area)

        # 播放控制栏
        ctrl_bar = BoxLayout(size_hint_y=0.11, spacing=4)
        self.btn_play = Button(text="开始朗读")
        self.btn_play.bind(on_press=self.toggle_play)
        self.btn_stop = Button(text="立即停止")
        self.btn_stop.bind(on_press=self.stop_all_audio)
        lbl_speed = Label(text="速度", size_hint_x=0.12)
        self.slider_speed = Slider(min=0.7, max=1.5, value=1.0, size_hint_x=0.4)
        self.slider_speed.bind(value=self.on_speed_changed)
        ctrl_bar.add_widget(self.btn_play)
        ctrl_bar.add_widget(self.btn_stop)
        ctrl_bar.add_widget(lbl_speed)
        ctrl_bar.add_widget(self.slider_speed)
        self.add_widget(ctrl_bar)

        # 底部功能栏
        bot_bar = BoxLayout(size_hint_y=0.09, spacing=4)
        btn_wordbook = Button(text="打开生词本")
        btn_wordbook.bind(on_press=self.open_wordbook_popup)
        btn_add_word = Button(text="添加当前词到生词本")
        btn_add_word.bind(on_press=self.add_current_to_wordbook)
        bot_bar.add_widget(btn_wordbook)
        bot_bar.add_widget(btn_add_word)
        self.add_widget(bot_bar)

    # ===================== 文件持久化 生词本 =====================
    def load_wordbook_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return []

    def save_wordbook_data(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.wordbook, f, ensure_ascii=False, indent=2)

    def add_current_to_wordbook(self, inst):
        w = self.now_highlight_word.strip()
        if w and w not in self.wordbook:
            self.wordbook.append(w)
            self.save_wordbook_data()
            self.show_popup_msg(f"已添加：{w}")

    # ===================== 题库加载 =====================
    def load_corpus_file(self, inst):
        sel_name = self.spinner_corpus.text
        path = os.path.join(BASE_PATH, sel_name)
        if not os.path.exists(path):
            self.show_popup_msg("文件不存在，请确认题库json放在程序目录！")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.current_corpus = json.load(f)
            self.show_popup_msg(f"{sel_name} 加载成功，共{len(self.current_corpus)}条")
        except Exception as e:
            self.show_popup_msg(f"加载失败：{str(e)}")

    # ===================== 单词搜索 =====================
    def do_search(self, inst):
        kw = self.txt_search.text.strip().lower()
        if not kw:
            return
        res = []
        for item in self.current_corpus:
            if kw in item.get("word", "").lower() or kw in item.get("sentence", "").lower():
                res.append(item)
        self.search_result_list = res
        txt_out = "\n".join([f'{x["word"]} | {x["sentence"]}' for x in res[:60]])
        self.set_display_text(txt_out)

    # ===================== 播放调速 =====================
    def on_speed_changed(self, inst, val):
        self.play_speed = round(val,2)

    # ===================== UI线程安全封装 =====================
    @mainthread
    def set_display_text(self, content):
        self.display_area.text = content

    @mainthread
    def set_highlight_word(self, word):
        self.now_highlight_word = word
        self.display_area.highlight_target = word

    @mainthread
    def show_popup_msg(self, msg):
        popup = Popup(title="提示", content=Label(text=msg), size_hint=(0.7,0.3))
        popup.open()

    # ===================== TTS音频核心函数（替换pygame） =====================
    async def speak_and_wait(self, text):
        if self.global_audio_stop:
            return False
        retry = 2
        rate = int((self.play_speed - 1.0)*100)
        for _ in range(retry):
            try:
                comm = Communicate(text, voice=self.voice_name, rate=f"{rate:+d}%")
                buf = io.BytesIO()
                async for seg in comm.stream():
                    if seg["type"] == "audio":
                        buf.write(seg["data"])
                    if self.global_audio_stop:
                        return False
                buf.seek(0)
                sound = SoundLoader.load(buf)
                if not sound:
                    await asyncio.sleep(0.3)
                    continue
                sound.play()
                while sound.state == "play" and not self.global_audio_stop:
                    await asyncio.sleep(0.1)
                sound.unload()
                return True
            except Exception as e:
                print("TTS错误:",e)
                await asyncio.sleep(0.4)
        return False

    # ===================== 播放主循环 =====================
    async def play_main_loop(self):
        self.running_play = True
        self.global_audio_stop = False
        self.btn_play.text = "暂停朗读"
        for item in self.search_result_list:
            if self.global_audio_stop:
                break
            word = item["word"]
            sentence = item["sentence"]
            self.set_highlight_word(word)
            await self.speak_and_wait(word)
            await asyncio.sleep(0.3)
            await self.speak_and_wait(sentence)
        self.running_play = False
        self.btn_play.text = "开始朗读"

    def toggle_play(self, inst):
        if self.running_play:
            self.stop_all_audio(None)
        else:
            asyncio.create_task(self.play_main_loop())

    def stop_all_audio(self, inst):
        self.global_audio_stop = True
        self.running_play = False
        self.btn_play.text = "开始朗读"

    # ===================== 生词本弹窗 =====================
    def open_wordbook_popup(self, inst):
        box = BoxLayout(orientation="vertical", spacing=4, padding=8)
        txt = TextInput(text="\n".join(self.wordbook), readonly=True)
        btn_close = Button(text="关闭", size_hint_y=0.15)
        popup = Popup(title="生词本", content=box, size_hint=(0.85,0.85))
        btn_close.bind(on_press=popup.dismiss)
        box.add_widget(txt)
        box.add_widget(btn_close)
        popup.open()

class WordTrainApp(App):
    def build(self):
        return MainUI()

if __name__ == "__main__":
    WordTrainApp().run()
