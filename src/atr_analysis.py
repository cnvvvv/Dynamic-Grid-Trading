import pandas as pd
import numpy as np
import os

class ATRElasticityAnalyzer:
    def __init__(self, data_dir='etf_data', result_dir='etf_results'):
        self.data_dir = data_dir
        self.result_dir = result_dir
        os.makedirs(result_dir, exist_ok=True)
    
    def calculate_atr(self, df, period=14):
        df = df.copy()
        
        df['High-Low'] = df['High'] - df['Low']
        df['High-PrevClose'] = np.abs(df['High'] - df['Close'].shift(1))
        df['Low-PrevClose'] = np.abs(df['Low'] - df['Close'].shift(1))
        
        df['TR'] = df[['High-Low', 'High-PrevClose', 'Low-PrevClose']].max(axis=1)
        
        df['ATR'] = df['TR'].rolling(window=period).mean()
        
        df['ATR_Ratio'] = df['ATR'] / df['Close'] * 100
        
        return df
    
    def analyze_etf(self, symbol):
        csv_path = os.path.join(self.data_dir, f'{symbol}_daily.csv')
        
        if not os.path.exists(csv_path):
            print(f"Data file not found for {symbol}")
            return None
        
        df = pd.read_csv(csv_path)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        
        df = self.calculate_atr(df)
        
        avg_atr_ratio = df['ATR_Ratio'].mean()
        max_atr_ratio = df['ATR_Ratio'].max()
        min_atr_ratio = df['ATR_Ratio'].min()
        volatility = df['Close'].pct_change().std() * np.sqrt(252) * 100
        
        result = {
            'symbol': symbol,
            'avg_atr_ratio': avg_atr_ratio,
            'max_atr_ratio': max_atr_ratio,
            'min_atr_ratio': min_atr_ratio,
            'volatility': volatility,
            'start_date': df.iloc[0]['Date'],
            'end_date': df.iloc[-1]['Date'],
            'days_count': len(df)
        }
        
        df.to_csv(os.path.join(self.data_dir, f'{symbol}_daily_with_atr.csv'), index=False)
        
        return result
    
    def analyze_all_etfs(self, top_percent=20):
        etf_list = pd.read_csv(os.path.join(self.data_dir, 'etf_list.csv'))
        
        results = []
        
        for idx, row in etf_list.iterrows():
            symbol = row['symbol']
            print(f"Analyzing {idx+1}/{len(etf_list)}: {symbol}")
            
            result = self.analyze_etf(symbol)
            
            if result is not None:
                results.append(result)
        
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('avg_atr_ratio', ascending=False).reset_index(drop=True)
        
        results_df['rank'] = results_df.index + 1
        results_df['elasticity_level'] = np.where(
            results_df['rank'] <= len(results_df) * top_percent / 100,
            'high',
            np.where(
                results_df['rank'] <= len(results_df) * 60 / 100,
                'medium',
                'low'
            )
        )
        
        results_df.to_csv(os.path.join(self.result_dir, 'etf_atr_analysis.csv'), index=False, encoding='utf-8-sig')
        
        top_etfs = results_df[results_df['elasticity_level'] == 'high']
        top_etfs.to_csv(os.path.join(self.result_dir, 'high_elasticity_etfs.csv'), index=False, encoding='utf-8-sig')
        
        print(f"\nATR分析完成，共分析{len(results_df)}只ETF")
        print(f"高弹性ETF数量: {len(top_etfs)}")
        print("\n高弹性ETF排名:")
        print(top_etfs[['rank', 'symbol', 'avg_atr_ratio', 'volatility']].to_string(index=False))
        
        return results_df, top_etfs
    
    def generate_report(self):
        analysis_df, top_etfs = self.analyze_all_etfs()
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("ETF ATR弹性分析报告")
        report_lines.append("=" * 80)
        report_lines.append(f"分析时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"分析ETF数量: {len(analysis_df)}")
        report_lines.append(f"时间范围: 2023-07-13 ~ 2026-07-13")
        report_lines.append("-" * 80)
        report_lines.append("\n一、ETF弹性排名（按平均ATR比率）")
        report_lines.append("-" * 80)
        report_lines.append(analysis_df[['rank', 'symbol', 'avg_atr_ratio', 'volatility', 'elasticity_level']].to_string(index=False))
        report_lines.append("\n二、高弹性ETF（前20%）")
        report_lines.append("-" * 80)
        report_lines.append(top_etfs[['rank', 'symbol', 'avg_atr_ratio', 'volatility']].to_string(index=False))
        report_lines.append("\n三、统计摘要")
        report_lines.append("-" * 80)
        report_lines.append(f"平均ATR比率均值: {analysis_df['avg_atr_ratio'].mean():.2f}%")
        report_lines.append(f"平均ATR比率中位数: {analysis_df['avg_atr_ratio'].median():.2f}%")
        report_lines.append(f"平均ATR比率最高: {analysis_df['avg_atr_ratio'].max():.2f}% ({analysis_df.iloc[0]['symbol']})")
        report_lines.append(f"平均ATR比率最低: {analysis_df['avg_atr_ratio'].min():.2f}% ({analysis_df.iloc[-1]['symbol']})")
        report_lines.append(f"平均波动率均值: {analysis_df['volatility'].mean():.2f}%")
        report_lines.append("\n" + "=" * 80)
        report_lines.append("报告结束")
        report_lines.append("=" * 80)
        
        report_text = "\n".join(report_lines)
        
        report_path = os.path.join(self.result_dir, 'etf_atr_report.txt')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(f"\n报告已保存至: {report_path}")
        
        return report_text

if __name__ == "__main__":
    analyzer = ATRElasticityAnalyzer()
    analyzer.generate_report()