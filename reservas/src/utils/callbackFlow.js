// Login callback decisions, kept free of React so they can be tested.
//
// The e-mailed link is single use. Mail scanners (Microsoft Defender Safe
// Links and similar) open links and run their JavaScript before the person
// does, so the page must never spend the link on load: it only offers a button,
// and the exchange runs on the click, which scanners do not make.

// On load: reuse a session stored by an earlier visit; never touch the link.
export async function resolveCallback({ api, storage, email, linkToken }) {
  if (!email) return { action: "organizer" };
  const stored = storage.getItem("token");
  if (stored && storage.getItem("userEmail") === email && (await api.validateToken(stored, email))) {
    return { action: "events" };
  }
  return { action: linkToken ? "needs-click" : "waiting" };
}

// On the click: trade the link for a session token.
export async function signIn({ api, storage, email, linkToken }) {
  const session = await api.exchangeToken(linkToken, email);
  if (!session) return { action: "denied" };
  storage.clear();
  storage.setItem("userEmail", email);
  storage.setItem("token", session);
  return { action: "events" };
}
