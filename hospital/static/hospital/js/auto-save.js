/**
 * Auto-Save Module for HMS - Senior Engineer Refactored Version
 * 
 * PHILOSOPHY: Opt-In (Whitelist) Approach
 * - Only auto-save DRAFT forms (consultation notes, clinical notes, appointment editing)
 * - NEVER auto-save FINAL SUBMISSION forms (patient registration, appointments creation, SMS, etc.)
 * - Prevents bulk/duplicate creation across the entire system
 */

(function() {
    'use strict';
    
    // Configuration
    const AUTO_SAVE_DELAY = 3000; // 3 seconds after user stops typing (increased for safety)
    const SYNC_INTERVAL = 10000; // Sync every 10 seconds (reduced frequency)
    const MAX_RETRIES = 2; // Reduced retries
    
    /**
     * WHITELIST: Forms that SHOULD have auto-save enabled
     * These are DRAFT forms where users are writing notes/documentation
     */
    const AUTO_SAVE_WHITELIST = [
        // Consultation/Clinical Notes (draft documentation)
        '/consultation/',
        '/clinical-note/',
        '/encounter/.*/notes',
        '/encounter/.*/documentation',
        '/session-notes',
        '/update-session-notes',
        
        // Appointment editing (not creation)
        '/appointments/.*/edit',
        '/appointments/.*/update',
        
        // Telemedicine consultation notes
        '/telemedicine/.*/notes',
        '/telemedicine/.*/consultation',
        
        // Medical records documentation
        '/medical-records/.*/documentation',
        '/encounter-documentation',
    ];
    
    /**
     * BLACKLIST: Forms that MUST NEVER be auto-saved
     * These are FINAL SUBMISSION forms that create records
     */
    const AUTO_SAVE_BLACKLIST = [
        // Patient Management
        '/patients/new',
        '/patient-registration',
        '/patient_create',
        '/patients/create',
        '/donor-registration',
        
        // Appointment Management (CREATION, not editing)
        '/appointments/new',
        '/appointments/create',
        '/frontdesk/appointments/create',
        '/appointment_create',
        
        // Marketing (objectives, tasks, campaigns)
        '/marketing/objectives/create',
        '/marketing/tasks/create',
        '/marketing/campaigns',
        '/create_marketing',
        '/create_task',
        
        // SMS & Notifications
        '/sms/send',
        '/sms/bulk',
        '/send_sms',
        '/send_bulk_sms',
        '/send.*sms',
        '/birthday.*sms',
        
        // Billing & Payments
        '/payment',
        '/process.*payment',
        '/cashier.*payment',
        '/create.*bill',
        '/invoice.*create',
        
        // Pharmacy
        '/pharmacy.*dispense',
        '/pharmacy.*dispensing',
        '/pharmacy.*create',
        '/prescribe.*drug',
        '/prescription.*create',
        // Consultation prescription creation (action=prescribe_drug)
        '/consultation/.*/prescribe',
        
        // Lab
        '/lab.*result.*create',
        '/lab.*order.*create',
        
        // Admission
        '/admission.*create',
        '/admit',
        
        // Procurement
        '/procurement.*create',
        '/procurement.*request',
        
        // Staff & HR
        '/staff.*create',
        '/leave.*request.*create',
        '/recruitment.*create',
        
        // Accounting
        '/account.*create',
        '/journal.*entry.*create',
        '/voucher.*create',
        
        // Backup
        '/backup.*create',
        
        // Insurance
        '/insurance.*enrollment',
        '/insurance.*claim.*create',
        
        // Blood Bank
        '/blood-bank.*create',
        '/transfusion.*request',
        
        // Ambulance
        '/ambulance.*dispatch.*create',
        
        // Queue
        '/queue.*create',
        
        // Discharge
        '/discharge',
        
        // Triage
        '/triage',
        
        // Quick Visit
        '/quick-visit',
        
        // Any form with "create" or "new" in URL (final submissions)
        '.*/new',
        '.*/create',
    ];
    
    /**
     * Form field patterns that indicate final submission forms
     */
    const FINAL_SUBMISSION_INDICATORS = [
        // Patient registration fields
        { name: 'first_name', type: 'input' },
        { name: 'last_name', type: 'input' },
        { name: 'mrn', type: 'input' },
        
        // Appointment creation fields
        { name: 'appointment_date', type: 'input' },
        { name: 'appointment_time', type: 'input' },
        
        // SMS fields
        { name: 'phone_number', type: 'input', context: 'sms' },
        { name: 'message', type: 'textarea', context: 'sms' },
        
        // Marketing fields
        { name: 'objective', type: 'select', context: 'marketing' },
        { name: 'title', type: 'input', context: 'marketing' },
        
        // Payment fields
        { name: 'amount', type: 'input', context: 'payment' },
        { name: 'payment_method', type: 'select' },
        
        // Submit buttons that indicate final submission
        { selector: 'button[type="submit"]', text: /register|create|send|submit|save.*patient|save.*appointment/i },
    ];
    
    // Auto-save manager
    class AutoSaveManager {
        constructor() {
            this.saveTimers = new Map();
            this.pendingSaves = new Map();
            this.isOnline = navigator.onLine;
            this.syncInterval = null;
            this.init();
        }
        
        init() {
            // Setup online/offline detection
            window.addEventListener('online', () => {
                this.isOnline = true;
                this.flushPendingSaves();
                this.showStatus('Back online - syncing...', 'success');
            });
            
            window.addEventListener('offline', () => {
                this.isOnline = false;
                this.showStatus('Offline - changes will sync when online', 'warning');
            });
            
            // Setup auto-save for approved forms only
            this.setupAutoSave();
            
            // Setup periodic sync (reduced frequency)
            this.startPeriodicSync();
            
            // Save before page unload (only for whitelisted forms)
            window.addEventListener('beforeunload', () => {
                this.flushPendingSaves();
            });
            
            // Save on visibility change (tab switch)
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    this.flushPendingSaves();
                }
            });
        }
        
        /**
         * Check if a form should be auto-saved (WHITELIST approach)
         */
        shouldAutoSave(form) {
            const action = form.getAttribute('action') || window.location.pathname;
            const formId = form.id || '';
            const formName = form.getAttribute('name') || '';
            
            // CRITICAL: Check blacklist FIRST (safety first)
            if (this.isBlacklisted(action, form, formId, formName)) {
                return false;
            }
            
            // Check if explicitly disabled
            if (form.hasAttribute('data-no-autosave')) {
                return false;
            }
            
            // CRITICAL: Consultation page - NEVER auto-save (prevents frozen screen & save conflicts)
            // Doctors had frozen screen and couldn't save; auto-save was conflicting with manual save.
            const isConsultationPage = /\/consultation\//i.test(action) || /\/consultation\//i.test(window.location.pathname);
            if (isConsultationPage && !form.hasAttribute('data-autosave')) {
                return false;
            }
            
            // Check whitelist (only enable for approved forms)
            if (this.isWhitelisted(action, form, formId, formName)) {
                return true;
            }
            
            // Default: DO NOT auto-save (opt-in approach)
            return false;
        }
        
        /**
         * Check if form is in blacklist (final submissions)
         */
        isBlacklisted(action, form, formId, formName) {
            // Check URL patterns
            for (const pattern of AUTO_SAVE_BLACKLIST) {
                const regex = new RegExp(pattern, 'i');
                if (regex.test(action) || regex.test(window.location.pathname)) {
                    console.log(`Auto-save: BLACKLISTED (URL pattern): ${action}`);
                    return true;
                }
            }
            
            // Check form ID patterns
            const blacklistedIds = ['patientForm', 'objectiveForm', 'taskForm', 'smsForm', 'appointmentForm', 'paymentForm'];
            if (blacklistedIds.some(id => formId.toLowerCase().includes(id.toLowerCase()))) {
                console.log(`Auto-save: BLACKLISTED (Form ID): ${formId}`);
                return true;
            }
            
            // Check for final submission indicators (form fields)
            for (const indicator of FINAL_SUBMISSION_INDICATORS) {
                if (indicator.name) {
                    const field = form.querySelector(`[name="${indicator.name}"]`);
                    if (field) {
                        // Check context if specified
                        if (indicator.context) {
                            const contextMatch = action.toLowerCase().includes(indicator.context) || 
                                                window.location.pathname.toLowerCase().includes(indicator.context);
                            if (contextMatch) {
                                console.log(`Auto-save: BLACKLISTED (Field + Context): ${indicator.name} in ${indicator.context}`);
                                return true;
                            }
                        } else {
                            // No context - any occurrence is blacklisted
                            console.log(`Auto-save: BLACKLISTED (Field): ${indicator.name}`);
                            return true;
                        }
                    }
                }
                
                if (indicator.selector) {
                    const element = form.querySelector(indicator.selector);
                    if (element && indicator.text && indicator.text.test(element.textContent)) {
                        console.log(`Auto-save: BLACKLISTED (Submit button text): ${element.textContent}`);
                        return true;
                    }
                }
            }
            
            // Check for common final submission patterns
            const submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
            for (const btn of submitButtons) {
                const btnText = btn.textContent || btn.value || '';
                if (/register|create|send|submit|new patient|new appointment|send sms/i.test(btnText)) {
                    console.log(`Auto-save: BLACKLISTED (Submit button): ${btnText}`);
                    return true;
                }
            }
            
            return false;
        }
        
        /**
         * Check if form is in whitelist (draft forms)
         */
        isWhitelisted(action, form, formId, formName) {
            // Check URL patterns
            for (const pattern of AUTO_SAVE_WHITELIST) {
                const regex = new RegExp(pattern, 'i');
                if (regex.test(action) || regex.test(window.location.pathname)) {
                    console.log(`Auto-save: WHITELISTED (URL pattern): ${action}`);
                    return true;
                }
            }
            
            // Check for explicit opt-in
            if (form.hasAttribute('data-autosave') || form.hasAttribute('data-autosave-enabled')) {
                console.log(`Auto-save: WHITELISTED (Explicit opt-in)`);
                return true;
            }
            
            // Check form ID patterns (draft forms)
            const whitelistedIds = ['notesForm', 'clinicalNoteForm', 'consultationForm', 'documentationForm'];
            if (whitelistedIds.some(id => formId.toLowerCase().includes(id.toLowerCase()))) {
                console.log(`Auto-save: WHITELISTED (Form ID): ${formId}`);
                return true;
            }
            
            return false;
        }
        
        setupAutoSave() {
            // Find all forms on the page
            const forms = document.querySelectorAll('form[method="post"], form[method="POST"]');
            
            let enabledCount = 0;
            let disabledCount = 0;
            
            forms.forEach(form => {
                if (this.shouldAutoSave(form)) {
                    // Setup auto-save for this form
                    this.enableAutoSaveForForm(form);
                    enabledCount++;
                } else {
                    disabledCount++;
                }
            });
            
            if (enabledCount > 0) {
                console.log(`Auto-save: Enabled for ${enabledCount} form(s), Disabled for ${disabledCount} form(s)`);
            }
        }
        
        enableAutoSaveForForm(form) {
            const action = form.getAttribute('action') || window.location.pathname;
            const method = form.getAttribute('method') || 'POST';
            
            // Setup auto-save for form inputs
            const inputs = form.querySelectorAll('input, textarea, select');
            inputs.forEach(input => {
                // Skip submit buttons, hidden fields, and file inputs
                if (input.type === 'submit' || 
                    input.type === 'button' || 
                    input.type === 'hidden' || 
                    input.type === 'file' ||
                    input.type === 'checkbox' ||
                    input.type === 'radio') {
                    return;
                }
                
                // Debounced auto-save
                input.addEventListener('input', () => {
                    this.scheduleAutoSave(form, action, method);
                });
                
                input.addEventListener('change', () => {
                    this.scheduleAutoSave(form, action, method);
                });
            });
        }
        
        scheduleAutoSave(form, action, method) {
            const formId = this.getFormId(form);
            
            // Clear existing timer
            if (this.saveTimers.has(formId)) {
                clearTimeout(this.saveTimers.get(formId));
            }
            
            // Schedule new save (increased delay for safety)
            const timer = setTimeout(() => {
                this.performAutoSave(form, action, method);
            }, AUTO_SAVE_DELAY);
            
            this.saveTimers.set(formId, timer);
            this.showStatus('Saving draft...', 'info');
        }
        
        async performAutoSave(form, action, method) {
            if (!this.isOnline) {
                this.queueForLater(form, action, method);
                return;
            }
            
            // Double-check: Make sure form is still whitelisted
            if (!this.shouldAutoSave(form)) {
                console.warn('Auto-save: Form was removed from whitelist, aborting save');
                return;
            }
            
            const formId = this.getFormId(form);
            const formData = new FormData(form);
            
            // Add auto-save flag
            formData.append('auto_save', 'true');
            
            // Use the form's action or default to current page
            const saveUrl = action || window.location.pathname;
            
            try {
                const response = await fetch(saveUrl, {
                    method: method,
                    body: formData,
                    headers: {
                        'X-CSRFToken': window.getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-Auto-Save': 'true',
                    },
                });
                
                if (response.ok) {
                    // Try to parse JSON response
                    let data = {};
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        data = await response.json();
                    } else {
                        // If not JSON, assume success
                        data = { status: 'saved', message: 'Auto-saved successfully' };
                    }
                    
                    // Check if server rejected auto-save
                    if (data.status === 'ignored') {
                        console.warn('Auto-save: Server rejected auto-save request');
                        return;
                    }
                    
                    this.showStatus('Draft saved', 'success');
                    this.pendingSaves.delete(formId);
                    
                    // Trigger custom event for other scripts
                    form.dispatchEvent(new CustomEvent('autosaved', { detail: data }));
                } else {
                    // Try to get error message
                    let errorMsg = 'Save failed';
                    try {
                        const errorData = await response.json();
                        errorMsg = errorData.message || errorMsg;
                    } catch (e) {
                        errorMsg = `Save failed: ${response.status} ${response.statusText}`;
                    }
                    throw new Error(errorMsg);
                }
            } catch (error) {
                console.error('Auto-save error:', error);
                this.queueForLater(form, action, method);
                this.showStatus('Save failed - will retry', 'warning');
            }
        }
        
        queueForLater(form, action, method) {
            const formId = this.getFormId(form);
            this.pendingSaves.set(formId, { form, action, method });
        }
        
        async flushPendingSaves() {
            if (!this.isOnline || this.pendingSaves.size === 0) {
                return;
            }
            
            for (const [formId, saveData] of this.pendingSaves.entries()) {
                // Only flush if form is still whitelisted
                if (this.shouldAutoSave(saveData.form)) {
                    await this.performAutoSave(saveData.form, saveData.action, saveData.method);
                }
            }
        }
        
        startPeriodicSync() {
            this.syncInterval = setInterval(() => {
                this.flushPendingSaves();
            }, SYNC_INTERVAL);
        }
        
        getFormId(form) {
            return form.id || form.getAttribute('name') || `form_${form.action || window.location.pathname}`;
        }
        
        showStatus(message, type = 'info') {
            // Create or update status indicator
            let statusEl = document.getElementById('autosave-status');
            if (!statusEl) {
                statusEl = document.createElement('div');
                statusEl.id = 'autosave-status';
                statusEl.style.cssText = `
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    padding: 12px 20px;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    z-index: 10000;
                    font-size: 14px;
                    font-weight: 500;
                    transition: all 0.3s ease;
                    display: none;
                `;
                document.body.appendChild(statusEl);
            }
            
            const colors = {
                success: '#10b981',
                warning: '#f59e0b',
                error: '#ef4444',
                info: '#3b82f6'
            };
            
            statusEl.textContent = message;
            statusEl.style.backgroundColor = colors[type] || colors.info;
            statusEl.style.color = 'white';
            statusEl.style.display = 'block';
            
            // Auto-hide after 3 seconds
            setTimeout(() => {
                statusEl.style.opacity = '0';
                setTimeout(() => {
                    statusEl.style.display = 'none';
                    statusEl.style.opacity = '1';
                }, 300);
            }, 3000);
        }
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.autoSaveManager = new AutoSaveManager();
        });
    } else {
        window.autoSaveManager = new AutoSaveManager();
    }
    
    // Real-time sync using polling (can be upgraded to WebSockets)
    class RealTimeSync {
        constructor() {
            this.lastSyncTime = Date.now();
            this.syncInterval = null;
            this.init();
        }
        
        init() {
            // Sync every 10 seconds
            this.syncInterval = setInterval(() => {
                this.checkForUpdates();
            }, 10000);
        }
        
        async checkForUpdates() {
            try {
                const response = await fetch('/api/hospital/sync-check/', {
                    method: 'GET',
                    headers: {
                        'X-CSRFToken': window.getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json',
                    },
                    credentials: 'same-origin',
                });
                
                if (response.ok) {
                    // Check if response is actually JSON before parsing
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        // Read as text first to avoid JSON parse errors on HTML responses
                        const text = await response.text();
                        try {
                            const data = JSON.parse(text);
                            if (data && data.has_updates) {
                                this.handleUpdates(data);
                            }
                        } catch (parseError) {
                            // Response is not valid JSON (likely HTML) - silently ignore
                            // This is expected if the endpoint redirects to login or returns an error page
                            if (!this._jsonErrorLogged) {
                                // Don't log - this is expected behavior
                                this._jsonErrorLogged = true;
                            }
                        }
                    } else {
                        // Response is not JSON (likely HTML error page or redirect)
                        // Silently ignore - this is expected
                        if (response.status === 404 && !this._endpointNotFoundLogged) {
                            // Endpoint doesn't exist - disable sync checks
                            if (this.syncInterval) {
                                clearInterval(this.syncInterval);
                                this.syncInterval = null;
                            }
                            this._endpointNotFoundLogged = true;
                        }
                    }
                } else {
                    // Response not OK (404, 500, etc.) - endpoint might not exist
                    if (response.status === 404) {
                        // Endpoint doesn't exist - disable sync checks to prevent spam
                        if (!this._endpointNotFoundLogged) {
                            if (this.syncInterval) {
                                clearInterval(this.syncInterval);
                                this.syncInterval = null;
                            }
                            this._endpointNotFoundLogged = true;
                        }
                    }
                }
            } catch (error) {
                // Silently ignore all errors - sync check is optional functionality
                // Don't log errors to console to avoid spam
            }
        }
        
        handleUpdates(data) {
            // Reload page or update specific elements
            if (data.reload_required) {
                window.location.reload();
            } else {
                // Update specific elements
                this.updateElements(data.updates);
            }
        }
        
        updateElements(updates) {
            // Update DOM elements based on server updates
            for (const [selector, content] of Object.entries(updates)) {
                const element = document.querySelector(selector);
                if (element) {
                    element.innerHTML = content;
                }
            }
        }
    }
    
    // Initialize real-time sync
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.realTimeSync = new RealTimeSync();
        });
    } else {
        window.realTimeSync = new RealTimeSync();
    }
})();
