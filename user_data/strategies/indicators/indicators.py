from collections import deque

import numpy as np
import scipy


class BaseIndicator:
    """
    Main structure of Indicators for Neural Network
    """

    def __init__(self, pair, timeframes, main_timeframe):
        self._pair = pair
        self._timeframes = timeframes
        self._main_timeframe = main_timeframe
        self._current_timeframe = None

    def populate(self, dataframe, metadata):
        """
        Based on configuration adds the indicator to the dataframe
        """
        print(
            f"Populating {self._pair}:{self.__class__.__name__}, timeframe: {metadata['timeframe']}"
        )
        if metadata["timeframe"] in self._timeframes:
            self._current_timeframe = metadata["timeframe"]
            self.calculate(dataframe)

    def calculate(self, dataframe):
        """
        Implemented by each indicator
        """
        raise NotImplementedError()

    def on_main_timeframe(self, dataframe):
        """
        Optional processing on main timeframe
        """
        pass

    def generate_indicators(self, prefix=None):
        """
        Should return a list with the following structure:
        [
            {indicator_name_1}_{timeframe}
        ]
        If prefix is present should be added to the start of the name
        """
        name_list = []
        skip_list = self.skip_name_list()
        for timeframe in self._timeframes:
            for name in self.get_names():
                if prefix:
                    name_to_add = f"{prefix}{name}_{timeframe}"
                else:
                    name_to_add = f"{name}_{timeframe}"
                if name_to_add not in skip_list:
                    name_list.append(name_to_add)
        return name_list


class OrderBlockIndicator(BaseIndicator):
    lookback_candles = 200
    distance_to_consider_ob_touched = 5

    class _OrderBlock:
        def __init__(self, candle, index, zone_amplitude, is_support: bool = True) -> None:
            # Inspired on: https://www.youtube.com/watch?v=4Tuk0Yztz3s
            self.candle_high = candle["high"]
            self.candle_low = candle["low"]
            self.index = index
            self.zone_amplitude = zone_amplitude
            self.is_support = is_support

            is_bullish = candle["close"] > candle["open"]
            is_bearish = not is_bullish

            upper_wick = candle["high"] - max(candle["open"], candle["close"])
            lower_wick = min(candle["open"], candle["close"]) - candle["low"]
            candle_body = abs(candle["close"] - candle["open"])
            if is_support:
                if lower_wick > (candle_body * 0.3):
                    # 3. Lower wick is bigger than the body
                    self.ob_high = min(candle["close"], candle["open"])
                    self.ob_low = candle["low"]
                else:
                    self.ob_high = candle["high"]
                    self.ob_low = candle["low"]
            else:
                if upper_wick > (candle_body * 0.3):
                    # 3. Upper wick is bigger than the body
                    self.ob_high = candle["high"]
                    self.ob_low = max(candle["close"], candle["open"])
                else:
                    self.ob_high = candle["high"]
                    self.ob_low = candle["low"]

        @property
        def fair_value(self):
            if self.is_support:
                return self.ob_low + ((self.ob_high - self.ob_low) / 2.0)
            else:
                return self.ob_high - ((self.ob_high - self.ob_low) / 2.0)

        @property
        def entry_point(self):
            # return self.fair_value
            if self.is_support:
                return self.ob_low
            else:
                return self.ob_high

        @property
        def upper_margin(self):
            # if self.is_support:
            #    return self.ob_high
            # else:
            #    return self.ob_high + (self.ob_high * self.zone_amplitude)
            return self.entry_point + (self.entry_point * self.zone_amplitude)

        @property
        def lower_margin(self):
            # if self.is_support:
            #    return self.ob_low - (self.ob_low * self.zone_amplitude)
            # else:
            #    return self.ob_low
            return self.entry_point - (self.entry_point * self.zone_amplitude)

    def __init__(
        self,
        pair,
        timeframes,
        main_timeframe,
        max_min_candle_numbers=10,
        zone_amplitude=0.0044,
        verbose=False,
    ):
        super().__init__(pair, timeframes, main_timeframe)
        self.max_min_candle_numbers = max_min_candle_numbers
        self.zone_amplitude = zone_amplitude
        self.verbose = verbose

    def calculate_supports(self, data):
        # Simplified version
        # 1. Let's start after a certain amount of candles
        min_indexes_found = scipy.signal.argrelmin(
            data["low"].values, axis=0, order=self.max_min_candle_numbers, mode="clip"
        )[0]

        supply_zones = deque()
        order_blocks = deque()
        # Lets
        for min_index in min_indexes_found:
            row = data.loc[min_index]
            order_block = self._OrderBlock(
                row, min_index, zone_amplitude=self.zone_amplitude, is_support=True
            )
            order_blocks.append(order_block)

        for i in range(0, len(data)):
            row = data.loc[i]

            # Lets see if there is a considered ob that has been touched
            while (
                len(supply_zones)
                and (row["low"] < supply_zones[-1].entry_point)
                and (i > (supply_zones[-1].index + self.distance_to_consider_ob_touched))
            ):
                supply_zones.pop()

            # Lets cancel all recent obs that have been touched
            while (
                len(order_blocks)
                and (row["low"] < order_blocks[0].entry_point)
                and (i > (order_blocks[0].index + self.distance_to_consider_ob_touched))
            ):
                # OB touched, discarding
                order_blocks.popleft()

            if len(order_blocks):
                first_ob = order_blocks[0]
                # We can consider it a minimum after the lookforward is gone
                if i >= first_ob.index + self.max_min_candle_numbers:
                    order_block = order_blocks.popleft()
                    # entry = (order_block.entry_point, order_block.lower_margin, order_block.upper_margin, order_block.index)

                    # If deque is empty add it
                    if not len(supply_zones):
                        supply_zones.append(order_block)
                    elif order_block.candle_low < supply_zones[-1].entry_point:
                        # If its a lower minimum, discard previous supply zones
                        # and add the present one
                        while (
                            len(supply_zones)
                            and order_block.candle_low < supply_zones[-1].entry_point
                        ):
                            supply_zones.pop()
                        if (
                            len(supply_zones)
                            and order_block.candle_low < supply_zones[-1].lower_margin
                        ):
                            supply_zones.append(order_block)
                    elif order_block.candle_low > supply_zones[-1].entry_point:
                        # It is a new higher low, then it is a new OB add it to the deque
                        supply_zones.append(order_block)

            if len(supply_zones):
                # for index in range(len(supply_zones)):
                index = 0
                if (
                    f"supply_zone_{index}_sl_{self.zone_amplitude}_{self.max_min_candle_numbers}"
                    not in data
                ):
                    data[
                        f"supply_zone_{index}_entry_{self.zone_amplitude}_{self.max_min_candle_numbers}"
                    ] = [np.nan] * len(data)
                    data[
                        f"supply_zone_{index}_sl_{self.zone_amplitude}_{self.max_min_candle_numbers}"
                    ] = [np.nan] * len(data)
                    data[
                        f"supply_zone_{index}_ob_high_{self.zone_amplitude}_{self.max_min_candle_numbers}"
                    ] = [np.nan] * len(data)

                # Invert index since it is a deque
                data.loc[
                    i,
                    f"supply_zone_{index}_entry_{self.zone_amplitude}_{self.max_min_candle_numbers}",
                ] = supply_zones[-1 - index].entry_point
                data.loc[
                    i, f"supply_zone_{index}_sl_{self.zone_amplitude}_{self.max_min_candle_numbers}"
                ] = supply_zones[-1 - index].lower_margin
                data.loc[
                    i,
                    f"supply_zone_{index}_ob_high_{self.zone_amplitude}_{self.max_min_candle_numbers}",
                ] = supply_zones[-1 - index].upper_margin

    def calculate_resistances(self, data):
        # Simplified version
        # 1. Let's start after a certain amount of candles
        max_indexes_found = scipy.signal.argrelmax(
            data["high"].values, axis=0, order=self.max_min_candle_numbers, mode="clip"
        )[0]
        demand_zones = deque()
        order_blocks = deque()

        # Lets
        for max_index in max_indexes_found:
            row = data.loc[max_index]
            order_block = self._OrderBlock(
                row, max_index, zone_amplitude=self.zone_amplitude, is_support=False
            )
            order_blocks.append(order_block)

        for i in range(0, len(data)):
            row = data.loc[i]

            # Lets see if there is a considered ob that has been touched
            while (
                len(demand_zones)
                and (row["high"] > demand_zones[-1].entry_point)
                and (i > (demand_zones[-1].index + self.distance_to_consider_ob_touched))
            ):
                demand_zones.pop()

            # Lets cancel all recent obs that have been touched
            while (
                len(order_blocks)
                and (row["high"] > order_blocks[0].entry_point)
                and (i > (order_blocks[0].index + self.distance_to_consider_ob_touched))
            ):
                # OB touched, discarding
                order_blocks.popleft()

            if len(order_blocks):
                first_ob = order_blocks[0]
                # We can consider it a minimum after the lookforward is gone
                if i >= first_ob.index + self.max_min_candle_numbers:
                    order_block = order_blocks.popleft()
                    # entry = (order_block.entry_point, order_block.lower_margin, order_block.upper_margin, order_block.index)

                    # If deque is empty add it
                    if not len(demand_zones):
                        demand_zones.append(order_block)
                    elif order_block.candle_high > demand_zones[-1].entry_point:
                        # If its a lower minimum, discard previous supply zones
                        # and add the present one
                        while (
                            len(demand_zones)
                            and order_block.candle_high > demand_zones[-1].entry_point
                        ):
                            demand_zones.pop()
                        if (
                            len(demand_zones)
                            and order_block.candle_high > demand_zones[-1].upper_margin
                        ):
                            demand_zones.append(order_block)
                    elif order_block.candle_high < demand_zones[-1].entry_point:
                        # It is a new lower high, then it is a new OB add it to the deque
                        demand_zones.append(order_block)

            if len(demand_zones):
                # for index in range(len(demand_zones)):
                index = 0
                if (
                    f"demand_zone_{index}_sl_{self.zone_amplitude}_{self.max_min_candle_numbers}"
                    not in data
                ):
                    data[
                        f"demand_zone_{index}_entry_{self.zone_amplitude}_{self.max_min_candle_numbers}"
                    ] = [np.nan] * len(data)
                    data[
                        f"demand_zone_{index}_sl_{self.zone_amplitude}_{self.max_min_candle_numbers}"
                    ] = [np.nan] * len(data)
                    data[
                        f"demand_zone_{index}_ob_low_{self.zone_amplitude}_{self.max_min_candle_numbers}"
                    ] = [np.nan] * len(data)

                # Invert index since it is a deque
                data.loc[
                    i,
                    f"demand_zone_{index}_entry_{self.zone_amplitude}_{self.max_min_candle_numbers}",
                ] = demand_zones[-1 - index].entry_point
                data.loc[
                    i, f"demand_zone_{index}_sl_{self.zone_amplitude}_{self.max_min_candle_numbers}"
                ] = demand_zones[-1 - index].upper_margin
                data.loc[
                    i,
                    f"demand_zone_{index}_ob_low_{self.zone_amplitude}_{self.max_min_candle_numbers}",
                ] = demand_zones[-1 - index].lower_margin

    def calculate(self, dataframe):
        self.calculate_supports(dataframe)
        self.calculate_resistances(dataframe)

    def on_main_timeframe(self, dataframe):
        pass

    def get_names(self):
        return []
