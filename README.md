# Dynamic Grid Trading (DGT) Strategy

本仓库实现了论文 **"Dynamic Grid Trading Strategy: From Zero Expectation to Market Outperformance"**（*Kai-Yuan Chen, Kai-Hsin Chen & Jyh-Shing Roger Jang*，[arXiv:2506.11921](https://arxiv.org/abs/2506.11921)）提出的 **动态网格交易（DGT）** 策略，并将其应用于 **中国 A 股市场 ETF**，提供完整的数据抓取、ATR 弹性筛选、参数寻优、回测与可视化流程。

> 论文原实验基于 BTC/ETH 分钟级数据；本项目将其迁移至 **A 股 ETF 日线**，并已移除加密货币与美国 ETF 标的。

---

## 📖 策略简介

传统网格交易在理想市场下是 **零期望系统**。DGT 的核心改进是：当价格突破网格上下界时 **动态重置网格中心**，从而适应趋势与波动，在回测中显著跑赢静态网格与买入持有。

---

## 📂 项目结构

```
Dynamic-Grid-Trading/
├── src/
│   ├── config.py                    # 全局配置（回测区间、网格参数、费率、数据源开关）
│   ├── etf_data_fetcher.py          # ETF 行情抓取（akshare 主 + xtquant/miniqmt 兜底）
│   ├── atr_analysis.py              # ATR 弹性分析 → 筛选高弹性 ETF
│   ├── etf_grid_strategy.py         # DGT 核心策略与单只 ETF 回测
│   ├── etf_backtest.py              # 全市场 ETF × 多参数组合回测
│   ├── etf_parameter_optimization.py# 参数寻优 + 滚动(walk-forward)验证
│   └── etf_visualization.py         # 收益曲线 / 对比图 / 完整报告
├── etf_data/                        # ETF 日线 CSV（自动生成）
├── etf_results/                     # 回测结果、图表、报告（自动生成）
├── requirements.txt
└── README.md
```

---

## ⚙️ 环境与安装

```bash
pip install -r requirements.txt
```

数据源依赖：
- **akshare**（主）：`pip install akshare`，A 股 ETF 后复权日线（`fund_etf_hist_em`），无需登录券商。
- **xtquant / miniQMT**（兜底）：需本地安装迅投 miniQMT 客户端并登录。文档见 http://dict.thinktrader.net/nativeApi/start_now.html 。xtquant 无 pip 包，需从客户端目录手动引入。

---

## 🚀 使用流程（从根目录运行）

```bash
# 1) 抓取 ETF 三年日线行情（默认 2023-07-13 ~ 2026-07-13）
python -m src.etf_data_fetcher

# 2) ATR 弹性分析，筛选高弹性 ETF（前 20%）
python -m src.atr_analysis

# 3) 全市场 ETF × 网格参数组合回测
python -m src.etf_backtest

# 4) 参数寻优 + 滚动验证（可选）
python -m src.etf_parameter_optimization

# 5) 生成图表与完整报告
python -m src.etf_visualization
```

### 配置（`src/config.py`）

```python
start_date = "2023-07-13"          # 回测起点
end_date   = "2026-07-13"          # 回测终点（滚动三年）
grid_sizes = [0.005, 0.01, 0.015, 0.02, 0.03, 0.05, 0.07, 0.1]
grid_numbers_half_list = [2, 3, 5, 7, 10]
grid_principal = 1000000           # 单只 ETF 网格初始资金（元）
fee_pct = 0.0003                   # ETF 手续费率（万三，免印花税）
use_akshare = True                 # 主数据源
use_xtquant = True                 # 兜底数据源
```

---

## 📊 标的范围

中国 A 股市场 ETF，覆盖 **宽基 / 行业 / 主题 / 商品 / 跨境 / 红利**，共约 44 只，示例：
- 宽基：510300（沪深300）、510500（中证500）、159915（创业板）、588000（科创50）、512100（中证1000）
- 行业：512000（券商）、512480（半导体）、512010（医药）、512660（军工）、512800（银行）
- 主题：515790（光伏）、562900（人工智能）、562500（机器人）、159992（创新药）
- 商品/跨境/红利：518880（黄金）、513100（纳指）、513050（中概互联）、510880（红利）

完整清单见 `src/etf_data_fetcher.py` 的 `cn_etfs`。

---

## 🔧 数据源策略

| 顺序 | 数据源 | 接口 | 说明 |
|------|--------|------|------|
| 主 | akshare | `fund_etf_hist_em(adjust='hfq')` | 东财后复权日线，无需券商客户端 |
| 兜底 | xtquant | `download_history_data` + `get_market_data_ex` | miniQMT 本地缓存，需客户端登录 |

- akshare 连续请求易被东财服务端断连，采用 **子进程隔离 + 硬超时 30s**，超时即 kill；连续失败 3 次触发 **熔断 120s**，期间直接走 xtquant。
- xtquant 的 `download_history_data` 偶发阻塞，用 **线程超时 45s** 包裹。
- 两源均失败则跳过该标的并告警，**绝不生成模拟随机数据污染回测**。

---

## 🙌 欢迎贡献

欢迎补充新的数据源、策略变体、参数优化方法或可视化。请 fork → 新建分支 → 提 PR。

---

## 🧾 引用

```bibtex
@article{chen2025dynamic,
  title={Dynamic Grid Trading Strategy: From Zero Expectation to Market Outperformance},
  author={Chen, Kai-Yuan and Chen, Kai-Hsin and Jang, Jyh-Shing Roger},
  journal={arXiv preprint arXiv:2506.11921},
  year={2025},
  url={https://arxiv.org/abs/2506.11921}
}
```
