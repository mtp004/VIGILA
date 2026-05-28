import os
import smtplib
from email.mime.text import MIMEText
from fastapi import FastAPI, HTTPException, Response
import firebase_admin
from firebase_admin import firestore, auth
from scraper_orchestrator import run_orchestrator
import traceback

if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

app = FastAPI()


def send_giftcard_email(to_email: str, html_snippets: list[str]) -> bool:
    if not to_email or not SENDER_EMAIL or not APP_PASSWORD:
        return False
        
    html_body = "<h2>Your Vigila Giftcard Alerts</h2>"
    html_body += "<p>The following brands have gift cards meeting your target discount thresholds:</p>"
    html_body += "".join(html_snippets)
    html_body += "<br><p>Happy Savings,<br>Vigila Team</p>"
    
    msg = MIMEText(html_body, 'html')
    msg['Subject'] = "Vigila - Giftcard Targets Reached!"
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
        alerts_query = db.collection_group("giftcard_alerts").stream()
        
        brand_user_alerts = {}
        
        for doc in alerts_query:
            data = doc.to_dict()
            
            if not data.get("isActive", True):
                continue
                
            brand = data.get("brand", "").lower()
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
            return {"status": "success", "message": "No active alerts to process."}

        all_urls = set()
        for brand, users_dict in brand_user_alerts.items():
            for uid, alerts_map in users_dict.items():
                for alert_id, alert_data in alerts_map.items():
                    urls_map = alert_data.get("urls", {})
                    for platform_name, url in urls_map.items():
                        if url:
                            all_urls.add(url)

        scraped_results = await run_orchestrator(list(all_urls))

        scraped_by_brand = {}
        for res in scraped_results:
            b = res["brand"]
            w = res["website"]
            if b not in scraped_by_brand:
                scraped_by_brand[b] = {}
            scraped_by_brand[b][w] = res["discounts"]

        emails_to_send = {}
        updates_batch = db.batch()

        for brand, users_dict in brand_user_alerts.items():
            brand_results = scraped_by_brand.get(brand, {})
            
            for uid, alerts_map in users_dict.items():
                for alert_id, alert_data in alerts_map.items():
                    min_discount = float(alert_data.get("minDiscountPercent", 0.0))
                    min_val = float(alert_data.get("minCardValue", 0))
                    max_val = float(alert_data.get("maxCardValue", 999999))
                    platforms_toggle = alert_data.get("platforms", {})
                    
                    triggered_cards = []
                    satisfied_platforms = set()
                    
                    for website, cards in brand_results.items():
                        if not platforms_toggle.get(website, True):
                            continue
                            
                        for card in cards:
                            face = float(card.get("face_value", 0))
                            pct = float(card.get("discount_pct", 0))
                            
                            if pct >= min_discount and min_val <= face <= max_val:
                                triggered_cards.append({**card, "website": website})
                                satisfied_platforms.add(website)
                                
                    doc_ref = db.collection("users").document(uid).collection("giftcard_alerts").document(alert_id)
                    updates_batch.update(doc_ref, {
                        "lastCheckedAt": firestore.SERVER_TIMESTAMP,
                        "satisfied_by": list(satisfied_platforms)
                    })
                                
                    if triggered_cards:
                        triggered_cards.sort(key=lambda x: x["discount_pct"], reverse=True)
                        
                        if uid not in emails_to_send:
                            emails_to_send[uid] = []
                            
                        # Build header with boundaries included
                        snippet = f"<h3>{brand.upper()} (Target: {min_discount}%, Limits: ${min_val} - ${max_val})</h3>"
                        
                        # Group the matching cards by their website platform
                        platform_groups = {}
                        for c in triggered_cards[:10]:  # Upbed to top 10 total offers
                            site = c['website'].upper()
                            if site not in platform_groups:
                                platform_groups[site] = []
                            platform_groups[site].append(c)
                            
                        # Append the grouped items to the email layout string
                        for site, cards_list in platform_groups.items():
                            snippet += f"<p style='margin-bottom: 5px;'><b>{site}:</b></p><ul style='margin-top: 5px;'>"
                            for c in cards_list:
                                snippet += f"<li>${c['face_value']} GC for <b>${c['sale_price']}</b> ({c['discount_pct']}% OFF)</li>"
                            snippet += "</ul>"
                        
                        emails_to_send[uid].append(snippet)

        updates_batch.commit()

        users_emailed = 0
        for uid, snippets in emails_to_send.items():
            try:
                user_record = auth.get_user(uid)
                if send_giftcard_email(user_record.email, snippets):
                    users_emailed += 1
            except Exception as e:
                print(f"Failed to fetch or email user {uid}: {e}")

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


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)