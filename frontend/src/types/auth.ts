export interface UserProfile {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'user' | string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

