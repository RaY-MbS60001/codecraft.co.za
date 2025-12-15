# init_email_system.py
from email_checker_service import email_checker
from learnership_emails import learnership_email_data

def initialize_email_system():
    print("Initializing 24-hour email reachability system..."); email_checker.start_24h_checker(); print(f"Monitoring {len(learnership_email_data)} learnership emails"); print("System will check emails every 24 hours automatically")

if __name__ == "__main__": initialize_email_system()