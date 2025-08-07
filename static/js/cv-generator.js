// Add this to your main script.js file

document.addEventListener('DOMContentLoaded', function() {
    // Wait for iframe to load
    const iframe = document.getElementById('templateFrame');
    let isTemplateReady = false;
    
    // Listen for template ready message
    window.addEventListener('message', function(event) {
        if (event.data.type === 'TEMPLATE_READY') {
            isTemplateReady = true;
            updateAllFields(); // Initial update
        }
    });
    
    // Function to send data to iframe
    function sendToTemplate(type, data) {
        if (isTemplateReady && iframe && iframe.contentWindow) {
            iframe.contentWindow.postMessage({
                type: type,
                data: data
            }, '*');
        }
    }
    
    // Update all fields at once
    function updateAllFields() {
        const allData = {
            personalInfo: getPersonalInfo(),
            summary: document.getElementById('summary').value,
            skills: getSkills(),
            experiences: getExperiences(),
            education: getEducation(),
            achievements: getAchievements(),
            languages: getLanguages(),
            photoUrl: currentPhotoUrl
        };
        
        sendToTemplate('UPDATE_ALL', allData);
    }
    
    // Helper functions to get form data
    function getPersonalInfo() {
        return {
            fullName: document.getElementById('fullName').value,
            jobTitle: document.getElementById('jobTitle').value,
            email: document.getElementById('email').value,
            phone: document.getElementById('phone').value,
            location: document.getElementById('location').value,
            nationality: document.getElementById('nationality').value,
            status: document.getElementById('status').value,
            linkedin: document.getElementById('linkedin').value,
            portfolio: document.getElementById('portfolio').value
        };
    }
    
    function getSkills() {
        return {
            programmingSkills: document.getElementById('programmingSkills').value,
            frameworks: document.getElementById('frameworks').value,
            databases: document.getElementById('databases').value,
            tools: document.getElementById('tools').value
        };
    }
    
    function getExperiences() {
        const experiences = [];
        const experienceItems = document.querySelectorAll('.experience-item');
        
        experienceItems.forEach(item => {
            const experience = {
                jobTitle: item.querySelector('.job-title').value,
                company: item.querySelector('.company').value,
                startDate: item.querySelector('.start-date').value,
                endDate: item.querySelector('.end-date').value,
                location: item.querySelector('.job-location').value,
                description: item.querySelector('.job-description').value
            };
            experiences.push(experience);
        });
        
        return { experiences };
    }
    
    function getEducation() {
        const education = [];
        const educationItems = document.querySelectorAll('.education-item');
        
        educationItems.forEach(item => {
            const edu = {
                degree: item.querySelector('.degree').value,
                fieldOfStudy: item.querySelector('.field-of-study').value,
                institution: item.querySelector('.institution').value,
                startYear: item.querySelector('.edu-start').value,
                endYear: item.querySelector('.edu-end').value,
                location: item.querySelector('.edu-location').value,
                info: item.querySelector('.edu-info').value
            };
            education.push(edu);
        });
        
        return { education };
    }
    
    function getAchievements() {
        const achievements = [];
        const achievementItems = document.querySelectorAll('.achievement-item');
        
        achievementItems.forEach(item => {
            const achievement = {
                title: item.querySelector('.achievement-title').value,
                description: item.querySelector('.achievement-description').value
            };
            achievements.push(achievement);
        });
        
        return { achievements };
    }
    
    function getLanguages() {
        const languages = [];
        const languageItems = document.querySelectorAll('.language-item');
        
        languageItems.forEach(item => {
            const language = {
                name: item.querySelector('.language-name').value,
                level: item.querySelector('.language-level').value
            };
            languages.push(language);
        });
        
        return { languages };
    }
    
    // Add event listeners to all form inputs
    function setupEventListeners() {
        // Personal info inputs
        const personalInputs = ['fullName', 'jobTitle', 'email', 'phone', 'location', 'nationality', 'status', 'linkedin', 'portfolio'];
        personalInputs.forEach(id => {
            const input = document.getElementById(id);
            if (input) {
                input.addEventListener('input', () => {
                    sendToTemplate('UPDATE_PERSONAL_INFO', getPersonalInfo());
                });
            }
        });
        
        // Summary
        const summaryInput = document.getElementById('summary');
        if (summaryInput) {
            summaryInput.addEventListener('input', () => {
                sendToTemplate('UPDATE_SUMMARY', { summary: summaryInput.value });
            });
        }
        
        // Skills
        const skillInputs = ['programmingSkills', 'frameworks', 'databases', 'tools'];
        skillInputs.forEach(id => {
            const input = document.getElementById(id);
            if (input) {
                input.addEventListener('input', () => {
                    sendToTemplate('UPDATE_SKILLS', getSkills());
                });
            }
        });
        
        // Experience - use event delegation for dynamic content
        document.addEventListener('input', function(e) {
            if (e.target.closest('.experience-item')) {
                sendToTemplate('UPDATE_EXPERIENCE', getExperiences());
            }
            if (e.target.closest('.education-item')) {
                sendToTemplate('UPDATE_EDUCATION', getEducation());
            }
            if (e.target.closest('.achievement-item')) {
                sendToTemplate('UPDATE_ACHIEVEMENTS', getAchievements());
            }
            if (e.target.closest('.language-item')) {
                sendToTemplate('UPDATE_LANGUAGES', getLanguages());
            }
        });
    }
    
    // Photo handling
    let currentPhotoUrl = null;
    const photoInput = document.getElementById('profilePhoto');
    if (photoInput) {
        photoInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    currentPhotoUrl = e.target.result;
                    sendToTemplate('UPDATE_PHOTO', { photoUrl: currentPhotoUrl });
                };
                reader.readAsDataURL(file);
            }
        });
    }
    
    // Template selector
    const templateSelector = document.getElementById('templateSelector');
    if (templateSelector) {
        templateSelector.addEventListener('change', function(e) {
            const newTemplate = e.target.value;
            iframe.src = `templates/${newTemplate}.html`;
            isTemplateReady = false;
            
            // Wait for new template to load
            iframe.onload = function() {
                setTimeout(() => {
                    updateAllFields();
                }, 500);
            };
        });
    }
    
    // Setup all event listeners
    setupEventListeners();
    
    // Initial iframe load
    iframe.onload = function() {
        setTimeout(() => {
            updateAllFields();
        }, 500);
    };
});

// Update your existing add buttons to trigger preview updates
document.getElementById('addExperience')?.addEventListener('click', function() {
    // Your existing add experience code here
    // Then trigger update:
    setTimeout(() => {
        const event = new Event('input', { bubbles: true });
        document.querySelector('.experience-item:last-child .job-title').dispatchEvent(event);
    }, 100);
});

// Similar updates for other add buttons...