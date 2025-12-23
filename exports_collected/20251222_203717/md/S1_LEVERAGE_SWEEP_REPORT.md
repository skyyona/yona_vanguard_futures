**S1 + Leverage Sweep Verification Report**

Date: 2025-12-20

Overview:
- Symbols analyzed: BTCUSDT, JELLYJELLYUSDT
- Time window: 7 days, 1m klines
- S1 grid: TP in [0.004,0.006,0.008], SL in [0.002,0.003,0.004], TS in [0.0,0.004,0.006]
- Leverage sweep: candidates 5x..50x step 5

---

**BTCUSDT**

- S1: ran 27 simulations
- Best S1 profit: -0.49318128477727896
- Best params: take_profit_pct=0.004, stop_loss_pct=0.003, trailing_stop_pct=0.0

Leverage sweep summary (recommended leverage_x = 5)

| leverage_x | profit_percentage | final_balance | max_drawdown_pct | total_trades | accepted |
|---:|---:|---:|---:|---:|:---:|
| 5  | -0.11865998424439113 | 998.8134001575561 | 0.18889316532111894 | 8  | True |
| 10 | -0.2053373039527287  | 997.9466269604727  | 0.3657448105106234  | 8  | True |
| 15 | -0.2920146236610435  | 997.0798537633896  | 0.542525820382946   | 8  | True |
| 20 | -0.37869194336938106 | 996.2130805663062  | 0.7192362372477628  | 8  | True |
| 25 | -0.4653692630777073  | 995.3463073692229  | 0.8958761033808864  | 8  | True |
| 30 | -0.5520465827860221  | 994.4795341721398  | 1.0724454610244136  | 8  | True |
| 35 | -0.6387239024943483  | 993.6127609750565  | 1.248944352386747   | 8  | True |
| 40 | -0.7254012222026859  | 992.7459877779731  | 1.4253728196425843  | 8  | True |
| 45 | -0.8120785419110007  | 991.87921458089    | 1.6017309049329396  | 8  | True |
| 50 | -0.8987558616193155  | 991.0124413838068  | 1.7780186503652682  | 8  | False |

Notes: All candidates up to 45x were marked accepted under the acceptance rule (estimated_equity_loss_frac <= 0.8), 50x rejected.

---

**JELLYJELLYUSDT**

- S1: ran 27 simulations
- Best S1 profit: -1.3250091807420858
- Best params: take_profit_pct=0.004, stop_loss_pct=0.003, trailing_stop_pct=0.0

Leverage sweep summary (recommended leverage_x = 5)

| leverage_x | profit_percentage | final_balance | max_drawdown_pct | total_trades | accepted |
|---:|---:|---:|---:|---:|:---:|
| 5  | -0.3907628523054086  | 996.0923714769459  | 0.5143301298376514  | 17 | True |
| 10 | -0.713590270094403   | 992.864097299056   | 1.0027559468367144  | 17 | True |
| 15 | -1.0364176878833973  | 989.635823121166   | 1.491181763835789   | 17 | True |
| 20 | -1.3592451056723802  | 986.4075489432762  | 1.9796075808348406  | 17 | True |
| 25 | -1.6820725234613747  | 983.1792747653863  | 2.4680333978339264  | 17 | True |
| 30 | -2.0048999412503465  | 979.9510005874965  | 2.9564592148329893  | 17 | False |
| 35 | -2.3277273590393293  | 976.7227264096067  | 3.4448850318320408  | 17 | False |
| 40 | -2.6505547768283235  | 973.4944522317168  | 3.9333108488311153  | 17 | False |
| 45 | -2.973382194617318   | 970.2661780538268  | 4.421736665830178   | 17 | False |
| 50 | -3.2962096124062894  | 967.0379038759371  | 4.91016248282923    | 17 | False |

Notes: Candidates up to 25x accepted; 30x+ rejected due to estimated equity loss.

---

Recommendations / Next steps:
- Persist the JSON summary to `reports/S1_LEVERAGE_SWEEP_REPORT.json` (created alongside this report) and add a UI loader that displays the `S_LEVER_SWEEP` section using the JSON data.
- Optionally, tighten acceptance criteria (lower allowed_loss_frac) or run finer-grained sweep around recommended leverage.
