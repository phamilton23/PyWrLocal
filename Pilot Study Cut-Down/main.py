import os
from scripts import normal_run, do_run, moea_run

def main():
    # Prepare the results directory
    # You might want to delete the results files between runs?
    if not os.path.exists("working_directory/results"):
        os.mkdir("working_directory/results")

    # Do a normal run, producing the run.csv file in the results directory
    print("Running normal model...")
    normal_run.run("working_directory/inputs/run.json",
                   "working_directory/results/run.csv")

    # Run the "DO" PyWr model, generating the DO_run.csv output file
    print("Running DO model...")
    do_run.run("working_directory/inputs/run_DO.json",
                   "working_directory/results/DO_run.csv",
                   "working_directory/results/DO_outputs.csv")

    # Run the "MOEA" PyWr model, generating the archive.db database file
    print("Running MOEA model...")
    print("This can take a few minutes and 100% CPU!")
    moea_run.run("working_directory/inputs/run_MOEA.json",
                 "working_directory/results/archive.db",
                 iterations=1)

    print("The end!")

if __name__ == "__main__":
    main()
