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

  async submitForm(data) {
    try {
      const response = await this.http.post("/events", data);
      return response.data;
    } catch (error) {
      console.error("Error submitting form data:", error);
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
}

const apiService = new ApiService();
export default apiService;
