# Client-Side Timezone Conversion

## Overview

This feature enables blog dates to be displayed in the user's local timezone on the client side, while all dates are stored and transmitted in UTC.

## How It Works

### Backend (Python)
1. All blog post dates are parsed and converted to UTC during the build process
2. Each post context now includes a `date_iso` field containing the ISO 8601 formatted UTC timestamp
3. Example: `2024-02-11T15:30:45+00:00`

### Frontend (JavaScript)
1. The `timezone.js` module runs when the page loads
2. It finds all `<time>` elements with `data-local="true"` attribute
3. Converts the UTC `datetime` attribute to the user's browser timezone
4. Displays the localized date using `Intl.DateTimeFormat` (respects browser language settings)

## Implementation

### Basic Usage

In your Jinja2 template:

```html
<time datetime="{{ post.date_iso }}" data-local="true">
  {{ post.date.strftime("%Y-%m-%d %H:%M UTC") }}
</time>
```

Include the JavaScript module before the closing `</body>` tag:

```html
<script src="/static/js/timezone.js"></script>
```

### With Macro (Recommended)

Use the provided macro for consistency:

```jinja2
{% import 'macros/dates.html' as dates %}

{{ dates.local_date(post.date, post.date_iso) }}
{{ dates.local_date(post.date, post.date_iso, format='long') }}
{{ dates.local_date(post.date, post.date_iso, format='date-only') }}
```

Available formats:
- `'short'` (default): `2024-02-11 15:30 UTC`
- `'long'`: `February 11, 2024 at 15:30 UTC`
- `'date-only'`: `2024-02-11`

## Features

### Accessibility
- Uses semantic `<time>` element with `datetime` attribute
- Sets `title` attribute with original UTC timestamp
- Provides fallback text visible before JavaScript loads

### Localization
- Uses browser's preferred language (`navigator.language`)
- Automatically formats dates per user's locale settings
- Shows timezone abbreviation (e.g., "EST", "PST")

### Error Handling
- Invalid date strings are logged and displayed as-is
- Graceful fallback if `Intl.DateTimeFormat` unavailable
- Works without JavaScript (shows UTC with fallback text)

### Performance
- Minimal JavaScript (~2.2 KB)
- No external dependencies required
- Runs once on page load
- Uses native browser APIs

## Browser Support

**Modern Browsers** (all recent versions):
- Chrome 24+
- Firefox 29+
- Safari 11+
- Edge 12+

**Older Browsers**:
- IE 11: Works with polyfill for `Intl.DateTimeFormat`

## Files Added

```
src/sitebuilder/templates/
├── static/
│   └── js/
│       └── timezone.js          # Client-side conversion module
├── macros/
│   └── dates.html               # Reusable date formatting macros
└── example-blog.html            # Example template showing usage
```

## Testing

### Manual Testing

1. Create a blog post with a date in your local timezone
2. Build the site: `site build`
3. Open the HTML file in your browser
4. Verify the date is displayed in your local timezone
5. Right-click on the date and inspect → check the `datetime` attribute (should be UTC)

### JavaScript Console

```javascript
// Test the converter directly
window.convertTimezone('2024-02-11T15:30:45+00:00')
// Returns: "Feb 11, 2024, 10:30:45 AM EST" (example for EST timezone)
```

## Future Enhancements

- Custom date format configuration
- Timezone name display preferences
- Client-side caching of formatted dates
- Support for relative time ("2 hours ago")

## FAQ

**Q: Will this break RSS feeds?**
A: No, RSS/Atom feeds continue to work as before with UTC timestamps.

**Q: What if JavaScript is disabled?**
A: Users will see the UTC fallback text provided in the template.

**Q: Does this impact build time?**
A: No, only adds ISO string generation (negligible overhead).

**Q: Can I customize the date format?**
A: Yes, the JavaScript uses `Intl.DateTimeFormat` which respects browser settings. For custom formats, modify the options in `timezone.js`.

## Implementation Details

See code comments in:
- `src/sitebuilder/cli.py` (date_iso generation)
- `src/sitebuilder/templates/static/js/timezone.js` (client-side logic)
- `src/sitebuilder/templates/macros/dates.html` (template helpers)
