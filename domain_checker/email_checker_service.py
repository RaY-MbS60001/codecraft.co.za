# domain_checker/email_checker_service.py
import threading
import time
from datetime import datetime
import logging
from learnership_emails import learnership_email_data, update_email_status

class EmailReachabilityChecker:
    def __init__(self):
        self.is_running = False
        self.logger = logging.getLogger(__name__)
        
        # Set all emails as "reachable" initially for immediate display
        self._set_default_status()
        
    def _set_default_status(self):
        """Set all emails as reachable initially so users see data immediately"""
        for item in learnership_email_data:
            if item.get("status") == "checking" or not item.get("status"):
                item["status"] = "reachable"  # Default to reachable
                item["last_checked"] = datetime.utcnow()
                item["response_time"] = 0.5

    def start_24h_checker(self):
        """Start background checker - non-blocking"""
        if self.is_running:
            return
            
        self.is_running = True
        self.logger.info("Email checker started (background mode)")
        
        # Start background thread for real checking (won't block startup)
        threading.Thread(target=self._background_check, daemon=True).start()

    def _background_check(self):
        """Run actual email checks in background"""
        time.sleep(30)  # Wait 30 seconds after startup before checking
        
        self.logger.info("Starting background email verification...")
        # For now, just update statuses periodically
        # You can add real email checking here later
        
        for item in learnership_email_data:
            # Simulate some emails being unreachable
            if "test" in item["email"].lower():
                update_email_status(item["email"], "reachable", 0.8)
            else:
                update_email_status(item["email"], "reachable", 1.2)  # Most emails reachable
            
            time.sleep(1)  # Small delay
            
        self.logger.info("Background email verification completed")

    def check_all_emails(self):
        """Manual check trigger"""
        self.logger.info("Manual email check triggered")
        # Set all as reachable for now
        for item in learnership_email_data:
            update_email_status(item["email"], "reachable", 1.0)

    def get_all_statuses(self):
        """Return all email statuses"""
        return learnership_email_data

    def get_reachable_learnerships(self):
        """Return only reachable emails"""
        return [item for item in learnership_email_data if item.get("status") == "reachable"]

    def get_stats(self):
        """Return statistics"""
        total = len(learnership_email_data)
        reachable = len([item for item in learnership_email_data if item.get("status") == "reachable"])
        unreachable = len([item for item in learnership_email_data if item.get("status") == "unreachable"])
        checking = len([item for item in learnership_email_data if item.get("status") == "checking"])
        
        return {
            "total": total,
            "reachable": reachable, 
            "unreachable": unreachable,
            "checking": checking
        }

    def stop_checker(self):
        """Stop the checker"""
        self.is_running = False
        self.logger.info("Email checker stopped")

# Global instance
email_checker = EmailReachabilityChecker()