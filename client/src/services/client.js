import axios from 'axios';

class ApiService {
  constructor() {
    this.http = axios.create({
      baseURL: 'http://localhost:5000',
    });

    this.http.interceptors.request.use(config => {
      // Add authorization header if available
      const token = localStorage.getItem('token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
  }

  async postAuthMail(email) {
    try {
      const response = await this.http.post('/auth-mail', null, {
        params: { email },
      });
      return response.data;
    } catch (error) {
      console.error(error);
      return null;
    }
  }
}
const apiService = new ApiService();
export default apiService;