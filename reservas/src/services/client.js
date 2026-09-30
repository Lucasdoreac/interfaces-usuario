export class ApiService {
  constructor({
    baseURL = import.meta.env?.VITE_API_BASE_URL || "http://localhost:5000",
    fetchImpl = globalThis.fetch,
    storage = globalThis.localStorage,
  } = {}) {
    this.baseURL = baseURL.replace(/\/$/, "");
    this.fetchImpl = fetchImpl.bind(globalThis);
    this.storage = storage;
    this.http = {
      get: (path, config) => this.request("GET", path, undefined, config),
      post: (path, data, config) => this.request("POST", path, data, config),
      put: (path, data, config) => this.request("PUT", path, data, config),
    };
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
    if (!response.ok) {
      const error = new Error(`Request failed with status code ${response.status}`);
      error.status = response.status;
      error.data = responseData;
      throw error;
    }
    return { status: response.status, data: responseData };
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
      this.storage?.clear();
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
        response = await this.http.put(`/events/${eventId}`, requestData);
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
        `/events/${eventId}/submit`,
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
