from pywr.parameters import IndexParameter
from pywr.recorders import IndexParameterRecorder
import numpy as np


class ForecastCrossingIndexParameter(IndexParameter):
    """A parameter that forecasts crossing a control curve.

    If a crossing is forecast in the defined window this parameter returns
    a value of 1, otherwise it returns a value of 0. It is intended to be
    used to trigger drought actions by projecting recent drawdown rates in
    to the future.
    """
    def __init__(self, model, storage_node, control_curve, rolling_window, forecast_window, **kwargs):
        super().__init__(model, **kwargs)
        self.storage_node = storage_node
        self.control_curve = control_curve
        self.children.add(control_curve)
        self.rolling_window = rolling_window
        self.forecast_window = forecast_window
        self._forecast_volume = None
        self._memory = None
        self._position = None

    def setup(self):
        super().setup()
        ncomb = len(self.model.scenarios.combinations)
        nts = len(self.model.timestepper)
        self._forecast_volume = np.empty(ncomb, np.float64)
        self._memory = np.empty((nts, ncomb,), np.float64)
        self._position = 0

    def reset(self):
        super().reset()
        self._forecast_volume[...] = 0
        self._memory[...] = 0
        self._position = 0

    def index(self, ts, si):
        # Current control curve value
        cc = self.control_curve.get_value(si)
        # Current reservoir volume
        # TODO This only works with an `AggregatedStorage` node.
        #  Needs a fix in Pywr to create `AggregatedStorage.get_max_volume(si)`
        max_vol = sum([s.get_max_volume(si) for s in self.storage_node.storage_nodes])
        # Convert control curve to absolute volume
        cc *= max_vol
        # Get current volume
        vol = self.storage_node.volume[si.global_id]

        if vol < cc:
            return 1  # Already lower than curve
        elif ts.index < self.rolling_window:
            # Can't forecast a crossing before the memory is full.
            return 0
        else:
            if self._forecast_volume[si.global_id] < cc:
                return 1  # Forecasting a failure
            return 0

    def after(self):
        # Get the current time-step
        timestep = self.model.timestepper.current

        if timestep.index < self.rolling_window:
            n = timestep.index + 1
        else:
            n = self.rolling_window

        # The flow at a storage node is the change in volume (i.e. gradient)
        self._memory[self._position, :] = self.storage_node.flow
        # Calculate the mean gradient in each scenario
        mean_gradient = np.mean(self._memory[:n, :], axis=0)
        # Make a forecast from the current volume using the mean gradient
        self._forecast_volume = self.storage_node.volume + mean_gradient * self.forecast_window
        # Update memory position
        self._position += 1
        if self._position >= self.rolling_window:
            self._position = 0


class StickyIndexParameter(IndexParameter):
    def __init__(self, model, index_parameter, minimum_timesteps=None, minimum_days=None, **kwargs):
        super().__init__(model, **kwargs)
        self.index_parameter = index_parameter
        self.children.add(index_parameter)

        if not minimum_timesteps and not minimum_days:
            raise ValueError("Either `minimum_timesteps` or `minimum_days` must be specified.")
        if minimum_timesteps:
            self.minimum_timesteps = int(minimum_timesteps)
        else:
            self.minimum_timesteps = 0
        if minimum_days:
            self.minimum_days = int(minimum_days)
        else:
            self.minimum_days = 0
        self._timestep_off = None

    def setup(self):
        super().setup()
        self._timestep_off = np.empty([len(self.model.scenarios.combinations)], np.int32)
        if self.minimum_days > 0:
            try:
                self.minimum_timesteps = self.minimum_days // self.model.timestepper.delta
            except TypeError:
                raise TypeError('A stick period defined as a minimum number of days is only valid '
                                'with daily time-steps.')
        if self.minimum_timesteps == 0:
            raise ValueError("Timesteps property of StickyIndexParameter is less than 1.")

    def reset(self):
        super().reset()
        self._timestep_off[...] = -1

    def index(self, ts, si):

        sid = si.global_id
        current_value = self.index_parameter.get_index(si)

        if self._timestep_off[sid] >= 0:
            # Action has been triggered
            # Check if it needs extending
            if current_value > 0:
                self._timestep_off[sid] = ts.index + self.minimum_timesteps

            if self._timestep_off[sid] >= ts.index:
                return 1  # Still on

        if current_value > 0:
            if self._timestep_off[sid] < 0:
                # Start minimum period
                self._timestep_off[sid] = ts.index + self.minimum_timesteps
            return 1
        else:
            self._timestep_off[sid] = -1
            return 0


class EventCountIndexParameterRecorder(IndexParameterRecorder):
    """Record the number of events an index parameter exceeds a threshold for each scenario.

    Parameters
    ----------
    model : `pywr.core.Model`
    parameter : `pywr.core.IndexParameter`
        The parameter to record
    threshold : int
        The threshold to compare the parameter to
    """
    def __init__(self, model, parameter, threshold: int, *args, **kwargs):
        super().__init__(model, parameter, *args, **kwargs)
        self.threshold = threshold
        self._count = None
        self._previous_value = None

    def setup(self):
        self._count = np.zeros(len(self.model.scenarios.combinations), np.int32)
        self._previous_value = np.zeros(len(self.model.scenarios.combinations), np.int32)

    def reset(self):
        self._count[...] = 0
        self._previous_value[...] = 0

    def after(self):
        for scenario_index in self.model.scenarios.combinations:
            sid = scenario_index.global_id
            value = self._param.get_index(scenario_index)
            if value >= self.threshold > self._previous_value[sid]:
                # threshold achieved, when previous value did not (i.e. new event)
                self._count[sid] += 1
            self._previous_value[sid] = value

    def values(self):
        return self._count.astype(np.float64)
