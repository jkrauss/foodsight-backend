import pathlib
import os
import dotenv
import toml

def __load_with_path(p):
    config = toml.load(os.path.join(p, 'pipeline/data/customer.toml'))
    # load env vars
    dotenv.load_dotenv(os.path.join(p, '.env'))
    
    # This is the only place where the path to the pipeline is set!
    config['base']['pipeline_path'] = os.path.join(p, 'pipeline')
    return config

def load_config():

    if os.environ['CONFIG_DIR']:
        config = __load_with_path(os.environ['CONFIG_DIR'])
    else:
        p = pathlib.Path.cwd()
        if p.parts[-1]=='foodsight':
            pass
        elif p.parent.parts[-1]=='foodsight':
            p = p.parent
        else:
            while not (p.parts[-1]=='pipeline'):
                p = p.parent
            if p.parts[-1]== '/':
                raise Exception("Can't load config in util.load_config - are we in the pipeline?")
            # p is now the path that contains config load env
        config = __load_with_path(p)
    return config