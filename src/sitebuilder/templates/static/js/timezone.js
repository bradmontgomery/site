/**
 * Client-side timezone conversion for blog dates.
 * 
 * Converts all <time> elements with data-local="true" attribute
 * from UTC to the user's browser timezone.
 * 
 * Usage: Add to your HTML template and include before closing </body> tag:
 *   <script src="/static/js/timezone.js"></script>
 * 
 * Then in templates, use:
 *   <time datetime="{{ post.date_iso }}" data-local="true">
 *     {{ post.date.strftime("%Y-%m-%d") }}
 *   </time>
 */

(function() {
  'use strict';

  /**
   * Convert a UTC datetime string to user's local timezone
   * @param {string} isoString - ISO 8601 datetime string (e.g., "2024-02-11T15:30:45+00:00")
   * @returns {string} - Formatted date/time in user's local timezone
   */
  function formatLocalTime(isoString) {
    try {
      const date = new Date(isoString);
      
      // Check if date is valid
      if (isNaN(date.getTime())) {
        console.warn('Invalid date string:', isoString);
        return isoString;
      }

      // Format using Intl.DateTimeFormat for locale-aware formatting
      const formatter = new Intl.DateTimeFormat(navigator.language || 'en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short'
      });

      return formatter.format(date);
    } catch (error) {
      console.error('Error formatting date:', error);
      return isoString;
    }
  }

  /**
   * Initialize timezone conversion for all marked time elements
   */
  function initTimezonConversion() {
    // Find all time elements marked for local timezone conversion
    const timeElements = document.querySelectorAll('time[data-local="true"]');
    
    timeElements.forEach(timeEl => {
      const isoString = timeEl.getAttribute('datetime');
      if (isoString) {
        const localTime = formatLocalTime(isoString);
        timeEl.textContent = localTime;
        // Add title attribute showing original UTC for reference
        timeEl.setAttribute('title', isoString + ' (UTC)');
      }
    });
  }

  // Run conversion when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTimezonConversion);
  } else {
    // DOM is already loaded
    initTimezonConversion();
  }

  // Expose function globally for manual use if needed
  window.convertTimezone = formatLocalTime;
})();
