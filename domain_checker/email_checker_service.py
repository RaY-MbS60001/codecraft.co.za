# email_checker_service.py
import smtplib
import socket
import dns.resolver
import threading
import time
import schedule
from datetime import datetime, timedelta
from learnership_emails import learnership_email_data, update_email_status
import logging

class EmailReachabilityChecker:
    def __init__(self):
        self.check_interval = 86400  # 24 hours in seconds
        self.is_running = False
        self.checker_thread = None
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def check_mx_record(self, domain):
        try: dns.resolver.resolve(domain, 'MX'); return True
        except: return False

    def check_smtp_connection(self, email):
        domain = email.split('@')[1]; start_time = time.time()
        try:
            if not self.check_mx_record(domain): return {"email": email, "status": "unreachable", "reason": "No MX record", "response_time": time.time() - start_time}
            mx_records = dns.resolver.resolve(domain, 'MX'); mx_record = str(mx_records[0].exchange).rstrip('.')
            with smtplib.SMTP(timeout=10) as server:
                server.connect(mx_record, 25); code, message = server.helo()
                if code == 250: code, message = server.mail('test@example.com'); return {"email": email, "status": "reachable" if code == 250 else "unreachable", "reason": f"SMTP code: {code}", "response_time": time.time() - start_time}
                return {"email": email, "status": "unreachable", "reason": f"HELO failed: {code}", "response_time": time.time() - start_time}
        except Exception as e: return {"email": email, "status": "error", "reason": str(e), "response_time": time.time() - start_time}

    def check_all_emails(self):
        self.logger.info("Starting 24-hour email reachability check...")
        for item in learnership_email_data:
            try:
                result = self.check_smtp_connection(item["email"]); update_email_status(item["email"], result["status"], result["response_time"]); self.logger.info(f"Checked {item['email']}: {result['status']}"); time.sleep(2)
            except Exception as e: self.logger.error(f"Error checking {item['email']}: {e}"); update_email_status(item["email"], "error", None)
        self.logger.info("24-hour email check completed.")

    def start_24h_checker(self):
        if self.is_running: return
        self.is_running = True; schedule.every(24).hours.do(self.check_all_emails); self.check_all_emails()
        def run_scheduler():
            while self.is_running: schedule.run_pending(); time.sleep(3600)
        self.checker_thread = threading.Thread(target=run_scheduler, daemon=True); self.checker_thread.start(); self.logger.info("24-hour email checker started")

    def stop_checker(self):
        self.is_running = False; schedule.clear(); self.logger.info("Email checker stopped")

    def get_reachable_learnerships(self):
        return [item for item in learnership_email_data if item["status"] == "reachable"]

    def get_stats(self):
        total = len(learnership_email_data); reachable = len([item for item in learnership_email_data if item["status"] == "reachable"]); unreachable = len([item for item in learnership_email_data if item["status"] in ["unreachable", "error"]]); checking = len([item for item in learnership_email_data if item["status"] == "checking"])
        return {"total": total, "reachable": reachable, "unreachable": unreachable, "checking": checking}

email_checker = EmailReachabilityChecker()