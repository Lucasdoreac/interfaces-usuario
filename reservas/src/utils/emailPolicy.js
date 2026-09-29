export function isAllowedOrganizerEmail(email, additionalAllowlist = "") {
  if (typeof email !== "string") return false;

  const normalizedEmail = email.trim().toLowerCase();
  const additionalOrganizerEmails = new Set(
    additionalAllowlist
      .split(",")
      .map((address) => address.trim().toLowerCase())
      .filter(Boolean),
  );
  return (
    /^[a-zA-Z0-9._%+-]+@udf\.edu\.br$/.test(normalizedEmail) ||
    additionalOrganizerEmails.has(normalizedEmail)
  );
}
