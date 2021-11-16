from pywr.utils.bisect import BisectionSearchModel
from pywr_model import patch_model
import pandas

def run(json_path, csv_path, output_csv_path):
    model = BisectionSearchModel.load(json_path, solver='glpk-edge')
    patch_model(model)

    model.bisect_epsilon = 0.0025
    model.bisect_parameter = "Demand Scaling Factor"

    stats = model.run()

    names = ["TUBS count", "NEUBs count", "Total Demand", "Total Cost",
             "DO Scaling Factor"]
    values = [model.recorders['Group TUBs Annual Count'].aggregated_value(),
              model.recorders['Group NEUBs Annual Count'].aggregated_value(),
              model.recorders['Total Demand Recorder'].aggregated_value(),
              model.recorders['Total Cost Recorder'].aggregated_value(),
              model.parameters[model.bisect_parameter].get_double_variables()[0]
              ]
    do_df = pandas.DataFrame()
    do_df['item'] = names
    do_df['value'] = values
    do_df.index = do_df.item
    do_df.drop(columns =['item'],inplace=True)

    do_values = {}
    for name, value in zip(names, values):
        do_values[name] = value

    dfs = {}
    for rec in model.recorders:
        if hasattr(rec, 'to_dataframe'):
            df = rec.to_dataframe()
            if isinstance(df.index, pandas.PeriodIndex):
                dfs[rec.name] = df

    dfs = pandas.concat(dfs, axis=1)
    dfs.columns.set_names('Recorder', level=0, inplace=True)

    dfs.to_csv(csv_path)
    do_df.to_csv(output_csv_path)
