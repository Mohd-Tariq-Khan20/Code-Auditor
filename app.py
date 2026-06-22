import streamlit as st
from openai import OpenAI
import re
import sqlite3

# --- 1. DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect('auditor_pro.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS audits 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  code TEXT, score TEXT, risk TEXT, feedback TEXT, 
                  audit_type TEXT DEFAULT 'SECURITY',
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    try:
        c.execute("SELECT audit_type FROM audits LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE audits ADD COLUMN audit_type TEXT DEFAULT 'SECURITY'")
        conn.commit()
    conn.commit()
    conn.close()

def save_audit(code, score, risk, feedback, audit_type):
    conn = sqlite3.connect('auditor_pro.db')
    c = conn.cursor()
    c.execute("INSERT INTO audits (code, score, risk, feedback, audit_type) VALUES (?, ?, ?, ?, ?)",
              (code, score, risk, feedback, audit_type))
    conn.commit()
    conn.close()

init_db()

# --- 2. PAGE CONFIG & HIGH VISIBILITY STYLING ---
st.set_page_config(page_title="Socratic AI Code Auditor", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    [data-testid="stSidebar"] .stMarkdown p, 
    [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #ffffff !important; 
        font-weight: bold !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] .stButton>button {
        color: #ffffff !important;
        background-color: #334155 !important;
        border: 1px solid #475569 !important;
        text-align: left !important;
        padding: 10px !important;
    }
    [data-testid="stSidebar"] .stButton>button:hover {
        background-color: #38bdf8 !important;
        color: #0f172a !important;
    }
    [data-testid="stChatInputTextArea"] {
        color: #000000 !important;
        background-color: #ffffff !important;
    }
    label p { color: #ffffff !important; font-weight: bold !important; font-size: 1.1rem !important; }
    textarea::placeholder { color: #ffffff !important; opacity: 0.8 !important; }
    
    .stTextArea textarea { 
        background-color: #1e293b !important; 
        color: #ffffff !important; 
        border: 2px solid #38bdf8 !important; 
        caret-color: #38bdf8 !important; 
        text-decoration: none !important;
    }
    
    .stButton>button { background-color: #38bdf8 !important; color: #0f172a !important; font-weight: bold !important; width: 100%; }
    .stat-card { background-color: #1e293b; padding: 20px; border-radius: 15px; border: 1px solid #334155; text-align: center; margin-bottom: 20px; }
    .placeholder-text { color: #38bdf8 !important; font-weight: bold; }
    .top-bar { background-color:#1e293b; padding:15px; border-radius:10px; border-bottom:3px solid #38bdf8; text-align:center; font-weight:bold; }
    
    .premium-feedback-box {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 2px solid #38bdf8;
        box-shadow: 0px 0px 15px rgba(56, 189, 248, 0.3);
        padding: 20px;
        border-radius: 12px;
        color: #f1f5f9 !important;
        font-size: 1.05rem;
        line-height: 1.6;
        white-space: pre-wrap;
    }
    .premium-feedback-box strong {
        color: #38bdf8 !important;
        font-weight: bold;
    }
    
    div.stButton > button[key="clear_session_btn"], div.stButton > button[key="comp_clear_btn"] { background-color: #475569 !important; color: #ffffff !important; }
    div.stButton > button[key="clear_session_btn"]:hover, div.stButton > button[key="comp_clear_btn"]:hover { background-color: #ef4444 !important; }
    div.stButton > button[key="challenge_submit_btn"] { background-color: #f59e0b !important; color: #0f172a !important; }
    div.stButton > button[key="challenge_submit_btn"]:hover { background-color: #d97706 !important; color: #ffffff !important;}
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.1rem !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

# SMART COMPILER ENGINE: JAVASCRIPT FOR AUTO-CLOSING BRACKETS, QUOTES & SPELLCHECK REMOVAL
js_compiler_helper = """
<script>
setTimeout(function(){
    var textareas = window.parent.document.querySelectorAll('textarea');
    textareas.forEach(function(textarea) {
        textarea.setAttribute('spellcheck', 'false');
        textarea.addEventListener('keydown', function(e) {
            var pairs = {
                '(': ')',
                '{': '}',
                '[': ']',
                '"': '"',
                "'": "'"
            };
            if (pairs[e.key] !== undefined) {
                e.preventDefault();
                var start = this.selectionStart;
                var end = this.selectionEnd;
                var value = this.value;
                var openChar = e.key;
                var closeChar = pairs[e.key];
                this.value = value.substring(0, start) + openChar + closeChar + value.substring(end);
                this.selectionStart = this.selectionEnd = start + 1;
                var event = new Event('input', { bubbles: true });
                this.dispatchEvent(event);
            }
        });
    });
}, 500);
</script>
"""

# --- 3. STATE SYNCHRONIZATION ---
if 'render_tab_selector' not in st.session_state:
    st.session_state.render_tab_selector = "🔍 CODE AUDITOR"

# Tab 1 States
if 'score' not in st.session_state: st.session_state.score = "--%"
if 'risk' not in st.session_state: st.session_state.risk = "Waiting..."
if 'feedback' not in st.session_state: st.session_state.feedback = ""
if 'current_code' not in st.session_state: st.session_state.current_code = ""

# Tab 2 States
if 'comp_problem' not in st.session_state: st.session_state.comp_problem = ""
if 'comp_score' not in st.session_state: st.session_state.comp_score = "--%"
if 'comp_status' not in st.session_state: st.session_state.comp_status = "Waiting..."
if 'comp_feedback' not in st.session_state: st.session_state.comp_feedback = ""
if 'comp_code' not in st.session_state: st.session_state.comp_code = ""

# Tab 3 States
if 'challenge_score' not in st.session_state: st.session_state.challenge_score = "--%"
if 'challenge_risk' not in st.session_state: st.session_state.challenge_risk = "Waiting..."
if 'challenge_feedback' not in st.session_state: st.session_state.challenge_feedback = ""

# --- 4. SIDEBAR LOGIC CONTROL ---
with st.sidebar:
    st.markdown("<h1>🛡️ Socratic AI Auditor</h1>", unsafe_allow_html=True)
    st.write("✨ Developer Edition v1.0")
    st.write("---")
    
    conn = sqlite3.connect('auditor_pro.db')
    sec_audits = conn.execute("SELECT COUNT(*) FROM audits WHERE audit_type='SECURITY'").fetchone()[0]
    comp_audits = conn.execute("SELECT COUNT(*) FROM audits WHERE audit_type='COMPETITIVE'").fetchone()[0]
    conn.close()
    
    st.markdown(f"🔍 Security Logs: **{sec_audits}**")
    st.markdown(f"🏆 Comp. Logs: **{comp_audits}**")
    st.write("---")
    st.subheader("📜 Recent Audits (DB)")
    
    conn = sqlite3.connect('auditor_pro.db')
    history = conn.execute("SELECT id, code, score, risk, feedback, timestamp, audit_type FROM audits ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    
    for row in history:
        label = f"🔍 Sec #{row[0]}" if row[6] == 'SECURITY' else f"🏆 Comp #{row[0]}"
        if st.button(f"{label} | Score: {row[2]}%\n({row[5][11:16]})", key=f"hist_sid_{row[0]}"):
            if row[6] == 'SECURITY':
                st.session_state.current_code = row[1]
                st.session_state.score = f"{row[2]}%"
                st.session_state.risk = row[3]
                st.session_state.feedback = row[4]
                st.session_state.render_tab_selector = "🔍 CODE AUDITOR"
            else:
                st.session_state.comp_code = row[1]
                st.session_state.comp_score = f"{row[2]}%"
                st.session_state.comp_status = row[3]
                st.session_state.comp_feedback = row[4]
                st.session_state.render_tab_selector = "🏆 COMPETITIVE AUDIT"
            st.rerun()

# --- 5. INITIALIZE CLIENT ---
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1", 
    api_key="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"
)

# --- 6. TOP BAR ---
st.markdown("<div class='top-bar'>🛡️ ENTERPRISE PRODUCTION WORKSPACE &nbsp;&nbsp;&nbsp; 🚀 SOCRATIC AI CODE AUDITOR</div>", unsafe_allow_html=True)
st.write("")

# Dynamic Tab Router Wrapper
tab_options = ["🔍 CODE AUDITOR", "🏆 COMPETITIVE AUDIT", "🎯 DAILY CHALLENGE"]
active_tab_label = st.radio("Navigate Workspace Tabs:", tab_options, index=tab_options.index(st.session_state.render_tab_selector), horizontal=True, label_visibility="collapsed")
st.session_state.render_tab_selector = active_tab_label

# ================= TAB 1: CODE AUDITOR =================
if active_tab_label == "🔍 CODE AUDITOR":
    col1, col2 = st.columns([2, 1])
    with col1:
        st.text_area("Student Code Input:", height=300, placeholder="// Paste code here for security audit...", key="current_code")
        st.components.v1.html(js_compiler_helper, height=0)
        
        b1, b2, bdg = st.columns([1.2, 1.2, 1])
        with b1: run_btn = st.button("RUN SECURITY AUDIT", key="auditor_submit_action")
        with b2: clear_btn = st.button("CLEAR SESSION", key="clear_session_btn")
        with bdg:
            if "DETECTED" in st.session_state.risk:
                st.error(st.session_state.risk)
            elif "PASSED" in st.session_state.risk:
                st.success(st.session_state.risk)

    with col2:
        st.markdown(f'<div class="stat-card"><h3>Health Score</h3><h1 class="placeholder-text">{st.session_state.score}</h1></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-card"><h3>Critical Risks</h3><h2 style="color:#38bdf8; font-weight:bold;">{st.session_state.risk}</h2></div>', unsafe_allow_html=True)

    if clear_btn:
        st.session_state.current_code = ""
        st.session_state.score = "--%"
        st.session_state.risk = "Waiting..."
        st.session_state.feedback = ""
        st.rerun()

    if run_btn and st.session_state.current_code:
        with st.spinner("Analyzing code vulnerability bounds..."):
            instruction = "Act as Socratic Security Tutor. Give 'Score: X' out of 100 points and 'Risks: Yes/No'. Then ask 2-3 short security diagnostic questions."
            response = client.chat.completions.create(
                model="meta/llama-3.3-70b-instruct", 
                messages=[{"role": "system", "content": instruction}, {"role": "user", "content": st.session_state.current_code}]
            )
            res_text = response.choices[0].message.content
            try:
                score_num = re.search(r'Score:\s*(\d+)', res_text).group(1)
                st.session_state.score = f"{score_num}%"
                st.session_state.risk = "DETECTED ⚠️" if "Yes" in res_text else "PASSED ✅"
            except:
                st.session_state.score = "85%"
                st.session_state.risk = "ANALYZED"
            st.session_state.feedback = res_text
            save_audit(st.session_state.current_code, st.session_state.score.replace('%',''), st.session_state.risk, res_text, "SECURITY")
            st.rerun()

    if st.session_state.feedback:
        st.markdown("---")
        st.subheader("💡 AI Tutor Feedback")
        if "gets" in st.session_state.current_code:
            st.error("⚠️ INSECURE LINE FOUND: gets() detect hua hai jo memory buffer overflow kar sakta hai!")
        st.markdown(f'<div class="premium-feedback-box">{st.session_state.feedback}</div>', unsafe_allow_html=True)


# ================= TAB 2: COMPETITIVE AUDIT =================
elif active_tab_label == "🏆 COMPETITIVE AUDIT":
    st.subheader("🏆 Competitive Optimization & LeetCode Judge")
    col1_comp, col2_comp = st.columns([2, 1])
    with col1_comp:
        st.session_state.comp_problem = st.text_area("Enter Problem Description / Constraints:", value=st.session_state.comp_problem, height=100, placeholder="Example: Two Sum array constraints 10^5 array sizes.", key="comp_problem_desc_box")
        st.text_area("Competitive Workspace Code:", height=220, placeholder="// Paste solution logic here...", key="comp_code")
        st.components.v1.html(js_compiler_helper, height=0)
        
        bc1, bc2, b_badge = st.columns([1.2, 1.2, 1])
        with bc1: comp_run_btn = st.button("RUN COMPETITIVE EVALUATION", key="comp_submit_trigger_btn")
        with bc2: comp_clear_btn = st.button("CLEAR LOGICAL WORKSPACE", key="comp_clear_btn")
        with b_badge:
            if "TLE" in st.session_state.comp_status:
                st.warning(st.session_state.comp_status)
            elif "PASSED" in st.session_state.comp_status:
                st.success(st.session_state.comp_status)

    with col2_comp:
        st.markdown(f'<div class="stat-card"><h3>Performance Score</h3><h1 class="placeholder-text">{st.session_state.comp_score}</h1></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-card"><h3>Execution Metric</h3><h2 style="color:#f59e0b; font-weight:bold;">{st.session_state.comp_status}</h2></div>', unsafe_allow_html=True)

    if comp_clear_btn:
        st.session_state.comp_problem = ""
        st.session_state.comp_code = ""
        st.session_state.comp_score = "--%"
        st.session_state.comp_status = "Waiting..."
        st.session_state.comp_feedback = ""
        st.rerun()

    if comp_run_btn and st.session_state.comp_code:
        with st.spinner("Evaluating algorithm matching constraints..."):
            comp_instruction = (
                "Act as a strict Socratic LeetCode Judge. Compare the provided Code against the provided Constraints.\n"
                "Verify if it handles edge parameters or triggers Time Limit Exceeded (TLE) matching requirements.\n"
                "CRITICAL: Do NOT print any dynamic replacement code blocks directly. Explain time complexity bounds, give clear pseudo-hints, and ask 2 analytical questions.\n"
                "Output structure must explicitly give: 'Score: X' out of 100 points, and 'Risks: TLE/Failed/No'."
            )
            combined_prompt = f"PROBLEM DESCRIPTION:\n{st.session_state.comp_problem}\n\nSTUDENT CODE ENTRY:\n{st.session_state.comp_code}"
            comp_response = client.chat.completions.create(
                model="meta/llama-3.3-70b-instruct",
                messages=[{"role": "system", "content": comp_instruction}, {"role": "user", "content": combined_prompt}]
            )
            res_comp_text = comp_response.choices[0].message.content
            try:
                score_val = re.search(r'Score:\s*(\d+)', res_comp_text).group(1)
                st.session_state.comp_score = f"{score_val}%"
                if "TLE" in res_comp_text:
                    st.session_state.comp_status = "TLE WARNING ⏱️"
                elif "Failed" in res_comp_text:
                    st.session_state.comp_status = "FAILED CASES ❌"
                else:
                    st.session_state.comp_status = "ALL PASSED ✅"
            except:
                st.session_state.comp_score = "80%"
                st.session_state.comp_status = "EVALUATED"
            
            st.session_state.comp_feedback = res_comp_text
            save_audit(st.session_state.comp_code, st.session_state.comp_score.replace('%',''), st.session_state.comp_status, res_comp_text, "COMPETITIVE")
            st.rerun()

    if st.session_state.comp_feedback:
        st.markdown("---")
        st.subheader("📊 LeetCode Judge Metric Optimization Log")
        if "TLE" in st.session_state.comp_status:
            st.warning("⏱️ TIME LIMIT EXCEEDED TRAP: Unoptimized loop structures detected.")
        st.markdown(f'<div class="premium-feedback-box">{st.session_state.comp_feedback}</div>', unsafe_allow_html=True)


# ================= TAB 3: DAILY CHALLENGE =================
elif active_tab_label == "🎯 DAILY CHALLENGE":
    st.subheader("🎯 Secure Coding Arena - Daily Puzzle")
    selected_lang = st.selectbox("Select Language to Solve Challenge:", ["C", "C++", "Java", "Python"], key="challenge_selector_menu_key")
    
    templates = {
        "C": "#include <stdio.h>\n#include <string.h>\n\nint main() {\n    char buffer[10];\n    printf(\"Enter secret key: \");\n    gets(buffer);\n    return 0;\n}",
        "C++": "#include <iostream>\nusing namespace std;\nint main() {\n    char buffer[10];\n    cout << \"Enter key: \";\n    cin >> buffer;\n    return 0;\n}",
        "Java": "import java.util.Scanner;\npublic class Main {\n    public static void main(String[] args) {\n        Scanner scanner = new Scanner(System.in);\n    }\n}",
        "Python": "import sqlite3\ndef query_db(user_id):\n    query = f\"SELECT * FROM accounts WHERE id = '{user_id}'\"\n    return query"
    }

    col1_ch, col2_ch = st.columns([2, 1])
    with col1_ch:
        challenge_input = st.text_area("Challenge Workspace Editor:", value=templates[selected_lang], height=250, key=f"ch_editor_area_{selected_lang}")
        st.components.v1.html(js_compiler_helper, height=0)
        submit_challenge_btn = st.button("🚀 SUBMIT CHALLENGE SOLUTION", key="challenge_submit_btn")
        
    with col2_ch:
        st.markdown(f'<div class="stat-card"><h3>Challenge Score</h3><h1 class="placeholder-text">{st.session_state.challenge_score}</h1></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-card"><h3>Security Rank Status</h3><h2 style="color:#f59e0b; font-weight:bold;">{st.session_state.challenge_risk}</h2></div>', unsafe_allow_html=True)

    if submit_challenge_btn and challenge_input:
        with st.spinner("Evaluating challenge entry bounds..."):
            instruction_ch = f"Act as strict security evaluator for {selected_lang}. Return tags 'Score: X' out of 100 points and 'Risks: Yes/No'. Provide clear analysis hints without code leaks."
            response_ch = client.chat.completions.create(
                model="meta/llama-3.3-70b-instruct",
                messages=[{"role": "system", "content": instruction_ch}, {"role": "user", "content": challenge_input}]
            )
            res_text_ch = response_ch.choices[0].message.content
            try:
                score_num_ch = re.search(r'Score:\s*(\d+)', res_text_ch).group(1)
                st.session_state.challenge_score = f"{score_num_ch}%"
                st.session_state.challenge_risk = "CHALLENGE PASSED ✅" if "No" in res_text_ch else "FAILED ❌"
            except:
                st.session_state.challenge_score = "80%"
                st.session_state.challenge_risk = "COMPLETED"
            st.session_state.challenge_feedback = res_text_ch
            st.rerun()

    if st.session_state.challenge_feedback:
        st.markdown("---")
        st.subheader("📊 Challenge Judgement Report")
        if "PASSED" in st.session_state.challenge_risk:
            st.success("🏆 Badge Unlocked: Safe Architect! Boundary conditions met specifications.")
        else:
            st.error("❌ FAILED: Found open stack/execution buffer leaks inside solution workspace.")
        st.markdown(f'<div class="premium-feedback-box">{st.session_state.challenge_feedback}</div>', unsafe_allow_html=True)