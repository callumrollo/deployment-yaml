import yaml
from pathlib import Path

with open(Path("/home/callum/Documents/community/ocean-gliders-format-vocabularies/yaml/validated_yaml/og1_sensors.yaml")) as fin:
    sensors = yaml.safe_load(fin)

sensor_model_conversion = {
    'Nortek AD2CP': 'Nortek Glider1000 AD2CP Acoustic Doppler Current Profiler',
    'Biospherical MPE-PAR': 'Biospherical Instruments PAR sensor (unspecified model)',
    'hello': 'Franatech METS Methane Sensor',
    'JFE Advantech AROD_FT': 'JFE Advantech Rinko FT ARO-FT oxygen sensor',
    'hello': 'Nortek Glider1000 AD2CP Acoustic Doppler Current Profiler',
    'hello': 'RBR Coda T.ODO Temperature and Dissolved Oxygen Sensor',
    'RBR legato CTD': 'RBR Legato3 CTD',
    'hello': 'RBR tridente scattering fluorescence sensor',
    'hello': 'Rockland Scientific MicroRider-1000 turbulence microstructure profiler',
    'hello': 'Satlantic {Sea-Bird} OCR-504 multispectral radiometer',
    'hello': 'Satlantic {Sea-Bird} Submersible Ultraviolet Nitrate Analyser V2 (SUNA V2) nutrient analyser series',
    'hello': 'Sea-Bird Slocum Glider Payload {GPCTD} CTD',
    'hello': 'WET Labs {Sea-Bird WETLabs} ECO Puck FLNTU-SLC fluorescence turbidity sensor',
    'Wetlabs FLBBPC': 'WET Labs {Sea-Bird WETLabs} ECO Puck Triplet FLBBPC scattering fluorescence sensor',
    'hello': 'WET Labs {Sea-Bird WETLabs} ECO Puck Triplet FLBBCD-SLC scattering fluorescence sensor',
    'hello': 'WET Labs {Sea-Bird WETLabs} SeaOWL UV-A Sea Oil-in-Water Locator',
}


def convert_devices(devices):
    og1_devices = {}
    for name, device in devices.items():
        sensor_model = sensor_model_conversion[device['make_model']]
        sensor_dict = sensors[sensor_model]
        
        sensor_type_cf = sensor_dict['sensor_type'].upper().replace(' ', '_').replace('-', '_')
        serial = device['sensor_serial_number']
        sensor_dict['sensor_serial_number'] = serial
        sensor_dict['sensor_calibration_date'] = device['sensor_calibration_date']
        if 'calibration_parameters' in device.keys():
            sensor_dict['calibration_parameters'] = str(device['calibration_parameters'])
        device_name = f"SENSOR_{sensor_type_cf}_{serial}"
        og1_devices[device_name] = sensor_dict

    return og1_devices

with open(Path("/home/callum/Documents/community/ocean-gliders-format-vocabularies/yaml/validated_yaml/og1_variables.yaml")) as fin:
    og1_variables = yaml.safe_load(fin)

sensor_variables = {
    'SeaExplorer': {
        'TIME': 'time',
        'LATITUDE': 'NAV_LATITUDE',
        'LONGITUDE': 'NAV_LONGITUDE',
        'NAV_RESOURCE': 'NAV_RESOURCE',
        'DIVE_NUMBER': 'fnum',

    },
    'RBR Legato3 CTD': {
        'PRES': 'LEGATO_PRESSURE',
        'TEMP': 'LEGATO_TEMPERATURE',
        'CNDC': 'LEGATO_CONDUCTIVITY',
    },
    'JFE Advantech Rinko FT ARO-FT oxygen sensor': {
        'DOXY': 'AROD_FT_DO',
        'TEMPDOXY': 'AROD_FT_TEMP',
    },
    'Nortek Glider1000 AD2CP Acoustic Doppler Current Profiler': {
        'AD2CP_HEADING': 'AD2CP_HEADING',
        'AD2CP_ROLL': 'AD2CP_ROLL',
        'AD2CP_PITCH': 'AD2CP_PITCH',
      #  'AD2CP_TIME': 'AD2CP_TIME',
    },
    'WET Labs {Sea-Bird WETLabs} ECO Puck Triplet FLBBPC scattering fluorescence sensor': {
        'CHLA': 'FLBBPC_CHL_SCALED',
        'FLUOCHLA': 'FLBBPC_CHL_COUNT',
        'PHYCOCYANIN': 'FLBBPC_PC_SCALED',
        #'FLUOPHYCOCYANIN': 'FLBBPC_PC_COUNT',
        'BBP700': 'FLBBPC_BB_700_SCALED',
        'RBBP700': 'FLBBPC_BB_700_COUNT',
    },
    'Biospherical Instruments PAR sensor (unspecified model)': {
        'DPAR': 'MPE-PAR_IRRADIANCE',
    },

}

def add_variables(devices):
    variables = {}
    variables['timebase'] = {'source': 'NAV_LATITUDE'}
    keep_vars = []
    devices_to_add = [device['long_name'] for device in devices.values()]
    devices_to_add.append('SeaExplorer')
    for device_name in devices_to_add:
        if device_name not in sensor_variables.keys():
            print("oh no", device_name)
            continue
        device_variables = sensor_variables[device_name]
        for var_name, source in device_variables.items():
            variable_dict = og1_variables[var_name]
            variable_dict['source'] = source
            if var_name in ['LATITUDE', 'LONGITUDE']:
                variable_dict['conversion'] = 'nmea2deg'
            variables[var_name] = variable_dict
        if device_name not in ['SeaExplorer']:
            if var_name == 'CNDC':
                var_name = 'conductivity'
            keep_vars.append(var_name)
    variables['keep_variables'] = keep_vars
    return variables

def convert_to_og1(yaml_path):
    yaml_out_dir = Path('og1')
    yaml_name = yaml_path.name
    yaml_out = yaml_out_dir / yaml_name.replace('.yml', '.yaml')
    with open('yaml_components/global_metadata.yaml') as fin:
        meta = yaml.safe_load(fin)['metadata']
    out = {}
    platform_deployment_id = yaml_name.split('.')[0]
    platform_serial, deployment_number = yaml_name.split('.')[0].split('_M')
    meta['deployment_id'] = int(deployment_number)
    meta['platform_serial_number'] = platform_serial

    # add platform meta
    with open(Path("yaml_components") / "platform" / f"{platform_serial}.yaml") as fin:
        platform_meta = yaml.safe_load(fin)
    meta = meta | platform_meta

    # add mission meta
    with open(Path("yaml_components") / "mission" / f"{platform_deployment_id}.yaml") as fin:
        mission_meta = yaml.safe_load(fin)
    meta = meta | mission_meta['metadata']
    out['metadata'] = meta

    # convert and add devices
    original_devices = mission_meta['platform_devices']
    og1_devices = convert_devices(original_devices)
    out['glider_devices'] = og1_devices

    # determine variables to add and add them
    variables = add_variables(og1_devices)
    out['netcdf_variables'] = variables

    # add pilot QC if present
    if 'qc' in mission_meta.keys():
        out['qc'] = mission_meta['qc']

    # any special exceptions etc.

    with open(yaml_out, "w") as fout:
        yaml.dump(out, fout)

def convert_all_yaml():
    yaml_files = list(Path("mission_yaml").glob("*.yml"))
    yaml_files.sort()
    for yml in yaml_files:
        convert_to_og1(yml)

if __name__ == '__main__':
    convert_to_og1(Path('mission_yaml/SEA045_M79.yml'))
