import os
import sys
import json
import time
import requests
import subprocess
import asyncio  # 🎙️ 音声合成のために追加
import random
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

# Google API公式ライブラリ
try:
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False

# 🎙️ edge-ttsのインポート（Actions環境で動くようtry-except）
try:
    import edge_tts
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# ==========================================================
# ⚙️ 設定・ディレクトリ構成
# ==========================================================
jst = timezone(timedelta(hours=9))
current_date = datetime.now(jst).strftime("%Y-%m-%d")

TEMPLATE_DIR = "../../templates"
WORKSPACE_DIR = "workspace"      
TEMP_DIR = "temp_assets"

os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class JapaneseCookingWisdomEngine:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    def ask_gemini(self, prompt, system_instruction=""):
        if not self.api_key: return "⚠️ API KEY MISSING"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]}
        }
        url = f"{self.base_url}?key={self.api_key}"
        for delay in [1, 2, 4]:
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=60)
                if res.status_code == 200:
                    return res.json()["candidates"][0]["content"]["parts"][0]["text"]
                elif res.status_code == 429:
                    time.sleep(delay)
            except Exception:
                time.sleep(delay)
        return "⚠️ API ERROR"

    def generate_gradient_placeholder(self, width=1080, height=1920):
        img = Image.new("RGB", (width, height), (22, 22, 22)) 
        draw = ImageDraw.Draw(img)
        for y in range(height):
            r = int(22 + (28 - 22) * (y / height))
            g = int(22 + (38 - 22) * (y / height))
            b = int(22 + (45 - 22) * (y / height))
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        draw.rectangle([40, 40, width-40, height-40], outline=(197, 160, 89), width=2)
        path = os.path.join(TEMP_DIR, "placeholder_bg.png")
        img.save(path)
        return path

    def generate_subtitle_image(self, text, output_path, width=1080, height=1920):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font_paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "Arial"]
        font = None
        for path in font_paths:
            if os.path.exists(path):
                font = ImageFont.truetype(path, 54)
                break
        if not font: font = ImageFont.load_default()

        words = text.split()
        lines, current_line = [], []
        for word in words:
            current_line.append(word)
            if len(" ".join(current_line)) > 18:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line: lines.append(" ".join(current_line))
        
        box_padding, line_height = 24, 65
        max_line_width = max([len(line) * 28 for line in lines]) if lines else 300
        box_width = min(max_line_width + box_padding * 2, 980)
        box_height = (len(lines) * line_height) + box_padding * 2
        box_x1, box_y1 = (width - box_width) // 2, 1300
        box_x2, box_y2 = box_x1 + box_width, box_y1 + box_height

        draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=15, fill=(0, 0, 0, 195))
        for idx, line in enumerate(lines[:2]):
            text_x = (width - (len(line) * 28)) // 2
            text_y = box_y1 + box_padding + (idx * line_height)
            draw.text((text_x, text_y), line, fill=(255, 255, 255, 255), font=font)
        img.save(output_path, "PNG")

    # 🎙️ ナレーション用の高品質音声(.mp3)を生成する関数
    def create_narration(self, voice_texts, output_path):
        if not TTS_AVAILABLE:
            print("⚠️ edge-tts が利用できません。音声生成をスキップします。")
            return False
        
        # 5枚のスライド文を、自然な間（. ）を開けて1つのナレーション原稿にする
        full_script = " . ".join(voice_texts)
        
        # 海外で大人気の「en-US-BrianNeural(渋い男性)」または「en-US-EmmaNeural(知的な女性)」
        voice = "en-US-BrianNeural" 
        
        async def amain():
            # rate="+8%" でShortsに最適な少し早口テンポに調整
            communicate = edge_tts.Communicate(full_script, voice, rate="+8%")
            await communicate.save(output_path)
            
        asyncio.run(amain())
        return True

    def upload_to_youtube(self, file_path, title, description, tags):
        # (YouTubeアップロードロジックは既存のものをそのまま維持)
        pass

    def run_rendering_pipeline(self):
        print("🎬 [映像編集部 - Cooking Wisdom] コンテキスト安全ミックスを開始します。")

        # 💡 【ネック解消】動画(Video)ごとに「100%マッチするテーマの選択肢」を内包させる
        video_concepts = {
            1: {
                "code": "JCW-A-UmamiDashi-v1",
                "name": "The Science of Dashi & Umami",
                "themes": [
                    "How Kombu and Katsuobushi create a 7x flavor synergy molecularly.",
                    "The reason Michelin chefs never boil master dashi broth.",
                    "Why Japanese Umami reduces sugar and fat cravings automatically."
                ]
            },
            2: {
                "code": "JCW-D-RiceWash-v1",
                "name": "Perfect Rice: Hydration Mechanism",
                "themes": [
                    "Why the first 10 seconds of washing rice decides the final flavor.",
                    "The molecular chemistry of rice starches at exact water temperatures.",
                    "How Japanese traditional heavy iron pots maximize rice sweetness."
                ]
            }
            # 避難訓練(Kids版)ならここに「おはしもの精神」「集団規律の理由」等のテーマだけを配列する
        }

        day_of_year = datetime.now(jst).timetuple().tm_yday
        concept_idx = (day_of_year % len(video_concepts)) + 1
        chosen_video = video_concepts[concept_idx]

        # 🎯 その映像に「絶対に合うテーマ」の中から、さらに日替わりで1つ選出（ココで100%ミスマッチを防ぐ）
        theme_idx = day_of_year % len(chosen_video["themes"])
        chosen_theme_desc = chosen_video["themes"][theme_idx]

        template_filename = f"{chosen_video['code']}.mp4"
        input_template_path = os.path.join(TEMPLATE_DIR, template_filename)
        use_placeholder_bg = False

        if not os.path.exists(input_template_path):
            # (既存のグラデーション動画自給自足ロジック)
            bg_png = self.generate_gradient_placeholder()
            placeholder_mp4 = os.path.join(TEMP_DIR, "placeholder_bg_30s.mp4")
            ffmpeg_bg_cmd = ["ffmpeg", "-y", "-loop", "1", "-i", bg_png, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-c:v", "libx264", "-t", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", placeholder_mp4]
            subprocess.run(ffmpeg_bg_cmd, capture_output=True, check=True)
            input_template_path = placeholder_mp4
            use_placeholder_bg = True

        print(f"🎥 背景動画: {template_filename}")
        print(f"🧠 厳選テーマ: {chosen_theme_desc}")

        # 🤖 Geminiに「テロップ」と「ナレーション原稿」を同時にJSON要求
        prompt = f"""
Create 5 engaging slide subtitles AND 5 matching spoken narration scripts for a 30-second YouTube Shorts.
[TOPIC]: "{chosen_theme_desc}"
[TARGET AUDIENCE]: Western food geeks, science enthusiasts, and high-end home cooks.

⚠️ STRICT FORMAT RULES:
- Keep each "text" (subtitle) under 8 words.
- Keep each "voice" (narration) under 15 words (must be spoken within 6 seconds).
- Deliver strictly in JSON format with keys "slide_1_text", "slide_1_voice" ... up to "slide_5_voice".
"""
        raw_json = self.ask_gemini(prompt, "You are a Michelin-level YouTube Shorts executive producer.")
        
        try:
            cleaned_json = raw_json.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_json)
        except Exception:
            # 自己修復用のデフォルトデータ
            data = {f"slide_{i}_text": "Japanese Culinary Secret" for i in range(1, 6)}
            for i in range(1, 6): data[f"slide_{i}_voice"] = "Discover the ultimate hidden science behind traditional Japanese cooking."

        # 🎨 Pillowで透過テロップ画像生成
        sub_image_paths = []
        for i in range(1, 6):
            slide_text = data.get(f"slide_{i}_text", "Cooking Wisdom")
            img_path = os.path.join(TEMP_DIR, f"slide_{i}.png")
            self.generate_subtitle_image(slide_text, img_path)
            sub_image_paths.append(img_path)

        # 🎙️ ナレーション音声ファイルの生成
        voice_texts = [data.get(f"slide_{i}_voice", "") for i in range(1, 6)]
        output_voice_path = os.path.join(TEMP_DIR, "narration.mp3")
        self.create_narration(voice_texts, output_voice_path)

        output_video_path = os.path.join(WORKSPACE_DIR, f"{current_date}_completed_shorts.mp4")
        
        # ⚙️ FFmpegのフィルター複雑合成
        # [0:a]元の動画BGMの音量を「0.25倍」にダッキング(下げる)
        # [6:a]ナレーション音声を「1.5倍」にブーストして、amixで綺麗に融合
        filter_complex = (
            "[0:v][1:v]overlay=0:0:enable='between(t,0,6)'[v1];"
            "[v1][2:v]overlay=0:0:enable='between(t,6,12)'[v2];"
            "[v2][3:v]overlay=0:0:enable='between(t,12,18)'[v3];"
            "[v3][4:v]overlay=0:0:enable='between(t,18,24)'[v4];"
            "[v4][5:v]overlay=0:0:enable='between(t,24,30)'[v5];"
            "[0:a]volume=0.25[bg];"
            "[6:a]volume=1.5[voice];"
            "[bg][voice]amix=inputs=2:duration=first[a]"
        )

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", input_template_path,        # 0
            "-i", sub_image_paths[0],         # 1
            "-i", sub_image_paths[1],         # 2
            "-i", sub_image_paths[2],         # 3
            "-i", sub_image_paths[3],         # 4
            "-i", sub_image_paths[4],         # 5
            "-i", output_voice_path,           # 6 (ナレーション)
            "-filter_complex", filter_complex,
            "-map", "[v5]",
            "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "aac",  # 音声を混ぜるためcopyからaacに変更
            output_video_path
        ]

        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
            print(f"✅ 【ナレーション＆BGMミックス完了】 -> {output_video_path}")
            
            # 残骸の削除、YouTube投稿処理へ...
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ エラー: {e.stderr}")
            return False
