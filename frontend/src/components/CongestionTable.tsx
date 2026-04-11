import type { ZoneCongestion } from "@/lib/api";
import clsx from "clsx";

const LEVEL_BADGE: Record<string, string> = {
  low:    "bg-green-900/50 text-green-300 border-green-800",
  medium: "bg-amber-900/50 text-amber-300 border-amber-800",
  high:   "bg-red-900/50 text-red-300 border-red-800",
};

interface Props {
  zones: ZoneCongestion[];
}

export default function CongestionTable({ zones }: Props) {
  if (zones.length === 0) {
    return (
      <p className="text-sm text-gray-600 text-center py-8">
        No data yet — IoT simulator may not be running.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-gray-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-800/50">
            <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-400">Zone</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-400">Vehicles</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-400">Avg speed</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-400">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {zones.map((z) => (
            <tr key={z.zone} className="hover:bg-gray-800/30 transition">
              <td className="px-4 py-2.5 text-gray-200 font-medium">{z.zone}</td>
              <td className="px-4 py-2.5 text-right text-gray-300">{z.vehicle_count}</td>
              <td className="px-4 py-2.5 text-right text-gray-300">{z.avg_speed_kmh} km/h</td>
              <td className="px-4 py-2.5 text-right">
                <span
                  className={clsx(
                    "inline-block px-2 py-0.5 rounded border text-xs capitalize",
                    LEVEL_BADGE[z.congestion_level] ?? LEVEL_BADGE.low,
                  )}
                >
                  {z.congestion_level}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
