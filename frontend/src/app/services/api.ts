/**
 * API Service Layer
 * All backend communication is routed through /api (proxied to localhost:8000 by Vite).
 */

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "";

function abortSignal(ms = 30_000): AbortSignal {
  const c = new AbortController();
  setTimeout(() => c.abort(), ms);
  return c.signal;
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<{ success: true; data: T } | { success: false; error: string; details?: unknown }> {
  try {
    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
      signal: options.signal ?? abortSignal(),
    });
    const json = await res.json();
    if (!res.ok) {
      return {
        success: false,
        error: json.reason ?? json.error ?? `HTTP ${res.status}`,
        details: json,
      };
    }
    return { success: true, data: json as T };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : "Network error",
    };
  }
}

export interface RegisterPayload {
  user_id: string;
  face_image_b64: string;
  pin: string;
}

export interface RegisterResponse {
  success: boolean;
  user_id: string;
  reason: string;
}

export interface InitiatePayload {
  user_id: string;
  face_image_b64: string;
  amount_rupees: number;
  recipient_upi: string;
}

export interface InitiateResponse {
  tx_id: string;
  stego_image_b64: string;
  salt_b64: string;
  pin_positions: number[];
  amount_rupees: number;
  recipient_upi: string;
}

export interface VerifyPayload {
  tx_id: string;
  pin_digits: Record<string, string>;
}

export interface VerifyResponse {
  authorized: boolean;
  receipt: Record<string, unknown> | null;
  reason: string;
  attempts_remaining: number;
}

export interface HealthResponse {
  status: string;
  device: string;
  payload_bits: number;
  cuda_available: boolean;
  timestamp: number;
}

export interface TransactionRecord {
  tx_id: string;
  sender_upi: string;
  recipient_upi: string;
  amount_rupees: number;
  timestamp: number;
  status: string;
}

export const apiClient = {
  async health() {
    return request<HealthResponse>("/api/health", { signal: abortSignal(5_000) });
  },

  async register(payload: RegisterPayload) {
    return request<RegisterResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async initiateTransaction(payload: InitiatePayload) {
    return request<InitiateResponse>("/api/transaction/initiate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async verifyTransaction(payload: VerifyPayload) {
    return request<VerifyResponse>("/api/transaction/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async listTransactions(userId: string) {
    return request<{ transactions: TransactionRecord[] }>(
      `/api/transactions/list?user_id=${encodeURIComponent(userId)}`
    );
  },
};
