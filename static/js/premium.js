// Premium features JavaScript
class PremiumManager {
    constructor() {
        this.init();
    }
    
    init() {
        this.checkApplicationLimit();
        this.setupEventListeners();
        this.startPeriodicUpdates();
    }
    
    checkApplicationLimit() {
        fetch('/api/check-application-limit')
            .then(response => response.json())
            .then(data => {
                this.updateLimitDisplay(data);
            })
            .catch(error => {
                console.error('Error checking application limit:', error);
            });
    }
    
    updateLimitDisplay(data) {
        const limitElement = document.getElementById('application-limit');
        if (limitElement) {
            if (data.is_premium) {
                limitElement.innerHTML = '<i class="fas fa-infinity text-success"></i> Unlimited';
            } else {
                limitElement.innerHTML = `${data.remaining} remaining today`;
                if (data.remaining <= 5) {
                    limitElement.classList.add('text-warning');
                }
                if (data.remaining === 0) {
                    limitElement.classList.remove('text-warning');
                    limitElement.classList.add('text-danger');
                }
            }
        }
    }
    
    setupEventListeners() {
        // Application form submission
        const applicationForms = document.querySelectorAll('.application-form');
        applicationForms.forEach(form => {
            form.addEventListener('submit', (e) => {
                this.handleApplicationSubmit(e, form);
            });
        });
    }
    
    handleApplicationSubmit(event, form) {
        // Check limit before submission
        fetch('/api/check-application-limit')
            .then(response => response.json())
            .then(data => {
                if (!data.can_apply) {
                    event.preventDefault();
                    this.showUpgradePrompt();
                }
            })
            .catch(error => {
                console.error('Error checking limit:', error);
            });
    }
    
    showUpgradePrompt() {
        const upgradeModal = `
            <div class="modal fade" id="upgradePrompt" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header bg-warning">
                            <h5 class="modal-title text-dark">
                                <i class="fas fa-exclamation-triangle"></i> Daily Limit Reached
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body text-center">
                            <i class="fas fa-crown fa-3x text-warning mb-3"></i>
                            <h4>Upgrade to Premium</h4>
                            <p>You've reached your daily application limit of 24.</p>
                            <p><strong>Upgrade to premium for unlimited applications!</strong></p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Later</button>
                            <a href="/upgrade-to-premium" class="btn btn-warning">
                                <i class="fas fa-arrow-up"></i> Upgrade Now
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', upgradeModal);
        new bootstrap.Modal(document.getElementById('upgradePrompt')).show();
    }
    
    startPeriodicUpdates() {
        // Update every 5 minutes
        setInterval(() => {
            this.checkApplicationLimit();
        }, 300000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new PremiumManager();
});