"""
app/ui/streamlit_app.py - HR Shortlisting Dashboard
"""
import streamlit as st
import requests
import json
import time
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(page_title="HR Shortlisting Agent", page_icon="🤖", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
* { font-family: 'Inter', sans-serif; }
.main { background: #0f0f1a; }
.metric-card {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border: 1px solid #4a4a8a; border-radius: 12px;
    padding: 20px; text-align: center; margin: 8px 0;
}
.hire-badge { background: #00c851; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.nohire-badge { background: #ff4444; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.review-badge { background: #ff8800; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.score-bar { height: 8px; border-radius: 4px; background: linear-gradient(90deg, #4a4a8a, #7b7bff); margin: 4px 0; }
</style>
""", unsafe_allow_html=True)

st.title("🤖 HR Resume & LinkedIn Shortlisting Agent")
st.caption("Powered by GPT-4o · LangChain · LangGraph · FAISS · OpenAI Embeddings")

tabs = st.tabs(["📤 Upload & Run", "📊 Rankings", "📋 Score Cards", "🔧 HR Override", "📈 Analytics", "🔍 Audit Logs"])

# ── Session state ──────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "results" not in st.session_state:
    st.session_state.results = None

# ── TAB 1: Upload ──────────────────────────────────────────
with tabs[0]:
    st.header("Step 1 — Upload Job Description")
    jd_input_method = st.radio("JD Input Method", ["Paste Text", "Upload File"], horizontal=True)

    jd_text = ""
    if jd_input_method == "Paste Text":
        jd_text = st.text_area("Paste Job Description", height=200,
            placeholder="We are looking for a Senior Python Developer with 3+ years experience...")
    else:
        jd_file = st.file_uploader("Upload JD (TXT)", type=["txt"])
        if jd_file:
            jd_text = jd_file.read().decode("utf-8")
            st.success(f"JD loaded: {len(jd_text)} characters")

    st.header("Step 2 — Upload Resumes")
    resume_files = st.file_uploader("Upload Resumes (PDF/DOCX)", type=["pdf","docx"], accept_multiple_files=True)
    if resume_files:
        st.success(f"✅ {len(resume_files)} resume(s) ready")

    st.header("Step 3 — Upload LinkedIn Profiles (Optional)")
    linkedin_files = st.file_uploader("Upload LinkedIn JSON Exports", type=["json"], accept_multiple_files=True)
    if linkedin_files:
        st.info(f"📎 {len(linkedin_files)} LinkedIn profile(s) ready")

    st.header("Step 4 — Run Pipeline")
    if st.button("🚀 Run HR Screening Pipeline", type="primary", use_container_width=True):
        if not jd_text.strip():
            st.error("Please provide a Job Description")
        elif not resume_files:
            st.error("Please upload at least one resume")
        else:
            with st.spinner("Uploading JD..."):
                try:
                    resp = requests.post(f"{API_BASE}/upload/jd", data={"jd_text": jd_text})
                    if resp.status_code == 200:
                        session_id = resp.json()["session_id"]
                        st.session_state.session_id = session_id
                    else:
                        st.error(f"JD upload failed: {resp.text}")
                        st.stop()
                except Exception as e:
                    st.error(f"API connection error: {e}. Is the FastAPI server running?")
                    st.stop()

            with st.spinner("Uploading resumes..."):
                files = [("files", (f.name, f.read(), f.type)) for f in resume_files]
                resp = requests.post(f"{API_BASE}/upload/resumes/{session_id}", files=files)
                if resp.status_code != 200:
                    st.error(f"Resume upload failed: {resp.text}")

            if linkedin_files:
                with st.spinner("Uploading LinkedIn profiles..."):
                    li_files = [("files", (f.name, f.read(), "application/json")) for f in linkedin_files]
                    requests.post(f"{API_BASE}/upload/linkedin/{session_id}", files=li_files)

            with st.spinner("🔄 Running AI pipeline (JD Parse → Resume Parse → Embed → Score → Rank → Report)..."):
                requests.post(f"{API_BASE}/upload/run/{session_id}")
                # Poll for results
                for _ in range(60):
                    time.sleep(3)
                    status_resp = requests.get(f"{API_BASE}/upload/status/{session_id}")
                    status = status_resp.json().get("status", "running")
                    if status != "running":
                        break
                results_resp = requests.get(f"{API_BASE}/scoring/results/{session_id}")
                if results_resp.status_code == 200:
                    st.session_state.results = results_resp.json()
                    st.success("✅ Pipeline complete!")
                    st.balloons()
                else:
                    st.error("Failed to retrieve results")

    if st.session_state.session_id:
        st.info(f"Session ID: `{st.session_state.session_id}`")

# ── TAB 2: Rankings ────────────────────────────────────────
with tabs[1]:
    st.header("Candidate Rankings")
    results = st.session_state.results
    if not results or "ranked_candidates" not in results:
        st.info("Run the pipeline to see rankings here.")
    else:
        ranked = results["ranked_candidates"]
        total = results.get("total_candidates", len(ranked))

        col1, col2, col3, col4 = st.columns(4)
        hire = sum(1 for r in ranked if r["recommendation"]=="Hire")
        review = sum(1 for r in ranked if r["recommendation"]=="Review")
        nohire = sum(1 for r in ranked if r["recommendation"]=="No-Hire")
        with col1: st.metric("Total Candidates", total)
        with col2: st.metric("✅ Hire", hire)
        with col3: st.metric("⚠️ Review", review)
        with col4: st.metric("❌ No-Hire", nohire)

        filter_rec = st.multiselect("Filter by Recommendation", ["Hire","Review","No-Hire"], default=["Hire","Review","No-Hire"])
        filtered = [r for r in ranked if r["recommendation"] in filter_rec]

        COLS = ["Rank", "Candidate ID", "Score", "Recommendation", "Semantic Sim.", "Override", "Needs Review"]
        df = pd.DataFrame(
            [{
                "Rank": r["rank"],
                "Candidate ID": r["candidate_id"][-12:],
                "Score": f"{r['total_score']:.1f}",
                "Recommendation": r["recommendation"],
                "Semantic Sim.": f"{r.get('semantic_similarity_score',0):.2f}",
                "Override": "✅" if r.get("override_applied") else "",
                "Needs Review": "⚠️" if r.get("needs_human_review") else "",
            } for r in filtered],
            columns=COLS,
        )

        def color_rec(val):
            if val=="Hire": return "background-color:#00432a;color:white"
            if val=="No-Hire": return "background-color:#430000;color:white"
            return "background-color:#433000;color:white"

        if df.empty:
            st.info("No candidates match the selected filters.")
        else:
            st.dataframe(df.style.map(color_rec, subset=["Recommendation"]), use_container_width=True, hide_index=True)

        if not filtered:
            st.info("No data to chart.")
        else:
            # Score bar chart
            fig = px.bar(
                x=[r["candidate_id"][-8:] for r in filtered],
                y=[r["total_score"] for r in filtered],
                color=[r["recommendation"] for r in filtered],
                color_discrete_map={"Hire":"#00c851","Review":"#ff8800","No-Hire":"#ff4444"},
                title="Candidate Scores Overview",
                labels={"x":"Candidate","y":"Total Score (0-100)"},
            )
            fig.add_hline(y=65, line_dash="dash", line_color="green", annotation_text="Hire threshold (65)")
            fig.add_hline(y=50, line_dash="dash", line_color="orange", annotation_text="Review threshold (50)")
            fig.update_layout(template="plotly_dark", height=400)
            st.plotly_chart(fig, use_container_width=True)

# ── TAB 3: Score Cards ─────────────────────────────────────
with tabs[2]:
    st.header("Candidate Score Cards")
    results = st.session_state.results
    if not results:
        st.info("Run the pipeline first.")
    else:
        ranked = results.get("ranked_candidates", [])
        if ranked:
            candidate_ids = [f"#{r['rank']} — {r['candidate_id'][-12:]} ({r['recommendation']})" for r in ranked]
            selected = st.selectbox("Select Candidate", candidate_ids)
            idx = candidate_ids.index(selected)
            cand = ranked[idx]

            col1, col2 = st.columns([1,2])
            with col1:
                score = cand["total_score"]
                color = "#00c851" if score>=65 else "#ff8800" if score>=50 else "#ff4444"
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=score,
                    gauge={"axis":{"range":[0,100]},
                           "bar":{"color":color},
                           "steps":[{"range":[0,50],"color":"#2d0000"},{"range":[50,65],"color":"#2d2000"},{"range":[65,100],"color":"#002d00"}]},
                    title={"text":"Total Score"},
                ))
                fig.update_layout(template="plotly_dark", height=300)
                st.plotly_chart(fig, use_container_width=True)
                rec = cand["recommendation"]
                badge = f'<span class="{rec.lower().replace("-","")}-badge">{rec}</span>'
                st.markdown(badge, unsafe_allow_html=True)
                if cand.get("override_applied"):
                    st.warning(f"⚠️ HR Override Applied: {cand.get('override_reason','')}")

            with col2:
                st.subheader("Dimension Breakdown")
                session_scores_resp = requests.get(
                    f"{API_BASE}/scoring/scores/{st.session_state.session_id}?candidate_id={cand['candidate_id']}"
                ) if st.session_state.session_id else None

                if session_scores_resp and session_scores_resp.status_code == 200:
                    score_detail = session_scores_resp.json()["scores"][0]
                    dims = [
                        ("skills_match","Skills Match","30%"),
                        ("experience_relevance","Experience","25%"),
                        ("education_certifications","Education","15%"),
                        ("projects_portfolio","Projects","20%"),
                        ("communication_quality","Communication","10%"),
                    ]
                    dim_scores = []
                    dim_names = []
                    for key, label, weight in dims:
                        d = score_detail.get(key, {})
                        s = d.get("score", 0)
                        dim_scores.append(s)
                        dim_names.append(f"{label} ({weight})")
                        col_a, col_b = st.columns([2,1])
                        col_a.write(f"**{label}** ({weight})")
                        col_b.write(f"**{s:.0f}/100**")
                        st.progress(int(s)/100)
                        st.caption(d.get("justification",""))

                    fig_radar = go.Figure(go.Scatterpolar(
                        r=dim_scores + [dim_scores[0]],
                        theta=dim_names + [dim_names[0]],
                        fill="toself", fillcolor="rgba(74,74,138,0.3)",
                        line_color="#7b7bff"
                    ))
                    fig_radar.update_layout(template="plotly_dark", height=350,
                        polar={"radialaxis":{"range":[0,100]}})
                    st.plotly_chart(fig_radar, use_container_width=True)

            st.subheader("Skills Analysis")
            c1, c2 = st.columns(2)
            with c1:
                st.success("✅ Matched Skills")
                for sk in cand.get("matched_skills",[]):
                    st.write(f"• {sk}")
            with c2:
                st.error("❌ Missing Skills")
                for sk in cand.get("missing_skills",[]):
                    st.write(f"• {sk}")

            st.subheader("Overall Summary")
            st.info(cand.get("overall_summary",""))

# ── TAB 4: HR Override ─────────────────────────────────────
with tabs[3]:
    st.header("🔧 Human-in-the-Loop Override")
    st.warning("⚠️ Overrides are logged in the audit trail. Provide a clear justification.")

    results = st.session_state.results
    if not results:
        st.info("Run the pipeline first.")
    else:
        ranked = results.get("ranked_candidates", [])
        if ranked:
            opts = [f"{r['rank']}. {r['candidate_id'][-12:]} — {r['recommendation']} ({r['total_score']:.1f})" for r in ranked]
            sel = st.selectbox("Select Candidate to Override", opts)
            idx = opts.index(sel)
            cand = ranked[idx]

            with st.form("override_form"):
                st.write(f"**Current Score:** {cand['total_score']:.1f} | **Current Recommendation:** {cand['recommendation']}")
                new_score = st.slider("New Score", 0.0, 100.0, float(cand["total_score"]), 0.5)
                new_rec = st.selectbox("New Recommendation", ["Hire","Review","No-Hire"],
                    index=["Hire","Review","No-Hire"].index(cand["recommendation"]))
                reason = st.text_area("Override Reason (required)", placeholder="Explain why you are overriding the AI score...")
                reviewer = st.text_input("Your Name/ID", value="HR Manager")

                if st.form_submit_button("Apply Override", type="primary"):
                    if len(reason.strip()) < 10:
                        st.error("Please provide a detailed reason (at least 10 characters)")
                    else:
                        payload = {
                            "session_id": st.session_state.session_id,
                            "candidate_id": cand["candidate_id"],
                            "original_score": cand["total_score"],
                            "overridden_score": new_score,
                            "original_recommendation": cand["recommendation"],
                            "overridden_recommendation": new_rec,
                            "override_reason": reason,
                            "hr_reviewer": reviewer,
                        }
                        resp = requests.post(f"{API_BASE}/override/apply", json=payload)
                        if resp.status_code == 200:
                            st.success("✅ Override applied and logged to audit trail!")
                            st.json(resp.json()["override"])
                        else:
                            st.error(f"Override failed: {resp.text}")

            st.subheader("Existing Overrides")
            if st.session_state.session_id:
                ov_resp = requests.get(f"{API_BASE}/override/list?session_id={st.session_state.session_id}")
                if ov_resp.status_code == 200:
                    overrides = ov_resp.json().get("overrides", [])
                    if overrides:
                        st.dataframe(pd.DataFrame(overrides), use_container_width=True)
                    else:
                        st.info("No overrides applied yet.")

# ── TAB 5: Analytics ───────────────────────────────────────
with tabs[4]:
    st.header("📈 Analytics Dashboard")
    results = st.session_state.results
    if not results:
        st.info("Run the pipeline first.")
    else:
        ranked = results.get("ranked_candidates", [])
        if ranked:
            scores = [r["total_score"] for r in ranked]

            col1, col2, col3 = st.columns(3)
            col1.metric("Average Score", f"{sum(scores)/len(scores):.1f}")
            col2.metric("Highest Score", f"{max(scores):.1f}")
            col3.metric("Lowest Score", f"{min(scores):.1f}")

            fig_hist = px.histogram(scores, nbins=10, title="Score Distribution",
                labels={"value":"Score","count":"Candidates"}, color_discrete_sequence=["#7b7bff"])
            fig_hist.update_layout(template="plotly_dark")
            st.plotly_chart(fig_hist, use_container_width=True)

            rec_counts = {"Hire":0,"Review":0,"No-Hire":0}
            for r in ranked:
                rec_counts[r["recommendation"]] = rec_counts.get(r["recommendation"],0) + 1
            fig_pie = px.pie(values=list(rec_counts.values()), names=list(rec_counts.keys()),
                title="Recommendation Distribution",
                color_discrete_map={"Hire":"#00c851","Review":"#ff8800","No-Hire":"#ff4444"})
            fig_pie.update_layout(template="plotly_dark")
            st.plotly_chart(fig_pie, use_container_width=True)

            # Semantic similarity vs score scatter
            fig_scatter = px.scatter(
                x=[r.get("semantic_similarity_score",0) for r in ranked],
                y=[r["total_score"] for r in ranked],
                color=[r["recommendation"] for r in ranked],
                color_discrete_map={"Hire":"#00c851","Review":"#ff8800","No-Hire":"#ff4444"},
                title="Semantic Similarity vs Total Score",
                labels={"x":"Semantic Similarity (FAISS)","y":"Total Score"},
                hover_name=[r["candidate_id"][-10:] for r in ranked],
            )
            fig_scatter.update_layout(template="plotly_dark")
            st.plotly_chart(fig_scatter, use_container_width=True)

        # Download buttons
        st.subheader("Download Reports")
        c1, c2 = st.columns(2)
        if st.session_state.session_id:
            with c1:
                if st.button("⬇️ Download PDF Report"):
                    r = requests.get(f"{API_BASE}/ranking/report/pdf/{st.session_state.session_id}")
                    if r.status_code == 200:
                        st.download_button("Save PDF", r.content, "hr_report.pdf", "application/pdf")
                    else:
                        st.error("PDF not ready yet")
            with c2:
                if st.button("⬇️ Download JSON Report"):
                    r = requests.get(f"{API_BASE}/ranking/report/json/{st.session_state.session_id}")
                    if r.status_code == 200:
                        st.download_button("Save JSON", r.content, "hr_report.json", "application/json")

# ── TAB 6: Audit Logs ─────────────────────────────────────
with tabs[5]:
    st.header("🔍 Audit Logs")
    st.caption("Complete audit trail of all pipeline events — for compliance and explainability.")

    limit = st.slider("Number of logs to show", 10, 200, 50)
    session_filter = st.text_input("Filter by Session ID (optional)", value=st.session_state.session_id or "")

    if st.button("Refresh Logs"):
        url = f"{API_BASE}/scoring/audit-logs?limit={limit}"
        if session_filter:
            url += f"&session_id={session_filter}"
        r = requests.get(url)
        if r.status_code == 200:
            logs = r.json().get("logs", [])
            if logs:
                df_logs = pd.DataFrame(logs)[["created_at","event_type","agent_name","status","output_summary","duration_ms"]]
                df_logs.columns = ["Timestamp","Event","Agent","Status","Summary","Duration(ms)"]
                st.dataframe(df_logs, use_container_width=True, hide_index=True)
            else:
                st.info("No logs found.")
        else:
            st.error("Could not fetch logs — is the API server running?")
