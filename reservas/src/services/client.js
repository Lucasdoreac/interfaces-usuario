import axios from "axios";

class ApiService {
  constructor() {
    this.http = axios.create({
      baseURL: "http://localhost:5000",
    });

    this.http.interceptors.request.use((config) => {
      // Add authorization header if available
      const token = localStorage.getItem("token");
      const email = localStorage.getItem("userEmail");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
        config.headers.email = email;
        config.headers.token = token;
      }
      return config;
    });
  }

  async postAuthMail(email) {
    try {
      const response = await this.http.post("/auth/send-link", null, {
        params: { email },
      });
      return !!response.data.message;
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
      return false;
    } catch (error) {
      console.error();
      return false;
    }
  }

  async getTypes() {
    try {
      const apiKey = "test";
      const response = await this.http.get("/types", {
        headers: {
          "X-API-Key": apiKey,
        },
      });
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
        return response.data;
      }
      return false;
    } catch (error) {
      console.error(error);
      return false;
    }
  }

  async getAvailableSlots(formattedDate, time, page = 1, page_size = 10) {
    try {
      const response = await this.http.get("/rooms/available-rooms", {
        params: { date: formattedDate, time: time, page, page_size },
      });
      if (response.status === 200) {
        return response.data;
      }
      return false;
    } catch (error) {
      console.error(error);
      return false;
    }
  }

  async submitReservationData(roomId, reservationDate, eventId) {
    try {
      const reservationData = { roomId, reservationDate, eventId };
      const response = await this.http.post("/reservations", reservationData);
      if (response.status === 201) return true;
      return false;
    } catch (error) {
      console.error(error);
      return false;
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
