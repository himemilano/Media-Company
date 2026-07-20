import os
import sys
import json
import time
import requests
import subprocess
import asyncio
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

# AIナレーション生成ライブラリ
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

class JapanKidsCompassEngine:
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
        # 🎨 教育・文化系に馴染む、落ち着いた日本の伝統色（深みのある藍〜茜色）の和風モダングラデーション
        img = Image.new("RGB", (width, height), (26, 36, 43)) 
        draw = ImageDraw.Draw(img)
        for y in range(height):
            r = int(26 + (50 - 26) * (y / height))
            g = int(36 + (40 - 36) * (y / height))
            b = int(43 + (44 - 43) * (y / height))
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        # 額縁フレーム枠（日本の伝統建築をイメージしたゴールドベージュ）
        draw.rectangle([40, 40, width-40, height-40], outline=(220, 195, 145), width=2)
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

        draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=15, fill=(15, 23, 36, 205))
        for idx, line in enumerate(lines[:2]):
            text_x = (width - (len(line) * 28)) // 2
            text_y = box_y1 + box_padding + (idx * line_height)
            draw.text((text_x, text_y), line, fill=(255, 255, 255, 255), font=font)
        img.save(output_path, "PNG")

    def create_narration(self, voice_texts, output_path):
        if not TTS_AVAILABLE:
            print("⚠️ edge-tts が利用できません。音声生成をスキップします。")
            return False
        
        full_script = " . ".join(voice_texts)
        # 🎙️ 教育・カルチャー系に最適な、優しく知的な女性音声を採用
        voice = "en-US-EmmaNeural" 
        
        async def amain():
            communicate = edge_tts.Communicate(full_script, voice, rate="+6%")
            await communicate.save(output_path)
            
        asyncio.run(amain())
        return True

    def run_rendering_pipeline(self):
        print("🎬 [映像編集部 - Japan Kids Compass] パイプラインを開始します。")

        # 🎯 【コンテキスト安全構造】動画素材ごとに「100%整合するテーマプール」をカプセル化
        video_concepts = {
            1: {
                "code": "JKC-A-SchoolLife-v1",
                "name": "Japanese School Independence",
                "themes": [
                    "Why Japanese children clean their own classrooms every day.",
                    "How the 'Ohashimo' rule keeps school kids safe during emergencies.",
                    "The secret behind Japan's independent primary school commuters."
                ]
            },
            2: {
                "code": "JKC-B-Mindset-v1",
                "name": "Japanese Parenting & Discipline",
                "themes": [
                    "The true meaning of 'Shitsuke' in Japanese positive parenting.",
                    "How Japanese parents build deep emotional bonds through early childhood patience.",
                    "Why public tantrums are rare: The social harmony mindset taught to infants."
                ]
            },
            3: {
                "code": "JKC-C-Activities-v1",
                "name": "Educational Crafts & Dexterity",
                "themes": [
                    "How Origami masterfully trains spatial awareness and fine motor skills in kids.",
                    "The cognitive science behind traditional Japanese finger-play games.",
                    "Why preschool scissor and craft practice is deeply prioritized in Japan."
                ]
            }
        }

        day_of_year = datetime.now(jst).timetuple().tm_yday
        concept_idx = (day_of_year % len(video_concepts)) + 1
        chosen_video = video_concepts[concept_idx]

        theme_idx = day_of_year % len(chosen_video["themes"])
        chosen_theme_desc = chosen_video["themes"][theme_idx]

        template_filename = f"{chosen_video['code']}.mp4"
        input_template_path = os.path.join(TEMPLATE_DIR, template_filename)

        if not os.path.exists(input_template_path):
            bg_png = self.generate_gradient_placeholder()
            placeholder_mp4 = os.path.join(TEMP_DIR, "placeholder_bg_30s.mp4")
            ffmpeg_bg_cmd = ["ffmpeg", "-y", "-loop", "1", "-i", bg_png, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-c:v", "libx264", "-t", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", placeholder_mp4]
            subprocess.run(ffmpeg_bg_cmd, capture_output=True, check=True)
            input_template_path = placeholder_mp4

        print(f"🎥 背景動画: {template_filename}")
        print(f"🧠 厳選テーマ: {chosen_theme_desc}")

        # Geminiへの構造化データ要求
        prompt = f"""
Create 5 engaging slide subtitles AND 5 matching spoken narration scripts for a 30-second YouTube Shorts.
[TOPIC]: "{chosen_theme_desc}"
[TARGET AUDIENCE]: Global parents, educators, and fans of Japanese culture and child development.

⚠️ STRICT FORMAT RULES:
- Keep each "text" (subtitle) under 8 words.
- Keep each "voice" (narration) under 15 words (must be spoken within 6 seconds).
- Deliver strictly in JSON format with keys "slide_1_text", "slide_1_voice" ... up to "slide_5_voice".
"""
        raw_json = self.ask_gemini(prompt, "You are an expert executive producer for global educational YouTube content.")
        
        try:
            cleaned_json = raw_json.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_json)
        except Exception:
            data = {f"slide_{i}_text": "Japan Kids Compass" for i in range(1, 6)}
            for i in range(1, 6): data[f"slide_{i}_voice"] = "Discover the unique cultural wisdom and parenting insights from Japan."

        # 字幕画像の生成
        sub_image_paths = []
        for i in range(1, 6):
            slide_text = data.get(f"slide_{i}_text", "Kids Compass")
            img_path = os.path.join(TEMP_DIR, f"slide_{i}.png")
            self.generate_subtitle_image(slide_text, img_path)
            sub_image_paths.append(img_path)

        # ナレーション音声の生成
        voice_texts = [data.get(f"slide_{i}_voice", "") for i in range(1, 6)]
        output_voice_path = os.path.join(TEMP_DIR, "narration.mp3")
        self.create_narration(voice_texts, output_voice_path)

        output_video_path = os.path.join(WORKSPACE_DIR, f"{current_date}_completed_kids_shorts.mp4")
        
        # 音声の自動ダッキング＆ミックスフィルター
        filter_complex = (
            "[0:v][1:v]overlay=0:0:enable='between(t,0,6)'[v1];"
            "[v1][2:v]overlay=0:0:enable='between(t,6,12)'[v2];"
            "[v2][3:v]overlay=0:0:enable='between(t,12,18)'[v3];"
            "[v3][4:v]overlay=0:0:enable='between(t,18,24)'[v4];"
            "[v4][5:v]overlay=0:0:enable='between(t,24,30)'[v5];"
            "[0:a]volume=0.20[bg];"  # ナレーションを引き立てるためBGMを20%に調整
            "[6:a]volume=1.6[voice];" # ナレーションの明瞭度を上げるため1.6倍にブースト
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
            "-i", output_voice_path,           # 6
            "-filter_complex", filter_complex,
            "-map", "[v5]",
            "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "aac",
            output_video_path
        ]

        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
            print(f"✅ 【Kids Compass 動画合成完了】 -> {output_video_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpegエラー: {e.stderr}")
            return False

if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY_MEDIA")
    engine = JapanKidsCompassEngine(api_key)
    engine.run_rendering_pipeline()
