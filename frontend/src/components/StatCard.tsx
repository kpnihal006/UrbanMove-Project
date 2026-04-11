import clsx from "clsx";

type Color = "blue" | "green" | "amber" | "purple";

const COLOR_MAP: Record<Color, string> = {
  blue:   "border-blue-800 bg-blue-950/40",
  green:  "border-green-800 bg-green-950/40",
  amber:  "border-amber-800 bg-amber-950/40",
  purple: "border-purple-800 bg-purple-950/40",
};

const VALUE_COLOR: Record<Color, string> = {
  blue:   "text-blue-300",
  green:  "text-green-300",
  amber:  "text-amber-300",
  purple: "text-purple-300",
};

interface Props {
  label: string;
  value: number | string;
  unit: string;
  color: Color;
  isText?: boolean;
}

export default function StatCard({ label, value, unit, color, isText = false }: Props) {
  return (
    <div className={clsx("rounded-xl border p-4", COLOR_MAP[color])}>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={clsx("font-bold", isText ? "text-lg" : "text-2xl", VALUE_COLOR[color])}>
        {typeof value === "number" ? value.toLocaleString() : value}
        {unit && !isText && (
          <span className="text-sm font-normal text-gray-500 ml-1">{unit}</span>
        )}
      </p>
    </div>
  );
}
