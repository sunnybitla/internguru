// App State
const state = {
    token: localStorage.getItem('token') || null,
    username: localStorage.getItem('username') || null,
    profile: null,
    jobs: [],
    queue: [],
    history: [],
    selectedJob: null,
    activeQueueJobId: null
};

// Helper for authenticated requests
function authFetch(url, options = {}) {
    if (!options.headers) {
        options.headers = {};
    }
    if (state.token) {
        options.headers['Authorization'] = `Bearer ${state.token}`;
    }
    return fetch(url, options).then(r => {
        if (r.status === 401) {
            logout();
            throw new Error("Session expired. Please log in again.");
        }
        return r.json();
    });
}

// API Endpoints
const API = {
    register: (username, password) => fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    }).then(r => r.json().then(data => {
        if (!r.ok) throw new Error(data.detail || 'Registration failed');
        return data;
    })),
    login: (username, password) => fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    }).then(r => r.json().then(data => {
        if (!r.ok) throw new Error(data.detail || 'Login failed');
        return data;
    })),
    getProfile: () => authFetch('/api/profile'),
    saveProfile: (formData) => authFetch('/api/profile', { method: 'POST', body: formData }),
    getJobs: (search = '', internship = null, sync = false) => {
        let url = `/api/jobs?sync=${sync}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (internship !== null) url += `&internship=${internship}`;
        return authFetch(url);
    },
    getQueue: () => authFetch('/api/queue'),
    addToQueue: (jobId) => authFetch('/api/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId })
    }),
    updateCoverLetter: (jobId, coverLetter) => authFetch(`/api/queue/${jobId}/cover-letter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cover_letter: coverLetter })
    }),
    removeFromQueue: (jobId) => authFetch(`/api/queue/${jobId}`, { method: 'DELETE' }),
    getHistory: () => authFetch('/api/history'),
    clearHistory: () => authFetch('/api/history/clear', { method: 'POST' }),
    triggerRun: () => authFetch('/api/trigger-run', { method: 'POST' }),
    toggleDaemon: (enabled) => authFetch('/api/toggle-daemon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
    }),
    toggleDryRun: (enabled) => authFetch('/api/toggle-dry-run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
    }),
    getAuthConfig: () => fetch('/api/auth/config').then(r => r.json()),
    googleLogin: (credential) => fetch('/api/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential })
    }).then(r => r.json().then(data => {
        if (!r.ok) throw new Error(data.detail || 'Google sign-in failed');
        return data;
    }))
};

// UI Elements
const DOM = {
    navLinks: document.querySelectorAll('.nav-item'),
    sections: document.querySelectorAll('.page-section'),
    pageTitle: document.getElementById('current-page-title'),
    pageSubtitle: document.getElementById('current-page-subtitle'),
    queueBadge: document.getElementById('queue-badge'),
    
    // User Display
    avatarLetters: document.getElementById('avatar-letters'),
    userDisplayName: document.getElementById('user-display-name'),
    userDisplayEmail: document.getElementById('user-display-email'),
    
    // Stats
    statTotalApplied: document.getElementById('stat-total-applied'),
    statQueuedCount: document.getElementById('stat-queued-count'),
    statManualAction: document.getElementById('stat-manual-action'),
    statSuccessRate: document.getElementById('stat-success-rate'),
    nextRunBadge: document.getElementById('next-run-badge'),
    
    // Dashboard
    btnSyncNowDashboard: document.getElementById('btn-sync-now-dashboard'),
    btnTriggerNow: document.getElementById('btn-trigger-now'),
    quickQueueList: document.getElementById('quick-queue-list'),
    
    // Finder
    searchInput: document.getElementById('search-input'),
    typeFilter: document.getElementById('type-filter'),
    btnSyncJobs: document.getElementById('btn-sync-jobs'),
    syncIcon: document.getElementById('sync-icon'),
    jobsGrid: document.getElementById('jobs-grid'),
    
    // Queue Editor
    queueItemsList: document.getElementById('queue-items-list'),
    queueCountHeading: document.getElementById('queue-count-heading'),
    coverLetterEditorContainer: document.getElementById('cover-letter-editor-container'),
    editorJobTitle: document.getElementById('editor-job-title'),
    coverLetterTextarea: document.getElementById('cover-letter-textarea'),
    btnSaveCoverLetter: document.getElementById('btn-save-cover-letter'),
    
    // History
    historyTableBody: document.getElementById('history-table-body'),
    btnClearHistory: document.getElementById('btn-clear-history'),
    
    // Settings Profile
    profileForm: document.getElementById('profile-form'),
    profileName: document.getElementById('profile-name'),
    profileEmail: document.getElementById('profile-email'),
    profilePhone: document.getElementById('profile-phone'),
    profileLinkedin: document.getElementById('profile-linkedin'),
    profileGithub: document.getElementById('profile-github'),
    profilePortfolio: document.getElementById('profile-portfolio'),
    profileGeminiKey: document.getElementById('profile-gemini-key'),
    profileLinkedinKey: document.getElementById('profile-linkedin-key'),
    resumeDropzone: document.getElementById('resume-dropzone'),
    resumeFileInput: document.getElementById('resume-file-input'),
    resumeFileInfo: document.getElementById('resume-file-info'),
    btnSaveProfile: document.getElementById('btn-save-profile'),
    
    // Daemon
    scheduleTime: document.getElementById('schedule-time'),
    daemonToggleSwitch: document.getElementById('daemon-toggle-switch'),
    daemonStatusText: document.getElementById('daemon-status-text'),
    dryRunSwitch: document.getElementById('dry-run-switch'),
    dryRunStatusText: document.getElementById('dry-run-status-text'),
    
    // Modal
    jobDetailsModal: document.getElementById('job-details-modal'),
    modalCompanyLogo: document.getElementById('modal-company-logo'),
    modalJobTitle: document.getElementById('modal-job-title'),
    modalCompanyLocation: document.getElementById('modal-company-location'),
    modalBadgeSource: document.getElementById('modal-badge-source'),
    modalBadgeType: document.getElementById('modal-badge-type'),
    modalBadgeDate: document.getElementById('modal-badge-date'),
    modalJobDescription: document.getElementById('modal-job-description'),
    modalBtnViewOriginal: document.getElementById('modal-btn-view-original'),
    modalBtnQueue: document.getElementById('modal-btn-queue'),
    btnCloseModal: document.getElementById('btn-close-modal'),
    
    // Toast
    toast: document.getElementById('toast'),
    
    // Auth Elements
    authOverlay: document.getElementById('auth-overlay'),
    authSubtitle: document.getElementById('auth-subtitle'),
    authForm: document.getElementById('auth-form'),
    authUsername: document.getElementById('auth-username'),
    authPassword: document.getElementById('auth-password'),
    btnAuthSubmit: document.getElementById('btn-auth-submit'),
    authToggleText: document.getElementById('auth-toggle-text'),
    authToggleBtn: document.getElementById('auth-toggle-btn'),
    btnLogout: document.getElementById('btn-logout')
};

// Show Toast Alert
function showToast(message, isError = false) {
    DOM.toast.innerText = message;
    if (isError) {
        DOM.toast.style.borderColor = 'var(--danger)';
    } else {
        DOM.toast.style.borderColor = 'rgba(99, 102, 241, 0.3)';
    }
    DOM.toast.classList.add('show');
    setTimeout(() => {
        DOM.toast.classList.remove('show');
    }, 3000);
}

// Auth State Verification & Actions
function checkAuthState() {
    if (state.token) {
        DOM.authOverlay.classList.add('hidden');
        return true;
    } else {
        DOM.authOverlay.classList.remove('hidden');
        DOM.authUsername.value = '';
        DOM.authPassword.value = '';
        return false;
    }
}

function logout() {
    state.token = null;
    state.username = null;
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    
    state.profile = null;
    state.jobs = [];
    state.queue = [];
    state.history = [];
    state.selectedJob = null;
    state.activeQueueJobId = null;
    
    checkAuthState();
}

// Router
function routeSPA() {
    if (!checkAuthState()) {
        return;
    }
    const hash = window.location.hash || '#dashboard';
    
    // Deactivate all nav links and pages
    DOM.navLinks.forEach(link => link.classList.remove('active'));
    DOM.sections.forEach(section => section.classList.remove('active'));
    
    // Find active element
    const activeLink = document.querySelector(`a[href="${hash}"]`);
    const activeSection = document.getElementById(`page-${hash.substring(1)}`);
    
    if (activeLink) activeLink.classList.add('active');
    if (activeSection) activeSection.classList.add('active');
    
    // Update headers
    let title = 'Dashboard';
    let subtitle = 'Overview of your internship and job application agent.';
    
    switch (hash) {
        case '#finder':
            title = 'Job Finder';
            subtitle = 'Search and queue recently posted jobs and internships.';
            loadJobFinder();
            break;
        case '#queue':
            title = 'Auto-Apply Queue';
            subtitle = 'Review and edit cover letters for scheduled Monday applications.';
            loadQueue();
            break;
        case '#history':
            title = 'History Logs';
            subtitle = 'Detailed submission logs for all past automation processes.';
            loadHistory();
            break;
        case '#settings':
            title = 'Profile & Settings';
            subtitle = 'Configure resume, LinkedIn profile, schedule triggers, and credentials.';
            loadSettings();
            break;
        default:
            title = 'Dashboard';
            subtitle = 'Welcome back! View your agent state and quick actions.';
            loadDashboard();
            break;
    }
    
    DOM.pageTitle.innerText = title;
    DOM.pageSubtitle.innerText = subtitle;
}

// Data Loaders
function loadDashboard() {
    refreshGlobalData().then(() => {
        // Render Dashboard Stats
        const totalCount = state.history.length;
        const queuedCount = state.queue.length;
        const manualCount = state.history.filter(h => h.status === 'requires_manual').length;
        
        const successCount = state.history.filter(h => h.status === 'completed').length;
        const rate = totalCount > 0 ? Math.round((successCount / totalCount) * 100) : 0;
        
        DOM.statTotalApplied.innerText = totalCount;
        DOM.statQueuedCount.innerText = queuedCount;
        DOM.statManualAction.innerText = manualCount;
        DOM.statSuccessRate.innerText = `${rate}%`;
        
        // Next run details
        const time = state.profile?.monday_time || '09:00';
        DOM.nextRunBadge.innerText = `Monday, ${formatTime(time)}`;
        
        // Header profile summary
        if (state.profile && state.profile.name) {
            DOM.userDisplayName.innerText = state.profile.name;
            DOM.userDisplayEmail.innerText = state.profile.email;
            
            // Generate initials for avatar
            const initials = state.profile.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
            DOM.avatarLetters.innerText = initials;
        } else {
            DOM.userDisplayName.innerText = "Guest User";
            DOM.userDisplayEmail.innerText = "Profile not configured";
            DOM.avatarLetters.innerText = "GU";
        }
        
        // Render quick queue
        DOM.quickQueueList.innerHTML = '';
        if (state.queue.length === 0) {
            DOM.quickQueueList.innerHTML = `<div class="empty-state">No jobs in queue. Go to <a href="#finder">Job Finder</a> to search.</div>`;
        } else {
            state.queue.slice(0, 5).forEach(item => {
                const div = document.createElement('div');
                div.className = 'quick-job-item';
                div.innerHTML = `
                    <div class="quick-job-info">
                        <h5>${escapeHTML(item.title)}</h5>
                        <p>${escapeHTML(item.company)} • ${escapeHTML(item.location)}</p>
                    </div>
                    <span class="tag source-tag">${escapeHTML(item.source)}</span>
                `;
                DOM.quickQueueList.appendChild(div);
            });
        }
    });
}

function loadJobFinder(sync = false) {
    const search = DOM.searchInput.value;
    const type = DOM.typeFilter.value;
    const isInternship = type === 'internships' ? true : (type === 'jobs' ? false : null);
    
    if (sync) {
        DOM.syncIcon.classList.add('fa-spin');
        DOM.btnSyncJobs.disabled = true;
    }
    
    API.getJobs(search, isInternship, sync).then(jobs => {
        state.jobs = jobs;
        renderJobsGrid();
    }).catch(err => {
        showToast("Error loading jobs: " + err, true);
    }).finally(() => {
        if (sync) {
            DOM.syncIcon.classList.remove('fa-spin');
            DOM.btnSyncJobs.disabled = false;
            showToast("Job cache synchronized successfully!");
        }
    });
}

function renderJobsGrid() {
    DOM.jobsGrid.innerHTML = '';
    if (state.jobs.length === 0) {
        DOM.jobsGrid.innerHTML = `<div class="empty-state" style="grid-column: 1/-1;">No jobs match your search parameters. Try syncing latest postings.</div>`;
        return;
    }
    
    state.jobs.forEach(job => {
        const card = document.createElement('div');
        card.className = 'job-card';
        
        const isQueued = state.queue.some(q => q.job_id === job.id);
        
        // Logo replacement helper
        const companyInitial = job.company ? job.company[0].toUpperCase() : 'J';
        
        card.innerHTML = `
            <div>
                <div class="job-card-top">
                    <img class="company-logo" src="${job.company_logo || ''}" data-char="${companyInitial}" alt="${escapeHTML(job.company)}" onerror="this.src='https://placehold.co/48x48/5A67D8/FFFFFF?text='+this.dataset.char">
                    <div class="job-card-titles">
                        <h4>${escapeHTML(job.title)}</h4>
                        <p>${escapeHTML(job.company)}</p>
                    </div>
                </div>
                <div class="job-card-middle">
                    <div class="job-tags">
                        <span class="tag source-tag">${escapeHTML(job.source)}</span>
                        ${job.is_internship ? '<span class="tag internship-tag">Internship</span>' : '<span class="tag source-tag" style="background:rgba(99,102,241,0.05);color:var(--text-muted);border-color:transparent;">Full-time</span>'}
                        <span class="tag location-tag">${escapeHTML(job.location)}</span>
                    </div>
                </div>
            </div>
            <div class="job-card-bottom">
                <button class="btn btn-secondary btn-sm btn-view-details" data-id="${job.id}">View Details</button>
                <button class="btn btn-primary btn-sm btn-queue-action" data-id="${job.id}" ${isQueued ? 'disabled' : ''}>
                    ${isQueued ? '<i class="fa-solid fa-check"></i> Queued' : '<i class="fa-solid fa-clock"></i> Queue'}
                </button>
            </div>
        `;
        
        // Add events
        card.querySelector('.btn-view-details').addEventListener('click', (e) => {
            e.stopPropagation();
            showJobModal(job);
        });
        
        card.querySelector('.btn-queue-action').addEventListener('click', (e) => {
            e.stopPropagation();
            queueJob(job.id, e.target);
        });
        
        DOM.jobsGrid.appendChild(card);
    });
}

function loadQueue() {
    API.getQueue().then(queue => {
        state.queue = queue;
        DOM.queueBadge.innerText = queue.length;
        DOM.queueCountHeading.innerText = queue.length;
        
        renderQueueList();
    });
}

function renderQueueList() {
    DOM.queueItemsList.innerHTML = '';
    if (state.queue.length === 0) {
        DOM.queueItemsList.innerHTML = `<div class="empty-state">No jobs in queue. Go to <a href="#finder">Job Finder</a> to search.</div>`;
        DOM.coverLetterEditorContainer.style.display = 'none';
        state.activeQueueJobId = null;
        return;
    }
    
    state.queue.forEach(item => {
        const div = document.createElement('div');
        div.className = `queue-item ${state.activeQueueJobId === item.job_id ? 'active' : ''}`;
        div.setAttribute('data-id', item.job_id);
        
        div.innerHTML = `
            <div class="queue-item-header">
                <div>
                    <h4>${escapeHTML(item.title)}</h4>
                    <p>${escapeHTML(item.company)}</p>
                </div>
                <button class="btn-remove-queue" data-id="${item.job_id}">
                    <i class="fa-regular fa-trash-can"></i>
                </button>
            </div>
            <div class="queue-item-body">
                <span class="tag location-tag">${escapeHTML(item.location)}</span>
                <span class="letter-status">
                    <i class="fa-solid fa-file-signature"></i> Cover Letter Ready
                </span>
            </div>
        `;
        
        div.addEventListener('click', (e) => {
            if (e.target.closest('.btn-remove-queue')) return;
            selectQueueItem(item);
        });
        
        div.querySelector('.btn-remove-queue').addEventListener('click', (e) => {
            e.stopPropagation();
            removeFromQueue(item.job_id);
        });
        
        DOM.queueItemsList.appendChild(div);
    });
    
    // Automatically select the first item if none selected
    if (state.queue.length > 0 && !state.activeQueueJobId) {
        selectQueueItem(state.queue[0]);
    } else if (state.activeQueueJobId) {
        const activeItem = state.queue.find(q => q.job_id === state.activeQueueJobId);
        if (activeItem) {
            selectQueueItem(activeItem);
        } else {
            selectQueueItem(state.queue[0]);
        }
    }
}

function selectQueueItem(item) {
    state.activeQueueJobId = item.job_id;
    
    // Toggle active class in list UI
    document.querySelectorAll('.queue-item').forEach(el => {
        el.classList.remove('active');
        if (el.getAttribute('data-id') === item.job_id) {
            el.classList.add('active');
        }
    });
    
    DOM.editorJobTitle.innerText = `${item.title} at ${item.company}`;
    DOM.coverLetterTextarea.value = item.cover_letter || '';
    DOM.coverLetterEditorContainer.style.display = 'block';
}

function loadHistory() {
    API.getHistory().then(history => {
        state.history = history;
        renderHistoryTable();
    });
}

function renderHistoryTable() {
    DOM.historyTableBody.innerHTML = '';
    if (state.history.length === 0) {
        DOM.historyTableBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-table-state">No application history found. Queue jobs and run them to log entries.</td>
            </tr>
        `;
        return;
    }
    
    state.history.forEach(item => {
        const tr = document.createElement('tr');
        
        let statusBadge = '';
        if (item.status === 'completed') {
            statusBadge = '<span class="status-badge completed"><i class="fa-solid fa-circle-check"></i> Applied</span>';
        } else if (item.status === 'requires_manual') {
            statusBadge = '<span class="status-badge manual"><i class="fa-solid fa-circle-info"></i> Manual Action</span>';
        } else {
            statusBadge = '<span class="status-badge failed"><i class="fa-solid fa-circle-xmark"></i> Failed</span>';
        }
        
        // Clean error messages or direct to files
        let logDetails = item.error_message || 'Application processed successfully.';
        if (item.status === 'requires_manual') {
            logDetails = `<a href="${item.url}" target="_blank" class="btn btn-secondary btn-sm" style="padding: 2px 8px; font-size:0.75rem;">Apply Manually <i class="fa-solid fa-arrow-up-right-from-square"></i></a>`;
        }
        
        tr.innerHTML = `
            <td>
                <div class="history-role">
                    <h5>${escapeHTML(item.title)}</h5>
                    <p>${escapeHTML(item.company)}</p>
                </div>
            </td>
            <td>${formatDate(item.applied_at)}</td>
            <td><a href="${item.url}" target="_blank">${escapeHTML(item.url.substring(0, 30))}...</a></td>
            <td>${statusBadge}</td>
            <td><div style="max-width:300px; font-size: 0.8rem; line-height: 1.4; color: var(--text-muted);">${logDetails}</div></td>
        `;
        DOM.historyTableBody.appendChild(tr);
    });
}

function loadSettings() {
    API.getProfile().then(profile => {
        state.profile = profile;
        if (profile) {
            DOM.profileName.value = profile.name || '';
            DOM.profileEmail.value = profile.email || '';
            DOM.profilePhone.value = profile.phone || '';
            DOM.profileLinkedin.value = profile.linkedin_url || '';
            DOM.profileGithub.value = profile.github_url || '';
            DOM.profilePortfolio.value = profile.portfolio_url || '';
            
            // Masked Gemini key will show sk-... if exists
            DOM.profileGeminiKey.value = profile.gemini_api_key || '';
            DOM.profileLinkedinKey.value = profile.linkedin_api_key || '';
            DOM.scheduleTime.value = profile.monday_time || '09:00';
            
            // Update file display info
            if (profile.resume_filename) {
                DOM.resumeFileInfo.innerText = `${profile.resume_filename} (Parsed Successfully)`;
                DOM.resumeDropzone.style.borderColor = 'var(--success)';
            } else {
                DOM.resumeFileInfo.innerText = "No file uploaded";
                DOM.resumeDropzone.style.borderColor = 'var(--border-color)';
            }
            
            // Toggle daemon switch
            const daemonActive = profile.windows_daemon_enabled === 1;
            DOM.daemonToggleSwitch.checked = daemonActive;
            updateDaemonLabel(daemonActive);
            
            // Toggle dry run switch
            const dryRunActive = profile.dry_run === 1;
            DOM.dryRunSwitch.checked = dryRunActive;
            updateDryRunLabel(dryRunActive);
        }
    });
}

function updateDaemonLabel(active) {
    if (active) {
        DOM.daemonStatusText.innerText = "Active";
        DOM.daemonStatusText.className = "status-label-on";
    } else {
        DOM.daemonStatusText.innerText = "Disabled";
        DOM.daemonStatusText.className = "status-label-off";
    }
}

function updateDryRunLabel(active) {
    if (active) {
        DOM.dryRunStatusText.innerText = "Enabled";
        DOM.dryRunStatusText.className = "status-label-on";
    } else {
        DOM.dryRunStatusText.innerText = "Disabled";
        DOM.dryRunStatusText.className = "status-label-off";
    }
}

// Actions Execution
function queueJob(jobId, buttonElement) {
    if (buttonElement) {
        buttonElement.disabled = true;
        buttonElement.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Queuing...`;
    }
    
    API.addToQueue(jobId).then(res => {
        if (res.status === 'success') {
            showToast("Job added to Auto-Apply Queue!");
            loadQueue();
            if (buttonElement) {
                buttonElement.innerHTML = `<i class="fa-solid fa-check"></i> Queued`;
            }
        } else {
            showToast("Error adding to queue.", true);
            if (buttonElement) {
                buttonElement.disabled = false;
                buttonElement.innerHTML = `<i class="fa-solid fa-clock"></i> Queue`;
            }
        }
    }).catch(err => {
        showToast("Error queuing: " + err, true);
        if (buttonElement) {
            buttonElement.disabled = false;
            buttonElement.innerHTML = `<i class="fa-solid fa-clock"></i> Queue`;
        }
    });
}

function removeFromQueue(jobId) {
    API.removeFromQueue(jobId).then(res => {
        if (res.status === 'success') {
            showToast("Job removed from queue.");
            // Reset active selection if we deleted it
            if (state.activeQueueJobId === jobId) {
                state.activeQueueJobId = null;
            }
            loadQueue();
            loadJobFinder(); // Reload finder cards to re-enable queue buttons
        }
    });
}

function refreshGlobalData() {
    return Promise.all([
        API.getProfile().then(p => state.profile = p),
        API.getQueue().then(q => {
            state.queue = q;
            DOM.queueBadge.innerText = q.length;
        }),
        API.getHistory().then(h => state.history = h)
    ]);
}

// Modal Interaction
function showJobModal(job) {
    state.selectedJob = job;
    
    // Logo replacement helper
    const companyInitial = job.company ? job.company[0].toUpperCase() : 'J';
    DOM.modalCompanyLogo.src = job.company_logo || '';
    DOM.modalCompanyLogo.dataset.char = companyInitial;
    DOM.modalCompanyLogo.alt = job.company;
    
    DOM.modalJobTitle.innerText = job.title;
    DOM.modalCompanyLocation.innerText = `${job.company} • ${job.location}`;
    DOM.modalBadgeSource.innerText = job.source;
    DOM.modalBadgeType.innerText = job.is_internship ? 'Internship' : 'Job';
    DOM.modalBadgeDate.innerText = formatDate(job.pub_date || 'Recently');
    
    // Render job description HTML safely
    DOM.modalJobDescription.innerHTML = job.description;
    
    DOM.modalBtnViewOriginal.onclick = () => window.open(job.url, '_blank');
    
    const isQueued = state.queue.some(q => q.job_id === job.id);
    DOM.modalBtnQueue.disabled = isQueued;
    DOM.modalBtnQueue.innerHTML = isQueued ? '<i class="fa-solid fa-check"></i> Queued' : '<i class="fa-solid fa-clock"></i> Queue for Monday Apply';
    
    DOM.modalBtnQueue.onclick = () => {
        queueJob(job.id, DOM.modalBtnQueue);
        DOM.jobDetailsModal.classList.remove('active');
    };
    
    DOM.jobDetailsModal.classList.add('active');
}

// Form Handlers
DOM.profileForm.addEventListener('submit', (e) => {
    e.preventDefault();
    DOM.btnSaveProfile.disabled = true;
    DOM.btnSaveProfile.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Saving...`;
    
    const formData = new FormData();
    formData.append('name', DOM.profileName.value);
    formData.append('email', DOM.profileEmail.value);
    formData.append('phone', DOM.profilePhone.value);
    formData.append('linkedin_url', DOM.profileLinkedin.value);
    formData.append('github_url', DOM.profileGithub.value);
    formData.append('portfolio_url', DOM.profilePortfolio.value);
    formData.append('gemini_api_key', DOM.profileGeminiKey.value);
    formData.append('linkedin_api_key', DOM.profileLinkedinKey.value);
    formData.append('monday_time', DOM.scheduleTime.value);
    
    if (DOM.resumeFileInput.files[0]) {
        formData.append('resume', DOM.resumeFileInput.files[0]);
    }
    
    API.saveProfile(formData).then(res => {
        if (res.status === 'success') {
            showToast("Profile credentials and resume saved!");
            loadSettings();
            loadDashboard();
        } else {
            showToast("Failed to update profile: " + res.message, true);
        }
    }).catch(err => {
        showToast("Error updating profile: " + err, true);
    }).finally(() => {
        DOM.btnSaveProfile.disabled = false;
        DOM.btnSaveProfile.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Save Profile Details`;
    });
});

// Auto-format URL inputs on blur and save click to prevent browser URL validation error
const urlInputs = [DOM.profileLinkedin, DOM.profileGithub, DOM.profilePortfolio];
urlInputs.forEach(input => {
    if (input) {
        input.addEventListener('blur', () => {
            let val = input.value.trim();
            if (val && !/^https?:\/\//i.test(val)) {
                input.value = `https://${val}`;
            }
        });
    }
});

DOM.btnSaveProfile.addEventListener('click', () => {
    urlInputs.forEach(input => {
        if (input) {
            let val = input.value.trim();
            if (val && !/^https?:\/\//i.test(val)) {
                input.value = `https://${val}`;
            }
        }
    });
});

// Dropzone Actions
DOM.resumeDropzone.addEventListener('click', () => DOM.resumeFileInput.click());

DOM.resumeFileInput.addEventListener('change', () => {
    const file = DOM.resumeFileInput.files[0];
    if (file) {
        if (file.type !== "application/pdf") {
            showToast("Only PDF documents are supported for resume parse.", true);
            DOM.resumeFileInput.value = '';
            return;
        }
        DOM.resumeFileInfo.innerText = `${file.name} (Ready to Save)`;
        DOM.resumeDropzone.style.borderColor = 'var(--primary)';
    }
});

DOM.resumeDropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    DOM.resumeDropzone.classList.add('dragover');
});

DOM.resumeDropzone.addEventListener('dragleave', () => {
    DOM.resumeDropzone.classList.remove('dragover');
});

DOM.resumeDropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    DOM.resumeDropzone.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        const file = files[0];
        if (file.type !== "application/pdf") {
            showToast("Only PDF documents are supported for resume parse.", true);
            return;
        }
        DOM.resumeFileInput.files = files; // Assign files array
        DOM.resumeFileInfo.innerText = `${file.name} (Ready to Save)`;
        DOM.resumeDropzone.style.borderColor = 'var(--primary)';
    }
});

// Queue Actions
DOM.btnSaveCoverLetter.addEventListener('click', () => {
    if (!state.activeQueueJobId) return;
    
    DOM.btnSaveCoverLetter.disabled = true;
    DOM.btnSaveCoverLetter.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Saving...`;
    
    const txt = DOM.coverLetterTextarea.value;
    API.updateCoverLetter(state.activeQueueJobId, txt).then(res => {
        if (res.status === 'success') {
            showToast("Cover Letter saved successfully!");
            // Update local memory
            const idx = state.queue.findIndex(q => q.job_id === state.activeQueueJobId);
            if (idx !== -1) {
                state.queue[idx].cover_letter = txt;
            }
        }
    }).finally(() => {
        DOM.btnSaveCoverLetter.disabled = false;
        DOM.btnSaveCoverLetter.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Save Letter`;
    });
});

// Windows Scheduler Toggle Daemon
DOM.daemonToggleSwitch.addEventListener('change', () => {
    const val = DOM.daemonToggleSwitch.checked;
    DOM.daemonToggleSwitch.disabled = true;
    
    API.toggleDaemon(val).then(res => {
        if (res.status === 'success') {
            showToast(res.message);
            updateDaemonLabel(val);
        } else {
            showToast(res.detail || "Daemon configuration failed.", true);
            DOM.daemonToggleSwitch.checked = !val; // Revert
        }
    }).catch(err => {
        showToast("Error updating daemon: " + err, true);
        DOM.daemonToggleSwitch.checked = !val; // Revert
    }).finally(() => {
        DOM.daemonToggleSwitch.disabled = false;
    });
});

// Dry Run Toggle
DOM.dryRunSwitch.addEventListener('change', () => {
    const val = DOM.dryRunSwitch.checked;
    DOM.dryRunSwitch.disabled = true;
    
    API.toggleDryRun(val).then(res => {
        if (res.status === 'success') {
            showToast(res.message);
            updateDryRunLabel(val);
        } else {
            showToast(res.detail || "Dry Run configuration failed.", true);
            DOM.dryRunSwitch.checked = !val; // Revert
        }
    }).catch(err => {
        showToast("Error updating Dry Run mode: " + err, true);
        DOM.dryRunSwitch.checked = !val; // Revert
    }).finally(() => {
        DOM.dryRunSwitch.disabled = false;
    });
});

// Sync triggers
DOM.btnSyncJobs.addEventListener('click', () => loadJobFinder(true));
DOM.btnSyncNowDashboard.addEventListener('click', () => {
    DOM.btnSyncNowDashboard.disabled = true;
    DOM.btnSyncNowDashboard.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Syncing...`;
    API.getJobs('', null, true).then(() => {
        showToast("Synced jobs successfully!");
        loadDashboard();
    }).finally(() => {
        DOM.btnSyncNowDashboard.disabled = false;
        DOM.btnSyncNowDashboard.innerHTML = `<i class="fa-solid fa-rotate"></i> Sync Jobs Now`;
    });
});

// Trigger now
DOM.btnTriggerNow.addEventListener('click', () => {
    if (state.queue.length === 0) {
        showToast("Your queue is empty. Queue jobs first.", true);
        return;
    }
    
    DOM.btnTriggerNow.disabled = true;
    DOM.btnTriggerNow.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Applying...`;
    
    API.triggerRun().then(res => {
        showToast(`Successfully processed queue. Applied/Triggered ${res.applied} applications.`);
        loadDashboard();
    }).catch(err => {
        showToast("Error processing queue: " + err, true);
    }).finally(() => {
        DOM.btnTriggerNow.disabled = false;
        DOM.btnTriggerNow.innerHTML = `<i class="fa-solid fa-play"></i> Trigger Queue Run Now`;
    });
});

// History Actions
DOM.btnClearHistory.addEventListener('click', () => {
    if (confirm("Are you sure you want to clear your application logs history?")) {
        API.clearHistory().then(() => {
            showToast("History logs cleared successfully!");
            loadHistory();
            loadDashboard();
        });
    }
});

// Finder Search & Filter
DOM.searchInput.addEventListener('input', debounce(() => loadJobFinder(), 300));
DOM.typeFilter.addEventListener('change', () => loadJobFinder());

// Modal Close Action
DOM.btnCloseModal.addEventListener('click', () => DOM.jobDetailsModal.classList.remove('active'));
window.addEventListener('click', (e) => {
    if (e.target === DOM.jobDetailsModal) {
        DOM.jobDetailsModal.classList.remove('active');
    }
});

// Auth View Toggle & Form Handling
let authMode = 'login';

DOM.authToggleBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (authMode === 'login') {
        authMode = 'register';
        DOM.authSubtitle.innerText = 'Create a new account to start automated job hunting';
        DOM.btnAuthSubmit.innerHTML = `<i class="fa-solid fa-user-plus"></i> Sign Up`;
        DOM.authToggleText.innerText = 'Already have an account?';
        DOM.authToggleBtn.innerText = 'Sign In';
    } else {
        authMode = 'login';
        DOM.authSubtitle.innerText = 'Sign in to manage your automated job search';
        DOM.btnAuthSubmit.innerHTML = `<i class="fa-solid fa-sign-in-alt"></i> Sign In`;
        DOM.authToggleText.innerText = "Don't have an account?";
        DOM.authToggleBtn.innerText = 'Sign Up';
    }
});

DOM.authForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const username = DOM.authUsername.value.trim();
    const password = DOM.authPassword.value;
    
    DOM.btnAuthSubmit.disabled = true;
    const submitText = DOM.btnAuthSubmit.innerHTML;
    DOM.btnAuthSubmit.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Processing...`;
    
    const authPromise = authMode === 'login' 
        ? API.login(username, password)
        : API.register(username, password);
        
    authPromise.then(res => {
        if (res.status === 'success') {
            state.token = res.token;
            state.username = res.username;
            localStorage.setItem('token', res.token);
            localStorage.setItem('username', res.username);
            
            showToast(authMode === 'login' ? "Welcome back!" : "Account created successfully!");
            checkAuthState();
            routeSPA();
        } else {
            showToast(res.message || "Authentication failed.", true);
        }
    }).catch(err => {
        showToast(err.message || "An error occurred during authentication.", true);
    }).finally(() => {
        DOM.btnAuthSubmit.disabled = false;
        DOM.btnAuthSubmit.innerHTML = submitText;
    });
});

DOM.btnLogout.addEventListener('click', () => {
    logout();
    showToast("Logged out successfully!");
});

// Google Credential Callback
function handleGoogleCredentialResponse(response) {
    if (!response.credential) return;
    
    DOM.btnAuthSubmit.disabled = true;
    const submitText = DOM.btnAuthSubmit.innerHTML;
    DOM.btnAuthSubmit.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Processing...`;
    
    API.googleLogin(response.credential).then(res => {
        if (res.status === 'success') {
            state.token = res.token;
            state.username = res.username;
            localStorage.setItem('token', res.token);
            localStorage.setItem('username', res.username);
            
            showToast("Logged in with Google successfully!");
            checkAuthState();
            routeSPA();
        } else {
            showToast(res.message || "Google Authentication failed.", true);
        }
    }).catch(err => {
        showToast(err.message || "An error occurred during Google authentication.", true);
    }).finally(() => {
        DOM.btnAuthSubmit.disabled = false;
        DOM.btnAuthSubmit.innerHTML = submitText;
    });
}

// Startup Helpers
window.addEventListener('hashchange', routeSPA);
window.addEventListener('DOMContentLoaded', () => {
    routeSPA();
    
    // Fetch auth config and initialize Google Sign-In
    API.getAuthConfig().then(config => {
        const btnContainer = document.getElementById("google-signin-btn-container");
        if (config.google_client_id && typeof google !== 'undefined' && btnContainer) {
            google.accounts.id.initialize({
                client_id: config.google_client_id,
                callback: handleGoogleCredentialResponse
            });
            google.accounts.id.renderButton(
                btnContainer,
                { theme: "outline", size: "large", width: 280, text: "signin_with" }
            );
        }
    }).catch(err => console.error("Error loading auth config:", err));
    
    // Load initial counts for badge if authenticated
    if (state.token) {
        API.getQueue().then(q => DOM.queueBadge.innerText = q.length).catch(() => {});
    }
});

// Utility functions
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

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
        return dateStr;
    }
}

function formatTime(timeStr) {
    if (!timeStr) return '';
    try {
        const [hour, min] = timeStr.split(':');
        const h = parseInt(hour);
        const ampm = h >= 12 ? 'PM' : 'AM';
        const displayHour = h % 12 || 12;
        return `${displayHour}:${min} ${ampm}`;
    } catch {
        return timeStr;
    }
}
