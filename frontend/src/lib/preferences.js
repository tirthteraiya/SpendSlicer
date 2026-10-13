// Storage can be disabled in native webviews and private browser sessions.
export const readPreference = (key) => {
  try { return localStorage.getItem(key) || ""; } catch { return ""; }
};
export const writePreference = (key, value) => {
  try { localStorage.setItem(key, value); } catch { /* preferences are optional */ }
};
