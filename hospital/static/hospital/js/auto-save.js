/**
 * Auto-Save Module for HMS
 * Automatically saves form data to server as user types
 * Provides real-time synchronization across devices
 */

(function() {
    'use strict';
    
    // Configuration
    const AUTO_SAVE_DELAY = 2000; // 2 seconds after user stops typing
    const SYNC_INTERVAL = 5000; // Sync every 5 seconds
    const MAX_RETRIES = 3;
    
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
            
            // Setup auto-save for all forms
            this.setupAutoSave();
            
            // Setup periodic sync
            this.startPeriodicSync();
            
            // Save before page unload
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
        
        setupAutoSave() {
            // Find all forms on the page
            const forms = document.querySelectorAll('form[method="post"], form[method="POST"]');
            
            forms.forEach(form => {
                // Skip if form has data-no-autosave attribute
                if (form.hasAttribute('data-no-autosave')) {
                    return;
                }
                
                // Get form action and method
                const action = form.getAttribute('action') || window.location.pathname;
                const method = form.getAttribute('method') || 'POST';
                
                // Setup auto-save for form inputs
                const inputs = form.querySelectorAll('input, textarea, select');
                inputs.forEach(input => {
                    // Skip submit buttons and hidden fields
                    if (input.type === 'submit' || input.type === 'button' || input.type === 'hidden') {
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
            });
        }
        
        scheduleAutoSave(form, action, method) {
            const formId = this.getFormId(form);
            
            // Clear existing timer
            if (this.saveTimers.has(formId)) {
                clearTimeout(this.saveTimers.get(formId));
            }
            
            // Schedule new save
            const timer = setTimeout(() => {
                this.performAutoSave(form, action, method);
            }, AUTO_SAVE_DELAY);
            
            this.saveTimers.set(formId, timer);
            this.showStatus('Saving...', 'info');
        }
        
        async performAutoSave(form, action, method) {
            if (!this.isOnline) {
                this.queueForLater(form, action, method);
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
                    
                    this.showStatus('Saved', 'success');
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
                await this.performAutoSave(saveData.form, saveData.action, saveData.method);
            }
        }
        
        startPeriodicSync() {
            this.syncInterval = setInterval(() => {
                this.flushPendingSaves();
            }, SYNC_INTERVAL);
        }
        
        getFormId(form) {
            return form.id || form.getAttribute('name') || `form_${form.action}`;
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
                    },
                    credentials: 'same-origin',
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.has_updates) {
                        this.handleUpdates(data);
                    }
                }
            } catch (error) {
                console.error('Sync check error:', error);
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

