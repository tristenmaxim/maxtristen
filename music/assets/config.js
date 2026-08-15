// Configuration file
// Real values come from assets/config.local.js (gitignored, deployed manually — see config.local.js.example)
const CONFIG = {
    YOUTUBE_API_KEY: window.YOUTUBE_API_KEY || '',
    PLAYLIST_ID: window.PLAYLIST_ID || 'PLHN1fIpFfV_l9SyVIk7_dfARNzp1aCEnq'
};

// Expose config globally
window.APP_CONFIG = CONFIG;