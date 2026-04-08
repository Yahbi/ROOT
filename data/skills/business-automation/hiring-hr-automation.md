---
name: Hiring and HR Process Automation
description: Automate candidate screening, interview scheduling, offer letters, and onboarding workflows
version: "1.0.0"
author: ROOT
tags: [business-automation, HR, hiring, onboarding, ATS, recruiting]
platforms: [all]
difficulty: intermediate
---

# Hiring and HR Process Automation

Reduce time-to-hire and recruiter workload by automating screening, scheduling,
and documentation while keeping the human elements that matter.

## Resume Screening Automation

### AI-Powered Initial Screening

```python
from anthropic import Anthropic
import json

client = Anthropic()

def screen_resume(resume_text: str, job_description: str, requirements: dict) -> dict:
    """Score and summarize a candidate's fit for a role."""
    response = client.messages.create(
        model="claude-haiku-20240307",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Evaluate this resume against the job requirements.

Job Description: {job_description}

Must-have requirements: {requirements['must_have']}
Nice-to-have requirements: {requirements['nice_to_have']}
Red flags (auto-reject if present): {requirements.get('red_flags', [])}

Resume:
{resume_text}

Return JSON:
{{
  "overall_score": 0-100,
  "must_have_met": {{"requirement": true/false}},
  "nice_to_have_met": {{"requirement": true/false}},
  "red_flags_found": [],
  "strengths": ["top 3 strengths for this role"],
  "concerns": ["top 2 concerns or gaps"],
  "recommendation": "strong_yes|yes|maybe|no",
  "one_line_summary": "Senior backend engineer with strong Python, weak on distributed systems"
}}"""
        }]
    )
    result = json.loads(response.content[0].text)

    # Auto-reject on red flags
    if result.get("red_flags_found"):
        result["recommendation"] = "no"
        result["auto_rejected"] = True

    return result

def batch_screen_applicants(job_id: str, ats_client) -> list:
    """Screen all unreviewed applicants for a job."""
    applicants = ats_client.get_applicants(job_id, status="new")
    job = ats_client.get_job(job_id)

    screened = []
    for applicant in applicants:
        score = screen_resume(
            resume_text=applicant["resume_text"],
            job_description=job["description"],
            requirements=job["requirements"]
        )
        ats_client.update_applicant_score(applicant["id"], score)
        screened.append({"applicant": applicant, "screening": score})

    return sorted(screened, key=lambda x: x["screening"]["overall_score"], reverse=True)
```

## Interview Scheduling Automation

```python
import requests
from datetime import datetime, timedelta

class CalendlyIntegration:
    def __init__(self, api_token: str):
        self.token = api_token
        self.headers = {"Authorization": f"Bearer {api_token}"}

    def create_interview_link(self, event_type: str, candidate_email: str) -> str:
        """Generate a unique scheduling link for a candidate."""
        response = requests.post(
            "https://api.calendly.com/scheduling_links",
            json={
                "max_event_count": 1,   # One-time use link
                "owner": f"https://api.calendly.com/event_types/{event_type}",
                "owner_type": "EventType"
            },
            headers=self.headers
        )
        return response.json()["resource"]["booking_url"]

    def get_upcoming_interviews(self, days: int = 7) -> list:
        """Get all interviews scheduled in the next N days."""
        now = datetime.utcnow()
        max_time = now + timedelta(days=days)
        response = requests.get(
            "https://api.calendly.com/scheduled_events",
            params={
                "min_start_time": now.isoformat() + "Z",
                "max_start_time": max_time.isoformat() + "Z",
                "status": "active"
            },
            headers=self.headers
        )
        return response.json()["collection"]

def send_scheduling_invite(candidate: dict, stage: str, event_type_id: str) -> dict:
    """Send personalized scheduling link to candidate."""
    cal = CalendlyIntegration(CALENDLY_TOKEN)
    scheduling_link = cal.create_interview_link(event_type_id, candidate["email"])

    send_email(
        to=candidate["email"],
        subject=f"Schedule your {stage} interview — {JOB_TITLE} at {COMPANY_NAME}",
        body=f"""Hi {candidate['first_name']},

Thank you for applying! We'd love to learn more about you.

Please use the link below to schedule your {stage} at a time that works best for you:
{scheduling_link}

The slot will expire in 5 days — please book as soon as possible.

Looking forward to speaking with you!

{RECRUITER_NAME} | Talent Acquisition
{COMPANY_NAME}
"""
    )
    return {"link": scheduling_link, "expires_at": (datetime.now() + timedelta(days=5)).isoformat()}
```

## Automated Candidate Communications

```python
CANDIDATE_EMAIL_TEMPLATES = {
    "application_received": {
        "subject": "We received your application — {job_title} at {company}",
        "body": "Thank you for applying to {job_title}. Our team will review your application within 5 business days..."
    },
    "moving_forward": {
        "subject": "Next steps for your {company} application",
        "body": "We reviewed your background and would love to continue the conversation..."
    },
    "rejection_after_screen": {
        "subject": "Your application to {company}",
        "body": "Thank you for your interest in the {job_title} role. After careful review, we've decided to move forward with other candidates whose backgrounds more closely match our current needs..."
    },
    "offer_extended": {
        "subject": "Offer Letter — {job_title} at {company}",
        "body": "We're excited to offer you the position of {job_title}..."
    },
    "interview_reminder": {
        "subject": "Reminder: Your interview tomorrow at {time}",
        "body": "Just a reminder of your {stage} interview scheduled for tomorrow..."
    }
}

def send_candidate_update(candidate: dict, template_name: str, stage: str = None):
    template = CANDIDATE_EMAIL_TEMPLATES[template_name]
    subject = template["subject"].format(**candidate, stage=stage)
    body = template["body"].format(**candidate, stage=stage)
    send_email(to=candidate["email"], subject=subject, body=body)
```

## Offer Letter Generation

```python
def generate_offer_letter(candidate: dict, offer_details: dict) -> str:
    """Generate personalized offer letter from template."""
    template = load_template("offer_letter_template.docx")

    merge_fields = {
        "{{CANDIDATE_NAME}}": candidate["full_name"],
        "{{JOB_TITLE}}": offer_details["title"],
        "{{START_DATE}}": offer_details["start_date"],
        "{{SALARY}}": f"${offer_details['salary']:,}",
        "{{EQUITY}}": offer_details.get("equity", "N/A"),
        "{{BONUS_TARGET}}": offer_details.get("bonus_target", "N/A"),
        "{{MANAGER}}": offer_details["reporting_to"],
        "{{OFFER_EXPIRY}}": (datetime.now() + timedelta(days=5)).strftime("%B %d, %Y"),
        "{{SIGNING_DATE}}": datetime.now().strftime("%B %d, %Y"),
    }

    for field, value in merge_fields.items():
        template = template.replace(field, str(value))

    # Save as PDF
    pdf_path = f"offers/{candidate['id']}_offer_{datetime.now().strftime('%Y%m%d')}.pdf"
    save_as_pdf(template, pdf_path)
    return pdf_path

def send_offer_via_docusign(candidate: dict, offer_pdf_path: str) -> dict:
    """Send offer letter for e-signature via DocuSign."""
    envelope_id = docusign_client.create_envelope(
        template_id=OFFER_TEMPLATE_ID,
        signers=[{
            "email": candidate["email"],
            "name": candidate["full_name"],
            "recipientId": "1",
            "routingOrder": "1",
        }],
        document_base64=encode_pdf(offer_pdf_path)
    )
    return {"envelope_id": envelope_id, "status": "sent"}
```

## New Hire Onboarding Automation

```python
ONBOARDING_CHECKLIST = {
    "day_minus_7": [
        "send_welcome_email",
        "provision_email_account",
        "order_equipment",
        "create_slack_account",
    ],
    "day_0": [
        "send_first_day_guide",
        "schedule_week_1_check_in",
        "assign_onboarding_buddy",
        "enroll_in_payroll",
    ],
    "day_30": [
        "send_30_day_survey",
        "schedule_30_day_review",
        "confirm_benefits_enrolled",
    ],
    "day_90": [
        "send_90_day_survey",
        "schedule_90_day_review",
        "complete_probation_review",
    ]
}

def trigger_onboarding_workflow(new_hire: dict, start_date: datetime):
    """Schedule all onboarding tasks for a new hire."""
    for days_offset_str, tasks in ONBOARDING_CHECKLIST.items():
        days_offset = int(days_offset_str.replace("day_minus_", "-").replace("day_", ""))
        trigger_date = start_date + timedelta(days=days_offset)

        for task in tasks:
            schedule_hr_task(
                assignee="hr_team",
                task=task,
                new_hire_id=new_hire["id"],
                due_date=trigger_date
            )
```
