import importlib
import glob
import sys, os, pathlib
import schedule
import time
import datetime as dt
import toml


# required so that plugins can be loaded 
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(HERE+'/pipeline')


def print_config(customer_id=0):
    config = toml.load(pathlib.Path(HERE)/'pipeline/data/pipeline.toml')
    config['base']['customer_id'] = customer_id
    config['base']['pipeline_path'] = str(pathlib.Path(HERE)/'pipeline')
    print(config)



def _import(pipeline, step):
    """Import the given plugin file from a package"""
    return importlib.import_module(f"{pipeline}.{step}")


def _import_pipeline(pipeline):

    cwd = os.getcwd()

    """import all steps/modules of the folder/package 'pipeline' in alphabetical order"""
    flist = list()
    for filepath in glob.iglob(f'{pipeline}/*.py'):
        if filepath != f'{pipeline}/util.py':
            flist.append(filepath)

    # this sorts the original list in place - handy for a sequential pipeline
    flist.sort()

    pipeline_steps = list()
    steps = [f[:-3] for f in flist if f[0] != "_"]
    for step in steps:
        pipeline_steps.append(_import(*step.split('/')))

    os.chdir(cwd)
    
    return pipeline_steps

def run_pipeline(pipeline_steps=_import_pipeline('pipeline'), customer_id=0):
    print(f'starting pipeline run for customer {customer_id} at {dt.datetime.now()}')

    config = toml.load(pathlib.Path(HERE)/'pipeline/data/pipeline.toml')
    config['base']['customer_id'] = customer_id
    config['base']['pipeline_path'] = str(pathlib.Path(HERE)/'pipeline')
    try:
        # run whole pipeline or break, but without breaking the process
        for step in pipeline_steps:
            step.run(config)
    except Exception as e:
        print(f'pipeline run failed in step {str(step)} at {dt.datetime.now()}, exception below..')
        print(e)
    else:
        print(f'pipeline completed successfully at {dt.datetime.now()}')


def start_schedule(pipeline_steps):

    schedule.every().day.at('03:00').do(run_pipeline, pipeline_steps)
    #schedule.every().day.at('09:00').do(run_pipeline, pipeline_steps)
    schedule.every().day.at('15:00').do(run_pipeline, pipeline_steps)
    #schedule.every().day.at('21:00').do(run_pipeline, pipeline_steps)    

    #schedule.every(10).minutes.do(run_pipeline, pipeline_steps)
    run_pipeline(pipeline_steps)

    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    #os.environ["CONFIG_DIR"] = os.getcwd()

    # import all steps/modules of the folder/package in alphabetical order
    pipeline_steps = _import_pipeline('pipeline')
    # start the schedule to run the pipeline
    start_schedule(pipeline_steps)
