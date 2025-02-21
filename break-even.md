# Break-Even Strategy

## Requirements

- Python 3.10 or higher
 
## Get Started

1. Install freqtrade from scratch

```
git clone https://github.com/IgnacioGoldman/freqtrade.git
cd freqtrade/
sudo chmod +x setup.sh
./setup.sh -i
```

2. Activate virtual environment

```
source ./.venv/bin/activate
```

3. Start strategy

```
freqtrade trade --config user_data/config.json --strategy SampleStrategy
```

## What does Break-Even means?

If I enter a trade at 90k and another at 80k, and I exit at 85k. How much earnings? No profit or loss at 85k, and I can manage to rescue the 90k trade.

## How the strategy works?

- Crypto trading bot can enter 3 different trades: 
    - highF
    - lowF1 
    - lowF2
- Running in 1m timeframe, for highest precision.
- No stop_loss
- Custom roi depending of trade type

### highF
- Marking support/resistances at 15m
- entry condition:
    - touching support level of 15m
    - if (buy price lowF1 exists):
        (1-[buy_price-highF/buy_price-lowF1]) > 0.05
- exit conditions:
    - (Closing trade at 95th percentile of price change range of last 200 candlesticks of 15m | touching resistance) & (gains > 0) —> approx 1% gains (30eur)
    - break-even condition (see below...)

### lowF1
- Marking support/resistances at 4h
- entry conditions:
    - touching support level of 4hs
    - [buy price lowF1] < [buy price highF]
- exit conditions:
    - if (1-[buy_price-highF/buy_price-lowF1]) > 0.05 # we want to break-even just if there is enough difference to cancel
        - sell_price = ([buy price highF]+[buy price lowF])/2 
        - if price == sell_price -> cancel both trades
    - else # otherwise there are close enough
        - (Closing trade at 95th percentile of price change range of last 200 candlesticks of 4h | touching resistance) & (gains > 0)

### lowF2
- Marking support/resistances at 4h
- entry conditions:
    - touching support level of 4hs
    - existing lowF1 trade in database
    - (1-[buy_price-lowF2/buy_price-lowF1]) > 0.05 # we don't want to create 2 orders at the same level
- exit conditions
    - if (highF exists) && (1-[buy_price-highF/buy_price-lowF2]) > 0.05 # break-even highF, just if there is a diff
        - sell price = ([buy price highF]+[buy price lowF2])/2 
        - lowF2 should be converted to lowF1. I could again enter a lowF2 
    - if (lowF1 exists) && (1-[buy_price-lowF2/buy_price-lowF1]) > 0.05 # break-even lowF1, just if there is a diff
        - sell price = ([buy price lowF1]+[buy price lowF2])/2 
    - else # otherwise it means they are entering at similar times
        - (Closing trade at 95th percentile of price change range of last 200 candlesticks of 4h | touching resistance) & (gains > 0)

## Expected Behavior
- Sideways market: highF will be executing constant minor earns (approx 1%), lowF1 could be triggered, and lowF2 no actions.
- Bull market: no major earns until it corrects again in a support level
- Bear market: highF positioned negative. Strat will wait for lowF1 to correct highF. If lowF1 goes negative, lowF2 will correct highF and lowF1

## Testing behavior

### Backtesting

1. Download data

```
freqtrade download-data --exchange binance --pairs BTC/USDT:USDT -t 1m 15m 4h --timerange="20250101-" --trading-mode futures
```

2. Run backtesting

```
freqtrade backtesting --timerange="20250101-20250201" --config="user_data/config.json" --strategy SampleStrategy --breakdown week month --cache none
```

3. Plot dataframe

```
freqtrade plot-dataframe --timerange="20250101-20250201" --config=user_data/config.json --strategy SampleStrategy -p BTC/USDT:USDT
```

## Run in prod

terraform init

terraform workspace new $TF_VAR_project_name

ssh-keygen -t rsa -f key-$TF_VAR_project_name -q -P ""
