# -*- coding: utf-8 -*-
"""
Created on Thu May 21 17:03:49 2020

@author: WOODCOH
"""
import numpy as np
from pywr.parameters import Parameter, load_parameter


class EstimatedFlow(Parameter):
    '''
    In WRAPSim, esimated flow is done with the following calculation:

    estimated flow = base_flow + prev_flow - prev_base_flow

    base_flow = sum of all upstream inflows
    '''

    # set input nodes to be [lobwood, grimwith]
    def __init__(self, model, gauge_node, inflows, inflows_node, **kwargs):
        super().__init__(model, **kwargs)
        # river_node = flow at addingham , release_node = grimwith release
        self.inflows = inflows
        self.gauge_node = gauge_node
        self.inflows_node = inflows_node
        self.children.add(inflows)

    def value(self, timestep, scenario_index):
        sid = scenario_index.global_id

        # take the previous flow at addingham:
        gauge_flow = self.gauge_node.prev_flow[sid]

        base_flow = self.inflows.get_value(scenario_index)
        prev_base_flow = self.inflows_node.prev_flow[sid]

        estimated_flow = base_flow - prev_base_flow + gauge_flow

        return estimated_flow

    @classmethod
    def load(cls, model, data):
        # called when the parameter is loaded from a JSON document
        gauge_node = data.pop("gauge_node")
        inflows = data.pop("inflows")
        inflows_node = data.pop("inflows_node")
        gauge_node = model.nodes[river_node]
        inflows = model.parameters[release_node]
        inflows_node = model.nodes[inflows_node]
        return cls(model, gauge_node, inflows, inflows_node, **data)


class AbstractionCostBands(Parameter):
    '''
    This is a parameter to replicate the cost found in WRAPSim on abstraction
    nodes.

    There are different costs for different flow rates based on the flow of
    another node.

    Node's current value is a prediction using the EstimatedFlow parameter
    '''

    def __init__(self, model, river_gauge, **kwargs):
        super().__init__(model, **kwargs)

        self.river_gauge = river_gauge
        self.children.add(river_gauge)

    def value(self, timestep, scenario_index):
        predicted_flow = self.river_gauge.get_value(scenario_index)

        if 0 < predicted_flow <= 120:
            abstraction_cost = 100
        elif 120 < predicted_flow <= 242:
            abstraction_cost = 50
        elif 242 < predicted_flow <= 379:
            abstraction_cost = -10
        elif 379 < predicted_flow <= 469:
            abstraction_cost = -70
        else:
            abstraction_cost = -70

        return abstraction_cost

    @classmethod
    def load(cls, model, data):
        # called when the parameter is loaded from a JSON document
        river_gauge = data.pop("river_gauge")
        river_gauge = model.parameters[river_gauge]
        return cls(model, river_gauge, **data)


class LobwoodAbstraction(Parameter):
    '''
    lobwood abstraction parameter.
    The flow at addingham is checked and the release at grimwith.

    The release is checked at the previous timestep and not the current.

    Because we set the release based on the previous lobwood flow we could use
    the function for grimwith release as the grimwith release input. This
    would mean what we abstract would fit the release, but what we release
    checks what was previously abstracted.
    '''

    # set input nodes to be [lobwood, grimwith]
    def __init__(self, model, river_node, high_flow_limit, low_flow_limit, **kwargs):
        super().__init__(model, **kwargs)
        # river_node = flow at addingham , release_node = grimwith release
        self.river_node = river_node
        self.high_flow_limit = high_flow_limit
        self.low_flow_limit = low_flow_limit
        self.children.add(river_node)
        self.children.add(high_flow_limit)
        self.children.add(low_flow_limit)

    def value(self, timestep, scenario_index):
        # take the previous flow at addingham:
        river_flow = self.river_node.get_value(scenario_index)

        # take max flow from the if statement
        if river_flow >= 488:
            limit = self.high_flow_limit.get_value(scenario_index)
        else:
            limit = self.low_flow_limit.get_value(scenario_index)
        return limit

    @classmethod
    def load(cls, model, data):
        # called when the parameter is loaded from a JSON document
        river_node = load_parameter(model, data.pop("river_node"))
        high_flow_limit = load_parameter(model, data.pop("river_node"))
        low_flow_limit = load_parameter(model, data.pop("river_node"))

        return cls(model, river_node, high_flow_limit, low_flow_limit, **data)


'''
class LobwoodMinimum(Parameter):

    def __init__(self, model, licence_node, lobwood_min_param, **kwargs):
        super().__init__(model, **kwargs)
        #licence node = lobwood licence,
        #lobwood_min_param = a monthly profile for the minimum lobwood flow.
        self.licence_node = licence_node
        self.lobwood_min_param = lobwood_min_param


    def value(self,timestep,scenario_index):
        sid = scenario_index.global_id

        #get the lobwood minimum value
        minimum = self.lobwood_min_param.get_value(scenario_index)
        #get the remaining licence
        remaining = self.licence_node.get_level(scenario_index)

        if minimum >= remaining:
            minimum = remaining #minimum can only use up remainder of licence.
        else:
            pass
        return minimum
'''
'''
def grimwith_rules(actually_abstracted):
    if actually_abstracted >= 93.2:
        return 0

    elif 88.6 <= actually_abstracted <93.2:
        return np.min([actually_abstracted-6.8,81.8])

    elif actually_abstracted < 88.6:
        return np.min([actually_abstracted+22.7,111.3])
'''

"""
class GrimwithRelease(Parameter):
    '''
    this parameter is the flow for the grimwith release node
    '''

    def __init__(self,model,lobwood, **kwargs):
        super().__init__(model, **kwargs)

        self.lobwood = lobwood
        #self.compensation = riverdibb_comp

    def value(self,timestep,scenario_index):
        sid = scenario_index.global_id

        #meeting compensation
        #comp_flow=self.compensation.prev_flow[sid]
        # previous abstraction
        abstracted = self.lobwood.prev_flow[sid]

        release = grimwith_rules(abstracted)

        return release
    @classmethod
    def load(cls, model, data):
        lobwood = data.pop("abstraction_node")
        riverdibb_comp= data.pop("comp_node")
        #grab nodes from the model
        lobwood = model.nodes[lobwood]
        riverdibb_comp=model.nodes[riverdibb_comp]
        return cls(model, lobwood, riverdibb_comp)
"""


class GrimwithReleaseMax(Parameter):
    '''
    set the max allowed release from Grimwith
    '''

    def __init__(self, model, river_gauge, **kwargs):
        super().__init__(model, **kwargs)

        self.river_gauge = river_gauge
        self.children.add(river_gauge)

    def value(self, timestep, scenario_index):
        sid = scenario_index.global_id

        current_flow = self.river_gauge.get_value(scenario_index)

        if current_flow >= 389:
            release = 0
        elif 252 <= current_flow < 389:
            release = 88.6 - 6.8
        else:
            release = 88.6

        return release

    @classmethod
    def load(cls, model, data):
        river_gauge = data.pop("river_gauge")
        # grab nodes from the model
        river_gauge = model.parameters[river_gauge]
        return cls(model, river_gauge, **data)


class GrimwithCompensationRelease(Parameter):
    '''
    set the max allowed release from Grimwith
    '''

    def __init__(self, model, grimwith_comp, river_gauge, **kwargs):
        super().__init__(model, **kwargs)

        self.grimwith_comp = grimwith_comp
        self.grimwith_comp = [15.1, 15.1, 15.1, 10.72, 3.8, 3.8, 3.8, 3.8, 3.8,
                              9.625, 15.1, 15.1]
        self.river_gauge = river_gauge
        self.children.add(river_gauge)
        self.children.add(grimwith_comp)

    def value(self, timestep, scenario_index):
        sid = scenario_index.global_id

        current_flow = self.river_gauge.get_value(scenario_index)

        idx = timestep.month - 1

        if current_flow < 252:
            new_comp = self.grimwith_comp[idx] + 22.7
        else:
            new_comp = self.grimwith_comp[idx]

        return new_comp

    @classmethod
    def load(cls, model, data):
        grimwith_comp = data.pop("grimwith_comp")
        river_gauge = data.pop("river_gauge")
        # grab nodes from the model
        river_gauge = model.parameters[river_gauge]
        grimwith_comp = model.parameters[grimwith_comp]
        return cls(model, grimwith_comp, river_gauge, **data)


class LobwoodRiverIntake(Parameter):
    def __init__(self, model, river_gauge, grimwith_comp, high_flow_limit, **kwargs):
        super().__init__(model, **kwargs)

        self.river_gauge = river_gauge
        self.grimwith_comp = grimwith_comp
        self.high_flow_limit = high_flow_limit
        self.children.add(river_gauge)
        self.children.add(grimwith_comp)
        self.children.add(high_flow_limit)

    def value(self, timestep, scenario_index):
        sid = scenario_index.global_id

        current_flow = self.river_gauge.get_value(scenario_index)
        current_comp = self.grimwith_comp.get_value(scenario_index)

        # when grimwith cannot release the entire amount can come from river
        if current_flow >= 488:
            allowed = self.high_flow_limit.get_value(scenario_index)
        # grimwith still cannot release (less can be took by river)
        elif 389 <= current_flow < 488:
            allowed = 88.6
        #
        elif 252 <= current_flow < 389:
            allowed = 6.8 + current_comp
        else:
            allowed = 0 + current_comp

        return allowed

    def load(cls, model, data):
        river_gauge = data.pop("river_gauge")
        grimwith_comp = data.pop("grimwith_comp")
        # grab nodes from the model
        river_gauge = model.parameters[river_gauge]
        grimwith_comp = model.parameters[grimwith_comp]
        return cls(model, river_gauge, grimwith_comp, **data)


'''
addingham > 488 -> Grimwith = 0, River = lobwood min and max
389, 488 -> grimwith 0, lobwood min and max
252 < addingham < 389 -> grimwith max = 88.6 - 6.8, river max = 6.8
addingham <=  252   grimwith max 88.6 + (22.7), river max = 0



## new pipe
flow = 0
addingham < = 252
return 22.7
'''

'''
    elif 389<=addingham_flow < 488: return 88.6
    elif 252<=addingham_flow<389: return grimwith_flow + 6.8
    else: return np.max([np.min([grimwith_flow - 22.7, 88.6]),0])
'''

"""
def grimwith_rules(actually_abstracted, wharfe_flow):
    '''
    #these need updated to correct values
    '''
    #the if statement
    if wharfe_flow >= 389: return 0
    elif 252 <=wharfe_flow <389 and actually_abstracted > 6.8: return actually_abstracted-6.8
    elif wharfe_flow < 252 and actually_abstracted >0: return actuall_abstracted + 22.7
    else: return 0
"""
