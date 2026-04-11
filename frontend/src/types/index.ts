export interface Vehicle {
  vehicle_id: string;
  lat: number;
  lng: number;
  speed_kmh: number;
  heading: number;
  zone: string;
  status: "active" | "idle" | "offline";
  event_ts: string;
  updated_at?: { seconds: number; nanoseconds: number };
}

export interface LatLng {
  lat: number;
  lng: number;
}

export type CongestionLevel = "low" | "medium" | "high";

export const CONGESTION_COLORS: Record<CongestionLevel, string> = {
  low:    "#22c55e",
  medium: "#f59e0b",
  high:   "#ef4444",
};

export const PARIS_CENTER: LatLng = { lat: 48.8566, lng: 2.3522 };
