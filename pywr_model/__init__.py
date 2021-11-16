# -*- coding: utf-8 -*-
"""
Created on Tue Jun  2 14:25:04 2020

@author: WOODCOH
"""
from pywr.recorders import AnnualCountIndexThresholdRecorder, NumpyArrayIndexParameterRecorder
from pywr.parameters.control_curves import ControlCurveIndexParameter
from pywr.recorders import NumpyArrayParameterRecorder
from pywr_model.lobwood_abstraction_licence import GrimwithReleaseMax, LobwoodAbstraction, EstimatedFlow, \
    AbstractionCostBands, GrimwithCompensationRelease
from pywr.parameters import ConstantParameter
from pywr_model.lobwood_abstraction_licence import LobwoodRiverIntake
from pywr_model.level_of_service import ForecastCrossingIndexParameter, StickyIndexParameter, EventCountIndexParameterRecorder
from .flood_profile import patch_nidd_flood_curve
import json


def patch_model(model):
    # ======Load nodes for custom parameters===========
    # river node (where the river gauge for lobwood is)
    river_node = model.nodes["Addingham"]
    # grimwith release node
    grimwith_release = model.nodes["Grimwith Release"]
    # the lobwood abstraction node
    abstraction_node = model.nodes["Lobwood Constraint"]
    # the lobwood licence
    # licence_node = model.nodes["Lobwood Licence"]
    # the seasonal minimum for lobwood
    seasonal_minimum = model.parameters["Lobwood Minimum Abstraction"]
    # set max flow at lobwood = to the lobwood abstraction parameter

    # wharfe inflow parameter
    wharfe2_inflow = model.parameters["Wharfe2 Inflow"]
    wharfe2_node = model.nodes["Wharfe2In"]

    # grimwith compensation
    grimwith_comp = model.parameters["Grimwith Compensation Flow"]

    # =======Set up Parameters===============
    estimated_flow = EstimatedFlow(model, river_node, wharfe2_inflow,
                                   wharfe2_node, name="Estimated Addingham Flow")
    lobwood_abstraction_cost = AbstractionCostBands(model, estimated_flow,
                                                    name="Lobwood Abstraction Cost")

    lobwood_high_flow_limit = ConstantParameter(model, 93.2, name="Lobwood high flow limit")
    lobwood_low_flow_limit = ConstantParameter(model, 88.6, name="Lobwood low flow limit")

    lobwood_max = LobwoodAbstraction(model, estimated_flow, lobwood_high_flow_limit, lobwood_low_flow_limit,
                                     name="Lobwood Abstraction Maximum")
    # lobwood_min = model.parameters["Lobwood Minimum Abstraction"]
    grimwith_release_max = GrimwithReleaseMax(model, estimated_flow,
                                              name="Grimwith Release Max")
    grimwith_comp_release = GrimwithCompensationRelease(model, grimwith_comp,
                                                        estimated_flow, name=
                                                        "Grimwith Compensation" \
                                                        "Release")
    river_intake_max = LobwoodRiverIntake(model, estimated_flow, grimwith_comp, lobwood_high_flow_limit,
                                          name="Allowed Lobwood River Intake")

    # =======Set up Nodes===============
    abstraction_node.min_flow = seasonal_minimum
    abstraction_node.max_flow = lobwood_max
    abstraction_node.cost = lobwood_abstraction_cost
    grimwith_release.max_flow = grimwith_release_max
    model.nodes["Grimwith Compensation"].max_flow = grimwith_comp_release
    model.nodes["Lobwood River Intake"].max_flow = river_intake_max
    # model.nodes["Lobwood River Intake"].cost = lobwood_abstraction_cost

    ### create a total grimwith release node
    # recorder the original grimwith comp
    NumpyArrayParameterRecorder(model, grimwith_comp, name="Grimwith Comp Recorder")
    NumpyArrayParameterRecorder(model, grimwith_comp_release, name="Grimwith Comp param Recorder")

    ### Create level of service parameters ###
    tubs_forecast_param = ForecastCrossingIndexParameter(model, model.nodes["Group Storage"],
                                                         model.parameters["Group line7"],
                                                         rolling_window=4 * 7, forecast_window=6 * 7,
                                                         name="Group TUBs forecast")
    tubs_param = StickyIndexParameter(model, tubs_forecast_param, minimum_days=12 * 7, name="Group TUBs active")
    NumpyArrayIndexParameterRecorder(model, tubs_forecast_param, name="Group TUBs forecast recorder")
    NumpyArrayIndexParameterRecorder(model, tubs_param, name="Group TUBs active recorder")

    tubs_count = EventCountIndexParameterRecorder(model, tubs_param, threshold=1, name="Group TUBs Annual Count",
                                                   constraint_upper_bounds=95 // 25)

    neubs_crossing_param = ControlCurveIndexParameter(model, model.nodes["Group Storage"],
                                                      model.parameters["Group line7"],
                                                      name="Group NEUBs crossed")
    neubs_param = StickyIndexParameter(model, neubs_crossing_param, minimum_days=12 * 7, name="Group NEUBs active")

    NumpyArrayIndexParameterRecorder(model, neubs_crossing_param, name="Group NEUBs crossing recorder")
    NumpyArrayIndexParameterRecorder(model, neubs_param, name="Group NEUBs active recorder")

    neubs_count = EventCountIndexParameterRecorder(model, neubs_param, threshold=1, name="Group NEUBs Annual Count",
                                                    constraint_upper_bounds=95 // 80)

    model.bisect_epsilon = 0.0025
    model.bisect_parameter = "Demand Scaling Factor"
    model.error_on_infeasible = False


def patch_json_data_reservoir_costs(data, reservoir):
    # Find the reservoir control curve parameter
    cc_param = data["parameters"][f"{reservoir} Curve"]
    cc_costs = cc_param.pop("values")
    cc_cost_params = []

    for i, cost in enumerate(cc_costs):
        name = f"{reservoir} cost{i + 1}"
        cc_cost_params.append(name)

        if i < 3:
            cost_param = {
                "type": "constant",
                "value": cost
            }
        elif i < 6:
            cost_param = {
                "type": "offset",
                "parameter": f"{reservoir} cost{i + 2}",
                "is_variable": True,
                "upper_bounds": 100,
                "lower_bounds": 0
            }
        else:
            cost_param = {
                "type": "constant",
                "value": cost
            }
        data["parameters"][name] = cost_param
    cc_param["parameters"] = cc_cost_params
    return data


def patch_json_data_group_curve(data):
    """Make Group reservoir curve a variable."""

    # TODO this only does line7; could be more flexible
    data["parameters"]["Group line7"] = {
        "type": "RbfProfileParameter",
        "days_of_year": [1, 120, 240],
        "values": [0.44, 0.49, 0.31],
        "lower_bounds": 0.2,
        "upper_bounds": 0.6,
        "is_variable": True,
    }

    # This recorder will produce daily time
    data["recorders"]["Group line7 profile"] = {
        "type": "NumpyArrayDailyProfileParameterRecorder",
        "parameter": "Group line7"
    }

    return data


def patch_json_data_objectives(data):
    # Setup objectives
    # data["recorders"]["Total Cost Recorder"]["is_objective"] = "min"
    data["recorders"]["Total Demand Recorder"]["is_objective"] = "max"

    return data


def remove_nodal_min_flows(data):
    for node in data['nodes']:
        if 'min_flow' in node:
            node.pop('min_flow')
    return data


def patch_json(input_fn, output_fn, include_flood_curves=False,
               moae_settings=None):

    with open(input_fn) as fh:
        data = json.load(fh)

    # data = patch_json_data_group_curve(data)
    data = patch_json_data_objectives(data)
    data = remove_nodal_min_flows(data)

    if include_flood_curves:
        data = patch_nidd_flood_curve(data, moae_settings)

    with open(output_fn, mode="w") as fh:
        json.dump(data, fh, indent=2)
