# MoonBite Wallet Settings & Preferences Implementation

## Overview

A complete preferences management system for the MoonBite PWA wallet with server-side persistence, localStorage sync, and comprehensive UI controls.

## Architecture

### 1. Database Layer (wallet_history.py)

#### Preferences Table Schema
```sql
CREATE TABLE preferences (
    user_session_id TEXT PRIMARY KEY,
    language TEXT DEFAULT 'en',
    currency TEXT DEFAULT 'USD',
    theme TEXT DEFAULT 'auto',
    time_format TEXT DEFAULT 'relative',
    amount_format TEXT DEFAULT 'full',
    notification_tx INTEGER DEFAULT 1,
    notification_price INTEGER DEFAULT 1,
    auto_lock_mins INTEGER DEFAULT 15,
    decimal_places INTEGER DEFAULT 8,
    hide_zero_balance INTEGER DEFAULT 0,
    sort_accounts TEXT DEFAULT 'created',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
```

#### Core Functions

**get_preference_defaults() -> dict**
- Returns default preferences for new users
- Used when user has no stored preferences

**validate_preference_value(key: str, value: any) -> bool**
- Validates preference key-value pairs before storage
- Enforces type checking and allowed values
- Raises ValueError for invalid inputs

**get_preferences(session_id: str) -> dict**
- Retrieves all user preferences with defaults filled in
- Returns dict with all preference keys
- Session-isolated access

**update_preferences(session_id: str, updates: dict) -> dict**
- Updates any preference settings
- Creates row if doesn't exist (auto-initialization)
- Returns all preferences after update
- Validates all values before updating

**reset_preferences(session_id: str) -> dict**
- Resets all preferences to defaults
- Useful for "factory reset" scenarios

**delete_preferences(session_id: str) -> bool**
- Removes all preferences for a session
- Used during account deletion

### 2. Flask API Endpoints (web_app.py)

All endpoints use session_id = request.remote_addr for user isolation.

#### GET /api/wallet/preferences
Get all current user preferences with defaults.
```json
{
    "status": "success",
    "preferences": {
        "language": "en",
        "currency": "USD",
        "theme": "auto",
        ...
    }
}
```

#### PATCH /api/wallet/preferences
Update one or more preferences.
```json
Request:
{
    "theme": "dark",
    "currency": "EUR",
    "auto_lock_mins": 30
}

Response:
{
    "status": "success",
    "preferences": { ... }
}
```

#### GET /api/wallet/preferences/defaults
Get default values for all preferences.
```json
{
    "status": "success",
    "defaults": { ... }
}
```

#### POST /api/wallet/preferences/reset
Reset all preferences to defaults.
```json
{
    "status": "success",
    "message": "Preferences reset to defaults",
    "preferences": { ... }
}
```

### 3. Frontend Implementation (wallet-pwa.html)

#### SettingsManager Class

A JavaScript class handling all preference interactions:

**Properties:**
- `STORAGE_KEY` - localStorage key for caching
- `API_ENDPOINT` - REST API endpoint
- `preferences` - Current preference values
- `defaults` - Default values

**Methods:**

`async load()`
- Loads preferences from server via API
- Falls back to localStorage cache
- Uses defaults if no cached data
- Automatically applies preferences

`async update(updates: dict)`
- Updates one or more preferences
- Sends to server, syncs localStorage
- Applies preferences immediately
- Returns true on success

`async reset()`
- Resets all preferences to defaults
- Updates UI and storage
- Returns true on success

`applyPreferences()`
- Applies theme to document
- Sets auto-lock timeout
- Prepares for language/i18n

`updateUI()`
- Syncs all form inputs to current values
- Called when opening settings modal
- Ensures UI reflects server state

`get(key: str)`
- Returns preference value with fallback to default

#### Settings Modal UI

Four-tab interface:

**Display Tab:**
- Language selector (en, es, fr, de, ja, zh)
- Theme selector (light, dark, auto)
- Currency selector (USD, EUR, GBP, JPY, CNY, BTC, MBITE)
- Decimal places selector (2, 4, 6, 8)
- Amount format (full, short, scientific)
- Time format (relative, absolute, unix)
- Hide zero balances toggle
- Sort accounts selector

**Security Tab:**
- Auto-lock timeout selector (Never to 2 hours)
- Reset wallet button (danger zone)
- Export seed phrase button

**Notifications Tab:**
- Transaction notifications toggle
- Price alerts toggle
- Privacy notice

**About Tab:**
- Version info
- Links (GitHub, Website, Privacy Policy)
- License information

#### Event Listeners

- Tab switching between Display/Security/Notifications/About
- Individual setting change handlers
- Reset to defaults confirmation
- Wallet reset confirmation
- Settings modal open/close

#### Theme Switching

Support for light, dark, and auto (system preference):
```javascript
document.documentElement.style.colorScheme = 'light dark'; // auto
document.documentElement.style.colorScheme = 'dark';       // dark only
document.documentElement.style.colorScheme = 'light';      // light only
```

#### Auto-Lock Timer

Implemented in initialization:
- Uses `auto_lock_mins` preference
- Triggers on inactivity
- Resets on user activity (click, keypress, touch)
- Gracefully handles 0 value (never auto-lock)

## Preference Reference

| Key | Type | Default | Options |
|-----|------|---------|---------|
| language | string | 'en' | en, es, fr, de, ja, zh |
| currency | string | 'USD' | USD, EUR, GBP, JPY, CNY, BTC, MBITE |
| theme | string | 'auto' | light, dark, auto |
| time_format | string | 'relative' | relative, absolute, unix |
| amount_format | string | 'full' | full, short, scientific |
| notification_tx | int | 1 | 0, 1 |
| notification_price | int | 1 | 0, 1 |
| auto_lock_mins | int | 15 | 0-120 |
| decimal_places | int | 8 | 2-8 |
| hide_zero_balance | int | 0 | 0, 1 |
| sort_accounts | string | 'created' | created, updated, name, balance |

## Usage Examples

### Loading Settings on App Start
```javascript
const settingsManager = new SettingsManager();
await settingsManager.load();
// Preferences loaded and applied
```

### Updating a Single Preference
```javascript
await settingsManager.update({ theme: 'dark' });
// UI and server automatically synced
```

### Resetting to Defaults
```javascript
await settingsManager.reset();
// All preferences reset, UI updated
```

### Getting a Preference Value
```javascript
const currency = settingsManager.get('currency');
// Returns current value or default
```

## Validation

All preferences are validated on update:

**Type Checking:** Each preference has expected type (str, int, bool)

**Allowed Values:** Some preferences have specific allowed values
- Example: theme must be 'light', 'dark', or 'auto'

**Range Checking:** Numeric preferences have min/max bounds
- Example: decimal_places must be 2-8

**Errors:** Invalid values raise ValueError on server, returned as error response

## Offline Support

- Preferences cached in localStorage (`moonbite_preferences` key)
- Works offline using cache
- Syncs with server when connection restored
- Graceful fallback to defaults if cache missing

## Security Considerations

- User isolation via session_id (IP address)
- No sensitive data stored (passwords remain separate)
- Settings apply only to UX, not security mechanisms
- Privacy notice in notifications tab
- Export/reset options clearly marked

## Future Enhancements

1. **Language/i18n Support:**
   - Create strings object with translations
   - Apply language setting to UI
   - Load translation JSON on language change

2. **Price Alerts:**
   - Implement threshold-based notifications
   - Store alert prices in preferences
   - Integrate with price data service

3. **Account Sort:**
   - Use sort_accounts preference when displaying account list
   - Filter hide_zero_balance when rendering

4. **Currency Formatting:**
   - Apply decimal_places to all balance displays
   - Use amount_format for scientific notation
   - Convert currency if not MBITE

5. **Time Formatting:**
   - Apply time_format to all transaction timestamps
   - Convert between formats for display

6. **Two-Factor Auth:**
   - Add to Security tab
   - Integrate with server authentication

## Database Indexes

Index on `user_session_id` for fast preference lookups:
```sql
CREATE INDEX idx_preferences_session ON preferences(user_session_id);
```

## Error Handling

**Server-side:**
- ValueError for validation failures → 400 Bad Request
- Generic exceptions → 500 Internal Server Error

**Client-side:**
- Network errors fall back to localStorage
- Invalid responses logged to console
- User notified of failures via alerts
