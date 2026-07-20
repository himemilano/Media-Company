import os
import sys
import json
import time
import re
import requests
import subprocess
import asyncio
import random
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

try:
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False

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

TEMPLATE_DIR = "../../templates/cooking_wisdom"  
WORKSPACE_DIR = "workspace"      
TEMP_DIR = "temp_assets"

os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class CookingWisdomEngine:
    def __init__(self, api_key):
        self.api_key = api_key
        # ⭕ 正式版 v1 ＆ 最新の gemini-2.5-flash に固定完了
        self.base_url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"

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
                else:
                    print(f"⚠️ Gemini API Status Code: {res.status_code}")
                    print(f"⚠️ Gemini Error Response: {res.text}")
                    time.sleep(delay)
            except Exception as e:
                print(f"⚠️ Gemini Connection Error: {e}")
                time.sleep(delay)
        return "⚠️ API ERROR"

    def generate_cooking_gradient_placeholder(self, width=1080, height=1920):
        # 🍳 料理用に合わせた、温かみのあるマホガニー・カフェ系グラデーション
        img = Image.new("RGB", (width, height), (54, 31, 20)) 
        draw = ImageDraw.Draw(img)
        for y in range(height):
            r = int(54 + (92 - 54) * (y / height))
            g = int(31 + (53 - 31) * (y / height))
            b = int(20 + (32 - 20) * (y / height))
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        draw.rectangle([40, 40, width-40, height-40], outline=(235, 180, 110), width=2)
        path = os.path.join(TEMP_DIR, "cooking_placeholder_bg.png")
        img.save(path)
        return path

    def generate_subtitle_image(self, text, output_path, width=1080, height=1920):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font_paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "Arial"]
        font = None
        for path in font_paths:
            if os.path.exists(path):
                font = ImageFont.truetype(path, 52)
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
        max_line_width = max([len(line) * 26 for line in lines]) if lines else 300
        box_width = min(max_line_width + box_padding * 2, 980)
        box_height = (len(lines) * line_height) + box_padding * 2
        box_x1, box_y1 = (width - box_width) // 2, 1300
        box_x2, box_y2 = box_x1 + box_width, box_y1 + box_height

        # 料理に合うダークトーンのブラウン座布団
        draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=15, fill=(28, 18, 14, 220))
        for idx, line in enumerate(lines[:2]):
            text_x = (width - (len(line) * 26)) // 2
            text_y = box_y1 + box_padding + (idx * line_height)
            draw.text((text_x, text_y), line, fill=(255, 248, 240), font=font)
        img.save(output_path, "PNG")

    def create_narration(self, voice_texts, output_path):
        if not TTS_AVAILABLE:
            print("⚠️ edge-tts が利用できません。")
            return False
        full_script = " . ".join(voice_texts)
        voice = "en-US-JennyNeural" # 🍳 料理に合う親しみやすい女性ナレーション
        async def amain():
            communicate = edge_tts.Communicate(full_script, voice, rate="+3%")
            await communicate.save(output_path)
        asyncio.run(amain())
        return True

    def run_rendering_pipeline(self):
        print("🎬 [Cooking Wisdom] レンダーパイプライン始動")

        # 🍳 テンプレートがなくても毎日違う料理の雑学が生成される仕組み
        cooking_concepts = {
            1: {"filename": "JCW-A-Umami-v1.mp4", "theme": "The hidden power of Umami in traditional Japanese cuisine."},
            2: {"filename": "JCW-B-Rice-v1.mp4", "theme": "The ultimate secret to perfectly washing and cooking sushi rice."},
            3: {"filename": "JCW-C-Dashi-v1.mp4", "theme": "How Japanese Dashi creates deep flavor in just 10 minutes."},
            4: {"filename": "JCW-D-Miso-v1.mp4", "theme": "The incredible health benefits of eating Miso soup every day."},
            5: {"filename": "JCW-E-Knives-v1.mp4", "theme": "Why Japanese chef knives are trusted by professionals worldwide."},
            6: {"filename": "JCW-F-Mottainai-v1.mp4", "theme": "The beautiful philosophy of 'Mottainai' in zero-waste Japanese cooking."},
            7: {"filename": "JCW-G-Tempura-v1.mp4", "theme": "Science secrets to making perfectly crispy Japanese Tempura."},
            8: {"filename": "JCW-H-Breakfast-v1.mp4", "theme": "Inside a traditional Japanese breakfast: Balance and longevity."},
            9: {"filename": "JCW-J-GreenTea-v1.mp4", "theme": "The art of pairing authentic green tea with Japanese sweets."}
        }

        day_of_year = datetime.now(jst).timetuple().tm_yday
        concept_idx = (day_of_year % len(cooking_concepts)) + 1
        chosen = cooking_concepts[concept_idx]

        input_template_path = os.path.join(TEMPLATE_DIR, chosen["filename"])

        if not os.path.exists(input_template_path):
            print(f"ℹ️ 料理テンプレートがないため、専用の特製グラデーション背景を自動生成します。")
            bg_png = self.generate_cooking_gradient_placeholder()
            placeholder_mp4 = os.path.join(TEMP_DIR, "cooking_placeholder_bg_30s.mp4")
            # 音声なしの動画テンプレートにダミー無音を追加
            ffmpeg_bg_cmd = ["ffmpeg", "-y", "-loop", "1", "-i", bg_png, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-c:v", "libx264", "-t", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", placeholder_mp4]
            subprocess.run(ffmpeg_bg_cmd, capture_output=True, check=True)
            input_template_path = placeholder_mp4
        else:
            print(f"🎯 本物の料理動画テンプレートを検出: {chosen['filename']}")

        prompt = f"""
Create 5 engaging short subtitles AND 5 matching spoken narration scripts for a 30-second YouTube Shorts about cooking.
[TOPIC]: "{chosen['theme']}"
[RULES]: 
- Subtitles under 8 words. 
- Narration under 15 words. 
- Deliver strictly in JSON format with keys "slide_1_text", "slide_1_voice" ... up to "slide_5_voice".
"""
        raw_json = self.ask_gemini(prompt, "You are a professional culinary YouTube Shorts scriptwriter. Output pure JSON only.")
        
        if "⚠️" in raw_json:
            print(f"❌ Gemini APIが正常なレスポンスを返さなかったため、処理を中断します。")
            return False

        try:
            json_match = re.search(r'\{.*\}', raw_json, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = json.loads(raw_json)
        except Exception as e:
            print(f"❌ JSONパース致命的エラー: {e}")
            return False

        sub_image_paths = []
        for i in range(1, 6):
            slide_text = data.get(f"slide_{i}_text", f"Tip {i}")
            img_path = os.path.join(TEMP_DIR, f"slide_{i}.png")
            self.generate_subtitle_image(slide_text, img_path)
            sub_image_paths.append(img_path)

        voice_texts = [data.get(f"slide_{i}_voice", "") for i in range(1, 6)]
        output_voice_path = os.path.join(TEMP_DIR, "narration.mp3")
        self.create_narration(voice_texts, output_voice_path)

        output_video_path = os.path.join(WORKSPACE_DIR, f"{current_date}_completed_cooking_shorts.mp4")
        
        filter_complex = (
            "[0:v][1:v]overlay=0:0:enable='between(t,0,6)'[v1];"
            "[v1][2:v]overlay=0:0:enable='between(t,6,12)'[v2];"
            "[v2][3:v]overlay=0:0:enable='between(t,12,18)'[v3];"
            "[v3][4:v]overlay=0:0:enable='between(t,18,24)'[v4];"
            "[v4][5:v]overlay=0:0:enable='between(t,24,30)'[v5];"
            "[0:a]volume=0.20[bg];"  
            "[6:a]volume=1.6[voice];" 
            "[bg][voice]amix=inputs=2:duration=first[a]"
        )

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", input_template_path,        
            "-i", sub_image_paths[0],         
            "-i", sub_image_paths[1],         
            "-i", sub_image_paths[2],         
            "-i", sub_image_paths[3],         
            "-i", sub_image_paths[4],         
            "-i", output_voice_path,           
            "-filter_complex", filter_complex,
            "-map", "[v5]",
            "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "aac",
            output_video_path
        ]

        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
            print(f"✅ 【Cooking Wisdom 動画完成】 -> {output_video_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpegエラー: {e.stderr}")
            return False

if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY_MEDIA")
    engine = CookingWisdomEngine(api_key)
    success = engine.run_rendering_pipeline()
    if not success:
        print("❌ パイプラインが失敗したため、プロセスを異常終了させます。")
        sys.exit(1)
