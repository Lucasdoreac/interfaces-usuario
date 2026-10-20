export function isAllowedOrganizerEmail(email) {
  if (typeof email !== "string") return false;

  const normalizedEmail = email.trim().toLowerCase();
  return (
    /^[a-zA-Z0-9._%+-]+@udf\.edu\.br$/.test(normalizedEmail) ||
    normalizedEmail === "danrley.pereira@cs.udf.edu.br"
  );
}
