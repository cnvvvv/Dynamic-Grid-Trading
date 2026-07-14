import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import os

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

class ETFVisualization:
    def __init__(self, result_dir='etf_results', data_dir='etf_data'):
        self.result_dir = result_dir
        self.data_dir = data_dir
        
    def plot_equity_curve(self, symbol, grid_size, grid_numbers_half, show_bh=True):
        from src.etf_grid_strategy import ETFGridStrategy
        
        csv_path = os.path.join(self.data_dir, f'{symbol}_daily.csv')
        df = pd.read_csv(csv_path)
        df['Date'] = pd.to_datetime(df['Date'])
        
        strategy = ETFGridStrategy(grid_principal=1000000, fee_pct=0.0003)
        result = strategy.backtest_single_etf(symbol, df, grid_size, grid_numbers_half)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
        
        dates = pd.to_datetime(result['dates'])
        
        equity_array = np.array(result['equity_curve'])
        ax1.plot(dates, equity_array, label=f'DGT策略 (IRR={result["IRR"]:.1f}%)', color='blue')
        
        if show_bh:
            bh_value = df['Open'].iloc[0] * (df['Close'] / df['Open'].iloc[0]) * (1000000 / df['Open'].iloc[0])
            buy_hold_return = (df.iloc[-1]['Close'] / df.iloc[0]['Open'] - 1) * 100
            ax1.plot(df['Date'], bh_value, label=f'买入持有 (收益={buy_hold_return:.1f}%)', color='red', alpha=0.7)
        
        ax1.set_title(f'{symbol} 收益曲线对比')
        ax1.set_ylabel('总资产 (元)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        peak = np.maximum.accumulate(equity_array)
        drawdown = (peak - equity_array) / peak * 100
        ax2.fill_between(dates, drawdown, 0, color='red', alpha=0.3)
        ax2.plot(dates, drawdown, label=f'MDD={result["MDD"]:.1f}%', color='red')
        ax2.set_title('回撤曲线')
        ax2.set_xlabel('日期')
        ax2.set_ylabel('回撤 (%)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        plot_path = os.path.join(self.result_dir, f'{symbol}_equity_curve.png')
        plt.savefig(plot_path, dpi=150)
        plt.close()
        
        print(f"收益曲线图已保存至: {plot_path}")
        
        return plot_path
    
    def plot_top_strategies(self, top_n=10):
        results_path = os.path.join(self.result_dir, 'etf_backtest_results.csv')
        if not os.path.exists(results_path):
            print("回测结果文件不存在")
            return None
        
        results_df = pd.read_csv(results_path)
        top_results = results_df.head(top_n)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        x = range(len(top_results))
        labels = [f'{r["symbol"]}\ngrid={r["grid_size"]:.1%}\nhalf={r["grid_numbers_half"]}' 
                  for _, r in top_results.iterrows()]
        
        ax1.bar(x, top_results['IRR'], color='skyblue')
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=45)
        ax1.set_title(f'Top {top_n} DGT策略 IRR对比')
        ax1.set_ylabel('IRR (%)')
        ax1.grid(True, alpha=0.3)
        
        for i, v in enumerate(top_results['IRR']):
            ax1.text(i, v, f'{v:.1f}', ha='center', va='bottom')
        
        ax2.bar(x, top_results['MDD'], color='salmon')
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=45)
        ax2.set_title(f'Top {top_n} DGT策略 最大回撤对比')
        ax2.set_ylabel('MDD (%)')
        ax2.grid(True, alpha=0.3)
        
        for i, v in enumerate(top_results['MDD']):
            ax2.text(i, v, f'{v:.1f}', ha='center', va='bottom')
        
        plt.tight_layout()
        
        plot_path = os.path.join(self.result_dir, 'top_strategies_comparison.png')
        plt.savefig(plot_path, dpi=150)
        plt.close()
        
        print(f"策略对比图已保存至: {plot_path}")
        
        return plot_path
    
    def plot_etf_comparison(self):
        results_path = os.path.join(self.result_dir, 'etf_backtest_results.csv')
        if not os.path.exists(results_path):
            print("回测结果文件不存在")
            return None
        
        results_df = pd.read_csv(results_path)
        
        etf_stats = results_df.groupby('symbol').agg({
            'IRR': ['mean', 'max', 'min'],
            'MDD': ['mean', 'min'],
            'Sharpe_ratio': ['mean', 'max']
        }).round(2)
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        etfs = etf_stats.index.tolist()
        x = range(len(etfs))
        
        axes[0, 0].bar(x, etf_stats['IRR']['mean'], color='skyblue')
        axes[0, 0].set_xticks(x)
        axes[0, 0].set_xticklabels(etfs, rotation=45)
        axes[0, 0].set_title('各ETF平均IRR')
        axes[0, 0].set_ylabel('IRR (%)')
        axes[0, 0].grid(True, alpha=0.3)
        
        axes[0, 1].bar(x, etf_stats['IRR']['max'], color='green')
        axes[0, 1].set_xticks(x)
        axes[0, 1].set_xticklabels(etfs, rotation=45)
        axes[0, 1].set_title('各ETF最高IRR')
        axes[0, 1].set_ylabel('IRR (%)')
        axes[0, 1].grid(True, alpha=0.3)
        
        axes[1, 0].bar(x, etf_stats['MDD']['mean'], color='salmon')
        axes[1, 0].set_xticks(x)
        axes[1, 0].set_xticklabels(etfs, rotation=45)
        axes[1, 0].set_title('各ETF平均MDD')
        axes[1, 0].set_ylabel('MDD (%)')
        axes[1, 0].grid(True, alpha=0.3)
        
        axes[1, 1].bar(x, etf_stats['Sharpe_ratio']['mean'], color='purple')
        axes[1, 1].set_xticks(x)
        axes[1, 1].set_xticklabels(etfs, rotation=45)
        axes[1, 1].set_title('各ETF平均夏普比率')
        axes[1, 1].set_ylabel('夏普比率')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        plot_path = os.path.join(self.result_dir, 'etf_comparison.png')
        plt.savefig(plot_path, dpi=150)
        plt.close()
        
        print(f"ETF对比图已保存至: {plot_path}")
        
        return plot_path
    
    def generate_full_report(self):
        results_path = os.path.join(self.result_dir, 'etf_backtest_results.csv')
        if not os.path.exists(results_path):
            print("回测结果文件不存在")
            return None
        
        results_df = pd.read_csv(results_path)
        
        self.plot_top_strategies(top_n=10)
        self.plot_etf_comparison()
        
        best_strategy = results_df.loc[results_df['IRR'].idxmax()]
        self.plot_equity_curve(
            best_strategy['symbol'],
            best_strategy['grid_size'],
            best_strategy['grid_numbers_half']
        )
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("ETF动态网格交易策略 - 3年回测报告")
        report_lines.append("=" * 80)
        report_lines.append(f"报告生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"回测时间范围: 2023-07-13 ~ 2026-07-13")
        report_lines.append(f"数据源: akshare(主) + miniqmt/xtquant(兜底)")
        report_lines.append(f"测试ETF数量: {results_df['symbol'].nunique()}")
        report_lines.append(f"策略参数组合: {len(results_df)}")
        report_lines.append("-" * 80)
        
        report_lines.append("\n一、最佳策略")
        report_lines.append("-" * 80)
        report_lines.append(f"标的: {best_strategy['symbol']}")
        report_lines.append(f"网格大小: {best_strategy['grid_size']:.1%}")
        report_lines.append(f"网格半层数: {best_strategy['grid_numbers_half']}")
        report_lines.append(f"IRR: {best_strategy['IRR']:.2f}%")
        report_lines.append(f"MDD: {best_strategy['MDD']:.2f}%")
        report_lines.append(f"夏普比率: {best_strategy['Sharpe_ratio']:.2f}")
        report_lines.append(f"总收益: {best_strategy['profit_percentage']:.2f}%")
        report_lines.append(f"买入持有收益: {best_strategy['buy_hold_return']:.2f}%")
        report_lines.append(f"策略优势: {best_strategy['strategy_vs_bh']:.2f}%")
        
        report_lines.append("\n二、策略表现统计")
        report_lines.append("-" * 80)
        report_lines.append(f"正IRR策略数: {len(results_df[results_df['IRR'] > 0])} ({len(results_df[results_df['IRR'] > 0])/len(results_df)*100:.1f}%)")
        report_lines.append(f"平均IRR: {results_df['IRR'].mean():.2f}%")
        report_lines.append(f"中位数IRR: {results_df['IRR'].median():.2f}%")
        report_lines.append(f"平均MDD: {results_df['MDD'].mean():.2f}%")
        report_lines.append(f"平均夏普比率: {results_df['Sharpe_ratio'].mean():.2f}")
        report_lines.append(f"DGT策略战胜买入持有比率: {len(results_df[results_df['strategy_vs_bh'] > 0])/len(results_df)*100:.1f}%")
        
        report_lines.append("\n三、各ETF表现")
        report_lines.append("-" * 80)
        etf_stats = results_df.groupby('symbol').agg({
            'IRR': 'mean',
            'MDD': 'mean',
            'Sharpe_ratio': 'mean',
            'profit_percentage': 'mean',
            'buy_hold_return': 'mean'
        }).round(2)
        report_lines.append(etf_stats.to_string())
        
        report_lines.append("\n" + "=" * 80)
        report_lines.append("报告结束")
        report_lines.append("=" * 80)
        
        report_text = "\n".join(report_lines)
        
        report_path = os.path.join(self.result_dir, 'etf_backtest_report.txt')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(f"\n完整报告已保存至: {report_path}")
        
        return report_text

if __name__ == "__main__":
    viz = ETFVisualization()
    viz.generate_full_report()