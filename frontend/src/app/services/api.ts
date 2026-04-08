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

    // Read body as text first — res.json() throws on empty bodies
    const text = await res.text();

    if (!text.trim()) {
      return {
        success: false,
        error: res.ok
          ? `Server returned an empty response (HTTP ${res.status})`
          : `Server error (HTTP ${res.status}) — backend may be unavailable`,
      };
    }

    let json: unknown;
    try {
      json = JSON.parse(text);
    } catch {
      return {
        success: false,
        error: `Invalid response from server: ${text.slice(0, 120)}`,
      };
    }

    if (!res.ok) {
      const errorData = json as Record<string, unknown>;
      return {
        success: false,
        error: (
          (errorData.reason as string) ??
          (errorData.error as string) ??
          `HTTP ${res.status}`
        ),
        details: json,
      };
    }

    return { success: true, data: json as T };
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      return { success: false, error: "Request timed out — backend may be offline" };
    }
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
