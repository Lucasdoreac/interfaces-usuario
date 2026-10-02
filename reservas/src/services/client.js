import { assertEventId } from "../utils/eventId.js";

export class ApiService {
  constructor({
    baseURL = import.meta.env?.VITE_API_BASE_URL || "http://localhost:5000",
    fetchImpl = globalThis.fetch,
    storage = globalThis.localStorage,
    wakeTimeoutMs = 90000,
    logoutTimeoutMs = 5000,
  } = {}) {
    this.baseURL = baseURL.replace(/\/$/, "");
    this.fetchImpl = fetchImpl.bind(globalThis);
    this.storage = storage;
    this.wakeTimeoutMs = wakeTimeoutMs;
    this.logoutTimeoutMs = logoutTimeoutMs;
    this.wakingListeners = new Set();
    this.pendingWakes = new Map();
    this.http = {
      get: (path, config) => this.request("GET", path, undefined, config),
      post: (path, data, config) => this.request("POST", path, data, config),
      put: (path, data, config) => this.request("PUT", path, data, config),
    };
  }

  // Subscribe to "a service is being woken"; returns the unsubscribe function.
  onWaking(listener) {
    this.wakingListeners.add(listener);
    return () => this.wakingListeners.delete(listener);
  }

  // The API answers 503 with `wake_url` (the public Auth /health) when Auth is
  // asleep. Only an https /health URL is followed; the request is opaque.
  safeWakeUrl(value) {
    try {
      const url = new URL(value);
      return url.protocol === "https:" && url.pathname === "/health" && !url.search ? url.href : null;
    } catch {
      return null;
    }
  }

  // A request from the browser wakes the free-plan service (the API's cannot),
  // and is held until it is up, so waiting for it is the wait for Auth.
  // Concurrent requests that hit the same sleeping service share one wake call.
  wakeService(url) {
    if (!this.pendingWakes.has(url)) {
      const pending = this.wakeOnce(url).finally(() => this.pendingWakes.delete(url));
      this.pendingWakes.set(url, pending);
    }
    return this.pendingWakes.get(url);
  }

  async wakeOnce(url) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.wakeTimeoutMs);
    try {
      await this.fetchImpl(url, { mode: "no-cors", cache: "no-store", signal: controller.signal });
    } catch {
      // Still asleep or unreachable: the retry below reports the final error.
    } finally {
      clearTimeout(timer);
    }
  }

  async request(method, path, data, config = {}) {
    const url = new URL(`${this.baseURL}${path}`);
    const params = config.params || {};
    const entries = params instanceof URLSearchParams
      ? params.entries()
      : Object.entries(params);
    for (const [key, value] of entries) {
      if (value !== undefined && value !== null) url.searchParams.set(key, value);
    }

    const headers = new Headers(config.headers || {});
    const token = this.storage?.getItem("token");
    const email = this.storage?.getItem("userEmail");
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
      if (email) headers.set("email", email);
      headers.set("token", token);
    }
    if (data !== undefined && data !== null) headers.set("Content-Type", "application/json");

    const response = await this.fetchImpl(url, {
      method,
      headers,
      body: data === undefined || data === null ? undefined : JSON.stringify(data),
    });
    const contentType = response.headers.get("content-type") || "";
    const responseData = contentType.includes("json")
      ? await response.json()
      : await response.text();
    if (response.status === 503 && !config.afterWake) {
      const wakeUrl = this.safeWakeUrl(responseData?.wake_url);
      if (wakeUrl) {
        this.wakingListeners.forEach((listener) => listener());
        await this.wakeService(wakeUrl);
        return this.request(method, path, data, { ...config, afterWake: true });
      }
    }
    if (!response.ok) {
      const error = new Error(`Request failed with status code ${response.status}`);
      error.status = response.status;
      error.data = responseData;
      throw error;
    }
    return { status: response.status, data: responseData };
  }

  // Ends the session at the Auth service (through the API) so the token stops working there too.
  // Best effort and bounded: leaving must never wait for, or fail because of, a sleeping or
  // unreachable service, so there is no wake-and-retry and nothing here throws. The caller
  // clears the local session afterwards either way. Resolves true only when the server confirmed.
  async logoutSession() {
    const token = this.storage?.getItem("token");
    const email = this.storage?.getItem("userEmail");
    if (!token || !email) return false;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.logoutTimeoutMs);
    try {
      const response = await this.fetchImpl(new URL(`${this.baseURL}/auth/logout`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, token }),
        signal: controller.signal,
      });
      return response.ok;
    } catch {
      return false;
    } finally {
      clearTimeout(timer);
    }
  }

  async postAuthMail(email) {
    try {
      const response = await this.http.post("/auth/send-link", null, {
        params: { email },
      });
      if (response.status === 202) return { dryRun: true };
      this.storage?.clear();
      this.storage?.setItem("userEmail", email);
      return !!response.data;
    } catch (error) {
      console.error(error);
      return null;
    }
  }

  // The e-mailed link token is single use: trade it for a session token. The
  // result is remembered per link so a repeated call (a double effect run) does
  // not spend it twice.
  exchangeToken(linkToken, email) {
    this.exchanges ??= new Map();
    const key = `${email}\0${linkToken}`;
    if (!this.exchanges.has(key)) {
      this.exchanges.set(key, this.exchangeOnce(linkToken, email));
    }
    return this.exchanges.get(key);
  }

  async exchangeOnce(linkToken, email) {
    try {
      const response = await this.http.post("/auth/exchange", { email, token: linkToken });
      return typeof response.data?.token === "string" ? response.data.token : null;
    } catch (error) {
      if (error.status !== 503) console.error("Troca do link falhou:", error.status);
      return null;
    }
  }

  async validateToken(token, email) {
    try {
      const params = new URLSearchParams({ token, email });
      const response = await this.http.get("/auth/validate", {
        params: params,
      });
      if (response.status === 200) return true;
      this.storage?.clear();
      return false;
    } catch (error) {
      // Auth unavailable (503) says nothing about the token: keep the session.
      if (error.status !== 503) this.storage?.clear();
      return false;
    }
  }

  async getTypes() {
    try {
      const response = await this.http.get("/types");
      return response.data;
    } catch (error) {
      console.error("Erro ao obter dados:", error);
      return null;
    }
  }

  async searchCourses(query) {
    try {
      const response = await this.http.get("/courses", {
        params: { course_name: query },
      });
      return response.data;
    } catch (error) {
      console.error("Erro ao buscar cursos:", error);
      return null;
    }
  }

  async getCourseById(courseId) {
    try {
      const response = await this.http.get("/courses", {
        params: { course_id: courseId },
      });
      if (response.status === 200) {
        return response.data.courses;
      }
      return null;
    } catch (error) {
      console.error("Erro ao obter curso:", error);
      return null;
    }
  }

  async submitEventData(data, status, eventId = null) {
    try {
      const requestData = { ...data, status };
      let response;
      // Update an event object
      if (eventId) {
        response = await this.http.put(`/events/${assertEventId(eventId)}`, requestData);
      } else {
        // Create a new event object
        response = await this.http.post("/events", requestData);
      }
      return response.data.eventId;
    } catch (error) {
      console.error("Erro ao enviar dados:", error);
      throw error;
    }
  }

  async submitEventForApproval(eventId, data) {
    try {
      const response = await this.http.post(
        `/events/${assertEventId(eventId)}/submit`,
        data,
      );
      return response.data.eventId;
    } catch (error) {
      console.error("Erro ao enviar dados:", error);
      throw error;
    }
  }

  async getUserEvents(userEmail) {
    try {
      const response = await this.http.get("/events", {
        params: { userEmail: userEmail },
      });
      if (response.status === 200) {
        return response.data;
      }
      return false;
    } catch (error) {
      console.error();
      return false;
    }
  }

  async getEventsReservations(eventId) {
    try {
      const response = await this.http.get("/reservations", {
        params: { eventId },
      });
      if (response.status === 200) {
        let reservation = response.data;

        // Modify the date strings to change "GMT" to "GMT-3" before parsing
        if (reservation && reservation.startAt) {
          // Replace GMT with GMT-3 in the date strings
          const startAtString = reservation.startAt.replace(" GMT", " GMT-3");
          const endAtString = reservation.endAt.replace(" GMT", " GMT-3");

          // Now parse the modified strings to Date objects
          const startDate = new Date(startAtString);
          const endDate = new Date(endAtString);

          reservation = {
            ...reservation,
            startAt: startDate,
            endAt: endDate,
          };
        }
        return reservation;
      }
      return null;
    } catch (error) {
      console.error("Error fetching reservations:", error);
      return null;
    }
  }

  async getAvailableSlots(
    formattedDate,
    time,
    page = 1,
    page_size = 10,
    roomName = ""
  ) {
    try {
      const params = {
        date: formattedDate,
        time: time,
        page,
        page_size,
      };

      if (roomName) {
        params.room_name = roomName;
      }

      const response = await this.http.get("/rooms/available-rooms", {
        params: params,
      });

      if (response.status === 200) {
        return response.data;
      }
      return false;
    } catch (error) {
      console.error(error);
      throw error;
    }
  }

  async getRoomById(roomId) {
    try {
      const response = await this.http.get("/rooms", {
        params: { roomId },
      });
      if (response.status === 200) {
        return response.data;
      }
      return null;
    } catch (error) {
      console.error("Erro ao obter sala:", error);
      return null;
    }
  }
}

const apiService = new ApiService();
export default apiService;
