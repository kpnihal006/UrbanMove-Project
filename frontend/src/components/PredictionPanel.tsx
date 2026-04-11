"use client";

import { useState } from "react";
import { analyticsApi, type PredictionResult } from "@/lib/api";

interface Props {
  zones: string[];
}

export default function PredictionPanel({ zones }: Props) {
  const [zone, setZone]             = useState(zones[0] ?? "Paris-1er");
  const [horizon, setHorizon]       = useState(30);
  const [result, setResult]         = useState<PredictionResult | null>(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);

  const predict = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await analyticsApi.predict(zone, horizon);
      setResult(res);
    } catch (err) {
      setError("Prediction unavailable — train the ML model first.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 h-full">
      <h2 className="text-sm font-semibold text-gray-300 mb-4">ML Congestion Prediction</h2>
      <p className="text-xs text-gray-500 mb-4">BigQuery ML · ARIMA_PLUS model</p>

      <div className="space-y-3 mb-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Zone</label>
          <select
            value={zone}
            onChange={(e) => setZone(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:outline-none focus:border-blue-500"
          >
            {(zones.length > 0 ? zones : ["Paris-1er", "Paris-2eme", "Paris-3eme"]).map((z) => (
              <option key={z} value={z}>{z}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Horizon: {horizon} min</label>
          <input
            type="range"
            min={5}
            max={120}
            step={5}
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="w-full accent-blue-500"
          />
        </div>
      </div>

      <button
        onClick={() => void predict()}
        disabled={loading}
        className="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900 disabled:cursor-not-allowed text-sm text-white font-medium transition mb-4"
      >
        {loading ? "Predicting…" : "Run prediction"}
      </button>

      {error && (
        <p className="text-xs text-amber-400 p-3 rounded-lg bg-amber-900/20 border border-amber-800">
          {error}
        </p>
      )}

      {result && !error && (
        <div className="space-y-3">
          <div className="p-3 rounded-lg bg-gray-800">
            <p className="text-xs text-gray-500">Predicted vehicles in {result.horizon_minutes} min</p>
            <p className="text-2xl font-bold text-blue-300 mt-1">
              {result.predicted_vehicle_count.toFixed(1)}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2 rounded-lg bg-gray-800 text-center">
              <p className="text-xs text-gray-500">Lower CI</p>
              <p className="text-sm font-semibold text-gray-200">{result.confidence_interval_lower.toFixed(1)}</p>
            </div>
            <div className="p-2 rounded-lg bg-gray-800 text-center">
              <p className="text-xs text-gray-500">Upper CI</p>
              <p className="text-sm font-semibold text-gray-200">{result.confidence_interval_upper.toFixed(1)}</p>
            </div>
          </div>
          <p className="text-xs text-gray-600">90% confidence interval</p>
        </div>
      )}
    </div>
  );
}
