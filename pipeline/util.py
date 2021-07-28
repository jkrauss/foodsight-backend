import pathlib

import dotenv
import toml

def load_config():
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

    # load env vars
    dotenv.load_dotenv(p/'.env')

    # load customer specific config
    config = toml.load(p/'customer.toml')
    return config