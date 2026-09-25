"""
Full End-to-End Gap2Hire Demo Flow Verification Script (Async httpx)
Validates every single step required by the user prompt.
"""
import uuid
import asyncio
import httpx
from app.main import app

async def run_full_demo():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unique_suffix = uuid.uuid4().hex[:6]
        company_name = f"Apex Systems {unique_suffix}"
        hr_name = f"Sarah Jenkins {unique_suffix}"
        email = f"sarah_{unique_suffix}@apexsystems.io"
        password = "SecurePassword123!"
        
        print("\n--- 1. COMPANY REGISTRATION ---", flush=True)
        reg_res = await client.post("/api/v1/auth/register", json={
            "organization_name": company_name,
            "full_name": hr_name,
            "email": email,
            "password": password
        })
        assert reg_res.status_code == 201, f"Reg failed: {reg_res.text}"
        print(f"Company registered: {company_name}", flush=True)
        
        print("\n--- 2. COMPANY LOGIN ---", flush=True)
        login_res = await client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Login successful, JWT token acquired.", flush=True)
        
        print("\n--- 3. HR DASHBOARD ME CHECK ---", flush=True)
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == email
        print(f"Verified HR Identity: {me_res.json()['full_name']}", flush=True)
        
        print("\n--- 4. CREATE JOB ---", flush=True)
        job_desc = """
        Senior Python / FastAPI Backend Engineer
        We are looking for an experienced backend engineer to lead API development.
        Requirements:
        - 5+ years of Python backend development experience.
        - Deep knowledge of FastAPI, Pydantic, and asynchronous programming.
        - Strong database modeling in PostgreSQL with SQLAlchemy ORM and Alembic migrations.
        - Experience with Redis caching and background task queues.
        - Docker containerization and Kubernetes deployment.
        - Proven track record debugging complex distributed systems.
        """
        create_job_res = await client.post("/api/v1/jobs", json={
            "title": "Senior Python Backend Engineer",
            "description": job_desc
        }, headers=headers)
        assert create_job_res.status_code == 201, f"Create job failed: {create_job_res.text}"
        job_id = create_job_res.json()["id"]
        print(f"Job created: {job_id} (Status: {create_job_res.json()['status']})", flush=True)
        
        print("\n--- 5. AI JD STRUCTURING ---", flush=True)
        analyze_res = await client.post(f"/api/v1/jobs/{job_id}/analyze", headers=headers)
        assert analyze_res.status_code == 200, f"JD Analysis failed: {analyze_res.text}"
        suggested_caps = analyze_res.json().get("suggested_capabilities", [])
        print(f"AI extracted {len(suggested_caps)} capabilities:", flush=True)
        for cap in suggested_caps[:5]:
            print(f"  • {cap['name']} ({cap.get('importance', 'CRITICAL')})", flush=True)
        assert len(suggested_caps) > 0
        
        print("\n--- 6. HR REVIEWS/APPROVES CAPABILITIES ---", flush=True)
        batch_caps = [
            {"name": c["name"], "description": c.get("description", ""), "importance": c.get("importance", "HIGH")}
            for c in suggested_caps
        ]
        approve_res = await client.post(f"/api/v1/jobs/{job_id}/capabilities/batch", json={"capabilities": batch_caps}, headers=headers)
        assert approve_res.status_code == 201
        print(f"Approved {len(approve_res.json())} capabilities.", flush=True)
        
        print("\n--- 7. PUBLISH JOB ---", flush=True)
        publish_res = await client.patch(f"/api/v1/jobs/{job_id}", json={"status": "ACTIVE"}, headers=headers)
        assert publish_res.status_code == 200
        assert publish_res.json()["status"] == "ACTIVE"
        print("Job published and accepting applications.", flush=True)
        
        print("\n--- 8. LOAD NEW RESUMES (BOUNDED INGESTION) ---", flush=True)
        sync_res = await client.post(f"/api/v1/email/sync?limit=2&target_job_id={job_id}", headers=headers)
        assert sync_res.status_code == 200, f"Email sync failed: {sync_res.text}"
        sync_data = sync_res.json()
        print("Bounded Sync Result:", flush=True)
        print(f"  Emails fetched: {sync_data['emails_fetched']}", flush=True)
        print(f"  Candidate applications: {sync_data['candidate_emails']}", flush=True)
        print(f"  Resumes processed: {sync_data['resumes_processed']}", flush=True)
        print(f"  Duplicates skipped: {sync_data['duplicates_skipped']}", flush=True)
        
        print("\n--- 9. SCREENING QUEUE ---", flush=True)
        candidates_res = await client.get(f"/api/v1/jobs/{job_id}/candidates", headers=headers)
        assert candidates_res.status_code == 200
        candidates = candidates_res.json()
        print(f"Retrieved {len(candidates)} candidates in screening queue.", flush=True)
        assert len(candidates) > 0
        target_candidate = candidates[0]
        app_id = target_candidate["application_id"]
        print(f"Target Candidate: {target_candidate.get('candidate_name')} ({target_candidate.get('candidate_email')})", flush=True)
        
        print("\n--- 10. CANDIDATE DETAIL & EVIDENCE VIEW ---", flush=True)
        screen_report_res = await client.get(f"/api/v1/applications/{app_id}/screening", headers=headers)
        assert screen_report_res.status_code == 200
        report_data = screen_report_res.json()
        print(f"Screening Summary: {report_data.get('summary_explanation')[:80]}...", flush=True)
        print(f"Eligibility: {report_data.get('eligibility_status')}", flush=True)
        print("Evaluated Requirements & Provenance:", flush=True)
        for req in report_data.get("requirements_evaluated", [])[:4]:
            print(f"  • {req['requirement_name']}: {req['status']} [{req['provenance']}]", flush=True)
            
        print("\n--- 11. HR SHORTLISTS CANDIDATE ---", flush=True)
        shortlist_res = await client.patch(f"/api/v1/applications/{app_id}/shortlist", json={
            "decision": "SHORTLISTED",
            "reason": "Strong Python and FastAPI claim evidence, cleared for interview round."
        }, headers=headers)
        assert shortlist_res.status_code == 200
        assert shortlist_res.json()["shortlist_status"] == "SHORTLISTED"
        print("Candidate successfully shortlisted.", flush=True)
        
        print("\n--- 12. INTERVIEW SETUP & AI SUGGESTED QUESTIONS ---", flush=True)
        suggest_q_res = await client.post(f"/api/v1/jobs/{job_id}/suggest-questions", headers=headers)
        assert suggest_q_res.status_code == 200
        q_suggestions = suggest_q_res.json().get("questions", [])
        print(f"AI generated {len(q_suggestions)} interview questions for approved capabilities:", flush=True)
        for q in q_suggestions[:3]:
            print(f"  • [{q['capability_name']}] {q['question']}", flush=True)
            
        print("\n--- 13. START LIVE AI INTERVIEW ---", flush=True)
        create_session_res = await client.post(f"/api/v1/applications/{app_id}/interviews", headers=headers)
        assert create_session_res.status_code == 201
        session_id = create_session_res.json()["id"]
        print(f"Created interview session: {session_id}", flush=True)
        
        start_session_res = await client.patch(f"/api/v1/interviews/{session_id}/start", headers=headers)
        assert start_session_res.status_code == 200
        print(f"Started session status: {start_session_res.json()['status']}", flush=True)
        
        print("\n--- 14. HR LIVE OBSERVER SNAPSHOT ---", flush=True)
        hr_live_res = await client.get(f"/api/v1/interviews/{session_id}/hr-live", headers=headers)
        assert hr_live_res.status_code == 200
        live_snapshot = hr_live_res.json()
        print(f"HR Observer: Candidate {live_snapshot['candidate_name']}, Status: {live_snapshot['status']}", flush=True)
        
        print("\n--- 15. INTERVIEW COMPLETION & REPORT ---", flush=True)
        report_res = await client.get(f"/api/v1/interviews/{session_id}/report", headers=headers)
        assert report_res.status_code == 200
        rep = report_res.json()
        print(f"Report Session: {rep['session_id']}, Status: {rep['status']}", flush=True)
        print(f"Total Questions Asked: {rep.get('total_questions', 0)}, Total Messages: {rep.get('total_messages', 0)}", flush=True)
        
        print("\n--- 16. FINAL HUMAN HIRING DECISION ---", flush=True)
        final_dec_res = await client.patch(f"/api/v1/applications/{app_id}", json={
            "status": "HIRED"
        }, headers=headers)
        assert final_dec_res.status_code == 200
        assert final_dec_res.json()["status"] == "HIRED"
        print("Human Decision: Candidate ADVANCED to HIRED / Offer.", flush=True)
        
        print("\n=======================================================", flush=True)
        print("[SUCCESS] COMPLETE GAP2HIRE DEMO FLOW VERIFIED 100%!", flush=True)
        print("=======================================================", flush=True)

if __name__ == "__main__":
    asyncio.run(run_full_demo())
