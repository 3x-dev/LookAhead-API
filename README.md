# Lookahead API

## Local setup

In order to run the API locally, you need to have python 3.11 or above installed.

There is a one time setup required to have the things going.

> Note: If you're on MacOS or Linux use `python3` instead of `python`

Run `python -m venv venv`

Activate venv (This step is required every time you open new terminal)

For windows -> `source venv/Scripts/activate`
For MacOS/Linux -> `source venv/bin/activate`

Then, install the dependencies (this is required only once unless you have added a new dependency)

`pip install -r requirements.txt`

Now in order to run the api locally -> `uvicorn main:app --reload --port 8080`

## Google Cloud

The api is deployed to google cloud run, thus you need to have google cloud cli installed on your computer. The steps to install it can be found in official google docs.

After installing google cloud cli, All you need to do, In order to deploy the code to cloud run is ->

`chmod +x ./deploy.sh` (One time setup, make the script executable)

Subsequently, to deploy, just run ->

`./deploy.sh`

You can read the `deploy.sh` file, to know what it does under the hood. (No black magic!)

## Tests

Tests are written using `pytest` thus, in order to run the tests -> `pytest -s -p no:warnings`
