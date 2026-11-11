"""Embed the shock-chart pack into a canvas the IDE can open."""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "shock_charts.json"
OUT = Path(r"C:\Users\chenx\.cursor\projects\c-Users-chenx-Desktop\canvases\event-shock-kline.canvas.tsx")

TEMPLATE = r'''import {
  Button,
  Callout,
  Divider,
  H1,
  H2,
  H3,
  Link,
  Row,
  Select,
  Stack,
  Stat,
  Table,
  Text,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

type Bar = [number, number, number, number, number];
type Horizon = "1h" | "4h" | "24h";
type WindowStat = { ret: number; up: number; dn: number; end: number; tDn?: number; tUp?: number };
type Bars = { pre: number; bars: Bar[] };
type Series = {
  anchor?: number;
  pre?: number;
  r1?: number;
  r5?: number;
  vol?: number;
  w?: Partial<Record<Horizon, WindowStat>>;
  m1?: Bars;
  m15?: Bars;
  error?: string;
};
type Slice = { bars: Bar[]; pre: number; step: number };
type Zoom = "shock" | "path";
type Coin = { id: string; name: string; symbol: string };
type EventRow = {
  id: string;
  short: string;
  title: string;
  local: string;
  utc: string;
  source: string;
  url: string;
  shock: string;
  detail: string;
  read: string;
  regime: string;
  series: Record<string, Series>;
};
type Held = { title: string; detail: string };
type Pack = { coins: Coin[]; events: EventRow[]; held: Held[] };

const PACK = __DATA__ as Pack;

const HORIZONS: { value: Horizon; label: string; minutes: number }[] = [
  { value: "1h", label: "1 小时", minutes: 60 },
  { value: "4h", label: "4 小时", minutes: 240 },
  { value: "24h", label: "24 小时", minutes: 1440 },
];

function formatPrice(value: number): string {
  const abs = Math.abs(value);
  const digits = abs >= 100 ? 2 : abs >= 1 ? 4 : abs >= 0.01 ? 4 : 6;
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function signed(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatUtc(ms: number): string {
  const date = new Date(ms);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;
}

function chartSlice(series: Series, horizon: Horizon): Slice | null {
  if (horizon === "24h") {
    if (!series.m15 || !series.w?.["24h"]) return null;
    return { bars: series.m15.bars, pre: series.m15.pre, step: 15 };
  }
  if (!series.m1 || !series.w?.[horizon]) return null;
  const need = series.m1.pre + (horizon === "1h" ? 60 : 240);
  if (series.m1.bars.length < need) return null;
  return { bars: series.m1.bars.slice(0, need), pre: series.m1.pre, step: 1 };
}

function shockSlice(series: Series): Slice | null {
  if (!series.m1 || !series.w?.["1h"]) return null;
  const need = series.m1.pre + 60;
  if (series.m1.bars.length < need) return null;
  return { bars: series.m1.bars.slice(0, need), pre: series.m1.pre, step: 1 };
}

function coarsen(slice: Slice, factor: number): Slice {
  if (factor <= 1 || slice.pre % factor !== 0 || slice.bars.length % factor !== 0) return slice;
  const bars: Bar[] = [];
  for (let index = 0; index < slice.bars.length; index += factor) {
    const chunk = slice.bars.slice(index, index + factor);
    const open = chunk[0];
    const last = chunk[chunk.length - 1];
    if (!open || !last) continue;
    let high = open[2];
    let low = open[3];
    let volume = 0;
    for (const bar of chunk) {
      high = Math.max(high, bar[2]);
      low = Math.min(low, bar[3]);
      volume += bar[4];
    }
    bars.push([open[0], high, low, last[3], volume]);
  }
  return { bars, pre: slice.pre, step: slice.step * factor };
}

function buildView(series: Series | undefined, horizon: Horizon, zoom: Zoom): { slice: Slice; shock: boolean } | null {
  if (!series || series.anchor === undefined) return null;
  const shock = shockSlice(series);
  const path = chartSlice(series, horizon);
  const useShock = zoom === "shock" && shock !== null;
  let slice = useShock ? shock : path;
  if (!slice) return null;
  if (!useShock && slice.step === 1 && slice.bars.length > 120) slice = coarsen(slice, 5);
  return { slice, shock: useShock };
}

function fromAnchor(price: number, anchor: number): number {
  return ((price / anchor) - 1) * 100;
}

function relativeStrength(coinPct: number, btcPct: number): number {
  const base = 1 + btcPct / 100;
  if (base === 0) return 0;
  return ((1 + coinPct / 100) / base - 1) * 100;
}

function ShockChart({
  bars,
  pre,
  step,
  eventUtc,
  anchor,
  benchmark,
}: {
  bars: Bar[];
  pre: number;
  step: number;
  eventUtc: string;
  anchor: number;
  benchmark: { bars: Bar[]; pre: number; step: number; anchor: number } | null;
}) {
  const theme = useHostTheme();
  const up = theme.category.green;
  const down = theme.category.red;
  const width = 1000;
  const padL = 8;
  const padR = 84;
  const padT = 18;
  const padB = 28;
  const volumeH = 56;
  const eventMs = Date.parse(eventUtc);
  const eventIndex = pre / step;
  const highs = bars.map((bar) => fromAnchor(bar[2], anchor));
  const lows = bars.map((bar) => fromAnchor(bar[3], anchor));
  const bench = (benchmark ? bars : []).map((_, index) => {
    if (!benchmark) return null;
    const offset = -pre + index * step;
    const benchIndex = (offset + benchmark.pre) / benchmark.step;
    if (benchIndex < 0 || benchIndex >= benchmark.bars.length || !Number.isInteger(benchIndex)) return null;
    return fromAnchor(benchmark.bars[benchIndex][3], benchmark.anchor);
  });
  const benchValues = bench.filter((value): value is number => value !== null);
  const benchReady = benchmark !== null && benchValues.length === bars.length;
  const rsValues = benchReady ? benchValues.map((btcPct, index) => relativeStrength(fromAnchor(bars[index][3], anchor), btcPct)) : [];
  const rsH = benchReady ? 84 : 0;
  const height = 460 + rsH;
  const plotBottom = height - padB - volumeH - rsH;
  const plotH = plotBottom - padT;
  const plotW = width - padL - padR;
  const max = Math.max(...highs, 0, ...(benchReady ? benchValues : []));
  const min = Math.min(...lows, 0, ...(benchReady ? benchValues : []));
  const span = max - min || 1;
  const maxVolume = Math.max(...bars.map((bar) => bar[4])) || 1;
  const slot = plotW / bars.length;
  const y = (value: number) => padT + ((max - value) / span) * plotH;
  const levels = [max, 0, min];
  let lowIndex = eventIndex;
  let highIndex = eventIndex;
  for (let index = eventIndex; index < bars.length; index += 1) {
    if (bars[index][3] < bars[lowIndex][3]) lowIndex = index;
    if (bars[index][2] > bars[highIndex][2]) highIndex = index;
  }
  const openMs = (index: number) => eventMs + (-pre + index * step) * 60000;
  const rsMax = rsValues.length ? Math.max(0.25, ...rsValues.map((value) => Math.abs(value))) : 1;
  const rsTop = height - padB - rsH;
  const yRs = (value: number) => rsTop + 18 + ((rsMax - value) / (2 * rsMax)) * (rsH - 30);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img">
      {levels.map((level, index) => (
        <g key={`${index}-${level}`}>
          <line
            x1={padL}
            x2={width - padR}
            y1={y(level)}
            y2={y(level)}
            stroke={level === 0 ? theme.text.secondary : theme.stroke.tertiary}
            strokeWidth={1}
            strokeDasharray={level === 0 ? "4 4" : undefined}
          />
          <text x={width - padR + 8} y={y(level) + 4} fill={theme.text.tertiary} fontSize={12}>
            {signed(level)}
          </text>
        </g>
      ))}
      <line
        x1={padL + eventIndex * slot}
        x2={padL + eventIndex * slot}
        y1={padT}
        y2={height - padB}
        stroke={theme.accent.primary}
        strokeWidth={1.5}
      />
      <text x={padL + eventIndex * slot + 6} y={padT + 4} fill={theme.accent.primary} fontSize={12}>
        事件
      </text>
      {bars.map((bar, index) => {
        const [open, high, low, close, volume] = bar;
        const openPct = fromAnchor(open, anchor);
        const highPct = fromAnchor(high, anchor);
        const lowPct = fromAnchor(low, anchor);
        const closePct = fromAnchor(close, anchor);
        const rising = close >= open;
        const color = rising ? up : down;
        const center = padL + index * slot + slot / 2;
        const bodyWidth = Math.max(1.4, slot * 0.62);
        const top = y(Math.max(openPct, closePct));
        const bodyHeight = Math.max(1, y(Math.min(openPct, closePct)) - top);
        const volumeHeight = (volume / maxVolume) * (volumeH - 10);
        const when = formatUtc(openMs(index));
        return (
          <g key={when}>
            <title>{`${when} UTC  收 ${formatPrice(close)}（${signed(fromAnchor(close, anchor))}）  高 ${formatPrice(high)}  低 ${formatPrice(low)}`}</title>
            <line x1={center} x2={center} y1={y(highPct)} y2={y(lowPct)} stroke={color} strokeWidth={1.1} />
            <rect x={center - bodyWidth / 2} y={top} width={bodyWidth} height={bodyHeight} fill={color} />
            <rect
              x={center - bodyWidth / 2}
              y={height - padB - rsH - volumeHeight}
              width={bodyWidth}
              height={volumeHeight}
              fill={color}
              opacity={0.45}
            />
          </g>
        );
      })}
      {benchReady ? (
        <polyline
          fill="none"
          stroke={theme.text.secondary}
          strokeWidth={1.5}
          points={benchValues
            .map((value, index) => `${padL + index * slot + slot / 2},${y(value)}`)
            .join(" ")}
        />
      ) : null}
      <circle cx={padL + highIndex * slot + slot / 2} cy={y(fromAnchor(bars[highIndex][2], anchor))} r={3} fill={up} />
      <circle cx={padL + lowIndex * slot + slot / 2} cy={y(fromAnchor(bars[lowIndex][3], anchor))} r={3} fill={down} />
      {benchReady ? (
        <g>
          {[-1, 0, 1].map((tick) => (
            <g key={tick}>
              <line
                x1={padL}
                x2={width - padR}
                y1={yRs(tick * rsMax)}
                y2={yRs(tick * rsMax)}
                stroke={tick === 0 ? theme.text.secondary : theme.stroke.tertiary}
                strokeWidth={1}
                strokeDasharray={tick === 0 ? "4 4" : undefined}
              />
              <text x={width - padR + 8} y={yRs(tick * rsMax) + 4} fill={theme.text.tertiary} fontSize={12}>
                {signed(tick * rsMax)}
              </text>
            </g>
          ))}
          <text x={padL} y={rsTop + 12} fill={theme.text.tertiary} fontSize={12}>
            相对强度（%）
          </text>
          <polyline
            fill="none"
            stroke={theme.accent.primary}
            strokeWidth={1.5}
            points={rsValues.map((value, index) => `${padL + index * slot + slot / 2},${yRs(value)}`).join(" ")}
          />
        </g>
      ) : null}
      <g fill={theme.text.tertiary} fontSize={12}>
        <text x={padL} y={height - 8}>{formatUtc(openMs(0))}</text>
        <text x={padL + eventIndex * slot} y={height - 8} textAnchor="middle">
          {formatUtc(eventMs)}
        </text>
        <text x={width - padR} y={height - 8} textAnchor="end">
          {formatUtc(openMs(bars.length - 1) + step * 60000)}
        </text>
      </g>
    </svg>
  );
}

function ReturnBars({
  rows,
  selected,
  onPick,
}: {
  rows: { id: string; ret: number; name: string }[];
  selected: string;
  onPick: (id: string) => void;
}) {
  const theme = useHostTheme();
  const width = 1000;
  const rowH = 26;
  const padL = 108;
  const padR = 88;
  const padT = 8;
  const height = padT + rows.length * rowH + 22;
  const maxAbs = Math.max(0.25, ...rows.map((row) => Math.abs(row.ret)));
  const inner = width - padL - padR;
  const mid = padL + inner / 2;
  const xOf = (value: number) => mid + (value / maxAbs) * (inner / 2);
  const ticks = [-maxAbs, -maxAbs / 2, 0, maxAbs / 2, maxAbs];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img">
      {ticks.map((tick) => (
        <g key={tick}>
          <line
            x1={xOf(tick)}
            x2={xOf(tick)}
            y1={padT}
            y2={padT + rows.length * rowH}
            stroke={theme.stroke.tertiary}
            strokeWidth={1}
          />
          <text x={xOf(tick)} y={height - 4} textAnchor="middle" fill={theme.text.tertiary} fontSize={12}>
            {tick.toFixed(1)}
          </text>
        </g>
      ))}
      {rows.map((row, index) => {
        const y = padT + index * rowH + rowH / 2;
        const x = xOf(row.ret);
        const color = row.ret >= 0 ? theme.category.green : theme.category.red;
        return (
          <g key={row.id} onClick={() => onPick(row.id)} style={{ cursor: "pointer" }}>
            <text
              x={padL - 10}
              y={y + 4}
              textAnchor="end"
              fill={row.id === selected ? theme.text.primary : theme.text.secondary}
              fontSize={13}
              fontWeight={row.id === selected ? 590 : 400}
            >
              {row.name}
            </text>
            <line x1={mid} x2={x} y1={y} y2={y} stroke={color} strokeWidth={8} />
            <text x={width - 8} y={y + 4} textAnchor="end" fill={color} fontSize={12}>
              {signed(row.ret)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function EventShockKline() {
  const [eventId, setEventId] = useCanvasState("event", "iran-hormuz-2026-06-09");
  const [coinId, setCoinId] = useCanvasState("coin", "BTC");
  const [horizon, setHorizon] = useCanvasState<Horizon>("horizon", "4h");
  const [zoom, setZoom] = useCanvasState<Zoom>("zoom", "shock");
  const event = PACK.events.find((item) => item.id === eventId) ?? PACK.events[0];
  const coin = PACK.coins.find((item) => item.id === coinId) ?? PACK.coins[0];
  const horizonMeta = HORIZONS.find((item) => item.value === horizon) ?? HORIZONS[1];
  if (!event || !coin) return <Text>这批公布没有装进图里。</Text>;
  const series = event.series[coin.id] ?? { error: "这只币不在这批里。" };
  const stat = series.w?.[horizon];
  const view = buildView(series, horizon, zoom);
  const overlayZoom: Zoom = view?.shock ? "shock" : "path";
  const btcSeries = event.series.BTC;
  const btcView = coin.id === "BTC" ? null : buildView(btcSeries, horizon, overlayZoom);
  const benchmark =
    btcView && btcSeries?.anchor !== undefined
      ? { bars: btcView.slice.bars, pre: btcView.slice.pre, step: btcView.slice.step, anchor: btcSeries.anchor }
      : null;
  const btcRet = btcSeries?.w?.[horizon]?.ret;
  const rs = stat && btcRet !== undefined && coin.id !== "BTC" ? relativeStrength(stat.ret, btcRet) : undefined;
  const rsRows = PACK.coins.flatMap((item) => {
    const ret = event.series[item.id]?.w?.[horizon]?.ret;
    if (ret === undefined || btcRet === undefined) return [];
    const value = item.id === "BTC" ? 0 : relativeStrength(ret, btcRet);
    const name =
      item.id === "BTC" ? "BTC 基准" : btcRet < 0 && value > 0 ? `${item.id} 扛跌` : item.id;
    return [{ id: item.id, ret: value, name }];
  }).sort((a, b) => b.ret - a.ret);
  const missing = PACK.coins.filter((item) => event.series[item.id]?.w?.[horizon] === undefined).map((item) => item.id);
  const scan = [
    series.pre !== undefined ? `事前 30 分钟 ${signed(series.pre)}` : "",
    series.r5 !== undefined ? `第 5 分钟 ${signed(series.r5)}` : "",
    series.r1 !== undefined && btcSeries?.r1 !== undefined && coin.id !== "BTC"
      ? `第 1 分钟相对强度 ${signed(relativeStrength(series.r1, btcSeries.r1))}`
      : "",
    stat?.tDn !== undefined ? `最低在 T+${stat.tDn} 分` : "",
    stat?.tUp !== undefined ? `最高在 T+${stat.tUp} 分` : "",
    series.vol !== undefined ? `后 5 分钟量能是事前的 ${series.vol.toFixed(1)} 倍` : "",
  ]
    .filter((part) => part !== "")
    .join(" · ");
  const candleNote = !view
    ? ""
    : view.shock
      ? "每根蜡烛是 1 分钟，从公布前 30 分钟到公布后 60 分钟。"
      : view.slice.step === 15
        ? "每根蜡烛是 15 分钟，由连续 1 分钟合成，覆盖到公布后 24 小时。"
        : view.slice.step === 5
          ? "每根蜡烛是 5 分钟，由连续 1 分钟合成。上面的涨跌幅仍按 1 分钟收盘计算。"
          : "每根蜡烛是 1 分钟。";

  return (
    <Stack gap={18}>
      <Stack gap={6}>
        <H1>公布打在 K 线上</H1>
        <Text tone="secondary">
          打开先看相对强度：每个币相对 BTC 强多少，就排在 K 线上面。除了 CPI、非农和 FOMC，同一排还有币安安全事件、美伊在霍尔木兹附近的打击、合作公告和交易所上币。HYPE 永续 2025-05-30 10:30 UTC 才上线，更早的公布没有它的路径。口里的 AVE 用的是 AAVE。
        </Text>
      </Stack>

      <Row gap={8} wrap>
        {PACK.events.map((item) => {
          const move = item.series.BTC?.w?.[horizon]?.ret;
          return (
            <Button key={item.id} variant={item.id === event.id ? "primary" : "secondary"} onClick={() => setEventId(item.id)}>
              {move === undefined ? item.short : `${item.short} ${signed(move)}`}
            </Button>
          );
        })}
      </Row>
      <Row gap={8} align="center" wrap>
        {PACK.coins.map((item) => {
          const move = event.series[item.id]?.w?.[horizon]?.ret;
          return (
            <Button key={item.id} variant={item.id === coin.id ? "primary" : "secondary"} onClick={() => setCoinId(item.id)}>
              {move === undefined ? item.id : `${item.id} ${signed(move)}`}
            </Button>
          );
        })}
        <Select
          value={horizon}
          onChange={(value) => setHorizon(value as Horizon)}
          options={HORIZONS.map((item) => ({ value: item.value, label: `窗口 ${item.label}` }))}
        />
        <Button variant={zoom === "shock" ? "primary" : "secondary"} onClick={() => setZoom("shock")}>
          冲击 1 分钟
        </Button>
        <Button variant={zoom === "path" ? "primary" : "secondary"} onClick={() => setZoom("path")}>
          整段窗口
        </Button>
      </Row>

      {rsRows.length > 0 && btcRet !== undefined ? (
        <Stack gap={8}>
          <H2>相对强度</H2>
          <Text tone="secondary">
            这一列是币相对 BTC 的价格比，(1+该币涨跌)/(1+BTC涨跌)−1。零线以上是强于 BTC。
            {btcRet < 0 ? " 这次 BTC 在跌，标了扛跌的是跌得比 BTC 少。" : " 这次 BTC 在涨，零线以上是涨得比 BTC 多。"}
          </Text>
          <ReturnBars rows={rsRows} selected={coin.id} onPick={setCoinId} />
          <Text tone="tertiary" size="small">
            纵轴是币，按相对强度从高到低。横轴是相对强度（%）。窗口是公布后{horizonMeta.label}。点这一列里的币，下面的 K 线跟着换。
            {missing.length > 0 ? ` 没有路径的币：${missing.join("、")}。` : ""}
          </Text>
          <Table
            headers={["币", "相对强度", "读法"]}
            columnAlign={["left", "right", "left"]}
            rows={rsRows.map((row) => [
              row.id,
              signed(row.ret),
              row.id === "BTC"
                ? "基准"
                : btcRet < 0 && row.ret > 0
                  ? "扛跌"
                  : btcRet < 0
                    ? "跌得更多"
                    : row.ret > 0
                      ? "涨得更多"
                      : "涨不过",
            ])}
            rowTone={rsRows.map((row) => (row.id === "BTC" ? "neutral" : row.ret >= 0 ? "success" : "danger"))}
            striped
          />
        </Stack>
      ) : null}

      <Stack gap={6}>
        <H2>{event.title}</H2>
        <Row gap={12} align="center" wrap>
          <Text tone="secondary" size="small">{event.source}</Text>
          <Text tone="tertiary" size="small">{event.local}</Text>
          <Text tone="tertiary" size="small">{event.utc.replace("T", " ").replace("Z", " UTC")}</Text>
          <Link href={event.url}>原文</Link>
        </Row>
        <Text>{event.shock}</Text>
        <Text tone="tertiary" size="small">{event.regime}</Text>
      </Stack>

      {series.error ? (
        <Callout tone="warning" title={`${coin.id} 这次没有路径`}>
          {series.error}
        </Callout>
      ) : null}

      {!series.error && !stat ? (
        <Callout tone="warning" title={`${horizonMeta.label}窗口没有连续分钟`}>
          中间缺了分钟，这条路径不算。换一个更短的窗口，或者换一只当时已经有合约的币。
        </Callout>
      ) : null}

      {stat && series.anchor !== undefined ? (
        <Stack gap={6}>
          <Row gap={16} wrap>
            <Stat value={formatPrice(series.anchor)} label="事件时价格 USDT" />
            {series.r1 !== undefined ? (
              <Stat value={signed(series.r1)} label="第 1 分钟" tone={series.r1 >= 0 ? "success" : "danger"} />
            ) : null}
            <Stat value={signed(stat.ret)} label={`这${horizonMeta.label}涨跌`} tone={stat.ret >= 0 ? "success" : "danger"} />
            <Stat value={signed(stat.dn)} label="最大跌幅" tone={stat.dn < 0 ? "danger" : undefined} />
            {rs !== undefined && btcRet !== undefined ? (
              <Stat value={signed(rs)} label={btcRet < 0 && rs > 0 ? "相对强度 · 扛跌" : "相对强度"} tone={rs >= 0 ? "success" : "danger"} />
            ) : null}
          </Row>
          {scan ? <Text tone="secondary" size="small">{scan}</Text> : null}
          <Text>{event.read}</Text>
        </Stack>
      ) : null}

      {view && series.anchor !== undefined ? (
        <Stack gap={6}>
          <H3>
            {view.shock
              ? `${coin.name} 相对事件时价格，公布前 30 分钟到公布后 60 分钟`
              : `${coin.name} 相对事件时价格，公布后 ${horizonMeta.label}`}
          </H3>
          <ShockChart
            bars={view.slice.bars}
            pre={view.slice.pre}
            step={view.slice.step}
            eventUtc={event.utc}
            anchor={series.anchor}
            benchmark={benchmark}
          />
          <Text tone="tertiary" size="small">
            {candleNote}
            纵轴是相对事件时价格的涨跌幅（%），横轴是 UTC，右端是最后一根的收盘。竖线是公布那一分钟。虚线是 0，也就是事件时价格。圆点是这窗口里的最高和最低。下方柱是成交量（标的币数量）。
            {benchmark ? " 价格图上叠的是 BTC 收盘。最下面是相对强度，(1+该币涨跌)/(1+BTC涨跌)−1。零线以上强于 BTC；BTC 在跌而这条线为正，就是扛跌。" : ""}
            来源：Binance USD-M 永续。这是日历路径，窗口里可以混进别的消息。
          </Text>
        </Stack>
      ) : null}

      <Divider />

      <Table
        headers={["币", "第 1 分钟", `${horizonMeta.label}涨跌`, "相对强度", "最大跌幅", "后 5 分钟量能"]}
        columnAlign={["left", "right", "right", "right", "right", "right"]}
        rows={PACK.coins.map((item) => {
          const itemSeries = event.series[item.id];
          const itemStat = itemSeries?.w?.[horizon];
          if (!itemSeries || itemSeries.anchor === undefined || !itemStat) {
            return [item.id, "", itemSeries?.error ? "当时没有永续" : "缺分钟", "", "", ""];
          }
          return [
            item.id,
            itemSeries.r1 === undefined ? "" : signed(itemSeries.r1),
            signed(itemStat.ret),
            item.id === "BTC" ? "基准" : btcRet === undefined ? "" : signed(relativeStrength(itemStat.ret, btcRet)),
            signed(itemStat.dn),
            itemSeries.vol === undefined ? "" : `${itemSeries.vol.toFixed(1)} 倍`,
          ];
        })}
        rowTone={PACK.coins.map((item) => {
          const ret = event.series[item.id]?.w?.[horizon]?.ret;
          if (ret === undefined) return "neutral";
          return ret >= 0 ? "success" : "danger";
        })}
        striped
      />
      <Text tone="secondary">{event.detail}</Text>
      <Text tone="tertiary" size="small">
        只有日期、没有分钟的不画 K 线：{PACK.held.map((item) => item.title).join("；")}。共识预期没有可引用的数字，这里不写超预期。利率区间只来自本库已收录的 FOMC 声明。价格是永续最新成交，不是可成交的冲击，没有盘口和资金费。上面那段读法只用测到的 1 小时路径，窗口里可以混进别的消息。
      </Text>
    </Stack>
  );
}
'''


def write_canvas(payload: str | None = None) -> None:
    raw = payload if payload is not None else DATA.read_text(encoding="utf-8")
    OUT.write_text(TEMPLATE.replace("__DATA__", raw), encoding="utf-8")
    print(OUT, OUT.stat().st_size)


def main() -> None:
    write_canvas()


if __name__ == "__main__":
    main()
