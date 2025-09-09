export interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  institution?: string;
  role: string;
  bio?: string;
  is_active: boolean;
  is_verified: boolean;
  created_at?: string;
  last_login?: string;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
  full_name?: string;
  institution?: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface UserUpdate {
  full_name?: string;
  institution?: string;
  bio?: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}