"""Embed the downloaded daily candles into a candlestick canvas."""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "spot_daily_30.json"
OUT = Path(r"C:\Users\chenx\.cursor\projects\c-Users-chenx-Desktop\canvases\spot-kline-30.canvas.tsx")

TEMPLATE = r'''import {
  Button,
  H1,
  H2,
  Row,
  Stack,
  Stat,
  Text,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

type Bar = [string, number, number, number, number, number];
type Coin = {
  symbol: string;
  name: string;
  group: string;
  changePct: number;
  last: number;
  bars: Bar[];
};

const COINS: Coin[] = __DATA__;

const GROUPS = ["全部", "大盘", "DeFi", "主流"] as const;

function formatPrice(value: number): string {
  if (value >= 1000) return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (value >= 1) return value.toFixed(2);
  if (value >= 0.01) return value.toFixed(4);
  return value.toPrecision(4);
}

function signed(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function CandleChart({ bars, height, compact = false }: { bars: Bar[]; height: number; compact?: boolean }) {
  const theme = useHostTheme();
  const up = theme.category.green;
  const down = theme.category.red;
  const width = 1000;
  const padL = compact ? 2 : 8;
  const padR = compact ? 2 : 76;
  const padT = compact ? 4 : 12;
  const padB = compact ? 4 : 24;
  const volumeH = compact ? 0 : 52;
  const plotBottom = height - padB - volumeH;
  const plotH = plotBottom - padT;
  const plotW = width - padL - padR;
  const highs = bars.map((bar) => bar[2]);
  const lows = bars.map((bar) => bar[3]);
  const max = Math.max(...highs);
  const min = Math.min(...lows);
  const span = max - min || 1;
  const maxVolume = Math.max(...bars.map((bar) => bar[5])) || 1;
  const slot = plotW / bars.length;
  const y = (price: number) => padT + ((max - price) / span) * plotH;
  const levels = [max, min + span * 0.5, min];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img">
      {compact
        ? null
        : levels.map((level) => (
            <g key={level}>
              <line
                x1={padL}
                x2={width - padR}
                y1={y(level)}
                y2={y(level)}
                stroke={theme.stroke.tertiary}
                strokeWidth={1}
              />
              <text x={width - padR + 8} y={y(level) + 4} fill={theme.text.tertiary} fontSize={12}>
                {formatPrice(level)}
              </text>
            </g>
          ))}
      {bars.map((bar, index) => {
        const [date, open, high, low, close, volume] = bar;
        const rising = close >= open;
        const color = rising ? up : down;
        const center = padL + index * slot + slot / 2;
        const bodyWidth = Math.max(compact ? 2 : 3, slot * 0.64);
        const top = y(Math.max(open, close));
        const bodyHeight = Math.max(1, y(Math.min(open, close)) - top);
        const volumeHeight = volumeH === 0 ? 0 : (volume / maxVolume) * (volumeH - 8);
        return (
          <g key={date}>
            <title>{`${date}  开 ${formatPrice(open)}  高 ${formatPrice(high)}  低 ${formatPrice(low)}  收 ${formatPrice(close)}`}</title>
            <line x1={center} x2={center} y1={y(high)} y2={y(low)} stroke={color} strokeWidth={1.2} />
            <rect x={center - bodyWidth / 2} y={top} width={bodyWidth} height={bodyHeight} fill={color} />
            {volumeH > 0 ? (
              <rect
                x={center - bodyWidth / 2}
                y={height - padB - volumeHeight}
                width={bodyWidth}
                height={volumeHeight}
                fill={color}
                opacity={0.45}
              />
            ) : null}
          </g>
        );
      })}
      {compact ? null : (
        <g fill={theme.text.tertiary} fontSize={12}>
          <text x={padL} y={height - 4}>{bars[0][0].slice(5)}</text>
          <text x={width / 2} y={height - 4} textAnchor="middle">{bars[Math.floor(bars.length / 2)][0].slice(5)}</text>
          <text x={width - padR} y={height - 4} textAnchor="end">{bars[bars.length - 1][0].slice(5)}</text>
        </g>
      )}
    </svg>
  );
}

export default function SpotKline30() {
  const theme = useHostTheme();
  const [group, setGroup] = useCanvasState<(typeof GROUPS)[number]>("group", "全部");
  const [symbol, setSymbol] = useCanvasState("symbol", "BTCUSDT");
  const visible = group === "全部" ? COINS : COINS.filter((coin) => coin.group === group);
  const selected = COINS.find((coin) => coin.symbol === symbol) ?? COINS[0];
  const windowHigh = Math.max(...selected.bars.map((bar) => bar[2]));
  const windowLow = Math.min(...selected.bars.map((bar) => bar[3]));

  return (
    <Stack gap={18}>
      <Stack gap={6}>
        <H1>30 个主流币的日 K 线</H1>
        <Text tone="secondary">
          Binance 现货 USDT，2026-07-13 至 2026-11-09，每币 120 根日线。最后一根是 11 月 9 日还没收盘的 K 线。悬停一根蜡烛可以看到开、高、低、收。
        </Text>
      </Stack>

      <Stack gap={8}>
        <Row gap={12} align="center">
          <H2>
            {selected.name} 日 K
          </H2>
          <Text tone="tertiary" size="small">{selected.group}</Text>
        </Row>
        <Row gap={16}>
          <Stat value={formatPrice(selected.last)} label="最新价 USDT" />
          <Stat value={signed(selected.changePct)} label="这 120 天涨跌" tone={selected.changePct >= 0 ? "success" : "danger"} />
          <Stat value={formatPrice(windowHigh)} label="区间最高" />
          <Stat value={formatPrice(windowLow)} label="区间最低" />
        </Row>
        <CandleChart bars={selected.bars} height={420} />
        <Text tone="tertiary" size="small">
          纵轴是价格（USDT），横轴是日期。下面一排细柱是成交量。涨的蜡烛用绿色，跌的用红色。
        </Text>
      </Stack>

      <Row gap={8}>
        {GROUPS.map((item) => (
          <Button
            key={item}
            variant={item === group ? "primary" : "secondary"}
            onClick={() => {
              setGroup(item);
              const pool = item === "全部" ? COINS : COINS.filter((coin) => coin.group === item);
              if (!pool.some((coin) => coin.symbol === symbol)) setSymbol(pool[0].symbol);
            }}
          >
            {item}
          </Button>
        ))}
      </Row>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
          gap: 10,
        }}
      >
        {visible.map((coin) => {
          const active = coin.symbol === selected.symbol;
          return (
            <button
              key={coin.symbol}
              type="button"
              onClick={() => setSymbol(coin.symbol)}
              style={{
                textAlign: "left",
                padding: 8,
                cursor: "pointer",
                color: theme.text.primary,
                background: active ? theme.fill.secondary : theme.bg.editor,
                border: `1px solid ${active ? theme.accent.primary : theme.stroke.tertiary}`,
                borderRadius: theme.radius.lg,
                font: "inherit",
              }}
            >
              <span style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 13 }}>
                <span>{coin.name}</span>
                <span style={{ color: coin.changePct >= 0 ? theme.category.green : theme.category.red }}>
                  {signed(coin.changePct)}
                </span>
              </span>
              <CandleChart bars={coin.bars} height={78} compact />
            </button>
          );
        })}
      </div>
    </Stack>
  );
}
'''


def main() -> None:
    coins = json.loads(DATA.read_text(encoding="utf-8"))["coins"]
    payload = json.dumps(coins, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(TEMPLATE.replace("__DATA__", payload), encoding="utf-8")
    print(OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
