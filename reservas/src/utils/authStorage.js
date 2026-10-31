// End the previous user's session and drafts while keeping only their visual preference.
export function clearAuthStorage(storage) {
  if (!storage) return;
  const theme = storage.getItem("theme");
  storage.clear();
  if (theme === "light" || theme === "dark") storage.setItem("theme", theme);
}
