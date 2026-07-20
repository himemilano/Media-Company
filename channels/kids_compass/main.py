import os
import sys
import json
import time
import re
import requests
import subprocess
import asyncio
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

# 外部ライブラリのチェック
try:
    import edge_tts
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# 設定
jst = timezone(timedelta(hours=9))
current_date = datetime.now(jst).strftime("%Y-%m-%d")
TEMPLATE_DIR = "../../templates/kids_compass"
WORKSPACE_DIR = "workspace"
TEMP_DIR = "temp_assets"

os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class JapanKidsCompassEngine:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"

    def ask_gemini(self, prompt, system_instruction=""):
        if not self.api_key: return "⚠️ API KEY MISSING"
        headers = {"Content-Type": "application/json"}
        combined_prompt = f"[Role Instruction]\n{system_instruction}\n\n[Task]\n{prompt}" if system_instruction else prompt
        payload = {"contents": [{"parts": [{"text": combined_prompt}]}]}
        url = f"{self.base_url}?key={self.api_key}"
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=60)
            if res.status_code == 200:
                return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"Gemini Error: {e}")
        return "⚠️ API ERROR"

    def generate_subtitle_image(self, text, output_path, width=1080, height=1920):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font = ImageFont.truetype(font_path, 54) if os.path.exists(font_path) else ImageFont.load_default()
        
        words = text.split()
        lines, current_line = [], []
        for word in words:
            current_line.append(word)
            if len(" ".join(current_line)) > 16:
                lines.append(" ".join(current_line))
                current_line = []
        if current_line: lines.append(" ".join(current_line))
        lines = lines[:3]

        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])

        max_line_width = max(line_widths) if line_widths else 200
        box_width = min(max_line_width + 100, width - 100)
        box_height = (len(lines) * 80) + 70
        box_x1 = (width - box_width) // 2
        box_y1 = 1250
        
        draw.rounded_rectangle([box_x1, box_y1, box_x1+box_width, box_y1+box_height], radius=20, fill=(15, 23, 36, 220))
        current_y = box_y1 + 35
        for i, line in enumerate(lines):
            text_x = box_x1 + (box_width - line_widths[i]) // 2
            draw.text((text_x, current_y), line, fill=(255, 255, 255, 255), font=font)
            current_y += 80
        img.save(output_path, "PNG")

    def create_narration(self, voice_texts, output_path):
        if not TTS_AVAILABLE: return False
        async def amain():
            full_script = " . ".join(voice_texts)
            communicate = edge_tts.Communicate(full_script, "en-US-EmmaNeural", rate="-10%")
            await communicate.save(output_path)
        asyncio.run(amain())
        return True

    def run_rendering_pipeline(self):
        print("🎬 [Japan Kids Compass] 自動スキャンモード起動")
        
        template_files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".mp4")]
        if not template_files:
            print("❌ テンプレートが見つかりません。")
            return False

        day_of_year = datetime.now(jst).timetuple().tm_yday
        chosen_filename = template_files[day_of_year % len(template_files)]
        theme_name = os.path.splitext(chosen_filename)[0].replace("-", " ")
        
        input_template_path = os.path.join(TEMPLATE_DIR, chosen_filename)

        prompt = f"""
        Generate 5 engaging slide subtitles and narration scripts for a 30-second YouTube Short.
        The theme is: "{theme_name}".
        Create scripts that match this specific theme.
        Output JSON: slide_1_text...slide_5_voice.
        """
        raw_json = self.ask_gemini(prompt, "You are a YouTube expert. Output ONLY JSON.")
        
        try:
            json_match = re.search(r'\{.*\}', raw_json, re.DOTALL)
            data = json.loads(json_match.group(0)) if json_match else json.loads(raw_json)
        except Exception as e:
            print(f"JSON Error: {e}")
            return False

        sub_image_paths = []
        for i in range(1, 6):
            slide_text = data.get(f"slide_{i}_text", f"Insight {i}")
            img_path = os.path.join(TEMP_DIR, f"slide_{i}.png")
            self.generate_subtitle_image(slide_text, img_path)
            sub_image_paths.append(img_path)

        voice_texts = [data.get(f"slide_{i}_voice", "") for i in range(1, 6)]
        output_voice_path = os.path.join(TEMP_DIR, "narration.mp3")
        self.create_narration(voice_texts, output_voice_path)

        output_video_path = os.path.join(WORKSPACE_DIR, f"{current_date}_completed_kids_shorts.mp4")
        
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
            "ffmpeg", "-y", "-i", input_template_path,        
            "-i", sub_image_paths[0], "-i", sub_image_paths[1],         
            "-i", sub_image_paths[2], "-i", sub_image_paths[3],         
            "-i", sub_image_paths[4], "-i", output_voice_path,           
            "-filter_complex", filter_complex, "-map", "[v5]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", output_video_path
        ]

        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
            print(f"✅ 【Kids Compass 動画完成】 -> {output_video_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpegエラー: {e.stderr}")
            return False

if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY_MEDIA")
    engine = JapanKidsCompassEngine(api_key)
    success = engine.run_rendering_pipeline()
    if not success:
        sys.exit(1)
