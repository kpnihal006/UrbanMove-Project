"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { analyticsApi, type DashboardStats, type CongestionStats } from "@/lib/api";
import Navbar from "@/components/Navbar";
import CongestionTable from "@/components/CongestionTable";
import StatCard from "@/components/StatCard";
import PredictionPanel from "@/components/PredictionPanel";

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats]           = useState<DashboardStats | null>(null);
  const [congestion, setCongestion] = useState<CongestionStats | null>(null);
  const [loading, setLoading]       = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const refresh = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([
        analyticsApi.getStats(),
        analyticsApi.getCongestion(),
      ]);
      setStats(s);
      setCongestion(c);
      setLastRefresh(new Date());
    } catch (err) {
      console.error("Dashboard fetch error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (user) => {
      if (!user) {
        router.replace("/login");
      } else {
        void refresh();
      }
    });
    return () => unsub();
  }, [router, refresh]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => void refresh(), 30_000);
    return () => clearInterval(interval);
  }, [refresh]);

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
      <main className="pt-14 min-h-screen bg-gray-950">
        <div className="max-w-7xl mx-auto px-4 py-6">

          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-xl font-bold text-white">Mobility Dashboard</h1>
              <p className="text-sm text-gray-500 mt-0.5">Paris — real-time urban analytics</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500">
                Refreshed {lastRefresh.toLocaleTimeString()}
              </span>
              <button
                onClick={() => void refresh()}
                className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-sm text-gray-300 transition"
              >
                Refresh
              </button>
            </div>
          </div>

          {/* KPI Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatCard
              label="Active vehicles"
              value={stats?.active_vehicles_now ?? 0}
              unit="now"
              color="blue"
            />
            <StatCard
              label="Events today"
              value={stats?.total_events_today ?? 0}
              unit="total"
              color="green"
            />
            <StatCard
              label="Average speed"
              value={stats?.avg_speed_kmh ?? 0}
              unit="km/h"
              color="amber"
            />
            <StatCard
              label="Busiest zone"
              value={stats?.busiest_zone ?? "—"}
              unit=""
              color="purple"
              isText
            />
          </div>

          {/* Main content */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Congestion table */}
            <div className="lg:col-span-2">
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
                <h2 className="text-sm font-semibold text-gray-300 mb-4">
                  Live congestion by zone
                </h2>
                <CongestionTable zones={congestion?.zones ?? []} />
              </div>
            </div>

            {/* Prediction panel */}
            <div>
              <PredictionPanel zones={congestion?.zones.map((z) => z.zone) ?? []} />
            </div>
          </div>

          {/* Live map link */}
          <div className="mt-6 p-4 rounded-xl bg-blue-900/30 border border-blue-800 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-300">Live Vehicle Tracking</p>
              <p className="text-xs text-blue-400/70 mt-0.5">
                {congestion?.total_active_vehicles ?? 0} vehicles on the map
              </p>
            </div>
            <button
              onClick={() => router.push("/map")}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm text-white font-medium transition"
            >
              Open map →
            </button>
          </div>
        </div>
      </main>
    </>
  );
}
