/**
 * API Utility Functions - Add to unified-dashboard.html <script> section
 * Provides: timeout handling, retry logic, error boundaries
 */

// Fetch with timeout support
async function fetchWithTimeout(url, options = {}, timeout = 15000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('Request timeout - API took too long to respond');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

// Fetch with retry logic
async function fetchWithRetry(url, options = {}, maxRetries = 3, initialDelay = 1000) {
  let lastError;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fetchWithTimeout(url, options, 15000);
    } catch (error) {
      lastError = error;
      if (attempt < maxRetries - 1) {
        const delay = initialDelay * Math.pow(2, attempt);
        console.warn(`Attempt ${attempt + 1} failed, retrying in ${delay}ms:`, error.message);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  throw lastError;
}

// Safe Promise.all that handles partial failures
async function safePromiseAll(promises, fallbacks = {}) {
  const results = await Promise.allSettled(promises);
  return results.map((result, index) =>
    result.status === 'fulfilled' ? result.value : fallbacks[index] || null
  );
}

// Safe DOM element access
function safeGetElement(id) {
  const element = document.getElementById(id);
  if (!element) {
    console.warn(`Element with ID "${id}" not found`);
    return null;
  }
  return element;
}

// Safe classList manipulation
function safeAddClass(element, className) {
  if (element && element.classList) {
    element.classList.add(className);
  }
}

function safeRemoveClass(element, className) {
  if (element && element.classList) {
    element.classList.remove(className);
  }
}

// Safe innerHTML with fallback
function safeSetHTML(elementId, html) {
  const element = safeGetElement(elementId);
  if (element) {
    element.innerHTML = html;
  }
}

function safeSetText(elementId, text) {
  const element = safeGetElement(elementId);
  if (element) {
    element.textContent = text;
  }
}

// Input validation helpers
function validatePositiveNumber(value, fieldName) {
  const num = parseFloat(value);
  if (isNaN(num) || num <= 0) {
    return { valid: false, error: `${fieldName} must be a positive number` };
  }
  return { valid: true };
}

function validatePercentage(value, fieldName) {
  const num = parseFloat(value);
  if (isNaN(num) || num < 0 || num > 100) {
    return { valid: false, error: `${fieldName} must be between 0 and 100` };
  }
  return { valid: true };
}

function validateSymbol(symbol) {
  if (!symbol || typeof symbol !== 'string' || symbol.length === 0) {
    return { valid: false, error: 'Symbol is required' };
  }
  return { valid: true };
}

// Safe numeric formatting
function safeFormatNumber(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) {
    return '—';
  }
  return parseFloat(value).toFixed(decimals);
}

// Error display helper
function showError(elementId, errorMessage) {
  safeSetHTML(elementId, `<div class="error-message" style="color: red; padding: 10px; background: #ffebee; border-radius: 4px;">❌ ${errorMessage}</div>`);
}

// Loading state helper
function setLoadingState(elementId, isLoading) {
  const element = safeGetElement(elementId);
  if (!element) return;

  if (isLoading) {
    element.innerHTML = '<div class="loading" style="padding: 20px; text-align: center;">⏳ Loading...</div>';
    element.style.opacity = '0.6';
  } else {
    element.style.opacity = '1';
  }
}

// HTML Escape - CRITICAL: Prevent XSS vulnerabilities
function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;'
  };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

// Safe JSON parsing
function safeParseJSON(jsonString, fallback = {}) {
  try {
    return JSON.parse(jsonString);
  } catch (error) {
    console.error('JSON parse error:', error);
    return fallback;
  }
}

// Validate API response structure
function validateResponse(response, requiredFields = []) {
  if (!response || typeof response !== 'object') {
    return { valid: false, error: 'Invalid response format' };
  }

  for (const field of requiredFields) {
    if (!(field in response)) {
      return { valid: false, error: `Missing required field: ${field}` };
    }
  }

  return { valid: true };
}
