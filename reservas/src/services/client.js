import axios from "axios";

class ApiService {
  constructor() {
    this.http = axios.create({
      baseURL: "http://localhost:8000",
      withCredentials: false,
      validateStatus: (status) => status >= 200 && status <= 404,
    });

    this.http.interceptors.request.use((config) => {
      // Add authorization header if available
      const token = localStorage.getItem("token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
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
      if (response.status >= 400) return false;
      return true;
    } catch (error) {
      console.error();
      return false;
    }
  }
}
const apiService = new ApiService();
export default apiService;
