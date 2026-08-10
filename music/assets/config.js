// Configuration file
// For production, these values should be set via environment variables or build process
const CONFIG = {
    YOUTUBE_API_KEY: window.YOUTUBE_API_KEY || 'REDACTED_DEAD_GOOGLE_API_KEY',
    PLAYLIST_ID: window.PLAYLIST_ID || 'PLHN1fIpFfV_l9SyVIk7_dfARNzp1aCEnq'
};

// Expose config globally
window.APP_CONFIG = CONFIG;