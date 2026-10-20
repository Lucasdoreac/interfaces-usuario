export function clearAuthStorage(storage) {
  storage?.removeItem("token");
  storage?.removeItem("userEmail");
}
