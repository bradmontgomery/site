/**
 * Client-side timezone conversion for blog dates.
 *
 * Converts all <time> elements with data-local="true" attribute
 * from UTC to the user's browser timezone using the Intl.DateTimeFormat API.
 *
 * The formatter is created once per page load and reused for all elements.
 * If Intl.DateTimeFormat is unavailable or a date string is invalid, the
 * original server-rendered UTC text is left in place as a fallback.
 *
 * Usage in Jinja2 templates:
 *   <time datetime="{{ post.date_iso }}" data-local="true">
 *     {{ post.date.strftime("%Y-%m-%d %H:%M UTC") }}
 *   </time>
 *   <script src="/static/js/timezone.js"></script>
 *
 * Or use the macros/dates.html macro:
 *   {% import 'macros/dates.html' as dates %}
 *   {{ dates.local_date(post.date, post.date_iso) }}
 *
 * Browser support: Chrome 24+, Firefox 29+, Safari 11+, Edge 12+.
 */

(function() {
  'use strict';

  /**
   * Create a locale-aware date formatter for the user's browser timezone.
   * Returns null if Intl.DateTimeFormat is not available.
   */
  function createFormatter() {
    try {
      return new Intl.DateTimeFormat(navigator.language || 'en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short'
      });
    } catch (error) {
      console.error('Intl.DateTimeFormat unavailable:', error);
      return null;
    }
  }

  /**
   * Format an ISO 8601 datetime string in the user's local timezone.
   * @param {string} isoString - ISO 8601 datetime (e.g. "2024-02-11T15:30:45+00:00")
   * @param {Intl.DateTimeFormat} formatter - Reusable formatter instance
   * @returns {string} Formatted local date/time, or the original string on failure
   */
  function formatLocalDate(isoString, formatter) {
    var date = new Date(isoString);

    if (isNaN(date.getTime())) {
      console.warn('Invalid date string:', isoString);
      return isoString;
    }

    if (!formatter) {
      return isoString;
    }

    try {
      return formatter.format(date);
    } catch (error) {
      console.error('Error formatting date:', error);
      return isoString;
    }
  }

  /**
   * Convert all <time data-local="true"> elements from UTC to local timezone.
   */
  function initTimezoneConversion() {
    var formatter = createFormatter();
    var timeElements = document.querySelectorAll('time[data-local="true"]');

    timeElements.forEach(function(timeEl) {
      var isoString = timeEl.getAttribute('datetime');
      if (isoString) {
        var localTime = formatLocalDate(isoString, formatter);
        timeEl.textContent = localTime;
        timeEl.setAttribute('title', isoString + ' (UTC)');
      }
    });
  }

  // Run conversion when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTimezoneConversion);
  } else {
    initTimezoneConversion();
  }

  // Expose for manual use (e.g. dynamically inserted content)
  window.formatLocalDate = function(isoString) {
    return formatLocalDate(isoString, createFormatter());
  };
})();
