/**
 * Mini-Enclava Application JavaScript
 * Utility functions for HTMX + Alpine.js frontend
 */

// Copy to clipboard functionality
async function copyToClipboard(text, buttonEl) {
  try {
    await navigator.clipboard.writeText(text);

    // Visual feedback
    const originalText = buttonEl.textContent;
    buttonEl.textContent = 'Copied!';
    buttonEl.classList.add('bg-green-500');

    setTimeout(() => {
      buttonEl.textContent = originalText;
      buttonEl.classList.remove('bg-green-500');
    }, 2000);
  } catch (err) {
    console.error('Failed to copy:', err);
  }
}

// File upload with drag and drop
function initFileUpload(dropzoneId, inputId, previewId) {
  const dropzone = document.getElementById(dropzoneId);
  const input = document.getElementById(inputId);
  const preview = document.getElementById(previewId);

  if (!dropzone || !input) return;

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => {
      dropzone.classList.add('border-primary', 'bg-primary/5');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => {
      dropzone.classList.remove('border-primary', 'bg-primary/5');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length) {
      input.files = files;
      updateFilePreview(files[0], preview);
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });

  dropzone.addEventListener('click', () => input.click());

  input.addEventListener('change', () => {
    if (input.files.length && preview) {
      updateFilePreview(input.files[0], preview);
    }
  });
}

function updateFilePreview(file, previewEl) {
  if (!previewEl) return;

  // Clear existing content
  previewEl.textContent = '';

  const container = document.createElement('div');
  container.className = 'flex items-center gap-2 text-sm';

  // Create SVG icon safely using DOM methods
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'h-4 w-4 text-muted-foreground');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('viewBox', '0 0 24 24');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('stroke-linecap', 'round');
  path.setAttribute('stroke-linejoin', 'round');
  path.setAttribute('stroke-width', '2');
  path.setAttribute('d', 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z');
  svg.appendChild(path);

  // Create filename span (using textContent for safety)
  const nameSpan = document.createElement('span');
  nameSpan.className = 'font-medium';
  nameSpan.textContent = file.name;

  // Create size span
  const sizeSpan = document.createElement('span');
  sizeSpan.className = 'text-muted-foreground';
  sizeSpan.textContent = '(' + formatFileSize(file.size) + ')';

  container.appendChild(svg);
  container.appendChild(nameSpan);
  container.appendChild(sizeSpan);
  previewEl.appendChild(container);
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Toast notifications
function showToast(message, type, duration) {
  type = type || 'info';
  duration = duration !== undefined ? duration : 5000;

  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast-enter p-4 rounded-lg shadow-lg flex items-center gap-3 min-w-[300px] ' + getToastClasses(type);

  // Add icon
  const icon = createToastIcon(type);
  toast.appendChild(icon);

  // Add message (textContent for safety)
  const msgSpan = document.createElement('span');
  msgSpan.className = 'flex-1';
  msgSpan.textContent = message;
  toast.appendChild(msgSpan);

  // Add close button
  const closeBtn = document.createElement('button');
  closeBtn.className = 'text-current opacity-70 hover:opacity-100';
  closeBtn.onclick = function() { toast.remove(); };
  const closeSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  closeSvg.setAttribute('class', 'h-4 w-4');
  closeSvg.setAttribute('fill', 'none');
  closeSvg.setAttribute('stroke', 'currentColor');
  closeSvg.setAttribute('viewBox', '0 0 24 24');
  const closePath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  closePath.setAttribute('stroke-linecap', 'round');
  closePath.setAttribute('stroke-linejoin', 'round');
  closePath.setAttribute('stroke-width', '2');
  closePath.setAttribute('d', 'M6 18L18 6M6 6l12 12');
  closeSvg.appendChild(closePath);
  closeBtn.appendChild(closeSvg);
  toast.appendChild(closeBtn);

  container.appendChild(toast);

  if (duration > 0) {
    setTimeout(function() {
      toast.classList.remove('toast-enter');
      toast.classList.add('toast-exit');
      setTimeout(function() { toast.remove(); }, 300);
    }, duration);
  }
}

function getToastClasses(type) {
  switch (type) {
    case 'success': return 'bg-green-500 text-white';
    case 'error': return 'bg-destructive text-destructive-foreground';
    case 'warning': return 'bg-yellow-500 text-white';
    default: return 'bg-card text-card-foreground border border-border';
  }
}

function createToastIcon(type) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'h-5 w-5');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('viewBox', '0 0 24 24');

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('stroke-linecap', 'round');
  path.setAttribute('stroke-linejoin', 'round');
  path.setAttribute('stroke-width', '2');

  const paths = {
    success: 'M5 13l4 4L19 7',
    error: 'M6 18L18 6M6 6l12 12',
    warning: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
    info: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
  };

  path.setAttribute('d', paths[type] || paths.info);
  svg.appendChild(path);
  return svg;
}

// HTMX event handlers
document.body.addEventListener('htmx:afterRequest', function(event) {
  // Handle toast messages from response headers
  const toastMessage = event.detail.xhr.getResponseHeader('X-Toast-Message');
  const toastType = event.detail.xhr.getResponseHeader('X-Toast-Type') || 'info';
  if (toastMessage) {
    showToast(toastMessage, toastType);
  }

  // Reset file upload forms after successful submission
  if (event.detail.successful && event.detail.elt.tagName === 'FORM') {
    const form = event.detail.elt;
    const fileInputs = form.querySelectorAll('input[type="file"]');
    fileInputs.forEach(function(input) {
      // Reset the file input
      input.value = '';
      // Clear the preview
      const previewId = input.id + '-preview';
      const preview = document.getElementById(previewId);
      if (preview) {
        preview.textContent = '';
      }
    });
  }
});

document.body.addEventListener('htmx:responseError', function(event) {
  // Show error toast for failed requests
  var status = event.detail.xhr.status;
  var message = 'An error occurred';

  if (status === 401) {
    message = 'Please log in to continue';
    window.location.href = '/login';
  } else if (status === 403) {
    message = 'You do not have permission to perform this action';
  } else if (status === 404) {
    message = 'The requested resource was not found';
  } else if (status >= 500) {
    message = 'A server error occurred. Please try again.';
  }

  showToast(message, 'error');
});

// Modal helpers
function openModal(modalId) {
  var modal = document.getElementById(modalId);
  if (modal) modal.showModal();
}

function closeModal(modalId) {
  var modal = document.getElementById(modalId);
  if (modal) modal.close();
}

// Close modal on backdrop click
document.addEventListener('click', function(event) {
  if (event.target.tagName === 'DIALOG') {
    var rect = event.target.getBoundingClientRect();
    if (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    ) {
      event.target.close();
    }
  }
});

// Confirm dialog helper
function confirmAction(message, onConfirm) {
  if (confirm(message)) {
    onConfirm();
  }
}

// Initialize theme from localStorage or system preference
function initTheme() {
  var stored = localStorage.getItem('theme');
  if (stored === 'dark' || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}

function toggleTheme() {
  var isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// Run on page load
document.addEventListener('DOMContentLoaded', function() {
  initTheme();
});
