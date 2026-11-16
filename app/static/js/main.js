/**
 * Savyant Systems - Core UI & Interaction JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Auto-dismiss flash messages after 6 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = 'opacity 0.4s ease-out, transform 0.4s ease-out';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-5px)';
            setTimeout(() => alert.remove(), 400);
        }, 6000);
    });

    // 2. Prevent duplicate form submissions across all standard forms
    const forms = document.querySelectorAll('form[data-prevent-duplicate]');
    forms.forEach(function (form) {
        form.addEventListener('submit', function (e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                if (submitBtn.disabled) {
                    e.preventDefault();
                    return false;
                }
                submitBtn.disabled = true;
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = `
                    <span style="display:inline-block;animation:spin 1s infinite linear;">⟳</span> Processing...
                `;
                // Fallback reset after 10s if submission hangs or fails without page reload
                setTimeout(function () {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }, 10000);
            }
        });
    });
});

// Flash alert manual close handler
function closeAlert(button) {
    const alert = button.closest('.alert');
    if (alert) {
        alert.remove();
    }
}

// Confirmation dialog helper for critical actions
function confirmAction(message, onConfirm) {
    if (window.confirm(message)) {
        if (typeof onConfirm === 'function') {
            onConfirm();
        }
        return true;
    }
    return false;
}
