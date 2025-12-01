import pandas as pd

def main():
    path = 'results/pippinusdt_breakout_analysis.csv'
    df = pd.read_csv(path)
    wins = df[df['net_pnl']>0]
    losses = df[df['net_pnl']<=0]
    print('total_trades',len(df))
    print('wins',len(wins),'losses',len(losses))
    print('win_rate', round(len(wins)/len(df)*100,2) if len(df) else None)
    print('mean_net_pnl_win', round(wins['net_pnl'].mean(),6) if len(wins) else None)
    print('mean_net_pnl_loss', round(losses['net_pnl'].mean(),6) if len(losses) else None)
    print('median_vol_mult_win', round(wins['vol_mult'].median(),6) if len(wins) else None)
    print('median_vol_mult_loss', round(losses['vol_mult'].median(),6) if len(losses) else None)
    print('\nTop 5 worst losses:')
    print(losses.sort_values('net_pnl').head(5)[['entry_index','net_pnl','vol_mult','volume']].to_string(index=False))

if __name__=='__main__':
    main()
