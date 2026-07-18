import os
import smtplib
from email.mime.text import MIMEText
from fastapi import FastAPI, HTTPException, Response
import firebase_admin
from firebase_admin import firestore, auth
from scraper_orchestrator import run_orchestrator, detect_website
from admin_diagnostic import count_platform_results, alert_admin_on_failure
import traceback

if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

app = FastAPI()


def send_giftcard_email(to_email: str, alert_reports: list[dict]) -> bool:
    if not to_email or not SENDER_EMAIL or not APP_PASSWORD:
        return False
        
    # 1. Extract unique brand names for the subject line
    unique_brands = sorted(list(set(report["brand"] for report in alert_reports)))
    brands_string = ", ".join(unique_brands)
    subject = f"Vigila Giftcard Alert: {brands_string}"
    
    # 2. Build the HTML body directly from the metadata structures
    html_snippets = []
    for report in alert_reports:
        brand_header = f"<h3>{report['brand'].upper()} (Target: {report['min_discount']}%, Limits: ${report['min_val']} - ${report['max_val']})</h3>"
        html_snippets.append(brand_header)
        
        for site, cards_list in report["platform_groups"].items():
            url = report.get("urls", {}).get(site, "")
            site_label = f"<a href='{url}'>{site}</a>" if url else site
            platform_html = f"<p style='margin-bottom: 5px; margin-left: 20px;'><b>{site_label}:</b></p>"
            platform_html += "<ul style='margin-top: 5px; margin-left: 40px;'>"
            for c in cards_list:
                platform_html += f"<li>${c['face_value']} GC for <b>${c['sale_price']}</b> ({c['discount_pct']}% OFF)</li>"
            platform_html += "</ul>"
            html_snippets.append(platform_html)
            
    html_body = "".join(html_snippets)
    html_body += "<br><p>Happy Savings,<br>Vigila Team</p>"
    
    # 3. Package and dispatch the email message
    msg = MIMEText(html_body, 'html')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"SMTP error: {e}")
        return False


@app.post("/run-giftcard-alerts")
async def trigger_giftcard_alerts():
    try:
        print("\n--- STARTING GIFT CARD ALERT RUN ---")
        alerts_query = db.collection_group("giftcard_alerts").stream()
        
        brand_user_alerts = {}
        
        for doc in alerts_query:
            data = doc.to_dict()
            
            if not data.get("isActive", True):
                continue
                
            brand = data.get("brand", "")
            if not brand:
                continue
                
            user_ref = doc.reference.parent.parent
            if not user_ref:
                continue
            uid = user_ref.id
            alert_id = doc.id
            
            if brand not in brand_user_alerts:
                brand_user_alerts[brand] = {}
            if uid not in brand_user_alerts[brand]:
                brand_user_alerts[brand][uid] = {}
                
            brand_user_alerts[brand][uid][alert_id] = data

        if not brand_user_alerts:
            print("[DEBUG] No active alerts found in database.")
            return {"status": "success", "message": "No active alerts to process."}

        # Collect unique URLs
        all_urls = list({
            url
            for users_dict in brand_user_alerts.values()
            for alerts_map in users_dict.values()
            for alert_data in alerts_map.values()
            for url in alert_data.get("urls", {}).values()
            if url and alert_data.get("platforms", {}).get(detect_website(url), {}).get("active", True)
        })

        scraped_results = await run_orchestrator(all_urls, db)

        # Store results by URL
        platform_results = count_platform_results(scraped_results)
        url_results = {}
        for res in scraped_results:
            url_results[res["url"]] = {"website": res["website"], "discounts": res["discounts"]}
            print(f"[DEBUG] Scraped '{res['url']}' via {res['website']} (Found {len(res['discounts'])} cards)")

        emails_to_send = {}
        updates_batch = db.batch()

        for brand, users_dict in brand_user_alerts.items():
            print(f"\n[DEBUG] Processing evaluation loop for Brand: '{brand}'")
            
            for uid, alerts_map in users_dict.items():
                for alert_id, alert_data in alerts_map.items():
                    min_discount = float(alert_data.get("minDiscountPercent", 0.0))
                    min_val = float(alert_data.get("minCardValue", 0))
                    max_val = float(alert_data.get("maxCardValue", 999999))
                    platforms_toggle = alert_data.get("platforms", {})

                    previously_satisfied = set(alert_data.get("satisfied_by", []))
                    print(f"  -> Alert ID: {alert_id} for User: {uid}")
                    print(f"     Criteria: min_discount={min_discount}%, range=[${min_val}, ${max_val}]")
                    print(f"     Allowed platforms toggle: {platforms_toggle}")
                    print(f"     Previously satisfied in DB: {previously_satisfied}")
                    
                    triggered_cards = []
                    satisfied_platforms = set()

                    highest_discounts_this_alert = {}
                    for platform_name, url in alert_data.get("urls", {}).items():
                        if not url or url not in url_results:
                            continue
                        result = url_results[url]
                        website = result["website"]
                        is_allowed = platforms_toggle.get(website, {}).get("active", True)
                        print(f"     Checking platform: '{website}' | Allowed? {is_allowed}")
                        if not is_allowed:
                            continue
                        for card in result["discounts"]:
                            face = float(card.get("face_value", 0))
                            pct = float(card.get("discount_pct", 0))

                            if website not in highest_discounts_this_alert or pct > highest_discounts_this_alert[website]:
                                highest_discounts_this_alert[website] = pct
                            if pct >= min_discount and min_val <= face <= max_val:
                                triggered_cards.append({**card, "website": website})
                                satisfied_platforms.add(website)
                                
                    print(f"     Currently satisfied this run: {satisfied_platforms}")
                    
                    update_payload = {
                        "lastCheckedAt": firestore.SERVER_TIMESTAMP,
                        "satisfied_by": list(satisfied_platforms)
                    }
                    for platform_name, url in alert_data.get("urls", {}).items():
                        if not url:
                            continue
                        website = platform_name
                        update_payload[f"platforms.{website}.highest_discount"] = highest_discounts_this_alert.get(website)
                    doc_ref = db.collection("users").document(uid).collection("giftcard_alerts").document(alert_id)
                    updates_batch.update(doc_ref, update_payload)

                    newly_satisfied = satisfied_platforms - previously_satisfied
                    newly_triggered_cards = [c for c in triggered_cards if c["website"] in newly_satisfied]
                    
                    print(f"     Set math result (newly_satisfied): {newly_satisfied}")
                    print(f"     Number of cards in newly_triggered_cards: {len(newly_triggered_cards)}")

                    if newly_triggered_cards:
                        newly_triggered_cards.sort(key=lambda x: x["discount_pct"], reverse=True)
                        
                        if uid not in emails_to_send:
                            emails_to_send[uid] = []
                            
                        # Group the matching cards by their website platform name string
                        platform_groups = {}
                        for c in newly_triggered_cards[:10]:
                            site = c['website']
                            if site not in platform_groups:
                                platform_groups[site] = []
                            platform_groups[site].append(c)
                            
                        # Package raw metadata structures into the queue tracking array
                        report_metadata = {
                            "brand": brand,
                            "min_discount": min_discount,
                            "min_val": min_val,
                            "max_val": max_val,
                            "platform_groups": platform_groups,
                            "urls": alert_data.get("urls", {}),
                        }
                        
                        emails_to_send[uid].append(report_metadata)
                    else:
                        print("     [SKIP] No email snippet built (No new platforms crossed threshold).")

        updates_batch.commit()

        users_emailed = 0
        for uid, alert_reports in emails_to_send.items():
            try:
                user_record = auth.get_user(uid)
                # Pass the raw array of reporting objects directly into the email utility
                if send_giftcard_email(user_record.email, alert_reports):
                    users_emailed += 1
            except Exception as e:
                print(f"Failed to fetch or email user {uid}: {e}")

        print(f"--- RUN FINISHED: Emailed {users_emailed} users ---\n")
        alert_admin_on_failure(db, platform_results)
        return {
            "status": "success",
            "brands_checked": len(brand_user_alerts),
            "users_emailed": users_emailed
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/_health")
def health_check():
    return Response(status_code=200)