/**
 * Live Dashboard Updates for Medical Dashboard
 * Automatically updates pending labs, imaging, and orders when they're completed
 */
(function() {
    'use strict';
    
    // Configuration
    const UPDATE_INTERVAL = 5000; // Check every 5 seconds
    const FADE_DURATION = 300; // Animation duration
    
    class DashboardLiveUpdates {
        constructor() {
            this.updateInterval = null;
            this.lastCheckTime = Date.now();
            this.pendingLabIds = new Set();
            this.pendingOrderIds = new Set();
            this.init();
        }
        
        init() {
            // Only run on medical dashboard
            if (!document.querySelector('.doctor-dashboard')) {
                return;
            }
            
            // Collect initial IDs
            this.collectInitialIds();
            
            // Log initialization for debugging
            console.log('Dashboard Live Updates initialized:', {
                pendingLabs: this.pendingLabIds.size,
                pendingOrders: this.pendingOrderIds.size
            });
            
            // Start polling for updates
            this.startPolling();
            
            // Stop polling when page is hidden
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    this.stopPolling();
                } else {
                    this.startPolling();
                }
            });
        }
        
        collectInitialIds() {
            // Collect pending lab order IDs
            const labItems = document.querySelectorAll('[data-lab-order-id]');
            labItems.forEach(item => {
                const orderId = item.getAttribute('data-lab-order-id');
                if (orderId) {
                    this.pendingLabIds.add(String(orderId));
                }
            });
            
            // Collect pending order IDs
            const orderItems = document.querySelectorAll('[data-order-id]');
            orderItems.forEach(item => {
                const orderId = item.getAttribute('data-order-id');
                if (orderId) {
                    this.pendingOrderIds.add(String(orderId));
                }
            });
        }
        
        startPolling() {
            if (this.updateInterval) {
                return; // Already running
            }
            
            this.updateInterval = setInterval(() => {
                this.checkForUpdates();
            }, UPDATE_INTERVAL);
            
            // Initial check after 2 seconds
            setTimeout(() => this.checkForUpdates(), 2000);
        }
        
        stopPolling() {
            if (this.updateInterval) {
                clearInterval(this.updateInterval);
                this.updateInterval = null;
            }
        }
        
        async checkForUpdates() {
            try {
                const response = await fetch('/api/hospital/dashboard-updates/', {
                    method: 'GET',
                    headers: {
                        'X-CSRFToken': window.getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    credentials: 'same-origin',
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.completed_labs?.length > 0 || data.completed_orders?.length > 0) {
                        console.log('Dashboard updates received:', data);
                    }
                    this.processUpdates(data);
                } else {
                    console.warn('Dashboard update failed:', response.status, response.statusText);
                }
            } catch (error) {
                console.error('Dashboard update error:', error);
            }
        }
        
        processUpdates(data) {
            let totalRemoved = 0;
            
            // Update pending labs
            if (data.completed_labs && data.completed_labs.length > 0) {
                data.completed_labs.forEach(orderId => {
                    if (this.removeLabOrder(orderId)) {
                        totalRemoved++;
                    }
                });
            }
            
            // Update pending orders
            if (data.completed_orders && data.completed_orders.length > 0) {
                data.completed_orders.forEach(orderId => {
                    if (this.removeOrder(orderId)) {
                        totalRemoved++;
                    }
                });
            }
            
            // Update imaging studies
            if (data.completed_imaging && data.completed_imaging.length > 0) {
                data.completed_imaging.forEach(studyId => {
                    if (this.removeImagingStudy(studyId)) {
                        totalRemoved++;
                    }
                });
            }
            
            // Update counts
            if (data.counts) {
                this.updateCounts(data.counts);
            }
            
            // Show notification if items were completed
            if (totalRemoved > 0) {
                this.showNotification(`${totalRemoved} item(s) completed`, 'success');
            }
        }
        
        removeLabOrder(orderId) {
            // Convert to string for comparison
            const orderIdStr = String(orderId);
            
            // Find and remove the lab order element
            const element = document.querySelector(`[data-lab-order-id="${orderIdStr}"]`);
            if (element && !element.classList.contains('removing')) {
                element.classList.add('removing');
                
                // Fade out animation
                element.style.transition = `opacity ${FADE_DURATION}ms, transform ${FADE_DURATION}ms`;
                element.style.opacity = '0';
                element.style.transform = 'translateX(-20px)';
                
                setTimeout(() => {
                    element.remove();
                    this.pendingLabIds.delete(orderIdStr);
                    this.updateLabCount();
                    this.checkEmptyState('pending-labs-section');
                }, FADE_DURATION);
                
                return true;
            }
            return false;
        }
        
        removeOrder(orderId) {
            // Find and remove the order element
            const element = document.querySelector(`[data-order-id="${orderId}"]`);
            if (element) {
                // Fade out animation
                element.style.transition = `opacity ${FADE_DURATION}ms, transform ${FADE_DURATION}ms`;
                element.style.opacity = '0';
                element.style.transform = 'translateX(-20px)';
                
                setTimeout(() => {
                    element.remove();
                    this.pendingOrderIds.delete(orderId);
                    this.updateOrderCount();
                }, FADE_DURATION);
            }
        }
        
        removeImagingStudy(studyId) {
            // Find and remove the imaging study element
            const element = document.querySelector(`[data-imaging-id="${studyId}"]`);
            if (element) {
                // Fade out animation
                element.style.transition = `opacity ${FADE_DURATION}ms, transform ${FADE_DURATION}ms`;
                element.style.opacity = '0';
                element.style.transform = 'translateX(-20px)';
                
                setTimeout(() => {
                    element.remove();
                    this.checkEmptyState('imaging-section');
                }, FADE_DURATION);
            }
        }
        
        updateLabCount() {
            const countElement = document.querySelector('[data-pending-labs-count]');
            if (countElement) {
                const currentCount = this.pendingLabIds.size;
                countElement.textContent = currentCount;
                
                // Update KPI card
                const kpiValue = document.querySelector('.kpi-card:nth-child(3) .kpi-value');
                if (kpiValue) {
                    kpiValue.textContent = currentCount;
                }
            }
        }
        
        updateOrderCount() {
            const countElement = document.querySelector('[data-pending-orders-count]');
            if (countElement) {
                countElement.textContent = this.pendingOrderIds.size;
            }
        }
        
        updateCounts(counts) {
            // Update pending labs count
            if (counts.pending_labs !== undefined) {
                const kpiValue = document.querySelector('.kpi-card:nth-child(3) .kpi-value');
                if (kpiValue) {
                    kpiValue.textContent = counts.pending_labs;
                }
            }
            
            // Update active patients count
            if (counts.active_patients !== undefined) {
                const kpiValue = document.querySelector('.kpi-card:nth-child(1) .kpi-value');
                if (kpiValue) {
                    kpiValue.textContent = counts.active_patients;
                }
            }
            
            // Update appointments count
            if (counts.appointments_count !== undefined) {
                const kpiValue = document.querySelector('.kpi-card:nth-child(2) .kpi-value');
                if (kpiValue) {
                    kpiValue.textContent = counts.appointments_count;
                }
            }
        }
        
        checkEmptyState(sectionClass) {
            const section = document.querySelector(`.${sectionClass}`);
            if (section) {
                const items = section.querySelectorAll('.list-tile, .timeline-item');
                if (items.length === 0) {
                    // Show empty state if not already shown
                    let emptyState = section.querySelector('.empty-state');
                    if (!emptyState) {
                        emptyState = document.createElement('div');
                        emptyState.className = 'empty-state';
                        emptyState.textContent = 'All items completed.';
                        section.appendChild(emptyState);
                    }
                }
            }
        }
        
        showNotification(message, type = 'info') {
            // Create notification element
            const notification = document.createElement('div');
            notification.className = `dashboard-notification dashboard-notification-${type}`;
            notification.textContent = message;
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: ${type === 'success' ? '#10b981' : '#3b82f6'};
                color: white;
                padding: 12px 20px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 10000;
                font-size: 14px;
                font-weight: 500;
                animation: slideIn 0.3s ease;
            `;
            
            document.body.appendChild(notification);
            
            // Remove after 3 seconds
            setTimeout(() => {
                notification.style.opacity = '0';
                notification.style.transform = 'translateX(100%)';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.dashboardLiveUpdates = new DashboardLiveUpdates();
        });
    } else {
        window.dashboardLiveUpdates = new DashboardLiveUpdates();
    }
    
    // Add CSS animation
    if (!document.getElementById('dashboard-live-updates-style')) {
        const style = document.createElement('style');
        style.id = 'dashboard-live-updates-style';
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        `;
        document.head.appendChild(style);
    }
})();

