"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { onAuthStateChanged } from "firebase/auth";
import { collection, onSnapshot, query, limit } from "firebase/firestore";
import { auth, db } from "@/lib/firebase";
import { routingApi, userApi, type RouteResponse } from "@/lib/api";
import Navbar from "@/components/Navbar";
import type { Vehicle } from "@/types";

const MAPS_API_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "YOUR_GOOGLE_MAPS_API_KEY";
const PARIS = { lat: 48.8566, lng: 2.3522 };

export default function MapPage() {
  const router  = useRouter();
  const mapRef  = useRef<HTMLDivElement>(null);
  const gMapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<Map<string, google.maps.Marker>>(new Map());
  const polylineRef = useRef<google.maps.Polyline | null>(null);

  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [route, setRoute]       = useState<RouteResponse | null>(null);
  const [loading, setLoading]   = useState(true);
  const [routeLoading, setRouteLoading] = useState(false);
  const [originLat, setOriginLat]   = useState("48.8566");
  const [originLng, setOriginLng]   = useState("2.3522");
  const [destLat, setDestLat]       = useState("48.8738");
  const [destLng, setDestLng]       = useState("2.2950");

  // Auth guard
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (user) => {
      if (!user) router.replace("/login");
      else setLoading(false);
    });
    return () => unsub();
  }, [router]);

  // Load Google Maps script
  useEffect(() => {
    if (loading || !mapRef.current) return;
    if (window.google?.maps) {
      initMap();
      return;
    }
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${MAPS_API_KEY}&libraries=geometry`;
    script.async = true;
    script.onload = initMap;
    document.head.appendChild(script);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  const initMap = useCallback(() => {
    if (!mapRef.current) return;
    gMapRef.current = new window.google.maps.Map(mapRef.current, {
      center: PARIS,
      zoom: 12,
      mapTypeId: "roadmap",
      styles: DARK_MAP_STYLES,
      disableDefaultUI: false,
      zoomControl: true,
      streetViewControl: false,
    });
  }, []);

  // Firestore real-time vehicle listener
  useEffect(() => {
    if (loading) return;
    const q = query(collection(db, "vehicles"), limit(50));
    const unsub = onSnapshot(q, (snapshot) => {
      const docs: Vehicle[] = [];
      snapshot.forEach((doc) => docs.push(doc.data() as Vehicle));
      setVehicles(docs);
    });
    return () => unsub();
  }, [loading]);

  // Update map markers when vehicles change
  useEffect(() => {
    const map = gMapRef.current;
    if (!map || !window.google?.maps) return;

    const currentIds = new Set(vehicles.map((v) => v.vehicle_id));

    // Remove stale markers
    markersRef.current.forEach((marker, id) => {
      if (!currentIds.has(id)) {
        marker.setMap(null);
        markersRef.current.delete(id);
      }
    });

    // Update or create markers
    vehicles.forEach((v) => {
      const pos = { lat: v.lat, lng: v.lng };
      if (markersRef.current.has(v.vehicle_id)) {
        markersRef.current.get(v.vehicle_id)!.setPosition(pos);
      } else {
        const marker = new window.google.maps.Marker({
          position: pos,
          map,
          title: `${v.vehicle_id} · ${v.speed_kmh} km/h`,
          icon: {
            path: window.google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
            scale: 4,
            fillColor: v.status === "active" ? "#3b82f6" : "#6b7280",
            fillOpacity: 1,
            strokeColor: "#fff",
            strokeWeight: 1,
            rotation: v.heading,
          },
        });
        markersRef.current.set(v.vehicle_id, marker);
      }
    });
  }, [vehicles]);

  const computeRoute = async () => {
    setRouteLoading(true);
    try {
      const r = await routingApi.getRoute(
        parseFloat(originLat), parseFloat(originLng),
        parseFloat(destLat),   parseFloat(destLng),
      );
      setRoute(r);
      drawPolyline(r.polyline);
      await userApi.saveTrip({
        origin_lat: parseFloat(originLat), origin_lng: parseFloat(originLng),
        dest_lat:   parseFloat(destLat),   dest_lng:   parseFloat(destLng),
      });
    } catch (err) {
      console.error("Route error:", err);
    } finally {
      setRouteLoading(false);
    }
  };

  const drawPolyline = (encoded: string) => {
    const map = gMapRef.current;
    if (!map || !window.google?.maps) return;
    polylineRef.current?.setMap(null);
    const path = window.google.maps.geometry.encoding.decodePath(encoded);
    polylineRef.current = new window.google.maps.Polyline({
      path,
      geodesic: true,
      strokeColor: "#3b82f6",
      strokeOpacity: 0.9,
      strokeWeight: 4,
      map,
    });
    const bounds = new window.google.maps.LatLngBounds();
    path.forEach((p) => bounds.extend(p));
    map.fitBounds(bounds, { top: 60, bottom: 20, left: 20, right: 20 });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <>
      <Navbar />
      <div className="pt-14 h-screen flex">
        {/* Map */}
        <div ref={mapRef} className="flex-1" />

        {/* Sidebar */}
        <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col overflow-y-auto">
          {/* Vehicle count */}
          <div className="p-4 border-b border-gray-800">
            <p className="text-xs text-gray-500">Active vehicles on map</p>
            <p className="text-2xl font-bold text-blue-300">{vehicles.length}</p>
            <p className="text-xs text-gray-600 mt-0.5">Updated in real-time via Firestore</p>
          </div>

          {/* Route planner */}
          <div className="p-4 border-b border-gray-800">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Route planner</h3>
            <div className="space-y-2 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-gray-500 block mb-1">Origin lat</label>
                  <input
                    value={originLat}
                    onChange={(e) => setOriginLat(e.target.value)}
                    className="w-full px-2 py-1.5 rounded bg-gray-800 border border-gray-700 text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="text-gray-500 block mb-1">Origin lng</label>
                  <input
                    value={originLng}
                    onChange={(e) => setOriginLng(e.target.value)}
                    className="w-full px-2 py-1.5 rounded bg-gray-800 border border-gray-700 text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="text-gray-500 block mb-1">Dest lat</label>
                  <input
                    value={destLat}
                    onChange={(e) => setDestLat(e.target.value)}
                    className="w-full px-2 py-1.5 rounded bg-gray-800 border border-gray-700 text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="text-gray-500 block mb-1">Dest lng</label>
                  <input
                    value={destLng}
                    onChange={(e) => setDestLng(e.target.value)}
                    className="w-full px-2 py-1.5 rounded bg-gray-800 border border-gray-700 text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
              <button
                onClick={() => void computeRoute()}
                disabled={routeLoading}
                className="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900 disabled:cursor-not-allowed text-white font-medium transition"
              >
                {routeLoading ? "Computing…" : "Get route"}
              </button>
            </div>

            {route && (
              <div className="mt-3 p-3 rounded-lg bg-gray-800 text-xs space-y-1">
                <p className="text-gray-300 font-medium">{route.summary}</p>
                <p className="text-gray-500">
                  {(route.total_distance_m / 1000).toFixed(1)} km ·{" "}
                  {Math.ceil(route.total_duration_s / 60)} min
                </p>
                {route.cached && (
                  <p className="text-green-500">From cache</p>
                )}
              </div>
            )}
          </div>

          {/* Vehicle list */}
          <div className="p-4 flex-1">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Vehicles</h3>
            <div className="space-y-1.5 max-h-64 overflow-y-auto scrollbar-hide">
              {vehicles.slice(0, 20).map((v) => (
                <div
                  key={v.vehicle_id}
                  className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-800 text-xs"
                >
                  <span className="text-gray-300 font-mono">{v.vehicle_id}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500">{v.speed_kmh} km/h</span>
                    <span
                      className={`w-2 h-2 rounded-full ${
                        v.status === "active" ? "bg-green-400" : "bg-gray-600"
                      }`}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

const DARK_MAP_STYLES: google.maps.MapTypeStyle[] = [
  { elementType: "geometry",     stylers: [{ color: "#1a1a2e" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#8ec3b9" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#1a3646" }] },
  { featureType: "road",         elementType: "geometry",          stylers: [{ color: "#304a7d" }] },
  { featureType: "road",         elementType: "geometry.stroke",   stylers: [{ color: "#255763" }] },
  { featureType: "water",        elementType: "geometry",          stylers: [{ color: "#17263c" }] },
  { featureType: "poi",          stylers: [{ visibility: "off" }] },
  { featureType: "transit",      stylers: [{ visibility: "off" }] },
];
