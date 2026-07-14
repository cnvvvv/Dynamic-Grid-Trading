"""
ETF 动态网格交易 - 全局配置
=========================
回测区间：2023-07-13 ~ 2026-07-13（滚动三年）
数据源：  akshare（主）+ miniqmt/xtquant（兜底）
标的：    中国 A 股市场 ETF（宽基/行业/主题/商品/跨境/红利）
        已去除美国 ETF 与加密货币标的
"""

# 回测时间范围（三年）
start_date = "2023-07-13"
end_date = "2026-07-13"

# 网格策略参数
grid_sizes = [0.005, 0.01, 0.015, 0.02, 0.03, 0.05, 0.07, 0.1]
grid_numbers_half_list = [2, 3, 5, 7, 10]

# 资金与费率
grid_principal = 1000000      # 单只 ETF 网格初始资金（元）
fee_pct = 0.0003              # ETF 交易手续费率（万三，免印花税）

# 数据源开关
use_akshare = True            # 主数据源：akshare fund_etf_hist_em（后复权）
use_xtquant = True            # 兜底数据源：miniQMT / xtquant
