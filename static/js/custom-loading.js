class CustomLoadingManager {
    constructor() {
        this.overlay = document.getElementById('custom-loading-overlay');
        this.titleElement = document.getElementById('loading-title');
        this.descriptionElement = document.getElementById('loading-description');
        this.progressBar = document.querySelector('.loading-progress-bar');
        this.isLoading = false;
        this.init();
    }

    init() {
        // Show loading on form submissions
        this.attachFormHandlers();
        
        // Show loading on navigation
        this.attachNavigationHandlers();
        
        // Hide loading when page loads completely
        window.addEventListener('load', () => {
            setTimeout(() => this.hide(), 500); // Small delay for smooth transition
        });

        // Handle browser navigation
        window.addEventListener('pageshow', (e) => {
            if (e.persisted) {
                this.hide();
            }
        });

        // Handle browser back button
        window.addEventListener('beforeunload', () => {
            this.show({
                title: 'Loading...',
                description: 'Please wait'
            });
        });
    }

    show(options = {}) {
        if (this.isLoading) return;
        
        this.isLoading = true;
        
        // Set custom messages
        this.titleElement.textContent = options.title || 'Loading...';
        this.descriptionElement.textContent = options.description || 'Please wait while we process your request';
        
        // Show overlay
        this.overlay.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Start progress if enabled
        if (options.showProgress) {
            this.startProgress();
        }
    }

    hide() {
        if (!this.isLoading) return;
        
        this.isLoading = false;
        this.overlay.classList.remove('active');
        document.body.style.overflow = '';
        this.resetProgress();
    }

    updateMessage(title, description) {
        if (title) this.titleElement.textContent = title;
        if (description) this.descriptionElement.textContent = description;
    }

    startProgress() {
        this.progressBar.style.animation = 'progressFlow 3s ease-in-out infinite';
    }

    resetProgress() {
        this.progressBar.style.animation = '';
        this.progressBar.style.width = '0%';
    }

    attachFormHandlers() {
        document.addEventListener('submit', (e) => {
            const form = e.target;
            
            // Skip if form has data-no-loading attribute
            if (form.hasAttribute('data-no-loading')) {
                return;
            }
            
            // Get custom messages from form data attributes
            const options = {
                title: form.dataset.loadingTitle || 'Processing...',
                description: form.dataset.loadingDescription || 'Please wait while we process your request',
                showProgress: form.dataset.showProgress === 'true'
            };

            // Handle different form types with specific messages
            if (form.classList.contains('login-form') || form.action.includes('login')) {
                options.title = 'Welcome Back!';
                options.description = 'Signing you into CodeCraftCo';
            } else if (form.classList.contains('application-form') || form.action.includes('apply')) {
                options.title = 'Submitting Application';
                options.description = 'Processing your learnership application';
                options.showProgress = true;
            } else if (form.classList.contains('upload-form') || form.enctype === 'multipart/form-data') {
                options.title = 'Uploading Files';
                options.description = 'Please wait while we upload your documents';
                options.showProgress = true;
            } else if (form.action.includes('register') || form.action.includes('signup')) {
                options.title = 'Creating Account';
                options.description = 'Setting up your CodeCraftCo account';
            }
            
            this.show(options);
        });
    }

    attachNavigationHandlers() {
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a[data-loading]');
            if (link && !link.getAttribute('href').startsWith('#') && 
                !link.hasAttribute('download') && 
                !link.getAttribute('href').startsWith('mailto:') &&
                !link.getAttribute('href').startsWith('tel:')) {
                
                const options = {
                    title: link.dataset.loadingTitle || 'Loading...',
                    description: link.dataset.loadingDescription || 'Loading page content',
                    showProgress: link.dataset.showProgress === 'true'
                };
                
                // Specific loading messages for different sections
                const href = link.getAttribute('href');
                if (href.includes('dashboard')) {
                    options.title = 'Loading Dashboard';
                    options.description = 'Preparing your personalized experience';
                } else if (href.includes('learnership')) {
                    options.title = 'Loading Opportunities';
                    options.description = 'Fetching available learnerships';
                } else if (href.includes('profile')) {
                    options.title = 'Loading Profile';
                    options.description = 'Getting your profile information';
                }
                
                this.show(options);
            }
        });
    }
}

// Initialize custom loading manager
document.addEventListener('DOMContentLoaded', () => {
    window.customLoading = new CustomLoadingManager();
});

// Global utility functions for manual control
function showCustomLoading(options = {}) {
    if (window.customLoading) {
        window.customLoading.show(options);
    }
}

function hideCustomLoading() {
    if (window.customLoading) {
        window.customLoading.hide();
    }
}

function updateLoadingMessage(title, description) {
    if (window.customLoading) {
        window.customLoading.updateMessage(title, description);
    }
}