// AuditFlow - Custom JavaScript for Enhanced UX
document.addEventListener('DOMContentLoaded', function() {
    
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Active navigation highlighting
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href && currentPath.includes(href) && href !== '/') {
            link.classList.add('active');
        } else if (currentPath === '/' && href === '/') {
            link.classList.add('active');
        }
    });

    // File upload drag and drop functionality
    setupFileUpload();
    
    // Form validation enhancement
    setupFormValidation();
    
    // Loading states for buttons
    setupLoadingStates();
    
    // Auto-hide alerts
    setupAutoHideAlerts();
    
    // Initialize charts if Chart.js is available
    if (typeof Chart !== 'undefined') {
        initializeCharts();
    }
});

// File Upload Enhancement
function setupFileUpload() {
    const fileUploadAreas = document.querySelectorAll('.file-upload-area');
    
    fileUploadAreas.forEach(area => {
        const fileInput = area.querySelector('input[type="file"]') || 
                         area.parentElement.querySelector('input[type="file"]');
        
        if (!fileInput) return;
        
        // Click to select files
        area.addEventListener('click', () => {
            fileInput.click();
        });
        
        // Drag and drop events
        area.addEventListener('dragover', (e) => {
            e.preventDefault();
            area.classList.add('dragover');
        });
        
        area.addEventListener('dragleave', (e) => {
            e.preventDefault();
            area.classList.remove('dragover');
        });
        
        area.addEventListener('drop', (e) => {
            e.preventDefault();
            area.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files;
                handleFileSelection(files, area);
            }
        });
        
        // File input change event
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileSelection(e.target.files, area);
            }
        });
    });
}

function handleFileSelection(files, area) {
    const fileList = Array.from(files);
    const fileNames = fileList.map(file => file.name).join(', ');
    
    // Update UI to show selected files
    const uploadText = area.querySelector('.upload-text');
    if (uploadText) {
        uploadText.innerHTML = `
            <i class="fas fa-check-circle text-success mb-2" style="font-size: 2rem;"></i>
            <div class="fw-bold text-success">Files Selected</div>
            <div class="text-muted small">${fileNames}</div>
        `;
    }
    
    // Show file info
    showFileInfo(fileList, area);
}

function showFileInfo(files, area) {
    let totalSize = 0;
    let fileTypes = new Set();
    
    files.forEach(file => {
        totalSize += file.size;
        fileTypes.add(file.type || 'unknown');
    });
    
    const sizeInMB = (totalSize / (1024 * 1024)).toFixed(2);
    
    // Create or update file info display
    let infoDiv = area.parentElement.querySelector('.file-info');
    if (!infoDiv) {
        infoDiv = document.createElement('div');
        infoDiv.className = 'file-info mt-3';
        area.parentElement.appendChild(infoDiv);
    }
    
    infoDiv.innerHTML = `
        <div class="row text-center">
            <div class="col-md-4">
                <small class="text-muted">Files: <strong>${files.length}</strong></small>
            </div>
            <div class="col-md-4">
                <small class="text-muted">Size: <strong>${sizeInMB} MB</strong></small>
            </div>
            <div class="col-md-4">
                <small class="text-muted">Types: <strong>${fileTypes.size}</strong></small>
            </div>
        </div>
    `;
}

// Form Validation Enhancement
function setupFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
                
                // Focus on first invalid field
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.focus();
                }
            }
            
            form.classList.add('was-validated');
        });
        
        // Real-time validation
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', () => {
                if (input.checkValidity()) {
                    input.classList.remove('is-invalid');
                    input.classList.add('is-valid');
                } else {
                    input.classList.remove('is-valid');
                    input.classList.add('is-invalid');
                }
            });
        });
    });
}

// Loading States for Buttons
function setupLoadingStates() {
    const loadingButtons = document.querySelectorAll('[data-loading]');
    
    loadingButtons.forEach(button => {
        button.addEventListener('click', () => {
            const originalText = button.innerHTML;
            const loadingText = button.getAttribute('data-loading') || 'Loading...';
            
            button.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                ${loadingText}
            `;
            button.disabled = true;
            
            // Re-enable after form submission or timeout
            setTimeout(() => {
                button.innerHTML = originalText;
                button.disabled = false;
            }, 3000);
        });
    });
}

// Auto-hide Alerts
function setupAutoHideAlerts() {
    const alerts = document.querySelectorAll('.alert[data-auto-hide]');
    
    alerts.forEach(alert => {
        const delay = parseInt(alert.getAttribute('data-auto-hide')) || 5000;
        
        setTimeout(() => {
            const alertInstance = new bootstrap.Alert(alert);
            alertInstance.close();
        }, delay);
    });
}

// Chart Initialization
function initializeCharts() {
    // Dashboard Revenue Chart
    const revenueChart = document.getElementById('revenueChart');
    if (revenueChart) {
        new Chart(revenueChart, {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{
                    label: 'Revenue',
                    data: [12000, 19000, 15000, 25000, 22000, 30000],
                    borderColor: '#87CEEB',
                    backgroundColor: 'rgba(135, 206, 235, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }
    
    // Document Status Pie Chart
    const statusChart = document.getElementById('statusChart');
    if (statusChart) {
        new Chart(statusChart, {
            type: 'doughnut',
            data: {
                labels: ['Processed', 'Pending', 'Failed'],
                datasets: [{
                    data: [75, 20, 5],
                    backgroundColor: ['#87CEEB', '#ffc107', '#ff7f7f'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
}

// Utility Functions
function showNotification(message, type = 'info') {
    const alertClass = `alert-${type}`;
    const icon = getIconForType(type);
    
    const notification = document.createElement('div');
    notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        <i class="${icon} me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            const alert = new bootstrap.Alert(notification);
            alert.close();
        }
    }, 5000);
}

function getIconForType(type) {
    const icons = {
        'success': 'fas fa-check-circle',
        'danger': 'fas fa-exclamation-circle',
        'warning': 'fas fa-exclamation-triangle',
        'info': 'fas fa-info-circle'
    };
    return icons[type] || icons['info'];
}

function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Search functionality
function setupSearch() {
    const searchInputs = document.querySelectorAll('[data-search]');
    
    searchInputs.forEach(input => {
        const targetSelector = input.getAttribute('data-search');
        const targetElements = document.querySelectorAll(targetSelector);
        
        input.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            
            targetElements.forEach(element => {
                const text = element.textContent.toLowerCase();
                const shouldShow = text.includes(searchTerm);
                
                element.style.display = shouldShow ? '' : 'none';
            });
        });
    });
}

// Export data functionality
function exportData(data, filename, type = 'json') {
    let content;
    let mimeType;
    
    switch (type.toLowerCase()) {
        case 'csv':
            content = convertToCSV(data);
            mimeType = 'text/csv';
            break;
        case 'json':
        default:
            content = JSON.stringify(data, null, 2);
            mimeType = 'application/json';
            break;
    }
    
    const blob = new Blob([content], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    
    window.URL.revokeObjectURL(url);
}

function convertToCSV(data) {
    if (!Array.isArray(data) || data.length === 0) return '';
    
    const headers = Object.keys(data[0]);
    const csvHeaders = headers.join(',');
    
    const csvRows = data.map(row => 
        headers.map(header => {
            const value = row[header];
            return typeof value === 'string' && value.includes(',') 
                ? `"${value}"` 
                : value;
        }).join(',')
    );
    
    return [csvHeaders, ...csvRows].join('\n');
}

// Format currency
function formatCurrency(amount, currency = 'Tzs') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

// Format date
function formatDate(date, options = {}) {
    const defaultOptions = {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    };
    
    return new Intl.DateTimeFormat('en-US', { ...defaultOptions, ...options })
        .format(new Date(date));
}
