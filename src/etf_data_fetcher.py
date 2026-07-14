"""
ETF 历史行情数据抓取器
=====================
数据源策略（akshare 主 + miniqmt/xtquant 兜底）：
    1. 默认走 akshare 的 fund_etf_hist_em（东方财富 ETF 日线，后复权 hfq），
       无需登录券商客户端，覆盖全市场 ETF。
    2. 单只 ETF 在 akshare 取数失败时，自动回退 xtquant(miniQMT) 的
       download_history_data + get_market_data_ex（需本地已启动 miniQMT 客户端）。
    3. 两源均失败则跳过该标的并打印告警，绝不生成模拟随机数据污染回测。

标的范围：中国 A 股市场 ETF（宽基 / 行业 / 主题 / 商品 / 跨境 / 红利），
        已去除全部美国上市 ETF 与加密货币标的。

落盘格式（与下游 atr_analysis / etf_backtest / etf_parameter_optimization 对齐）：
    etf_data/{symbol}_daily.csv
    列：Date, Open, High, Low, Close, Adj_Close, Volume
"""

import os
import time
import datetime
from threading import Thread
import pandas as pd
import numpy as np


class _ResultHolder:
    """线程间结果传递容器（用于给阻塞调用加超时）。"""
    __slots__ = ('value',)

    def __init__(self):
        self.value = None


def _run_with_timeout(func, args=(), kwargs=None, timeout=60):
    """在子线程中运行 func，超时返回 None。防止 xtquant 阻塞调用挂死主流程。"""
    holder = _ResultHolder()
    err = [None]

    def _worker():
        try:
            holder.value = func(*args, **(kwargs or {}))
        except Exception as e:  # noqa
            err[0] = e

    t = Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None, TimeoutError(f'调用超时({timeout}s)')
    return holder.value, err[0]


# requests 超时补丁（幂等）：akshare 内部 requests 调用未设超时，
# 东财服务器偶发"socket 不响应但不断开"会永久挂起。这里给所有
# requests 请求强制默认超时，确保数据源切换不会卡死。
_REQUESTS_PATCHED = False


def _patch_requests_timeout(timeout=15):
    global _REQUESTS_PATCHED
    if _REQUESTS_PATCHED:
        return
    try:
        import requests
        _orig_request = requests.Session.request

        def _request(self, *args, **kwargs):
            if 'timeout' not in kwargs or kwargs['timeout'] is None:
                kwargs['timeout'] = timeout
            return _orig_request(self, *args, **kwargs)

        requests.Session.request = _request
        _REQUESTS_PATCHED = True
    except Exception:
        pass


class ETFDataFetcher:
    # 默认三年回测窗口（滚动到今天）
    DEFAULT_START = '2023-07-13'
    DEFAULT_END = '2026-07-13'

    def __init__(self, data_dir='etf_data'):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        # akshare 熔断：连续失败超过阈值后本轮跳过 akshare，直接走 xtquant
        self._ak_consecutive_fail = 0
        self._ak_trip_at = 0          # 触发熔断的时间戳
        self.AK_CIRCUIT_FAILS = 3     # 连续失败阈值
        self.AK_CIRCUIT_COOLDOWN = 120  # 熔断冷却秒数

        # 中国 A 股市场 ETF 清单（代码: 名称）
        # 宽基指数
        # 行业 / 主题
        # 商品 / 跨境 / 红利
        self.cn_etfs = {
            # ===== 宽基指数 =====
            '510300': '沪深300ETF',
            '510500': '中证500ETF',
            '510050': '上证50ETF',
            '159915': '创业板ETF',
            '588000': '科创50ETF',
            '512100': '中证1000ETF',
            '560010': '中证A500ETF',
            '159901': '深100ETF',
            '588050': '上证科创50ETF',
            '512560': '中证A100ETF',
            # ===== 行业 =====
            '512000': '券商ETF',
            '512480': '半导体ETF',
            '512010': '医药ETF',
            '512660': '军工ETF',
            '512800': '银行ETF',
            '512070': '非银ETF',
            '515030': '新能源车ETF',
            '516160': '新能源ETF',
            '159995': '芯片ETF',
            '512980': '传媒ETF',
            '512690': '酒ETF',
            '159928': '消费ETF',
            '515170': '食品饮料ETF',
            '512200': '房地产ETF',
            '512690': '白酒ETF',
            '159766': '旅游ETF',
            '562900': '人工智能ETF',
            '515050': '5G通信ETF',
            '512720': '计算机ETF',
            # ===== 主题 =====
            '159775': '半导体设备ETF',
            '516150': '稀土ETF',
            '515790': '光伏ETF',
            '159825': '农业ETF',
            '562500': '机器人ETF',
            '159992': '创新药ETF',
            '515250': '智能汽车ETF',
            '516510': '数字经济ETF',
            # ===== 商品 / 跨境 / 红利 / 价值 =====
            '518880': '黄金ETF',
            '159980': '有色金属ETF',
            '513100': '纳指ETF',
            '513050': '中概互联ETF',
            '513030': '德国ETF',
            '510880': '红利ETF',
            '512890': '红利低波ETF',
            '159905': '深证红利ETF',
        }

    # ------------------------------------------------------------------
    # ETF 清单落盘
    # ------------------------------------------------------------------
    def fetch_etf_list(self):
        df = pd.DataFrame(list(self.cn_etfs.items()), columns=['symbol', 'name'])
        df.to_csv(os.path.join(self.data_dir, 'etf_list.csv'), index=False, encoding='utf-8-sig')
        print(f"已保存 {len(df)} 只 ETF 到 etf_list.csv")
        return df

    # ------------------------------------------------------------------
    # 数据源 1：akshare（主）—— 用子进程隔离，硬超时可终止挂起
    # ------------------------------------------------------------------
    def _fetch_via_akshare(self, symbol, start_date, end_date):
        """akshare fund_etf_hist_em，后复权日线。失败返回 None。

        注意：akshare 的 requests 调用偶发"socket 不响应不断开"会永久阻塞，
        线程超时无法中断 C 层 socket 读。因此用 subprocess 隔离，
        超时可 kill 整个进程，确保不卡死主流程。
        """
        # 熔断中：冷却期内直接跳过
        if self._ak_trip_at and (time.time() - self._ak_trip_at) < self.AK_CIRCUIT_COOLDOWN:
            return None

        import subprocess
        import sys as _sys
        import tempfile
        import json as _json

        ak_start = start_date.replace('-', '')
        ak_end = end_date.replace('-', '')
        out_path = os.path.join(tempfile.gettempdir(), f'ak_{symbol}_{int(time.time())}.csv')

        # 子进程脚本：取数 -> 落盘 CSV
        worker = (
            "import sys,json,akshare as ak\n"
            f"ak.fund_etf_hist_em(symbol='{symbol}',period='daily',"
            f"start_date='{ak_start}',end_date='{ak_end}',adjust='hfq')"
            f".to_csv(r'{out_path}',index=False)\n"
        )

        backoff_delays = [3, 6]  # 共 2 次尝试（首次 + 1 次重试）
        last_err = None
        for attempt, _delay in enumerate(backoff_delays + [0], 1):
            proc = None
            try:
                proc = subprocess.Popen(
                    [_sys.executable, '-c', worker],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                )
                try:
                    _, stderr = proc.communicate(timeout=30)  # 硬超时 30s
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    last_err = 'subprocess timeout(30s)'
                    if attempt <= len(backoff_delays):
                        time.sleep(_delay)
                        continue
                    break

                if proc.returncode != 0 or not os.path.exists(out_path):
                    last_err = (stderr or b'').decode('utf-8', 'ignore')[:200] or f'retcode={proc.returncode}'
                    if attempt <= len(backoff_delays):
                        time.sleep(_delay)
                        continue
                    break

                df = pd.read_csv(out_path)
                if df is None or len(df) == 0:
                    last_err = '空返回'
                    if attempt <= len(backoff_delays):
                        time.sleep(_delay)
                        continue
                    break

                # 中文列 -> 英文列
                col_map = {
                    '日期': 'Date', '开盘': 'Open', '收盘': 'Close',
                    '最高': 'High', '最低': 'Low', '成交量': 'Volume',
                    '成交额': 'Amount',
                }
                df = df.rename(columns=col_map)
                df['Date'] = pd.to_datetime(df['Date'])
                df['Adj_Close'] = df['Close']  # 后复权价即调整价
                df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume', 'Amount']]
                df = self._preprocess_data(df)
                if len(df) > 0:
                    self._ak_consecutive_fail = 0  # 成功，重置熔断计数
                    try:
                        os.remove(out_path)
                    except OSError:
                        pass
                    return df
                last_err = '预处理后为空'
            except Exception as e:
                last_err = f'{type(e).__name__}: {e}'
            if attempt <= len(backoff_delays):
                time.sleep(_delay)

        # 最终失败：累计熔断计数
        self._ak_consecutive_fail += 1
        if self._ak_consecutive_fail >= self.AK_CIRCUIT_FAILS and not self._ak_trip_at:
            self._ak_trip_at = time.time()
            print(f"  [akshare] 连续失败 {self._ak_consecutive_fail} 次，触发熔断 {self.AK_CIRCUIT_COOLDOWN}s，本轮改用 xtquant")
        print(f"  [akshare] {symbol} 取数失败: {last_err}")
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except OSError:
            pass
        return None

    # ------------------------------------------------------------------
    # 数据源 2：xtquant / miniQMT（兜底）
    # ------------------------------------------------------------------
    def _fetch_via_xtquant(self, symbol, start_date, end_date):
        """xtquant 下载 ETF 日线。需要本地 miniQMT 客户端已启动登录。失败返回 None。"""
        try:
            from xtquant import xtdata
        except Exception as e:
            print(f"  [xtquant] 导入失败（未安装或无 miniQMT 客户端）: {e}")
            return None

        xt_code = f'{symbol}.SH' if symbol.startswith(('5', '6', '11', '13')) else f'{symbol}.SZ'

        def _do_fetch():
            xtdata.download_history_data(xt_code, '1d', start_date, end_date)
            return xtdata.get_market_data_ex(
                [], [xt_code], period='1d',
                start_time=start_date.replace('-', ''), end_time=end_date.replace('-', '')
            )

        # download_history_data 在 QMT 缓存过期时可能永久阻塞，加 45s 超时
        data, err = _run_with_timeout(_do_fetch, timeout=45)
        if err is not None:
            print(f"  [xtquant] {symbol} 取数失败: {err}")
            return None
        try:
            if not data or xt_code not in data:
                return None
            df = data[xt_code].reset_index()
            # 列: time, open, high, low, close, volume ...
            df = df.rename(columns={
                'time': 'Date', 'open': 'Open', 'high': 'High',
                'low': 'Low', 'close': 'Close', 'volume': 'Volume',
            })
            if 'Date' not in df.columns:
                # 兼容索引列名为 'index'
                df = df.rename(columns={df.columns[0]: 'Date'})
            df['Date'] = pd.to_datetime(df['Date'])
            # xtquant 返回的时间戳可能是毫秒
            try:
                df['Date'] = pd.to_datetime(df['Date'].astype('int64'), unit='ms')
            except Exception:
                pass
            df['Adj_Close'] = df['Close']
            df['Amount'] = df.get('Amount', np.nan)
            df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume', 'Amount']]
            df = self._preprocess_data(df)
            return df if len(df) > 0 else None
        except Exception as e:
            print(f"  [xtquant] {symbol} 解析失败: {e}")
            return None

    # ------------------------------------------------------------------
    # 数据预处理
    # ------------------------------------------------------------------
    def _preprocess_data(self, df):
        for col in ['Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
        df = df[df['Volume'] > 0]
        df = df.drop_duplicates(subset=['Date']).sort_values('Date').reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # 单只 ETF 取数：akshare 主 + xtquant 兜底
    # ------------------------------------------------------------------
    def fetch_etf_history(self, symbol, start_date=None, end_date=None):
        start_date = start_date or self.DEFAULT_START
        end_date = end_date or self.DEFAULT_END

        # 主：akshare
        df = self._fetch_via_akshare(symbol, start_date, end_date)
        source = 'akshare'

        # 兜底：xtquant
        if df is None or len(df) == 0:
            df = self._fetch_via_xtquant(symbol, start_date, end_date)
            source = 'xtquant'

        if df is None or len(df) == 0:
            print(f"  [FAIL] {symbol} 两源均失败，跳过")
            return None

        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume']]
        if 'Amount' in df.columns:
            df = df.drop(columns=['Amount'])
        csv_path = os.path.join(self.data_dir, f'{symbol}_daily.csv')
        df.to_csv(csv_path, index=False)
        print(f"  [OK][{source}] {symbol} {len(df)} 条 ({df.iloc[0]['Date'].date()} ~ {df.iloc[-1]['Date'].date()})")
        return df

    # ------------------------------------------------------------------
    # 全市场 ETF 取数
    # ------------------------------------------------------------------
    def fetch_all_etf_history(self, start_date=None, end_date=None, max_etfs=None):
        start_date = start_date or self.DEFAULT_START
        end_date = end_date or self.DEFAULT_END

        etf_list_path = os.path.join(self.data_dir, 'etf_list.csv')
        if not os.path.exists(etf_list_path):
            self.fetch_etf_list()
        etf_list = pd.read_csv(etf_list_path)

        if max_etfs:
            etf_list = etf_list.head(max_etfs)

        success, fail = 0, 0
        total = len(etf_list)
        for idx, row in etf_list.iterrows():
            symbol = str(row['symbol'])
            print(f"[{idx + 1}/{total}] {symbol} - {row['name']}")
            df = self.fetch_etf_history(symbol, start_date, end_date)
            if df is not None and len(df) > 100:
                success += 1
            else:
                fail += 1
            time.sleep(1.0)  # akshare 限频保护（东财易断连）

        print(f"\n取数完成：成功 {success}，失败 {fail}")
        return success, fail


if __name__ == "__main__":
    fetcher = ETFDataFetcher()

    print("=" * 60)
    print("步骤 1：生成 ETF 清单")
    print("=" * 60)
    fetcher.fetch_etf_list()

    print("\n" + "=" * 60)
    print(f"步骤 2：拉取 ETF 三年历史行情 ({ETFDataFetcher.DEFAULT_START} ~ {ETFDataFetcher.DEFAULT_END})")
    print("=" * 60)
    fetcher.fetch_all_etf_history()
