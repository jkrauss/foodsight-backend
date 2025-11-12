November '25 - making this public, maybe someone finds it useful. This was the backend/API of a machine-learning startup we tried to pull of. The purpose was to serve bakeries with sales predictions so they can optimize their stocklevels

# Backend

## Startup
- To start the webserver and in parallel schedule the pipeline  do `python -m startup` .
- To start the webserver only run `uvicorn main:app`
- To run the pipeline 'unscheduled' the easiest is to run the scripts in order e.g. `python -m 0_load_date_dimension`

## Data-pipeline

The data-folder has several subfolders, that represent different stages in the data transformation-pipeline. For every stage there's also one or more corresponding jupyter-notebooks. 
- e.g. 0_load_weather_history loads data from external sources and writes to the 0_raw directory
- 2_prepare_training_data reads from layers below and writes to the 2_pre_train directory
- The stages are to be run in order e.g. first complete all that start with 0_ then 1_ ...
- The notebooks are 'paired' with .py-files, using jupytext. Only the .py-files go into the git-repository
  - use sync_notebooks.sh to sync
  - each script is wrapped in a run()-method, and these are used to run the pipeline in production

- For the start I used an open dataset of orange-juice-sales:
  - Description of the orange-juice data / columns can be found here: https://rdrr.io/cran/bayesm/man/orangeJuice.html

## API

The API is built using the fantastic fastapi-package. The development server can be started with `uvicorn main:app --reload`

# Frontend

## fastapi-svelte

Simple Combination of FastAPI and Svelte.

### Setup Instructions:

1. Clone this Repo
2. ```pip install -r requirements.txt``` to install python dependencies.
3. Run ```npx degit sveltejs/template client``` inside root directory to create Svelte app inside ```client``` directory.
4. Inside ```client``` directory run ```npm install```

### Local Development:

**Build Svelte app and watch for changes:**```npm run dev``` (run inside client folder)

**Run Uvicorn server for FastAPI app with hotreloading:** ```uvicorn main:app --reload```
