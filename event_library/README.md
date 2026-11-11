# 历史事件冲击库 impact-v1

这是事件库的第一刀，不是预测模型。一条记录回答三件事：当时发生了什么，官方文本里的冲击是什么，之后 BTC、ETH、SOL 的价格路径怎样。

## 和 Crypto-Trader 的分工

Crypto-Trader 的 L1–L3.5 负责持续采集，L4 负责把一轮研究冻成证据、规则版本和到期方向分。那个到期分只看观察期两端的收盘价，不描述一次宏观公布后的路径。

这边的库单独保存人工选入的历史事件。数字来自公开原文和 Binance USD-M 永续 1 分钟 K 线。共识预期没有可靠的可引用源，就留空，不估计。

## 判断口径

只对 `timeStatus = verified_instant` 的事件计算路径。官方解禁时刻精确到分钟，才有锚点。只有日期、没有分钟的事件入库存档，不计算收益。

锚点是事件时刻之前那根已走完的 1 分钟 K 线收盘价。1 小时、4 小时、24 小时、7 天，分别取事件之后正好那么多分钟的那根 K 线收盘价。中间缺任何一分钟，该窗口记为不可用，不用前后价格填补。

`maxUpPct` / `maxDownPct` 是锚点之后、窗口结束之前的最高价和最低价相对锚点的百分比。窗口里会混入别的新闻，尤其是 24 小时和 7 天。这是日历路径，不是把其他因素剔干净的因果效应，也不是扣过费用的策略收益。

利率环境只来自本库已收录的 FOMC 声明。下一次已收录的决议会把区间封口。没有下一次声明时，区间状态是 `open_ended`，不能写成那之后利率一直没变。

## 用法

在 `事件分析` 目录运行：

```bash
python -m unittest event_library.test_impact
python -m event_library
```

结果写入 `event_library/data/events.sqlite3`。K 线缓存在 `event_library/data/cache/`，冲击图的原始 1 分钟缓存在 `event_library/data/cache_shock/`。这两处缓存不进 git。增加事件时改 `events.json`，保留原文链接和原文中的数字，再重跑。

## 冲击简报

`fetch_shock_charts.py` 拉 12 个永续（BTC、ETH、SOL、HYPE、AAVE、UNI、ZEC、BNB、XRP、DOGE、LINK、ADA）在每次已核实公布前后的 1 分钟路径，写成 `data/shock_charts.json`。相对强度是同一窗口里该币收益相对 BTC 收益的比值，不是两个百分比相减。BTC 在跌、比值仍为正，记为扛跌。

交互页在 `canvases/event-shock-kline.canvas.tsx`，只在 Cursor 里打开。HYPE 永续 2025-05-30 才上线，这 9 次公布没有它的 K 线。
