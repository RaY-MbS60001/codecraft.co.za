class EmailProgressTracker {
    constructor() {
        this.eventSource = null;
        this.isRunning = false;
        this.cancelled = false;
        this.init();
    }

    init() {
        // Add overlay div if it doesn't exist
        if (!document.getElementById('progress-overlay')) {
            const overlay = document.createElement('div');
            overlay.id = 'progress-overlay';
            overlay.className = 'progress-overlay';
            document.body.appendChild(overlay);
        }

        // Set up cancel button
        const cancelBtn = document.getElementById('cancel-sending');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.cancelSending());
        }
    }

    startProgress(totalEmails) {
        this.isRunning = true;
        this.cancelled = false;
        
        // Show progress container and overlay
        document.getElementById('progress-overlay').style.display = 'block';
        document.getElementById('email-progress-container').style.display = 'block';
        
        // Reset progress
        this.updateProgress(0, totalEmails, 'Preparing to send emails...');
        this.clearLog();
        
        // Connect to SSE endpoint
        this.connectToProgressStream();
    }

    connectToProgressStream() {
        this.eventSource = new EventSource('/email-progress-stream');
        
        this.eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleProgressUpdate(data);
        };

        this.eventSource.onerror = (error) => {
            console.error('Progress stream error:', error);
            this.addLogEntry('Connection error. Please refresh if progress stops.', 'error');
        };
    }

    handleProgressUpdate(data) {
        switch(data.type) {
            case 'progress':
                this.updateProgress(data.sent, data.total, data.message);
                break;
            case 'email_sent':
                this.addLogEntry(`✓ Email sent to ${data.company}`, 'success');
                break;
            case 'email_failed':
                this.addLogEntry(`✗ Failed to send to ${data.company}: ${data.error}`, 'error');
                break;
            case 'completed':
                this.completeProgress(data.sent, data.total, data.failed);
                break;
            case 'cancelled':
                this.cancelledProgress();
                break;
        }
    }

    updateProgress(sent, total, message) {
        const percentage = total > 0 ? Math.round((sent / total) * 100) : 0;
        
        document.getElementById('progress-fill').style.width = `${percentage}%`;
        document.getElementById('progress-percentage').textContent = `${percentage}%`;
        document.getElementById('progress-details').textContent = 
            `${message} (${sent}/${total})`;
    }

    addLogEntry(message, type = 'info') {
        const logContainer = document.getElementById('progress-log');
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        
        logContainer.appendChild(entry);
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    clearLog() {
        document.getElementById('progress-log').innerHTML = '';
    }

    completeProgress(sent, total, failed) {
        this.isRunning = false;
        this.closeEventSource();
        
        const successRate = total > 0 ? Math.round((sent / total) * 100) : 0;
        
        this.updateProgress(sent, total, 'All emails processed!');
        this.addLogEntry(`Completed! ${sent} sent, ${failed} failed (${successRate}% success rate)`, 'info');
        
        // Auto-close after 3 seconds
        setTimeout(() => {
            this.hideProgress();
        }, 3000);
    }

    cancelledProgress() {
        this.isRunning = false;
        this.closeEventSource();
        
        this.addLogEntry('Email sending cancelled by user', 'error');
        
        setTimeout(() => {
            this.hideProgress();
        }, 2000);
    }

    cancelSending() {
        if (this.isRunning) {
            this.cancelled = true;
            
            // Send cancel request to server
            fetch('/cancel-email-sending', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({cancel: true})
            });
            
            this.addLogEntry('Cancelling email sending...', 'info');
        }
    }

    hideProgress() {
        document.getElementById('progress-overlay').style.display = 'none';
        document.getElementById('email-progress-container').style.display = 'none';
        this.closeEventSource();
    }

    closeEventSource() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}

// Initialize progress tracker
const emailProgress = new EmailProgressTracker();

// Update your bulk email form submission
document.addEventListener('DOMContentLoaded', function() {
    const bulkEmailForm = document.getElementById('bulk-email-form');
    if (bulkEmailForm) {
        bulkEmailForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const selectedEmails = formData.getAll('selected_emails');
            
            if (selectedEmails.length === 0) {
                alert('Please select at least one company to send emails to.');
                return;
            }
            
            // Start progress tracking
            emailProgress.startProgress(selectedEmails.length);
            
            // Submit form
            fetch('/apply_bulk_email', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'started') {
                    emailProgress.addLogEntry('Email sending process started', 'info');
                } else {
                    emailProgress.addLogEntry('Failed to start email sending', 'error');
                    emailProgress.hideProgress();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                emailProgress.addLogEntry(`Error: ${error.message}`, 'error');
                emailProgress.hideProgress();
            });
        });
    }
});