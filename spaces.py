import boto3
import botocore.exceptions
import os
import json


def upload_file(file_name: str):
    """Upload a file to the S3 bucket

    :param file_name: File to upload
    :return: True if file was uploaded, else False
    """

    # use filename as object_name
    object_name = os.path.basename(file_name)

    # create client
    session = boto3.session.Session()
    client = session.client('s3',
                            region_name='us-east-1',  # is mainly ignored but validated by boto3
                            endpoint_url=os.getenv('SPACES_URL'),
                            aws_access_key_id=os.getenv('SPACES_KEY'),
                            aws_secret_access_key=os.getenv('SPACES_SECRET'))

    # Upload the file
    try:
        client.upload_file(file_name, os.getenv('SPACES_BUCKET_NAME'), object_name)
    except botocore.exceptions.ClientError as e:
        print(e)
        return False
    return True


def download_file(file_name: str):
    """Download a file from the S3 bucket

    :param file_name: File to upload
    :return: True if file was uploaded, else False
    """

    # use filename as object_name
    object_name = os.path.basename(file_name)

    # create client
    session = boto3.session.Session()
    client = session.client('s3',
                            region_name='us-east-1',  # is mainly ignored but validated by boto3
                            endpoint_url=os.getenv('SPACES_URL'),
                            aws_access_key_id=os.getenv('SPACES_KEY'),
                            aws_secret_access_key=os.getenv('SPACES_SECRET'))

    # Upload the file
    try:
        client.download_file(os.getenv('SPACES_BUCKET_NAME'), object_name, file_name)
    except botocore.exceptions.ClientError as e:
        print(e)
        return False
    return True


class SpaceDict(object):
    """
    Class to read and write to dict/json that is in the S3 bucket - batteries included (context manager)
    Does only work if file already exists in S3 bucket
    """

    def __init__(self, config_file: str):
        """
        Constructor
        :param config_file: The name of the config file in the S3 bucket
        """
        if download_file(config_file):
            self.file_obj = json.load(open(config_file))
        else:
            self.file_obj = {}
        self.file_path = config_file

    def __enter__(self):
        return self.file_obj

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            json.dump(self.file_obj, open(self.file_path, 'w'))
            try:
                upload_file(self.file_path)
            except Exception as e:
                print('Error uploading config file', e)
        else:
            print('Error: {}'.format(exc_val))
            return False


def recalculate_forecast(customer_id: str):
    """
    Recalculate the forecast for a user
    :param customer_id: The id of the customer
    :return: The forecast
    """

    print('recalculating the forecast...')
    with SpaceDict('./config.json') as config:
        returns_current = config["customers"][customer_id]["returns_current"]
        sales_price_cost_share = config["customers"][customer_id]["sales_price_cost_share"]
    print('returns_current: {}'.format(returns_current))
    print('sales_price_cost_share: {}'.format(sales_price_cost_share))
    with SpaceDict(f'./forecast_{customer_id}.json') as forecast:
        for store_id in forecast.keys():
            store_fc = forecast.get(store_id)
            # For key in store_fc, for each donut_data in store_fc[key], calculate the forecast
            for tshirt_size in store_fc.keys():
                donut_data = store_fc[tshirt_size]['donut_data']
                donut_data['returns_current'] = returns_current*30.417
                donut_data['returns_savings'] = donut_data['returns_current'] - donut_data['above']
                # rename above to 'returns_remaining'
                donut_data['returns_remaining'] = donut_data['above']

                donut_data['profits_current'] = donut_data['weekly_revenue']*4.333
                donut_data['profits_lost'] = donut_data['below']  # *4.333
                donut_data['profits_remaining'] = donut_data['profits_current'] - donut_data['profits_lost']

                # calculate return delivery fields as cost only
                donut_data['returns_current'] *= sales_price_cost_share
                donut_data['returns_savings'] *= sales_price_cost_share
                donut_data['returns_remaining'] *= sales_price_cost_share
                
                # calculate mohtly profits as profits only
                donut_data['profits_current'] *= (1 - sales_price_cost_share)
                donut_data['profits_lost'] *= (1 - sales_price_cost_share)
                donut_data['profits_remaining'] *= (1 - sales_price_cost_share)

                if donut_data['returns_savings'] < 0:
                    # we save less than nothing, but negative values can't be shown in the donut-chart
                    donut_data['returns_savings'] = 0

                # write back to store_fc
                store_fc[tshirt_size]['donut_data'] = donut_data
            forecast[store_id] = store_fc
        return forecast
