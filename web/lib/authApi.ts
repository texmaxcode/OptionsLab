import { fetchApi } from "./apiBase";
import { setToken } from "./auth";

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export async function register(email: string, password: string): Promise<void> {
  const data = await fetchApi<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  });
  setToken(data.access_token);
}

export async function login(email: string, password: string): Promise<void> {
  const data = await fetchApi<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  });
  setToken(data.access_token);
}
