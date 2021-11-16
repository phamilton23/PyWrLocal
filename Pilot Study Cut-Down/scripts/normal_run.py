from pywr.core import Model

def run(json_path, csv_path):
    model = Model.load(json_path, solver='glpk-edge')
    model.run()
    df = model.to_dataframe()
    df.to_csv(csv_path)
