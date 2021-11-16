from pywr.parameters import Parameter, load_parameter
import numpy as np


class FloodProfileParameter(Parameter):
    def __init__(self, *args, **kwargs):
        draw_down_pc = kwargs.pop('draw_down_pc')
        start_doy = kwargs.pop('start_doy')
        end_doy = kwargs.pop('end_doy')
        super().__init__(*args, **kwargs)
        self.children.add(draw_down_pc)
        self.draw_down_pc = draw_down_pc
        self.start_doy = start_doy
        self.end_doy = end_doy
        self.integer_size = 2

    def value(self, ts, si):
        if self.end_doy < ts.dayofyear < self.start_doy:
            return 1.01
        else:
            return self.draw_down_pc.get_value(si)

    def set_integer_variables(self, values):
        self.start_doy = int(values[0])
        self.end_doy = int(values[1])

    def get_integer_variables(self):
        return np.array([self.start_doy, self.end_doy], dtype=np.int32)

    def get_integer_lower_bounds(self):
        return np.array([214, 0], dtype=np.int32)

    def get_integer_upper_bounds(self):
        return np.array([367, 244], dtype=np.int32)

    @classmethod
    def load(cls, model, data):
        draw_down_pc = load_parameter(model, data.pop('draw_down_pc'))
        return cls(model, draw_down_pc=draw_down_pc, **data)
FloodProfileParameter.register()


def patch_nidd_flood_curve(data, moae_settings):
    """Add a flood line0 to a reservoir"""
    if moae_settings is not None:
        nidd_lower = moae_settings['nidd_group_flood_pc_lower']
        nidd_upper = moae_settings['nidd_group_flood_pc_upper']
        nidd_max_flood_release = moae_settings['nidd_group_max_flood_release']
        flood_upper = nidd_max_flood_release['upper_bounds']
        flood_lower = nidd_max_flood_release['lower_bounds']
        nidd_group_flood_profile = moae_settings['nidd_group_flood_profile']
        start_day = nidd_group_flood_profile['start_day']
        end_day = nidd_group_flood_profile['end_day']
    else:
        nidd_lower = 0.7
        nidd_upper = 1.0
        flood_upper = 400
        flood_lower = 0
        start_day = 306
        end_day = 91

    data["parameters"]["Nidd Group flood pc"] = {
        "type": "constant",
        "value": 1.0,
        "lower_bounds": nidd_lower,
        "upper_bounds": nidd_upper,
        "is_variable": True
    }

    data["parameters"]["Nidd Group flood release"] = {
        "type": "controlcurveparameter",
        "storage_node": "Nidd Group",
        "control_curves": [
            "Nidd Group line0"
        ],
        "parameters": [
            "Nidd Group max flood release",
            "Nidd Group no flood release",
        ]
    }

    data["parameters"]["Nidd Group max flood release"] = {
        "type": "constant",
        "value": 0.0,
        "lower_bounds": flood_lower,
        "upper_bounds": flood_upper,
        "is_variable": True
    }

    data["parameters"]["Nidd Group no flood release"] = {
        "type": "constant",
        "value": 0.0
    }

    data["parameters"]["Nidd Group line0"] = {
        "type": "floodprofile",
        "draw_down_pc": "Nidd Group flood pc",
        "start_doy": start_day,
        "end_doy": end_day,
        "is_variable": True
    }

    data["nodes"].append({
        "name": "Nidd Group Flood Release",
        "type": "link",
        "cost": -50,
        "max_flow": "Nidd Group flood release"
    })

    data["nodes"].append({
        "name": "Nidd Group total outflow",
        "type": "AggregatedNode",
        "nodes": ["Nidd Group Flood Release", "Nidd Group Spill"]
    })

    data["nodes"].append({
        "name": "Gouthwaite total outflow",
        "type": "AggregatedNode",
        "nodes": ["Gouthwaite Spill", "GouthwaiteComp"]
    })

    data["edges"].append([
        "Nidd Group",
        "Nidd Group Flood Release"
    ])
    data["edges"].append([
        "Nidd Group Flood Release",
        "Gouthwaite"
    ])

    data["recorders"]["Nidd Group total FDC"] = {
        "type": "FlowDurationCurveRecorder",
        "node": "Nidd Group total outflow",
        "percentiles": [1, 5, 10, 25, 50, 75, 90, 95, 99],
        "fdc_agg_func": "max",
    }

    data["recorders"]["Nidd Group total FDC Q01"] = {
        "type": "FlowDurationCurveRecorder",
        "node": "Nidd Group total outflow",
        "percentiles": [99],
        "fdc_agg_func": "max",
        "is_objective": "minimise"
    }

    data["recorders"]["Nidd Group total FDC Q10"] = {
        "type": "FlowDurationCurveRecorder",
        "node": "Nidd Group total outflow",
        "percentiles": [90],
        "fdc_agg_func": "max",
        "is_objective": "minimise"
    }

    data["recorders"]["Gouthwaite total FDC"] = {
        "type": "FlowDurationCurveRecorder",
        "node": "Gouthwaite total outflow",
        "percentiles": [1, 5, 10, 25, 50, 75, 90, 95, 99],
        "fdc_agg_func": "max",
    }

    data["recorders"]["peq02255 FDC"] = {
        "type": "FlowDurationCurveRecorder",
        "node": "peq02255",
        "percentiles": [1, 5, 10, 25, 50, 75, 90, 95, 99],
    }

    data["recorders"]["Nidd Group SDC"] = {
        "type": "StorageDurationCurveRecorder",
        "node": "Nidd Group",
        "percentiles": [0, 5, 10, 25, 50, 75, 90, 95, 100],
    }

    data["recorders"]["Nidd Group SDC"] = {
        "type": "StorageDurationCurveRecorder",
        "node": "Grimwith",
        "percentiles": [0, 5, 10, 25, 50, 75, 90, 95, 100],
    }

    data["recorders"]["Nidd Group SDC"] = {
        "type": "StorageDurationCurveRecorder",
        "node": "Gouthwaite",
        "percentiles": [0, 5, 10, 25, 50, 75, 90, 95, 100],
    }

    data["recorders"]["Gouthwaite Total Outflow Recorder"] = {
        "type": "numpyarraynoderecorder",
        "node":  "Gouthwaite total outflow"
    }

    data["recorders"]["Nidd Group Total Outflow Recorder"] = {
        "type": "numpyarraynoderecorder",
        "node": "Nidd Group total outflow"
    }

    data["recorders"]["Nidd Group Flood Release Recorder"] = {
        "type": "numpyarraynoderecorder",
        "node": "Nidd Group Flood Release"
    }

    data["recorders"]["Group Storage Recorder"] = {
        "type": "numpyarraystoragerecorder",
        "node": "Group Storage"
    }

    data["recorders"]["Nidd Group Flood Release Param Recorder"] = {
        "type": "numpyarrayparameterrecorder",
        "parameter": "Nidd Group flood release"
    }

    data["recorders"]["Nidd Group line0 Recorder"] = {
        "type": "NumpyArrayDailyProfileParameterRecorder",
        "parameter": "Nidd Group line0"
    }

    # TODO:
    # - Minimise Q1 or max flow from Nidd
    # - Minimise Q1 or max flow from Gouthwaite
    # - Check it could activate flood draw-down all year round.
    #  - Check this impacts max flow in a manual test run.
    # - ~~Add recorder for the profiles~~
    # - ~~Add a FDC/SDC recorders for Nidd, Grimwith, Gouthwaite (and their total outflows),~~
    #       ~~and the flow to the network (peq02255)~~
    # - Check upper limit on DO scaling factor

    return data
