import streamlit as st
import random
from threading import Lock
from streamlit_autorefresh import st_autorefresh

# --- 1. 페이지 설정 및 실제 게임판 스타일 CSS 정의 ---
st.set_page_config(page_title="Streamlit Hold'em Pro", page_icon="🃏", layout="wide")

custom_css = """
<style>
    /* 전체 배경색 (어두운 라운지 느낌) */
    .stApp {
        background-color: #1e1e1e;
        color: white;
    }
    
    /* 사이드바 스타일 */
    [data-testid="stSidebar"] {
        background-color: #2d2d2d;
    }

    /* 중앙 포커 테이블 felt 디자인 */
    .poker-table {
        background-color: #076324; /* 녹색 felt */
        border: 15px solid #4a3121; /* 나무 테두리 */
        border-radius: 150px;
        padding: 50px;
        margin: 20px auto;
        min-height: 550px;
        box-shadow: inset 0 0 100px rgba(0,0,0,0.5);
        position: relative;
        text-align: center;
    }

    /* 포커 카드 디자인 */
    .poker-card {
        background-color: white;
        border-radius: 8px;
        padding: 10px 15px;
        color: black;
        font-weight: bold;
        font-family: 'Courier New', monospace;
        font-size: 20px;
        display: inline-block;
        margin: 5px;
        box-shadow: 3px 3px 10px rgba(0,0,0,0.3);
        border: 1px solid #ccc;
    }
    /* 카드 문양 색상 */
    .suit-heart, .suit-diamond { color: #d63031; } /* Red */
    .suit-spade, .suit-club { color: #2d3436; } /* Black */

    /* 플레이어 좌석 박스 디자인 */
    .player-seat {
        background-color: rgba(0,0,0,0.6);
        border-radius: 15px;
        padding: 15px;
        width: 180px;
        margin: 10px;
        border: 2px solid #555;
        display: inline-block;
        vertical-align: top;
        transition: all 0.3s ease;
    }
    
    /* 현재 턴 플레이어 강조 효과 (노란색 빛) */
    .active-turn {
        border-color: #f1c40f;
        box-shadow: 0 0 20px #f1c40f;
        transform: scale(1.05);
    }
    
    /* 폴드한 플레이어 어둡게 처리 */
    .folded-player {
        opacity: 0.3;
    }
    
    /* 공용 정보판 (Pot 등) */
    .info-board {
        background-color: rgba(0,0,0,0.8);
        border-radius: 10px;
        padding: 10px 20px;
        display: inline-block;
        margin-bottom: 20px;
        border: 1px solid #444;
    }

    /* 스트림릿 기본 요소 숨기기 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# 로컬 세션 닉네임 저장
if "my_name" not in st.session_state:
    st.session_state.my_name = None

# 2초마다 화면 실시간 동기화
st_autorefresh(interval=2000, limit=None, key="poker_autorefresh")

# --- 2. 전역 상태(Global State) 및 Lock ---
if not hasattr(st, "_shared_game_state"):
    st._shared_game_state = {
        "players": {},           
        "player_order": [],      
        "deck": [],              
        "community_cards": [],   
        "pot": 0,                
        "highest_bet": 0,        
        "current_turn_idx": 0,   
        "game_started": False,   
        "round_stage": "Lobby",
        "last_action": "테이블이 준비되었습니다. 좌석에 앉아주세요."
    }
if not hasattr(st, "_game_lock"):
    st._game_lock = Lock()

shared = st._shared_game_state
lock = st._game_lock

# --- 3. 유틸리티 함수 ---
def create_deck():
    suits = ['♠', '◆', '♥', '♣']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [f"{rank}{suit}" for suit in suits for rank in ranks]
    random.shuffle(deck)
    return deck

def next_turn():
    active_players = [p for p in shared["player_order"] if not shared["players"][p]["folded"]]
    if len(active_players) == 1:
        shared["round_stage"] = "Showdown"
        shared["last_action"] = f"나머지 플레이어가 모두 폴드하여 {active_players[0]}님이 승리했습니다!"
        return
    for _ in range(len(shared["player_order"])):
        shared["current_turn_idx"] = (shared["current_turn_idx"] + 1) % len(shared["player_order"])
        next_player = shared["player_order"][shared["current_turn_idx"]]
        if not shared["players"][next_player]["folded"]:
            break

def get_card_html(card_str):
    """'A♠' 형태의 문자열을 그래픽 카드 HTML로 변환합니다."""
    if not card_str: return ""
    rank = card_str[:-1]
    suit = card_str[-1]
    suit_class = ""
    if suit in ['♥', '◆']: suit_class = "suit-heart"
    elif suit in ['♠', '♣']: suit_class = "suit-spade"
    return f'<span class="poker-card {suit_class}">{rank}{suit}</span>'

def get_hidden_card_html():
    """뒷면 카드를 HTML로 표현합니다."""
    return f'<span class="poker-card" style="background-color:#c0392b; color:#c0392b;">??</span>'

# --- 4. 사이드바 UI (접속 및 게임 정보) ---
st.sidebar.title("🃏 Streamlit Hold'em Pro")

with lock:
    # 로그인 처리
    if st.session_state.my_name is None:
        st.sidebar.info("닉네임을 입력하고 게임에 참여하세요.")
        with st.sidebar.form("login_form"):
            input_name = st.text_input("닉네임 (최대 6자)", max_chars=6).strip()
            submitted = st.form_submit_button("테이블 앉기")
            if submitted and input_name:
                if input_name not in shared["players"]:
                    if not shared["game_started"]:
                        shared["players"][input_name] = {"chips": 1000, "cards": [], "current_bet": 0, "folded": False}
                        shared["player_order"].append(input_name)
                        st.session_state.my_name = input_name
                        st.rerun()
                    else: st.error("게임이 이미 진행 중입니다.")
                else: st.error("이미 사용 중인 이름입니다.")
    else:
        me = st.session_state.my_name
        st.sidebar.success(f"[{me}]님 테이블 접속 중")
        
        c1, c2 = st.sidebar.columns(2)
        with c1:
            if not shared["game_started"]:
                if st.button("🚪 테이블 나가기"):
                    del shared["players"][me]
                    shared["player_order"].remove(me)
                    st.session_state.my_name = None
                    st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"### 📢 최근 액션")
        st.sidebar.caption(shared["last_action"])


# --- 5. 메인 게임 테이블 화면 (CSS 적용) ---
with lock:
    # 게임 대기 화면 (로비)
    if not shared["game_started"]:
        st.title("텍사스 홀덤 클럽 대기실")
        
        st.markdown('<div class="poker-table">', unsafe_allow_html=True)
        st.markdown("## 🛑 딜 대기 중")
        st.markdown("최소 2명이 자리에 앉으면 게임을 시작할 수 있습니다.")
        
        # 현재 대기 중인 플레이어들을 Seat 형태로 시각화
        cols = st.columns(max(len(shared["player_order"]), 1))
        for i, name in enumerate(shared["player_order"]):
            with cols[i]:
                st.markdown(f"""
                <div class="player-seat">
                    <div style="font-size:24px;">👤</div>
                    <strong>{name}</strong><br>
                    Chips: 1000
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        if len(shared["players"]) >= 2:
            if st.button("🚀 게임 시작 (카드 분배)", type="primary"):
                shared["deck"] = create_deck()
                shared["community_cards"] = []
                shared["pot"] = 0
                shared["highest_bet"] = 0
                shared["current_turn_idx"] = 0
                shared["round_stage"] = "Pre-flop"
                shared["game_started"] = True
                shared["last_action"] = "게임 시작! 카드가 분배됩니다."
                for p in shared["players"]:
                    shared["players"][p]["cards"] = [shared["deck"].pop(), shared["deck"].pop()]
                    shared["players"][p]["current_bet"] = 0
                    shared["players"][p]["folded"] = False
                st.rerun()

    # 게임 진행 중 화면 (실제 게임판)
    else:
        st.title("Poker Room #001")
        
        # 5-1. 실제 포커 테이블 Felt 구현
        st.markdown('<div class="poker-table">', unsafe_allow_html=True)
        
        # 테이블 중앙 정보 (Pot 및 Community Cards)
        st.markdown(f"""
        <div class="info-board">
            <span style="font-size:18px; color:#aaa;">단계: {shared['round_stage']}</span><br>
            <span style="font-size:28px; font-weight:bold; color:#f1c40f;">POT: {shared['pot']} 칩</span>
        </div>
        """, unsafe_allow_html=True)
        
        community_html = "".join([get_card_html(c) for c in shared["community_cards"]])
        if not community_html: community_html = '<div style="height:70px; color:#aaa; font-style:italic;">카드를 기다리는 중...</div>'
        st.markdown(f'<div style="margin-bottom:40px;">{community_html}</div>', unsafe_allow_html=True)
        
        st.markdown('---', unsafe_allow_html=True)
        
        # 5-2. 플레이어 좌석 배치 (Seat)
        num_players = len(shared["player_order"])
        player_cols = st.columns(num_players)
        
        for i, name in enumerate(shared["player_order"]):
            with player_cols[i]:
                info = shared["players"][name]
                me = st.session_state.my_name
                
                # 좌석 스타일 결정 (턴 강조, 폴드 어둡게)
                is_turn = shared["game_started"] and shared["player_order"][shared["current_turn_idx"]] == name and shared["round_stage"] != "Showdown"
                seat_class = "player-seat"
                if is_turn: seat_class += " active-turn"
                if info["folded"]: seat_class += " folded-player"
                
                # 카드 표시 로직
                if name == me and not info["folded"]:
                    cards_display = "".join([get_card_html(c) for c in info["cards"]])
                elif shared["round_stage"] == "Showdown" and not info["folded"]:
                    cards_display = "".join([get_card_html(c) for c in info["cards"]])
                else:
                    cards_display = get_hidden_card_html() * 2 if shared["round_stage"] != "Lobby" else ""
                
                st.markdown(f"""
                <div class="{seat_class}">
                    <strong>{name}</strong><br>
                    Chips: {info['chips']}<br>
                    <span style="color:#f1c40f;">Bet: {info['current_bet']}</span><br>
                    {cards_display}
                </div>
                """, unsafe_allow_html=True)
        
        # 포커 테이블 felt 닫기
        st.markdown('</div>', unsafe_allow_html=True)

        # 5-3. 본인 액션 컨트롤 UI (테이블 하단)
        me = st.session_state.my_name
        if me and me in shared["players"]:
            my_info = shared["players"][me]
            
            if my_info["folded"]:
                st.error("이번 판은 기권하셨습니다.")
            else:
                current_turn_player = shared["player_order"][shared["current_turn_idx"]]
                if current_turn_player == me and shared["round_stage"] != "Showdown":
                    st.markdown("### 🎯 내 차례 - 액션 선택")
                    call_amount = shared["highest_bet"] - my_info["current_bet"]
                    
                    with st.form("action_form"):
                        action = st.radio("액션", ["Check / Call", "Bet / Raise", "Fold"], horizontal=True)
                        bet_val = st.slider("금액 (Raise 선택 시)", min_value=0, max_value=my_info["chips"], step=10, value=call_amount)
                        
                        if st.form_submit_button("확정"):
                            if action == "Fold":
                                shared["players"][me]["folded"] = True
                                shared["last_action"] = f"{me}님이 폴드했습니다."
                            elif action == "Check / Call":
                                actual_call = min(call_amount, my_info["chips"])
                                shared["players"][me]["chips"] -= actual_call
                                shared["players"][me]["current_bet"] += actual_call
                                shared["pot"] += actual_call
                                shared["last_action"] = f"{me}님이 체크/콜 했습니다."
                            elif action == "Bet / Raise":
                                if bet_val < call_amount:
                                    st.error(f"최소 {call_amount} 이상을 베팅해야 합니다.")
                                    st.stop()
                                shared["players"][me]["chips"] -= bet_val
                                shared["players"][me]["current_bet"] += bet_val
                                shared["pot"] += bet_val
                                shared["highest_bet"] = shared["players"][me]["current_bet"]
                                shared["last_action"] = f"{me}님이 {bet_val} 칩 베팅/레이즈했습니다."
                            next_turn()
                            st.rerun()

        # 5-4. 딜러 컨트롤 및 정산
        st.markdown("---")
        with st.expander("🛠️ 딜러(방장) 컨트롤 및 정산"):
            if shared["round_stage"] != "Showdown":
                c1, c2, c3, c4 = st.columns(4)
                if c1.button("🟢 플랍(Flop) 3장 오픈"):
                    if shared["round_stage"] == "Pre-flop":
                        shared["community_cards"] = [shared["deck"].pop() for _ in range(3)]
                        shared["round_stage"] = "Flop"
                        shared["last_action"] = "플랍 카드가 오픈되었습니다."
                        st.rerun()
                if c2.button("🔵 턴(Turn) 1장 오픈"):
                    if shared["round_stage"] == "Flop":
                        shared["community_cards"].append(shared["deck"].pop())
                        shared["round_stage"] = "Turn"
                        shared["last_action"] = "턴 카드가 오픈되었습니다."
                        st.rerun()
                if c3.button("🟣 리버(River) 1장 오픈"):
                    if shared["round_stage"] == "Turn":
                        shared["community_cards"].append(shared["deck"].pop())
                        shared["round_stage"] = "River"
                        shared["last_action"] = "리버 카드가 오픈되었습니다."
                        st.rerun()
                if c4.button("🏁 강제 쇼다운"):
                    shared["round_stage"] = "Showdown"
                    st.rerun()
            else:
                st.markdown("### 🏆 승자 정산 및 다음 판")
                active_players = [p for p in shared["player_order"] if not shared["players"][p]["folded"]]
                if not active_players: winner = "없음"
                elif len(active_players) == 1: winner = active_players[0]
                else: winner = st.selectbox("승자를 선택하세요 (자동 족보 계산 미구현)", active_players)
                
                if st.button("💰 팟 지급 및 새 게임", type="primary"):
                    if winner != "없음":
                        shared["players"][winner]["chips"] += shared["pot"]
                    shared["game_started"] = False
                    shared["community_cards"] = []
                    shared["pot"] = 0
                    shared["highest_bet"] = 0
                    shared["round_stage"] = "Lobby"
                    shared["last_action"] = f"이전 판 승자: {winner}. 새 게임을 준비합니다."
                    for p in shared["players"]:
                        shared["players"][p]["cards"] = []
                        shared["players"][p]["current_bet"] = 0
                        shared["players"][p]["folded"] = False
                    st.rerun()
