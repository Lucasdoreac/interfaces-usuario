// One request at a time per button: a second click while the first is pending is ignored.
export async function runSingleFlight(flag, action, onChange = () => {}) {
  if (flag.current) return undefined;
  flag.current = true;
  onChange(true);
  try {
    return await action();
  } finally {
    flag.current = false;
    onChange(false);
  }
}
