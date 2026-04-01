import { fetchApi } from "./apiBase";

export interface UserSettings {
  default_symbol?: string | null;
  default_strategy?: string | null;
  default_from_date?: string | null;
  default_to_date?: string | null;
  massive_api_key?: string | null;
  alpaca_api_key?: string | null;
  alpaca_api_secret?: string | null;
  etrade_consumer_key?: string | null;
  etrade_consumer_secret?: string | null;
  etrade_access_token?: string | null;
  etrade_access_secret?: string | null;
  etrade_sandbox?: boolean | null;
  fred_api_key?: string | null;
  bls_api_key?: string | null;
  bea_api_key?: string | null;
  openai_api_key?: string | null;
}

export async function getUserSettings(): Promise<UserSettings> {
  return fetchApi<UserSettings>("/user/settings");
}

export async function updateUserSettings(
  body: UserSettings
): Promise<UserSettings> {
  return fetchApi<UserSettings>("/user/settings", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

