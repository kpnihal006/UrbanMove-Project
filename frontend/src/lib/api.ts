import { auth } from "./firebase";

const USER_SERVICE    = process.env.NEXT_PUBLIC_USER_SERVICE_URL    ?? "http://localhost:8001";
const ROUTING_ENGINE  = process.env.NEXT_PUBLIC_ROUTING_ENGINE_URL  ?? "http://localhost:8002";
const ANALYTICS_URL   = process.env.NEXT_PUBLIC_ANALYTICS_SERVICE_URL ?? "http://localhost:8003";

async function authHeaders(): Promise<HeadersInit> {
  const user = auth.currentUser;
  if (!user) return { "Content-Type": "application/json" };
  const token = await user.getIdToken();
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

async function get<T>(url: string, authenticated = false): Promise<T> {
  const headers = authenticated ? await authHeaders() : { "Content-Type": "application/json" };
  const res = await fetch(url, { headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(url: string, body: unknown, authenticated = true): Promise<T> {
  const headers = authenticated ? await authHeaders() : { "Content-Type": "application/json" };
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── User Service ──────────────────────────────────────────────

export interface UserProfile {
  uid: string;
  email: string;
  display_name: string | null;
  created_at: string | null;
}

export const userApi = {
  sync: () => post<UserProfile>(`${USER_SERVICE}/users/sync`, {}),
  me:   () => get<UserProfile>(`${USER_SERVICE}/users/me`, true),
  saveTrip: (trip: {
    origin_lat: number; origin_lng: number;
    dest_lat: number;   dest_lng: number;
    origin_name?: string; dest_name?: string;
  }) => post<{ trip_id: string }>(`${USER_SERVICE}/trips`, trip),
};

// ── Routing Engine ────────────────────────────────────────────

export interface RouteStep {
  instruction: string;
  distance_m: number;
  duration_s: number;
  start_lat: number;
  start_lng: number;
  end_lat: number;
  end_lng: number;
}

export interface RouteResponse {
  route_id: string;
  origin: string;
  destination: string;
  total_distance_m: number;
  total_duration_s: number;
  summary: string;
  steps: RouteStep[];
  polyline: string;
  cached: boolean;
  computed_at: string;
}

export const routingApi = {
  getRoute: (
    originLat: number, originLng: number,
    destLat: number,   destLng: number,
    mode = "driving",
  ) =>
    get<RouteResponse>(
      `${ROUTING_ENGINE}/route?origin_lat=${originLat}&origin_lng=${originLng}&dest_lat=${destLat}&dest_lng=${destLng}&mode=${mode}`,
    ),
};

// ── Analytics Service ─────────────────────────────────────────

export interface ZoneCongestion {
  zone: string;
  vehicle_count: number;
  avg_speed_kmh: number;
  congestion_level: "low" | "medium" | "high";
}

export interface CongestionStats {
  timestamp: string;
  total_active_vehicles: number;
  zones: ZoneCongestion[];
}

export interface PredictionResult {
  zone: string;
  horizon_minutes: number;
  predicted_vehicle_count: number;
  confidence_interval_lower: number;
  confidence_interval_upper: number;
  predicted_at: string;
}

export interface DashboardStats {
  total_events_today: number;
  active_vehicles_now: number;
  avg_speed_kmh: number;
  busiest_zone: string;
  timestamp: string;
}

export const analyticsApi = {
  getCongestion: () => get<CongestionStats>(`${ANALYTICS_URL}/congestion`),
  predict: (zone: string, horizon = 30) =>
    get<PredictionResult>(`${ANALYTICS_URL}/congestion/predict?zone=${encodeURIComponent(zone)}&horizon=${horizon}`),
  getStats: () => get<DashboardStats>(`${ANALYTICS_URL}/stats`),
};
