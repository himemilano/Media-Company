 import os
import sys
import json
import time
import requests
import subprocess
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

# Google API公式ライブラリの読み込み
try:
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False

# ==========================================================
# ⚙️ 1. 設定・ディレクトリ構成
# ==========================================================
jst = timezone(timedelta(hours=9))
current_date = datetime.now(jst).strftime("%Y-%m-%d")

TEMPLATE_DIR = "../../templates" # ルートの共通テンプレートフォルダを参照
WORKSPACE_DIR = "workspace"      # ローカルフォルダ
TEMP_DIR = "temp_assets"

os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class JapaneseCookingWisdomEngine:
    """
    【完全無人・自己修復・直撃アップロード型字幕合成システム】
    """
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    def ask_gemini(self, prompt, system_instruction=""):
        if not self.api_key:
            return "⚠️ API KEY IS MISSING"
        
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
                    print(f"⚠️ API制限 (429)。{delay}秒待機して再試行します...")
                    time.sleep(delay)
            except Exception as e:
                print(f"⚠️ 接続エラー: {e}")
                time.sleep(delay)
        return "⚠️ APIエラーのため、ローカル復旧データから補完します。"

    def generate_gradient_placeholder(self, width=1080, height=1920):
        """🎨 テンプレート未作成時に、超高級感のある和風モダングラデーション背景を自動描写"""
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

        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "Arial"
        ]
        font = None
        for path in font_paths:
            if os.path.exists(path):
                font = ImageFont.truetype(path, 54)
                break
        if not font:
            font = ImageFont.load_default()

        words = text.split()
        lines = []
        current_line = []
        for word in words:
            current_line.append(word)
            if len(" ".join(current_line)) > 18:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
            
        final_text = "\n".join(lines[:2])

        box_padding = 24
        line_height = 65
        
        max_line_width = max([len(line) * 28 for line in lines]) if lines else 300
        box_width = min(max_line_width + box_padding * 2, 980)
        box_height = (len(lines) * line_height) + box_padding * 2
        
        box_x1 = (width - box_width) // 2
        box_y1 = 1300
        box_x2 = box_x1 + box_width
        box_y2 = box_y1 + box_height

        draw.rounded_rectangle(
            [box_x1, box_y1, box_x2, box_y2],
            radius=15,
            fill=(0, 0, 0, 195)
        )

        for idx, line in enumerate(lines[:2]):
            text_w = len(line) * 28
            text_x = (width - text_w) // 2
            text_y = box_y1 + box_padding + (idx * line_height)
            draw.text((text_x, text_y), line, fill=(255, 255, 255, 255), font=font)

        img.save(output_path, "PNG")

    def upload_to_youtube(self, file_path, title, description, tags):
        if not YOUTUBE_API_AVAILABLE:
            print("⚠️ [YouTube API] 必要なパッケージがインポートされていません。アップロードをスキップします。")
            return False

        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        # 🔑 JCW専用の合鍵を引き当てます！
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            print("💡 [YouTube API] API認証トークンがSecretsに設定されていません。ローカルに完成動画を保存して終了します。")
            return False

        print("🚀 [YouTube API] JCWチャンネルへの自動アップロードプロセスを開始します...")
        try:
            creds = google.oauth2.credentials.Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret
            )
            youtube = build("youtube", "v3", credentials=creds)

            seo_title = f"{title[:80]} #Shorts #JapaneseCookingWisdom"

            body = {
                "snippet": {
                    "title": seo_title,
                    "description": description,
                    "tags": tags + ["Shorts", "JapaneseCookingWisdom", "Washoku"],
                    "categoryId": "27" 
                },
                "status": {
                    "privacyStatus": "public", 
                    "selfDeclaredMadeForKids": False
                }
            }

            media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"   [アップロード中] {int(status.progress() * 100)}% 完了...")

            print(f"🎉 【YouTube投稿成功！】動画ID: {response.get('id')}")
            print(f"🔗 視聴リンク: https://youtu.be/{response.get('id')}")
            return True

        except Exception as e:
            print(f"❌ YouTubeアップロード中に重大なエラーが発生しました: {e}")
            return False

    def run_rendering_pipeline(self):
        print("🎬 [映像編集部 - Cooking Wisdom] 自律レンダリングプロセスを開始します。")

        concepts = {
            1: {"code": "JCW-A-UmamiDashi-v1", "name": "The Science of Dashi & Umami", "desc": "伝統和食の出汁（昆布と鰹節）の旨味シナジー効果。グルタミン酸とイノシン酸が結合して旨味が最大化する科学的仕組み。"},
            2: {"code": "JCW-B-CryoMeat-v1", "name": "Cryo-Freezing Science: Meat Preservation", "desc": "先進冷凍技術。細胞を壊さずドリップを防ぎ、解凍後も抜群のジューシーさを保つための、最大氷結晶生成帯を最速で突破する温度管理。"},
            3: {"code": "JCW-C-OnionCaramel-v1", "name": "The Chemistry of Caramelized Onions", "desc": "日本のエリート学術フード研究会によるカレー。タマネギの甘味とコクを極限まで引き出すメイラード反応の科学。"},
            4: {"code": "JCW-D-RiceWash-v1", "name": "Perfect Rice: The Hydration Mechanism", "desc": "伝統的なお米研ぎと浸水の科学。最初の10秒間の洗米でヌカの吸水をシャットアウトし、デンプンのアルファ化を促すための最適な浸水温度。"},
            5: {"code": "JCW-E-CryoFish-v1", "name": "Preservation Secrets: Drip-Free Seafood", "desc": "日本の先進食品保存。浸透圧を利用した塩水処理により、魚の解凍時にドリップを100%防ぎ、モチモチの食感を保つ科学。"},
            6: {"code": "JCW-F-SpiceSynergy-v1", "name": "Molecular Spice Synergy in Curry", "desc": "学術的スパイスカレー研究。スパイスの揮発性香気成分を最大化し、香りのレイヤーを構築するための、秒単位でのスパイス投入プロセス。"},
            7: {"code": "JCW-G-KnifePhysics-v1", "name": "The Physics of the Perfect Knife Cut", "desc": "包丁と切断の物理。ミクロのノコギリ刃を整えることで、食材の細胞壁を破壊せずに切断し、雑味や酸化を徹底的に防ぐプロの技術。"},
            8: {"code": "JCW-H-CryoVeg-v1", "name": "Blanching: Capturing Vegetable Nutrients", "desc": "先端冷凍科学。野菜の色味、ビタミン、シャキシャキの食感を半永久的に保つための、秒単位のブランチング（不活性化熱処理）と冷水冷却法。"},
            9: {"code": "JCW-I-AcidityUmami-v1", "name": "The Umami-Acid Balance Formula", "desc": "学術的スパイス研究。スパイスの尖りを消し去り、脳が美味しさを強く感じるアミノ酸と穏やかな酸味（バルサミコや果汁）の黄金比率。"},
            10: {"code": "JCW-J-TempuraDehyd-v1", "name": "The Physics of Perfect Tempura", "desc": "和食の脱水工学。180度($180^\circ\text{C}$)の油の中で、小麦粉の衣を水分の通過フィルターとして用い、食材自体を内部から蒸気で蒸し上げる調理物理。"}
        }

        day_of_year = datetime.now(jst).timetuple().tm_yday
        concept_idx = (day_of_year % 10) + 1
        chosen = concepts[concept_idx]

        template_filename = f"{chosen['code']}.mp4"
        input_template_path = os.path.join(TEMPLATE_DIR, template_filename)

        use_placeholder_bg = False

        if not os.path.exists(input_template_path):
            print(f"💡 [自律防衛発動] テンプレート `{input_template_path}` はまだ作成されていません。")
            print("💡 対策：Pythonグラフィックスを駆動し、超高級感のある和風モダンのグラデーション背景を自動生成して動画化します。")
            
            bg_png = self.generate_gradient_placeholder()
            placeholder_mp4 = os.path.join(TEMP_DIR, "placeholder_bg_30s.mp4")
            
            ffmpeg_bg_cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", bg_png,
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", 
                "-c:v", "libx264", "-t", "30", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest",
                placeholder_mp4
            ]
            try:
                subprocess.run(ffmpeg_bg_cmd, capture_output=True, check=True)
                input_template_path = placeholder_mp4
                use_placeholder_bg = True
                print("✅ 30秒の高級和風モダン背景動画をローカルで自給自足ビルドしました！")
            except Exception as e:
                print(f"❌ 背景自給自足ビルドに失敗したため、本日は処理をスルーします: {e}")
                return False

        print("🤖 本物の調理科学ノウハウに合致する5枚のスライドテロップをGeminiに特注中...")
        prompt = f"""
Create 5 highly engaging, short, punchy slide subtitles for a 30-second YouTube Shorts video.
The background topic being shown is exactly about: "{chosen['desc']}".
The target audience is Western food geeks, high-end home cooks, and science enthusiasts.

⚠️ STRICT ANONYMIZATION RULE:
- Do NOT mention any specific corporate names (e.g., Nichirei), real university names (e.g., Kyoto University), or real book titles/authors.
- Instead, refer to them anonymously as 'Elite Japanese Preservation Scientists', 'Top Culinary Scholars in Kyoto', or 'Michelin-starred Japanese Master Chefs'.
- Subtitles MUST perfectly match the theme "{chosen['name']}".
- Keep each slide text under 10 words (very short, highly professional).
- Deliver strictly in JSON format with keys "slide_1" to "slide_5".
"""
        raw_json = self.ask_gemini(prompt, "You are an elite food science YouTube producer.")
        
        try:
            cleaned_json = raw_json.replace("```json", "").replace("```", "").strip()
            subtitles_data = json.loads(cleaned_json)
        except Exception as e:
            print(f"⚠️ JSONパースに失敗したため、デフォルトの安全な匿名字幕を自動ビルドします: {e}")
            subtitles_data = {
                "slide_1": f"Discover Japan's Legendary {chosen['name']}",
                "slide_2": "Culinary science meets centuries of tradition.",
                "slide_3": "The molecular balance changes everything.",
                "slide_4": "Apply this simple formula in your kitchen.",
                "slide_5": "Want to cook smarter? Subscribe for more secrets!"
            }

        print("🎨 Pillowグラフィックエンジンを駆動。透過字幕カードを自動作成中...")
        sub_image_paths = []
        for i in range(1, 6):
            text_key = f"slide_{i}"
            slide_text = subtitles_data.get(text_key, "Molecular Food Chemistry")
            img_path = os.path.join(TEMP_DIR, f"slide_{i}.png")
            
            self.generate_subtitle_image(slide_text, img_path)
            sub_image_paths.append(img_path)

        output_video_path = os.path.join(WORKSPACE_DIR, f"{current_date}_completed_shorts.mp4")
        print(f"⚙️ FFmpeg動画合成エンジンを召喚。ミリ単位のタイムオーバーレイを実行中...")
        
        filter_complex = (
            "[0:v][1:v]overlay=0:0:enable='between(t,0,6)'[v1];"
            "[v1][2:v]overlay=0:0:enable='between(t,6,12)'[v2];"
            "[v2][3:v]overlay=0:0:enable='between(t,12,18)'[v3];"
            "[v3][4:v]overlay=0:0:enable='between(t,18,24)'[v4];"
            "[v4][5:v]overlay=0:0:enable='between(t,24,30)'[v5]"
        )

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", input_template_path,             
            "-i", sub_image_paths[0],               
            "-i", sub_image_paths[1],               
            "-i", sub_image_paths[2],               
            "-i", sub_image_paths[3],               
            "-i", sub_image_paths[4],               
            "-filter_complex", filter_complex,
            "-map", "[v5]",                        
            "-map", "0:a",                         
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-c:a", "copy" if not use_placeholder_bg else "aac", 
            output_video_path
        ]

        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
            print(f"✅ 【完全自走レンダリング完了】お宝調理科学Shorts動画（MP4）が100%完成しました！")
            
            for path in sub_image_paths:
                if os.path.exists(path):
                    os.remove(path)
            if use_placeholder_bg:
                bg_png_path = os.path.join(TEMP_DIR, "placeholder_bg.png")
                if os.path.exists(bg_png_path): os.remove(bg_png_path)
                if os.path.exists(input_template_path): os.remove(input_template_path)
                    
            seo_prompt = f"Create a viral YouTube Shorts Title and Description for our video: '{chosen['name']}' using subtitles: {subtitles_data}. Strictly keep all real brand, university, or author names 100% anonymous."
            seo_info = self.ask_gemini(seo_prompt, "You are a professional YouTube growth hacker.")
            
            self.upload_to_youtube(
                file_path=output_video_path,
                title=f"{chosen['name']} 🇯🇵",
                description=seo_info,
                tags=["Japan", "JapaneseFood", "FoodScience", "CulinaryArt", "MichelinSecrets"]
            )
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpegレンダリング中にエラーが発生しました: {e.stderr}")
            return False

def main():
    # 🔑 会長が定義された「メディア統一キー」で完璧に起動！
    api_key = os.getenv("GEMINI_API_KEY_MEDIA")
    
    if not api_key:
        print("❌ GEMINI_API_KEY_MEDIA がセットされていません。")
        sys.exit(1)

    engine = JapaneseCookingWisdomEngine(api_key=api_key)
    engine.run_rendering_pipeline()

if __name__ == "__main__":
    main()
