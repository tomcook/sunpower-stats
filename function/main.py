import requests
import json
import boto3
import datadog

secrets_client = boto3.client('secretsmanager')

secrets_raw = secrets_client.get_secret_value(
    SecretId=os.environ['SUNPOWER_STATS_SECRETS_ARN']
)

secrets = json.loads(secrets_raw['SecretString'])

dd_opts = {
    'api_key': secrets['DATADOG_API_KEY'],
    'app_key': secrets['DATADOG_APP_KEY']
}

sunpower_token = secrets['SUNPOWER_TOKEN']

dd_prefix = 'solar.'

datadog.initialize(**dd_opts)

def handle(event, context):

    current_production_url = "https://monitor.us.sunpower.com/CustomerPortal/CurrentPower/CurrentPower.svc/GetCurrentPower?id=%s" % (sunpower_token)
    realtime_net_display_url = "http://monitor.us.sunpower.com/CustomerPortal/SystemInfo/SystemInfo.svc/getRealTimeNetDisplay?id=%s" % (sunpower_token)
    per_module_stats_url = "http://monitor.us.sunpower.com/CustomerPortal/SystemInfo/SystemInfo.svc/getACPVModuleInfo?id=%s" % (sunpower_token)

    current_power_raw = requests.get(current_production_url).json()['Payload']
    address_id = current_power_raw['AddressId']
    last_timestamp = current_power_raw['SystemList'][0]['DateTimeReceived']

    # ------------------------------------------------------------------------

    energy_data_url = "https://monitor.us.sunpower.com/CustomerPortal/SystemInfo/SystemInfo.svc/getEnergyData?guid=%s&interval=minute&startDateTime=%s&endDateTime=%s" % (sunpower_token, last_timestamp, last_timestamp)

    energy_data = requests.get(energy_data_url).json()['Payload']['series']['data'][0]

    for k,v in energy_data.iteritems():

        if k == 'bdt':
            continue

        if v == None:
            v = 0

        datadog.api.Metric.send(metric="%soverall.%s" % (dd_prefix, k),
                                points=v,
                                tags=["AddressId:%s" % (address_id)])

    # ------------------------------------------------------------------------

    realtime_net_display = requests.get(realtime_net_display_url).json()['Payload']

    datadog.api.Metric.send(metric="%soverall.CurrentConsumption" % (dd_prefix),
                            points=float(realtime_net_display['CurrentConsumption']['value']),
                            tags=["AddressId:%s" % (address_id)])

    datadog.api.Metric.send(metric="%soverall.CurrentProduction" % (dd_prefix),
                            points=float(realtime_net_display['CurrentProduction']['value']),
                            tags=["AddressId:%s" % (address_id)])

    datadog.api.Metric.send(metric="%soverall.NamePlateValue" % (dd_prefix),
                            points=float(realtime_net_display['NamePlateValue']['value']),
                            tags=["AddressId:%s" % (address_id)])

    # ------------------------------------------------------------------------

    module_stats = requests.get(per_module_stats_url).json()['Payload']['ACPVModulePosition']

    for module in module_stats:

        datadog.api.Metric.send(metric="%smodule.generation" % (dd_prefix),
                                points=module['currentGeneration'],
                                tags=["AddressId:%s"    % (address_id),
                                    "ModuleID:%s"     % (module['ModuleID']),
                                    "SerialNumber:%s" % (module['SerialNumber'])])
