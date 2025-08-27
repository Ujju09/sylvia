// Godown Operations JavaScript

// Toast notification system
window.showToast = function(message, type = 'info', duration = 5000) {
    // Create toast container if it doesn't exist
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Initialize and show toast
    const bsToast = new bootstrap.Toast(toast, { delay: duration });
    bsToast.show();
    
    // Remove toast element after it's hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
};

// Loading overlay system
window.showLoadingOverlay = function(show = true) {
    let overlay = document.querySelector('.loading-overlay');
    
    if (show) {
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'loading-overlay';
            overlay.innerHTML = '<div class="loading-spinner"></div>';
            document.body.appendChild(overlay);
        }
        overlay.style.display = 'flex';
    } else {
        if (overlay) {
            overlay.style.display = 'none';
        }
    }
};

// CSRF token helper
window.getCSRFToken = function() {
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    return csrfInput ? csrfInput.value : '';
};

// Auto-refresh functionality
window.setupAutoRefresh = function(interval = 60000) {
    setInterval(() => {
        const refreshButton = document.querySelector('[onclick*="refresh"]');
        if (refreshButton && document.visibilityState === 'visible') {
            location.reload();
        }
    }, interval);
};

// Real-time status updates
window.updateStatus = function(elementId, status, statusText) {
    const element = document.getElementById(elementId);
    if (element) {
        element.className = `badge status-badge status-${status.toLowerCase()}`;
        element.textContent = statusText;
    }
};

// Form validation helpers
window.validateQuantities = function(expectedField, actualField, errorContainer) {
    const expected = parseInt(document.getElementById(expectedField).value) || 0;
    const actual = parseInt(document.getElementById(actualField).value) || 0;
    const container = document.getElementById(errorContainer);
    
    if (Math.abs(expected - actual) > expected * 0.1) { // 10% tolerance
        container.innerHTML = `
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Large discrepancy detected: Expected ${expected}, Actual ${actual}
            </div>
        `;
        return false;
    } else {
        container.innerHTML = '';
        return true;
    }
};

// Inventory availability checker
window.checkInventoryAvailability = function(godownId, productId, quantity, callbackFunction) {
    if (!godownId || !productId || !quantity) {
        showToast('Please fill in all required fields first', 'warning');
        return;
    }
    
    showLoadingOverlay(true);
    
    fetch(`/godown/inventory/check-availability/?godown_id=${godownId}&product_id=${productId}&quantity=${quantity}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            showLoadingOverlay(false);
            if (callbackFunction) {
                callbackFunction(data);
            }
        })
        .catch(error => {
            showLoadingOverlay(false);
            console.error('Error checking inventory:', error);
            showToast('Error checking inventory availability', 'danger');
        });
};

// FIFO allocation helper
window.displayFIFOAllocation = function(containerId, allocationData) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    let html = '<h6 class="text-primary mb-2">FIFO Allocation Preview</h6>';
    
    if (allocationData && allocationData.length > 0) {
        html += `
            <div class="table-responsive">
                <table class="table table-sm table-hover">
                    <thead class="table-light">
                        <tr>
                            <th>Batch ID</th>
                            <th>Date</th>
                            <th>Available</th>
                            <th>Allocated</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        allocationData.forEach(batch => {
            html += `
                <tr>
                    <td><code class="bg-light p-1">${batch.batch_id}</code></td>
                    <td>${batch.batch_date}</td>
                    <td>${batch.available_bags}</td>
                    <td><strong class="text-primary">${batch.allocated_bags}</strong></td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
    } else {
        html += '<p class="text-muted">No inventory batches available for allocation.</p>';
    }
    
    container.innerHTML = html;
};

// Priority color coding
window.getPriorityClass = function(priority) {
    const priorityMap = {
        'URGENT': 'priority-urgent',
        'HIGH': 'priority-high',
        'MEDIUM': 'priority-medium',
        'LOW': 'priority-low',
        'NORMAL': 'priority-medium'
    };
    return priorityMap[priority.toUpperCase()] || 'priority-medium';
};

// Status color coding
window.getStatusClass = function(status) {
    return `status-${status.toLowerCase().replace(' ', '_')}`;
};

// Initialize tooltips
window.initializeTooltips = function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
};

// Format numbers for display
window.formatNumber = function(number, decimals = 0) {
    return new Intl.NumberFormat('en-IN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(number);
};

// Date formatting helpers
window.formatDate = function(dateString, format = 'short') {
    const date = new Date(dateString);
    const options = {
        short: { month: 'short', day: 'numeric' },
        medium: { month: 'short', day: 'numeric', year: 'numeric' },
        long: { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }
    };
    return date.toLocaleDateString('en-IN', options[format] || options.medium);
};

// Relative time formatting
window.timeAgo = function(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = (now - date) / 1000;
    
    if (diffInSeconds < 60) return 'Just now';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} min ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hrs ago`;
    return `${Math.floor(diffInSeconds / 86400)} days ago`;
};

// Keyboard shortcuts handler
window.setupKeyboardShortcuts = function() {
    document.addEventListener('keydown', function(e) {
        // Only handle shortcuts when not in input fields
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
            return;
        }
        
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 'r':
                    e.preventDefault();
                    location.reload();
                    break;
                case 'n':
                    e.preventDefault();
                    const createButton = document.querySelector('a[href*="create"]');
                    if (createButton) createButton.click();
                    break;
                case 'f':
                    e.preventDefault();
                    const searchInput = document.querySelector('input[name="search"]');
                    if (searchInput) searchInput.focus();
                    break;
            }
        }
        
        // Escape key to close modals
        if (e.key === 'Escape') {
            const openModal = document.querySelector('.modal.show');
            if (openModal) {
                const modal = bootstrap.Modal.getInstance(openModal);
                if (modal) modal.hide();
            }
        }
    });
};

// Initialize on DOM content loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initializeTooltips();
    
    // Setup keyboard shortcuts
    setupKeyboardShortcuts();
    
    // Add real-time indicators where needed
    const realTimeElements = document.querySelectorAll('.real-time');
    realTimeElements.forEach(element => {
        const indicator = document.createElement('span');
        indicator.className = 'real-time-indicator ms-2';
        indicator.title = 'Real-time data';
        element.appendChild(indicator);
    });
    
    // Auto-focus search fields
    const searchInput = document.querySelector('input[name="search"]');
    if (searchInput && !searchInput.value) {
        // Only focus if no existing value and not on mobile
        if (window.innerWidth > 768) {
            setTimeout(() => searchInput.focus(), 100);
        }
    }
    
    // Setup auto-refresh for list views
    if (document.querySelector('.auto-refresh')) {
        setupAutoRefresh();
    }
    
    // Initialize any existing popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

// OrderInTransit specific functions
window.calculateTransitQuantities = function(expectedTotal, actualReceived) {
    const shortage = Math.max(0, expectedTotal - actualReceived);
    const excess = Math.max(0, actualReceived - expectedTotal);
    const discrepancy = expectedTotal - actualReceived;
    const discrepancyPercentage = expectedTotal > 0 ? Math.abs(discrepancy) / expectedTotal * 100 : 0;
    
    return {
        shortage,
        excess,
        discrepancy,
        discrepancyPercentage: Math.round(discrepancyPercentage * 100) / 100
    };
};

window.validateTransitBags = function(actualReceived, goodBags, damagedBags, crossoverBags = 0) {
    const errors = [];
    const totalAccounted = goodBags + damagedBags;
    
    // Check if good + damaged equals actual received
    if (totalAccounted !== actualReceived) {
        errors.push(`Good bags (${goodBags}) + Damaged bags (${damagedBags}) = ${totalAccounted}, but you received ${actualReceived} bags`);
    }
    
    // Check if crossover bags exceed good bags
    if (crossoverBags > goodBags) {
        errors.push(`Crossover bags (${crossoverBags}) cannot exceed good bags (${goodBags})`);
    }
    
    // Calculate storage bags
    const storageBags = Math.max(0, goodBags - crossoverBags);
    
    return {
        valid: errors.length === 0,
        errors,
        storageBags,
        totalAccounted
    };
};

window.updateTransitSummary = function(expected, received, good, damaged, crossover = 0) {
    const summaryElements = {
        expected: document.getElementById('summary-expected'),
        received: document.getElementById('summary-received'),
        good: document.getElementById('summary-good'),
        storage: document.getElementById('summary-storage')
    };
    
    if (summaryElements.expected) summaryElements.expected.textContent = expected || 0;
    if (summaryElements.received) summaryElements.received.textContent = received || 0;
    if (summaryElements.good) summaryElements.good.textContent = good || 0;
    if (summaryElements.storage) summaryElements.storage.textContent = Math.max(0, (good || 0) - (crossover || 0));
};

window.submitTransitCalculation = async function(expectedTotal, actualReceived) {
    try {
        const response = await fetch('/godown/ajax/transit/calculate-quantities/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                expected_total: expectedTotal,
                actual_received: actualReceived
            })
        });
        
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error calculating quantities:', error);
        showToast('Error calculating quantities', 'danger');
        return null;
    }
};

window.submitTransitValidation = async function(actualReceived, goodBags, damagedBags, crossoverBags = 0) {
    try {
        const response = await fetch('/godown/ajax/transit/validate-bags/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                actual_received: actualReceived,
                good_bags: goodBags,
                damaged_bags: damagedBags,
                crossover_bags: crossoverBags
            })
        });
        
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error validating bags:', error);
        showToast('Error validating bag quantities', 'danger');
        return null;
    }
};

window.showTransitDiscrepancyAlert = function(containerId, discrepancyData) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const { discrepancy, discrepancyPercentage } = discrepancyData;
    let content = '';
    let alertClass = 'alert-info';
    
    if (discrepancy > 0) {
        content = `<div class="text-danger"><i class="fas fa-exclamation-triangle me-2"></i>Shortage: ${discrepancy} bags (${discrepancyPercentage}%)</div>`;
        alertClass = 'alert-warning';
    } else if (discrepancy < 0) {
        content = `<div class="text-success"><i class="fas fa-plus me-2"></i>Excess: ${Math.abs(discrepancy)} bags (${discrepancyPercentage}%)</div>`;
        alertClass = 'alert-success';
    } else {
        content = `<div class="text-success"><i class="fas fa-check me-2"></i>Perfect match: No discrepancy</div>`;
        alertClass = 'alert-success';
    }
    
    container.innerHTML = content;
    container.className = `alert ${alertClass}`;
    container.style.display = 'block';
};

window.showTransitValidationAlert = function(containerId, validationData) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const { valid, errors, storageBags } = validationData;
    let content = '';
    let alertClass = 'alert-success';
    
    if (!valid && errors.length > 0) {
        content = errors.map(error => `<div class="text-warning"><i class="fas fa-exclamation-triangle me-2"></i>${error}</div>`).join('');
        alertClass = 'alert-warning';
    } else {
        content = `<div class="text-success"><i class="fas fa-check me-2"></i>All quantities validated successfully. ${storageBags} bags for storage.</div>`;
    }
    
    container.innerHTML = content;
    container.className = `alert ${alertClass}`;
    container.style.display = 'block';
};

window.initializeTransitFormHelpers = function() {
    // Auto-fill arrival date to current time for new records
    const arrivalDateInput = document.querySelector('input[type="datetime-local"][name*="arrival_date"]');
    if (arrivalDateInput && !arrivalDateInput.value) {
        const now = new Date();
        const localDateTime = new Date(now.getTime() - (now.getTimezoneOffset() * 60000));
        arrivalDateInput.value = localDateTime.toISOString().slice(0, 16);
    }
    
    // Add helpful tooltips
    const ewayInput = document.querySelector('input[name*="eway_bill"]');
    if (ewayInput && !ewayInput.hasAttribute('title')) {
        ewayInput.setAttribute('title', 'Enter the 12-digit E-way bill number exactly as shown on the document');
    }
    
    // Set up quantity validation on blur
    const quantityInputs = document.querySelectorAll('input[type="number"][name*="bags"]');
    quantityInputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.value < 0) {
                this.value = 0;
                showToast('Negative values are not allowed', 'warning');
            }
        });
    });
    
    // Add keyboard shortcuts for form navigation
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            const submitButton = document.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.click();
            }
        }
    });
};

window.enhanceTransitListView = function() {
    // Add row click navigation
    const tableRows = document.querySelectorAll('tbody tr[data-url]');
    tableRows.forEach(row => {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function(e) {
            // Don't navigate if clicking on action buttons
            if (!e.target.closest('.btn, .btn-group')) {
                window.location.href = this.dataset.url;
            }
        });
    });
    
    // Add keyboard navigation for table
    let selectedRowIndex = -1;
    const rows = document.querySelectorAll('tbody tr');
    
    document.addEventListener('keydown', function(e) {
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
            return;
        }
        
        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                selectedRowIndex = Math.min(selectedRowIndex + 1, rows.length - 1);
                highlightRow(selectedRowIndex);
                break;
            case 'ArrowUp':
                e.preventDefault();
                selectedRowIndex = Math.max(selectedRowIndex - 1, 0);
                highlightRow(selectedRowIndex);
                break;
            case 'Enter':
                if (selectedRowIndex >= 0 && rows[selectedRowIndex]) {
                    const url = rows[selectedRowIndex].dataset.url;
                    if (url) {
                        window.location.href = url;
                    }
                }
                break;
        }
    });
    
    function highlightRow(index) {
        rows.forEach((row, i) => {
            row.classList.toggle('table-active', i === index);
        });
        
        if (rows[index]) {
            rows[index].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
};

// Export enhanced functions for use in templates
window.GodownJS = {
    showToast,
    showLoadingOverlay,
    getCSRFToken,
    setupAutoRefresh,
    updateStatus,
    validateQuantities,
    checkInventoryAvailability,
    displayFIFOAllocation,
    getPriorityClass,
    getStatusClass,
    initializeTooltips,
    formatNumber,
    formatDate,
    timeAgo,
    setupKeyboardShortcuts,
    // OrderInTransit specific functions
    calculateTransitQuantities,
    validateTransitBags,
    updateTransitSummary,
    submitTransitCalculation,
    submitTransitValidation,
    showTransitDiscrepancyAlert,
    showTransitValidationAlert,
    initializeTransitFormHelpers,
    enhanceTransitListView
};