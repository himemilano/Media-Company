# ... (既存のインポートなどはそのまま維持してください)

    def run_rendering_pipeline(self):
        print("🎬 [Japan Kids Compass] 自動スキャンモード起動")
        
        # 💡 フォルダ内を自動スキャンしてテンプレートを取得
        template_files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".mp4")]
        
        if not template_files:
            print("❌ テンプレートが見つかりません。")
            return False

        # 📅 日付で動画を1つ決定
        day_of_year = datetime.now(jst).timetuple().tm_yday
        chosen_filename = template_files[day_of_year % len(template_files)]
        # ファイル名からテーマを抽出（拡張子を除去）
        theme_name = os.path.splitext(chosen_filename)[0].replace("-", " ")
        
        input_template_path = os.path.join(TEMPLATE_DIR, chosen_filename)
        
        # ... (動画テンプレート検証処理はそのまま)

        # 💡 Geminiへの指示を、ファイル名（テーマ名）を直接渡す方式にアップデート
        prompt = f"""
        Generate 5 engaging slide subtitles and narration scripts for a 30-second YouTube Short.
        The theme is: "{theme_name}".
        Create scripts that match this specific theme.
        Output JSON: slide_1_text...slide_5_voice.
        """
        raw_json = self.ask_gemini(prompt, "You are a YouTube expert. Output ONLY JSON.")
        
        # ... (以下、字幕生成・FFmpeg・アップロード処理へ)
