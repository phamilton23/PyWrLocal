import pathlib
from pywr.utils.bisect import BisectionSearchModel
import json
import pandas as pd
import numpy as np
from pywr_model import patch_model, patch_json
import platypus
from pywr.optimisation.platypus import PlatypusWrapper, PywrRandomGenerator
from pywr.recorders import NumpyArrayDailyProfileParameterRecorder, FlowDurationCurveRecorder, StorageDurationCurveRecorder
import sqlite3
import os
from pathlib import Path

CREATE_DB_SQL = """
        CREATE TABLE IF NOT EXISTS solutions (
            id INTEGER PRIMARY KEY,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            vars JSON,
            objs JSON,
            cons JSON,
            metrics JSON,
            profiles JSON
            );
    """

class YWWrapper(PlatypusWrapper):
    def __init__(self, *args, **kwargs):
        self.archive_fn = kwargs.pop('archive_fn', None)
        super().__init__(*args, **kwargs)

    def customise_model(self, model):
        patch_model(model)

    def variables_to_dict(self):
        data = {}
        for var in self.model_variables:
            var_data = {
                'type': var.__class__.__name__
            }
            if var.double_size > 0:
                var_data['doubles'] = np.array(var.get_double_variables()).tolist()
            if var.integer_size > 0:
                var_data['integers'] = np.array(var.get_integer_variables()).tolist()
            data[var.name] = var_data
        return data

    def objectives_to_dict(self):
        data = {}
        for r in self.model_objectives:
            data[r.name] = {
                'value': r.aggregated_value(),
                'type': r.__class__.__name__,
                'direction': r.is_objective,
            }
        return data

    def constraints_to_dict(self):
        data = {}
        for r in self.model_constraints:
            data[r.name] = {
                'value': r.aggregated_value(),
                'type': r.__class__.__name__,
                'is_constraint_violated': r.is_constraint_violated()
            }
        return data

    def metrics_to_dict(self):
        data = {}
        for r in self.model.recorders:
            try:
                value = r.aggregated_value()
            except Exception:
                pass
            else:
                data[r.name] = {
                    'value': value,
                    'type': r.__class__.__name__
                }
        return data

    def fdcs_to_dict(self):
        data = {}
        for r in self.model.recorders:
            if not isinstance(r, (FlowDurationCurveRecorder, StorageDurationCurveRecorder)):
                continue
            data[r.name] = r.to_dataframe().to_dict(orient='records')
        return data

    def profiles_to_dict(self):
        daily_profiles = {}
        for r in self.model.recorders:
            if isinstance(r, NumpyArrayDailyProfileParameterRecorder):
                # Take only the first profile; assume these are not varying across scenario.
                profile = r.to_dataframe().iloc[:, 0]
                daily_profiles[r.name] = profile.values.tolist()
        return daily_profiles

    def evaluate(self, solution):
        result = super().evaluate(solution)

        conn = sqlite3.connect(self.archive_fn)
        c = conn.cursor()

        c.execute(CREATE_DB_SQL)
        c.execute(
            "INSERT INTO solutions (vars, objs, cons, metrics, profiles)"
            " VALUES (?, ?, ?, ?, ?);",
            [
                json.dumps(self.variables_to_dict()),
                json.dumps(self.objectives_to_dict()),
                json.dumps(self.constraints_to_dict()),
                json.dumps(self.metrics_to_dict()),
                json.dumps(self.profiles_to_dict()),
                # json.dumps(self.fdcs_to_dict()),
            ]
        )
        conn.commit()

        return result

def moea_callback(alg):

    objectives = pd.DataFrame(data=np.array([s.objectives for s in alg.archive[:]]),
                              columns=[o.name for o in alg.problem.wrapper.model_objectives])

    variables = pd.DataFrame(data=np.array([s.variables for s in alg.archive[:]]))
    objectives.to_csv(f'working_directory/results/objective-{alg.nfe:06d}.csv')
    variables.to_csv(f'working_directory/results/variables-{alg.nfe:06d}.csv')


def run(json_path, db_path, iterations):
    if os.path.exists(db_path):
        os.unlink(db_path)    

    wrapper = YWWrapper(json_path,
                        model_klass=BisectionSearchModel,
                        archive_fn=Path(".") / db_path)
    generator = PywrRandomGenerator(wrapper=wrapper, use_current=True)

    with platypus.ProcessPoolEvaluator() as evaluator:
        algorithm = platypus.EpsNSGAII(wrapper.problem, evaluator=evaluator,
                                       population_size=128, epsilons=[0.1, 0.1],
                                       generator=generator)

        algorithm.run(iterations, callback=moea_callback)

