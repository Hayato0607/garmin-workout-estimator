import streamlit as st
import pandas as pd
import numpy as np
from garminconnect import Garmin

st.title("🏃‍♂️ Garminカスタム練習メニュー推定アプリ")
st.write("設定された独自の優先ルールに基づいて、直近のアクティビティを自動仕分けします。")

# --- 1. サイドバーでログイン情報を入力 ---
st.sidebar.header("ログイン情報")
email = st.sidebar.text_input("メールアドレス")
password = st.sidebar.text_input("パスワード", type="password")

# --- 2. 修正された新しい判定ロジック（優先順位順） ---
def judge_workout(max_hr, avg_hr, max_pace_sec, avg_pace_sec, duration_min):
    # ① （最高ペースがキロ3分[180秒]よりも速い）
    if max_pace_sec < 180:
        return "インターバル 🥵"
    
    # ② レース：（平均心拍数が170以上）かつ（平均ペースがキロ3分40秒[220秒]よりも速い）
    elif avg_hr >= 170 and avg_pace_sec < 220:
        return "レース 🏅"
    
    # ③ テンポ走：（最大心拍数が170以上）かつ（平均ペースがキロ4分[240秒]よりも速い）
    elif max_hr >= 170 and avg_pace_sec < 240:
        return "テンポ走 🏃‍♂️"
    
    # ④ ロングジョグ：（総走行時間が90分以上）
    elif duration_min >= 90:
        return "ロングジョグ 🐢"
    
    # ⑤ ジョグ：上の4つの条件以外
    else:
        return "ジョグ 👟"

# --- 3. メイン画面の処理 ---

# ★ 取得したデータを保持するための「箱（セッションステート）」を準備
if "df_res" not in st.session_state:
    st.session_state.df_res = None

# サイドバーのボタンが押されたときの処理（データの取得と保存のみ行う）
if st.sidebar.button("データを取得して推定する", type="primary"):
    if not email or not password:
        st.error("メールアドレスとパスワードを入力してください。")
    else:
        with st.spinner("ガーミンコネクトから最新のランニングデータを取得中..."):
            try:
                garmin = Garmin(email, password)
                garmin.login()
                activities = garmin.get_activities(0, 15)
                
                results = []
                for act in activities:
                    if act.get("activityType", {}).get("typeKey") != "running":
                        continue
                        
                    date = act["startTimeLocal"][:10]
                    name = act["activityName"]
                    distance = act["distance"] / 1000
                    duration_min = act["duration"] / 60
                    
                    max_hr = act.get("maxHR", 0)
                    avg_hr = act.get("averageHR", 0)
                    
                    avg_pace_sec = act["duration"] / distance if distance > 0 else 9999
                    max_speed = act.get("maxSpeed", 0)
                    max_pace_sec = 1000 / max_speed if max_speed > 0 else 9999
                    
                    menu = judge_workout(max_hr, avg_hr, max_pace_sec, avg_pace_sec, duration_min)
                    
                    avg_pace_str = f"{int(avg_pace_sec // 60)}:{int(avg_pace_sec % 60):02d}"
                    max_pace_str = f"{int(max_pace_sec // 60)}:{int(max_pace_sec % 60):02d}" if max_pace_sec < 9999 else "N/A"
                    
                    results.append({
                        "日付": date,
                        "タイトル": name,
                        "距離 (km)": round(distance, 2),
                        "時間 (分)": round(duration_min, 1),
                        "平均ペース": f"{avg_pace_str}/km",
                        "最高ペース": f"{max_pace_str}/km",
                        "平均心拍": int(avg_hr) if avg_hr else "N/A",
                        "最大心拍": int(max_hr) if max_hr else "N/A",
                        "判定結果": menu
                    })
                
                if results:
                    df = pd.DataFrame(results)
                    # 初期値として推定結果を「正解メニュー」に入れておく
                    df["正解メニュー"] = df["判定結果"]
                    # ★ データをセッションステート（メモリ）に保存
                    st.session_state.df_res = df
                else:
                    st.warning("ランニングのアクティビティが見つかりませんでした。")
                    
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

# =========================================================
# ★ データが保存されている場合のみ、表と計算ボタンを表示する
# =========================================================
if st.session_state.df_res is not None:
    st.success("データの取得が完了しました！")
    st.write("👇 以下の表の「正解メニュー」列をクリックして、本当の練習メニューに修正してください。")

    menu_options = [
        "インターバル 🥵", 
        "レース 🏅", 
        "テンポ走 🏃‍♂️", 
        "ロングジョグ 🐢", 
        "ジョグ 👟"
    ]

    # データエディターの表示
    edited_df = st.data_editor(
        st.session_state.df_res,
        column_config={
            "正解メニュー": st.column_config.SelectboxColumn(
                "本当のメニューは？",
                options=menu_options,
                required=True,
            )
        },
        disabled=["日付", "タイトル", "距離 (km)", "時間 (分)", "平均ペース", "最高ペース", "平均心拍", "最大心拍", "判定結果"],
        hide_index=True,
    )

    # ---------------------------------------------------------
    # 【ご提示いただいたコードの差し込み位置】
    # ---------------------------------------------------------
    st.markdown("---")
    if st.button("📊 精度を計算する", type="primary"):
        # 判定結果と正解メニューが一致している行数をカウント
        correct_count = (edited_df["判定結果"] == edited_df["正解メニュー"]).sum()
        total_count = len(edited_df)
        
        # 正答率を計算 (%)
        accuracy = (correct_count / total_count) * 100
        
        st.header(f"🎯 正答率: {accuracy:.1f} %")
        st.write(f"全 {total_count} 件中、 {correct_count} 件が正解でした！")
        
        # 間違えていた（推定に失敗した）データだけを抽出して表示する
        mistakes = edited_df[edited_df["判定結果"] != edited_df["正解メニュー"]]
        
        if len(mistakes) > 0:
            st.warning("🤔 以下のデータは推定が外れました。ルールの見直し（閾値の調整）に役立てましょう。")
            st.dataframe(mistakes)
        else:
            st.balloons() # 全問正解のときは風船を飛ばす！
            st.success("完璧です！現在のルールで完全に推定できています。")