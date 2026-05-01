"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Pass = { dac: number; score: number };

const COARSE: Pass[] = [
  { dac: 0, score: 114.49 },
  { dac: 256, score: 153.78 },
  { dac: 512, score: 240.9 },
  { dac: 768, score: 415.64 },
  { dac: 1024, score: 298.62 },
  { dac: 1280, score: 158.19 },
  { dac: 1536, score: 98.12 },
  { dac: 1792, score: 69.03 },
  { dac: 2048, score: 53.87 },
  { dac: 2304, score: 45.64 },
  { dac: 2560, score: 39.89 },
  { dac: 2816, score: 36.19 },
  { dac: 3072, score: 31.97 },
  { dac: 3328, score: 26.69 },
  { dac: 3584, score: 24.92 },
  { dac: 3840, score: 23.98 },
  { dac: 4095, score: 22.88 },
];

const FINE: Pass[] = [
  { dac: 512, score: 261.48 },
  { dac: 544, score: 261.6 },
  { dac: 576, score: 275.04 },
  { dac: 608, score: 297.94 },
  { dac: 640, score: 324.05 },
  { dac: 672, score: 344.53 },
  { dac: 704, score: 388.73 },
  { dac: 736, score: 398.64 },
  { dac: 768, score: 411.27 },
  { dac: 800, score: 414.53 },
  { dac: 832, score: 401.15 },
  { dac: 864, score: 387.81 },
  { dac: 896, score: 377.48 },
  { dac: 928, score: 349.21 },
  { dac: 960, score: 316.27 },
  { dac: 992, score: 266.53 },
  { dac: 1024, score: 239.92 },
];

type Datum = { dac: number; coarse: number | null; fine: number | null };

const allDacs = Array.from(
  new Set([...COARSE, ...FINE].map((d) => d.dac))
).sort((a, b) => a - b);

const data: Datum[] = allDacs.map((dac) => ({
  dac,
  coarse: COARSE.find((d) => d.dac === dac)?.score ?? null,
  fine: FINE.find((d) => d.dac === dac)?.score ?? null,
}));

const PEAK = { dac: 800, score: 414.53 };

const tickStyle = {
  fontFamily: "var(--font-mono)",
  fontSize: 11,
  fill: "#78716c",
};
const labelStyle = {
  fontFamily: "var(--font-mono)",
  fontSize: 11,
  fill: "#57534e",
};

export function FocusChart() {
  return (
    <figure className="my-10">
      <div className="w-full" style={{ minHeight: 280 }}>
        <ResponsiveContainer width="100%" aspect={16 / 9} minHeight={280}>
          <LineChart
            data={data}
            margin={{ top: 16, right: 16, bottom: 40, left: 24 }}
          >
            <CartesianGrid stroke="#e7e5e4" strokeDasharray="3 3" />
            <XAxis
              dataKey="dac"
              type="number"
              domain={[0, 4095]}
              ticks={[0, 1024, 2048, 3072, 4095]}
              stroke="#a8a29e"
              tick={tickStyle}
              tickLine={false}
              label={{
                value: "DAC value",
                position: "insideBottom",
                offset: -20,
                style: labelStyle,
              }}
            />
            <YAxis
              stroke="#a8a29e"
              tick={tickStyle}
              tickLine={false}
              width={48}
              label={{
                value: "Tenengrad score",
                angle: -90,
                position: "insideLeft",
                offset: 8,
                style: { ...labelStyle, textAnchor: "middle" },
              }}
            />
            <Tooltip
              contentStyle={{
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                background: "#fafaf9",
                border: "1px solid #d6d3d1",
                borderRadius: 4,
                padding: "6px 10px",
              }}
              labelFormatter={(label: number) => `DAC ${label}`}
              formatter={(value: number, name: string) => [
                value.toFixed(1),
                name === "coarse" ? "Coarse pass" : "Fine pass",
              ]}
            />
            <Line
              type="monotone"
              dataKey="coarse"
              stroke="#a8a29e"
              strokeWidth={1.5}
              dot={{ r: 2.5, fill: "#a8a29e", strokeWidth: 0 }}
              activeDot={{ r: 4, fill: "#57534e" }}
              connectNulls
              name="coarse"
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="fine"
              stroke="#1c1917"
              strokeWidth={2}
              dot={{ r: 3, fill: "#1c1917", strokeWidth: 0 }}
              activeDot={{ r: 5, fill: "#1c1917" }}
              connectNulls
              name="fine"
              isAnimationActive={false}
            />
            <ReferenceDot
              x={PEAK.dac}
              y={PEAK.score}
              r={7}
              fill="none"
              stroke="#1c1917"
              strokeWidth={2}
              ifOverflow="visible"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-4 px-2 text-center font-mono text-[0.7rem] uppercase tracking-wider text-stone-500">
        <span className="mr-4">
          <span className="mr-1.5 inline-block h-px w-4 align-middle bg-stone-400" />
          Coarse pass · 17 frames
        </span>
        <span className="mr-4">
          <span className="mr-1.5 inline-block h-0.5 w-4 align-middle bg-stone-900" />
          Fine pass · 17 frames
        </span>
        <span>
          <span className="mr-1.5 inline-block h-2 w-2 rounded-full border-2 border-stone-900 align-middle" />
          Peak · DAC 800
        </span>
      </figcaption>
    </figure>
  );
}
