import { apiService } from './api';
import { API_ENDPOINTS } from '@/utils/constants';
import { 
  User, 
  LoginCredentials, 
  RegisterData, 
  AuthToken, 
  UserUpdate 
} from '@/types/auth';

export class AuthService {
  /**
   * Register a new user account
   */
  async register(userData: RegisterData): Promise<User> {
    return apiService.post<User>(API_ENDPOINTS.AUTH.REGISTER, userData);
  }

  /**
   * Authenticate user and return access token
   */
  async login(credentials: LoginCredentials): Promise<AuthToken> {
    const response = await apiService.post<AuthToken>(
      API_ENDPOINTS.AUTH.LOGIN, 
      credentials
    );
    
    // Store token in localStorage
    apiService.setAuthToken(response.access_token);
    
    return response;
  }

  /**
   * Logout user and clear authentication data
   */
  async logout(): Promise<void> {
    try {
      await apiService.post(API_ENDPOINTS.AUTH.LOGOUT);
    } finally {
      // Always clear local auth data, even if API call fails
      apiService.clearAuthToken();
    }
  }

  /**
   * Get current user profile
   */
  async getCurrentUser(): Promise<User> {
    return apiService.get<User>(API_ENDPOINTS.AUTH.ME);
  }

  /**
   * Update current user profile
   */
  async updateProfile(userData: UserUpdate): Promise<User> {
    return apiService.put<User>(API_ENDPOINTS.AUTH.UPDATE_PROFILE, userData);
  }

  /**
   * Check if user is currently authenticated
   */
  isAuthenticated(): boolean {
    return !!apiService.getAuthToken();
  }

  /**
   * Get stored auth token
   */
  getToken(): string | null {
    return apiService.getAuthToken();
  }

  /**
   * Validate token by making a request to the protected endpoint
   */
  async validateToken(): Promise<boolean> {
    try {
      await this.getCurrentUser();
      return true;
    } catch {
      apiService.clearAuthToken();
      return false;
    }
  }
}

export const authService = new AuthService();
export default authService;