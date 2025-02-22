# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# mypy: ignore-errors

# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Optional, Union

from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    informative,  # @informative decorator
    # Hyperopt Parameters
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    RealParameter,
    # timeframe helpers
    timeframe_to_minutes,
    timeframe_to_next_date,
    timeframe_to_prev_date,
    # Strategy helper functions
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
from technical import qtpylib
from indicators.indicators import OrderBlockIndicator
from freqtrade.loggers import setup_logging_pre
import logging
from freqtrade.persistence import Trade

logger = logging.getLogger("freqtrade")


class SampleStrategy(IStrategy):
    """
    This is a sample strategy to inspire you.
    More information in https://www.freqtrade.io/en/latest/strategy-customization/

    You can:
        :return: a Dataframe with all mandatory indicators for the strategies
    - Rename the class name (Do not forget to update class_name)
    - Add any methods you want to build your strategy
    - Add any lib you need to build your strategy

    You must keep:
    - the lib in the section "Do not remove these libs"
    - the methods: populate_indicators, populate_entry_trend, populate_exit_trend
    You should keep:
    - timeframe, minimal_roi, stoploss, trailing_*
    """

    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = False

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {"0": 100}

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -1

    # Trailing stoploss
    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # Optimal timeframe for the strategy.
    timeframe = "1m"

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    zone_amplitude = CategoricalParameter(
        [0.005, 0.01, 0.015, 0.02], default=0.005, optimize=True, space="buy"
    )
    space_for_finding_extrema = CategoricalParameter(
        [5, 10, 20, 30], default=30, optimize=False, space="buy"
    )

    # Hyperoptable parameters
    buy_rsi = IntParameter(low=1, high=50, default=30, space="buy", optimize=True, load=True)
    sell_rsi = IntParameter(low=50, high=100, default=70, space="sell", optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space="sell", optimize=True, load=True)
    exit_short_rsi = IntParameter(low=1, high=50, default=30, space="buy", optimize=True, load=True)

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    # Optional order type mapping.
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    # Optional order time in force.
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    highF_meet_conditions = 0

    @property
    def plot_config(self):
        return {
            "main_plot": {
                "supply_zone_0_entry_0.005_30_15m": {"color": "green"},
                "supply_zone_0_sl_0.005_30_15m": {"color": "green"},
                "supply_zone_0_ob_high_0.005_30_15m": {"color": "green"},
                "supply_zone_0_entry_0.005_30_4h": {"color": "orange"},
                "supply_zone_0_sl_0.005_30_4h": {"color": "orange"},
                "supply_zone_0_ob_high_0.005_30_4h": {"color": "orange"},
                # "demand_zone_0_entry_0.005_30_15m": {"color": "yellow"},
                # "demand_zone_0_sl_0.005_30_15m": {"color": "yellow"},
                # "demand_zone_0_ob_low_0.005_30_15m": {"color": "yellow"},
                # "demand_zone_0_entry_0.005_30_4h": {"color": "orange"},
                # "demand_zone_0_sl_0.005_30_4h": {"color": "orange"},
                # "demand_zone_0_ob_low_0.005_30_4h": {"color": "orange"},
            },
            "subplots": {"highF": {"highF": {"color": "black"}}},
        }

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

    @informative("4h")
    @informative("15m")
    def populate_indicators_informative(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define your informative pair/interval combinations here.
        The informative pair/interval combinations are cached from the exchange and can be used in the
        `populate_buy_trend()` and `populate_sell_trend()` functions.
        For more information, please consult the documentation
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame
        """

        for space_for_finding_extrema in self.space_for_finding_extrema.range:
            for zone_amplitude in self.zone_amplitude.range:
                OrderBlockIndicator(
                    metadata["pair"],
                    [metadata["timeframe"]],
                    self.timeframe,
                    space_for_finding_extrema,
                    zone_amplitude,
                ).populate(dataframe, metadata)

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        :param dataframe: Dataframe with data from the exchange
        :param metadata: Additional information, like the currently traded pair
        :return: a Dataframe with all mandatory indicators for the strategies
        """

        for space_for_finding_extrema in self.space_for_finding_extrema.range:
            for zone_amplitude in self.zone_amplitude.range:
                ##
                # for entry conditions
                ##
                # price in 15m support zone
                dataframe[
                    f"in_supply_zone_amplitude_{zone_amplitude}_{space_for_finding_extrema}_15m"
                ] = (
                    dataframe["close"]
                    <= dataframe[
                        f"supply_zone_0_ob_high_{zone_amplitude}_{space_for_finding_extrema}_15m"
                    ]
                ) & (
                    dataframe["close"]
                    >= dataframe[
                        f"supply_zone_0_sl_{zone_amplitude}_{space_for_finding_extrema}_15m"
                    ]
                )

                # price in 4h support zone
                dataframe[
                    f"in_supply_zone_amplitude_{zone_amplitude}_{space_for_finding_extrema}_4h"
                ] = (
                    dataframe["close"]
                    <= dataframe[
                        f"supply_zone_0_ob_high_{zone_amplitude}_{space_for_finding_extrema}_4h"
                    ]
                ) & (
                    dataframe["close"]
                    >= dataframe[
                        f"supply_zone_0_sl_{zone_amplitude}_{space_for_finding_extrema}_4h"
                    ]
                )

                ##
                # for exit conditions
                ##
                # price in 15m support zone
                dataframe[
                    f"in_demand_zone_amplitude_{zone_amplitude}_{space_for_finding_extrema}_15m"
                ] = (
                    dataframe["close"]
                    >= dataframe[
                        f"demand_zone_0_ob_low_{zone_amplitude}_{space_for_finding_extrema}_15m"
                    ]
                ) & (
                    dataframe["close"]
                    <= dataframe[
                        f"demand_zone_0_sl_{zone_amplitude}_{space_for_finding_extrema}_15m"
                    ]
                )

                # price in 4h support zone
                dataframe[
                    f"in_demand_zone_amplitude_{zone_amplitude}_{space_for_finding_extrema}_4h"
                ] = (
                    dataframe["close"]
                    >= dataframe[
                        f"demand_zone_0_ob_low_{zone_amplitude}_{space_for_finding_extrema}_4h"
                    ]
                ) & (
                    dataframe["close"]
                    <= dataframe[
                        f"demand_zone_0_sl_{zone_amplitude}_{space_for_finding_extrema}_4h"
                    ]
                )

        # set all variables to 0
        dataframe["highF_meet_conditions"] = 0
        dataframe["lowF1_meet_conditions"] = 0
        dataframe["lowF2_meet_conditions"] = 0

        # If there are open trade, check status
        # current_price = self.dp.ticker(metadata["pair"])["last"]
        open_trades = Trade.get_open_trades()
        highF = next((x for x in open_trades if x.enter_tag == "highF"), None)
        lowF1 = next((x for x in open_trades if x.enter_tag == "lowF1"), None)
        lowF2 = next((x for x in open_trades if x.enter_tag == "lowF2"), None)

        support_zone_15m = dataframe[
            f"in_supply_zone_amplitude_{self.zone_amplitude.value}_{self.space_for_finding_extrema.value}_15m"
        ].iloc[-1]
        support_zone_4h = dataframe[
            f"in_supply_zone_amplitude_{self.zone_amplitude.value}_{self.space_for_finding_extrema.value}_4h"
        ].iloc[-1]

        logger.info(f"[ENTRY] highF: {highF} | lowF1: {lowF1} | lowF2: {lowF2}")
        logger.info(
            f"[ENTRY] 15m support zone: {support_zone_15m} | 4h support zone: {support_zone_4h}"
        )

        ##
        # Meet conditions for highF
        ##
        # does not exist a highF yet
        if (not highF) and support_zone_15m:
            logger.info("[ENTRY] highF does not exist. What about lowF1?")
            # if lowF1 exists
            if lowF1:
                logger.info(
                    f"[ENTRY] lowF1 exist at {lowF1.open_rate} while trying to open highF at {dataframe['close'].iloc[-1]}"
                )
                # lowF1 open rate must be smaller than the current potential open price
                if (1 - (dataframe["close"] > lowF1.open_rate)) > 0.01:
                    logger.info(
                        "[ENTRY] lowF1 exist and it is 0,03 lower than highF, opening highF trade..."
                    )
                    dataframe["highF_meet_conditions"] = 1
            else:
                logger.info("[ENTRY] lowF1 does not exist, opening highF trade...")
                # if lowF1 does not exist, nothing to check
                dataframe["highF_meet_conditions"] = 1
        ##
        # Meet conditions for lowF1
        ##
        # highF need to exist, not a lowF1 and touching 4h support
        elif (highF) and (not lowF1) and support_zone_4h:
            logger.info(
                f"[ENTRY] highF exist at {highF.open_rate} while trying to open lowF1 at {dataframe['close'].iloc[-1]}"
            )
            # away from highF rate
            if (1 - (dataframe["close"] / highF.open_rate)) > 0.01:
                logger.info("[ENTRY] opening lowF1 trade...")
                dataframe["lowF1_meet_conditions"] = 1
        ##
        # Meet conditions for lowF2
        ##
        elif (lowF1) and (not lowF2) and support_zone_4h:
            logger.info(
                f"[ENTRY] lowF1 exist at {lowF1.open_rate} while trying to open lowF2 at {dataframe['close'].iloc[-1]}"
            )
            # away from lowF1 rate
            if (1 - (dataframe["close"] / lowF1.open_rate)) > 0.01:
                logger.info("[ENTRY] opening lowF2 trade...")
                dataframe["lowF2_meet_conditions"] = 1

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry columns populated
        """
        dataframe.loc[
            (dataframe["highF_meet_conditions"] == 1),
            ["enter_long", "enter_tag"],
        ] = (1, "highF")

        dataframe.loc[
            (dataframe["lowF1_meet_conditions"] == 1),
            ["enter_long", "enter_tag"],
        ] = (1, "lowF1")

        dataframe.loc[
            (dataframe["lowF2_meet_conditions"] == 1),
            ["enter_long", "enter_tag"],
        ] = (1, "lowF2")

        return dataframe

    def calculatePercentuals(self, dataframe, timeframe):
        # Initialize return dataframe
        df_nonzero = dataframe.copy()

        # Calculate pct_change for all candlesticks, as we are at 1m timeframe many of them will be zero
        df_nonzero[f"price_change_{timeframe}"] = df_nonzero[f"close_{timeframe}"].pct_change()

        # remove zero values
        df_nonzero = df_nonzero[df_nonzero[f"price_change_{timeframe}"] != 0]

        # Select the last 200 candlesticks
        last_200_candles = df_nonzero[f"price_change_{timeframe}"].iloc[-200:]
        # Calculate the 95th percentile
        percentile_95 = last_200_candles.quantile(0.95)
        return percentile_95

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        ##
        # Get dataframe
        ##
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        # last_candle = dataframe.iloc[-1].squeeze()

        ##
        # Get open trades, we need to compare them when exiting
        ##
        open_trades = Trade.get_open_trades()
        highF = next((x for x in open_trades if x.enter_tag == "highF"), None)
        lowF1 = next((x for x in open_trades if x.enter_tag == "lowF1"), None)
        lowF2 = next((x for x in open_trades if x.enter_tag == "lowF2"), None)

        ##
        # Calculate percentuals of 15m and 4h to exit based on the past behavior
        ##
        percentile_95_15m = self.calculatePercentuals(dataframe, "15m")
        percentile_95_4h = self.calculatePercentuals(dataframe, "4h")

        enter_tag = trade.enter_tag  # Retrieve entry tag

        logger.info(f"[EXIT] Checking exit condition for {enter_tag}")
        if enter_tag == "highF":
            logger.info(
                f"[EXIT] highF: current_profit ({current_profit}) must be higher than {percentile_95_15m}"
            )
            if (
                (
                    current_profit
                    > percentile_95_15m  # profit is higher than percentile 95 of last 200 candlesticks OR
                    or dataframe["in_demand_zone_amplitude_0.005_30_15m"].iloc[
                        -1
                    ]  # touching a resistance
                )
                and (current_profit > 0.005)
            ):  # AND profit is positive
                logger.info("[EXIT] exiting highF...")
                return "highF_exit"
            else:
                return None
        # lowF1 reason of exit depends on highF. highF must exist for lowF1 to get cancelled
        elif enter_tag == "lowF1" and highF:
            # if lowF1 at 80000, highF at 100000, denominator at 900000
            # if current_rate at 90500
            # proximity 1.005-1=0.005
            proximity = (current_rate / ((lowF1.open_rate + highF.open_rate) / 2)) - 1
            logger.info(
                f"[EXIT] lowF1: proximity of {proximity}, must be higher than 0 to close both trades"
            )
            if proximity > 0.001:
                logger.info("[EXIT] forcing trade highF, exiting lowF1...")
                # forces to close highF
                self.force_trade(highF)
                # closes lowF1
                return "lowF1_exit"
            else:
                return None
        elif enter_tag == "lowF2":
            if highF:
                proximity = (current_rate / ((lowF2.open_rate + highF.open_rate) / 2)) - 1
                logger.info(
                    f"[EXIT] lowF2: proximity of {proximity}, must be higher than 0 to close both trades (LowF2 & highF)"
                )
                if proximity > 0.001:
                    logger.info("[EXIT] forcing trade highF, exiting lowF2...")
                    # forces to close highF
                    self.force_trade(highF)
                    # closes lowF2
                    return "lowF2_exit"
                else:
                    return None
            if lowF1:
                proximity = (current_rate / ((lowF2.open_rate + lowF1.open_rate) / 2)) - 1
                logger.info(
                    f"[EXIT] lowF2: proximity of {proximity}, must be higher than 0 to close both trades (LowF2 & LowF1)"
                )
                if proximity > 0.001:
                    logger.info("[EXIT] forcing trade lowF1, exiting lowF2...")
                    # forces to close lowF1
                    self.force_trade(lowF1)
                    # closes lowF2
                    return "lowF2_exit"
                else:
                    return None
            else:
                return None
        else:
            return None

    # IGNORE!!!
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit signal, it will never happen!
        # Exit happens at custom_exit()
        dataframe.loc[
            (
                dataframe[
                    f"in_supply_zone_amplitude_{self.zone_amplitude.value}_{self.space_for_finding_extrema.value}_15m"
                ]
                == -2
            ),
            ["exit_long", "enter_tag"],
        ] = (1, "highF")

        return dataframe
