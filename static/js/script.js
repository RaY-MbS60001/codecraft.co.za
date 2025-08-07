// Flash message auto-hide
document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            message.style.transform = 'translateX(100%)';
            setTimeout(() => message.remove(), 300);
        }, 5000);
    });

    // Enhanced file input handling for document upload
    const documentForm = document.querySelector('form[method="POST"]');
    const fileInput = document.querySelector('input[name="document"]');
    const submitButton = document.querySelector('button[type="submit"]');
    
    if (fileInput && documentForm) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                console.log('File selected:', file.name);
                
                // Show file name
                const fileName = document.createElement('div');
                fileName.className = 'selected-file';
                fileName.textContent = `Selected: ${file.name}`;
                
                // Remove previous file name display
                const existingFileName = document.querySelector('.selected-file');
                if (existingFileName) {
                    existingFileName.remove();
                }
                
                // Add file name after the input
                fileInput.parentNode.insertBefore(fileName, fileInput.nextSibling);
                
                // Enable submit button
                if (submitButton) {
                    submitButton.disabled = false;
                }
            }
        });
        
        // Prevent form submission without file
        documentForm.addEventListener('submit', function(e) {
            if (!fileInput.files || fileInput.files.length === 0) {
                e.preventDefault();
                alert('Please select a file to upload.');
                return false;
            }
        });
    }

    // Improved loading state for forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitButton = form.querySelector('[type="submit"]');
            const fileInput = form.querySelector('input[type="file"]');
            
            // Check if file is selected for file upload forms
            if (fileInput && fileInput.files.length === 0) {
                e.preventDefault();
                alert('Please select a file to upload.');
                return false;
            }
            
            if (submitButton && !submitButton.disabled) {
                submitButton.disabled = true;
                submitButton.classList.add('loading');
                const originalText = submitButton.textContent;
                submitButton.innerHTML = '<span class="spinner"></span> Processing...';
                
                // Re-enable button after a timeout in case of errors
                setTimeout(() => {
                    submitButton.disabled = false;
                    submitButton.classList.remove('loading');
                    submitButton.innerHTML = originalText;
                }, 10000); // 10 seconds timeout
            }
        });
    });

    // Confirm delete actions
    const deleteButtons = document.querySelectorAll('.btn-delete');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
                e.preventDefault();
            }
        });
    });

    // Toggle password visibility
    const passwordToggles = document.querySelectorAll('.password-toggle');
    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const input = this.previousElementSibling;
            if (input.type === 'password') {
                input.type = 'text';
                this.innerHTML = '<svg>...</svg>'; // Hide icon
            } else {
                input.type = 'password';
                this.innerHTML = '<svg>...</svg>'; // Show icon
            }
        });
    });

    // Table row hover effect
    const tableRows = document.querySelectorAll('.users-table tbody tr');
    tableRows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f9fafb';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Form validation feedback
    const formInputs = document.querySelectorAll('.form-control');
    formInputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.value.trim() === '' && this.hasAttribute('required')) {
                this.classList.add('error');
            } else {
                this.classList.remove('error');
            }
        });
    });

    // Profile picture preview (if file upload is added)
    const generalFileInput = document.querySelector('input[type="file"]:not([name="document"])');
    if (generalFileInput) {
        generalFileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file && file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const preview = document.querySelector('.avatar-preview');
                    if (preview) {
                        preview.src = e.target.result;
                    }
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // File upload drag and drop functionality
    const uploadArea = document.querySelector('.upload-area');
    if (uploadArea) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, unhighlight, false);
        });

        function highlight(e) {
            uploadArea.classList.add('drag-over');
        }

        function unhighlight(e) {
            uploadArea.classList.remove('drag-over');
        }

        uploadArea.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (files.length > 0 && fileInput) {
                fileInput.files = files;
                fileInput.dispatchEvent(new Event('change'));
            }
        }
    }
});

// Utility functions
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Search functionality (if search is added)
const searchInput = document.querySelector('.search-input');
if (searchInput) {
    searchInput.addEventListener('input', debounce(function(e) {
        const searchTerm = e.target.value.toLowerCase();
        const rows = document.querySelectorAll('.users-table tbody tr');
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    }, 300));
}

// Progress bar for file uploads
function updateProgressBar(percent) {
    const progressBar = document.querySelector('.progress-bar');
    if (progressBar) {
        progressBar.style.width = percent + '%';
        progressBar.textContent = Math.round(percent) + '%';
    }
}

// File size validation
function validateFileSize(file, maxSizeMB = 5) {
    const maxSize = maxSizeMB * 1024 * 1024; // Convert to bytes
    if (file.size > maxSize) {
        alert(`File size must be less than ${maxSizeMB}MB`);
        return false;
    }
    return true;
}

// File type validation
function validateFileType(file, allowedTypes = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png']) {
    const fileExtension = file.name.split('.').pop().toLowerCase();
    if (!allowedTypes.includes(fileExtension)) {
        alert(`File type .${fileExtension} is not allowed. Allowed types: ${allowedTypes.join(', ')}`);
        return false;
    }
    return true;
}

// Enhanced error handling for AJAX requests
function handleAjaxError(xhr, status, error) {
    console.error('AJAX Error:', {
        status: xhr.status,
        statusText: xhr.statusText,
        error: error,
        response: xhr.responseText
    });
    
    let errorMessage = 'An error occurred. Please try again.';
    
    if (xhr.status === 0) {
        errorMessage = 'Network error. Please check your connection.';
    } else if (xhr.status === 404) {
        errorMessage = 'Resource not found.';
    } else if (xhr.status === 500) {
        errorMessage = 'Server error. Please try again later.';
    }
    
    alert(errorMessage);
}

// Loading spinner utility
function showSpinner(element) {
    element.innerHTML = '<span class="spinner"></span> Loading...';
    element.disabled = true;
}

function hideSpinner(element, originalText) {
    element.innerHTML = originalText;
    element.disabled = false;
}

// Document ready state check
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        console.log('DOM fully loaded and parsed');
    });
} else {
    console.log('DOM already loaded');
}