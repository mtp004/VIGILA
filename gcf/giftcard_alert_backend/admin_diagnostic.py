import smtplib
import os
from datetime import datetime, timezone
from html import escape
from email.mime.text import MIMEText

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

PLATFORMS = [
    "gcx",
    "cardcash",
    "carddepot",
]

def count_platform_results(scraped_results: list) -> dict:
    counts = {p: {"success": 0, "failed": 0} for p in PLATFORMS}
    for res in scraped_results:
        website = res["website"]
        if website not in counts:
            continue
        if res["discounts"]:
            counts[website]["success"] += 1
        else:
            counts[website]["failed"] += 1
    return counts


def classify_platform_health(platform_results: dict) -> dict:
    failures = {}
    for platform, counts in platform_results.items():
        total = counts["success"] + counts["failed"]
        if total == 0:
            continue
        fail_rate = counts["failed"] / total
        if fail_rate == 1.0:
            failures[platform] = "scraper_broken"
        elif fail_rate > 0.5:
            failures[platform] = "timeout_issue"
    return failures


def _build_admin_email_html(platform_results: dict, platform_failures: dict,
                            unmapped_urls: list[str], bq_error: dict | None) -> str:
    run_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows_html = ""
    for platform, issue in platform_failures.items():
        counts = platform_results[platform]
        total = counts["success"] + counts["failed"]

        if issue == "scraper_broken":
            icon, label, diagnosis, color = (
                "🔴",
                f"100% failure ({counts['failed']}/{total})",
                "Diagnosis: Possible HTML structure change — update scraper selectors.",
                "#fff0f0",
            )
        else:
            fail_pct = int(counts["failed"] / total * 100)
            icon, label, diagnosis, color = (
                "🟡",
                f"{fail_pct}% failure ({counts['failed']}/{total})",
                "Diagnosis: Possible timeouts or rate limiting — check delays/headers.",
                "#fffbe6",
            )

        rows_html += f"""
        <tr style="background-color:{color};">
            <td style="padding:10px 14px;font-weight:bold;text-transform:uppercase;">{icon} {platform}</td>
            <td style="padding:10px 14px;">{label}</td>
            <td style="padding:10px 14px;color:#444;">{diagnosis}</td>
        </tr>"""

    sections = f"""
        <table style="width:100%;border-collapse:collapse;margin-top:16px;">
            <thead>
                <tr style="background-color:#2c3e50;color:white;">
                    <th style="padding:10px 14px;text-align:left;">Platform</th>
                    <th style="padding:10px 14px;text-align:left;">Status</th>
                    <th style="padding:10px 14px;text-align:left;">Diagnosis</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>""" if platform_failures else ""

    if bq_error:
        sections += f"""
        <h3 style="color:#c0392b;margin-top:24px;">BigQuery write failed</h3>
        <p>{bq_error['row_count']} listing rows were not recorded.</p>
        <pre style="background:#f6f6f6;padding:10px;white-space:pre-wrap;">{escape(bq_error['message'])}</pre>"""

    if unmapped_urls:
        items = "".join(f"<li>{escape(u)}</li>" for u in unmapped_urls)
        sections += f"""
        <h3 style="margin-top:24px;">Unmapped gift card URLs</h3>
        <p>Not in giftcard_catalog, so not recorded to BigQuery (alerts unaffected):</p>
        <ul>{items}</ul>"""

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;">
        <h2 style="color:#c0392b;">⚠️ Vigila — Platform Health Alert</h2>
        <p style="color:#888;font-size:12px;">{run_time}</p>{sections}
    </div>"""


def get_admin_email(db) -> str | None:
    try:
        doc = db.collection("app_config").document("admin").get()
        if not doc.exists:
            print("[admin_alerts] app_config/admin doc not found.")
            return None
        admin_email = doc.to_dict().get("admin_email")
        if not admin_email:
            print("[admin_alerts] admin_email field missing from app_config/admin.")
        return admin_email
    except Exception as e:
        print(f"[admin_alerts] Failed to read admin_email: {e}")
        return None


def alert_admin_on_failure(db, platform_results: dict, unmapped_urls: list[str] | None = None,
                           bq_error: dict | None = None) -> bool:
    platform_failures = classify_platform_health(platform_results)
    unmapped_urls = unmapped_urls or []

    if not platform_failures and not unmapped_urls and not bq_error:
        print("[admin_diagnostic] All platforms healthy.")
        return False

    admin_email = get_admin_email(db)
    if not admin_email or not SENDER_EMAIL or not APP_PASSWORD:
        print("[admin_diagnostic] Missing email config — skipping alert.")
        return False

    issue_types = set(platform_failures.values())
    if issue_types == {"scraper_broken"}:
        subject_tag = "Scraper Format Error"
    elif issue_types == {"timeout_issue"}:
        subject_tag = "Timeout Issues"
    elif issue_types:
        subject_tag = "Mixed Platform Issues"
    else:
        subject_tag = "Data Pipeline Issues"

    flagged = [p.upper() for p in platform_failures]
    if bq_error:
        flagged.append("BIGQUERY")
    if unmapped_urls:
        flagged.append(f"{len(unmapped_urls)} UNMAPPED URLS")
    subject = f"[VIGILA ALERT] {subject_tag} — {', '.join(flagged)}"

    html = _build_admin_email_html(platform_results, platform_failures, unmapped_urls, bq_error)
    msg = MIMEText(html, "html")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = admin_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
        print(f"[admin_diagnostic] Alert sent to {admin_email} — {subject}")
        return True
    except Exception as e:
        print(f"[admin_diagnostic] SMTP error: {e}")
        return False