import datetime
import yaml
import pandas as pd
import os
from pathlib import Path
from coefficients import arod_coefficients, glider_missions_affected

df_cal = pd.read_csv('new_cal.csv')
df_comments = pd.read_csv('piloting_comments.csv')
df_missions = pd.read_csv('https://erddap.observations.voiceoftheocean.org/erddap/tabledap/meta_users_table.csv')
expected_failures = [(70, 29), (57, 58), (57, 75)]
import sys

sys.path.append("/home/callum/Documents/data-flow/raw-to-nc/deployment-yaml")
from yaml_checker import expected_units


def correct_yaml(yaml_path):
    with open(yaml_path) as fin:
        deployment = yaml.safe_load(fin)
    meta = deployment['metadata']
    df_glider = df_missions[df_missions['glider_serial'] == f"SEA{meta['glider_serial'].zfill(3)}"]
    mission = df_glider[df_glider['deployment_id'] == int(meta['deployment_id'])]
    if mission.empty:
        if (int(meta['glider_serial']), int(meta['deployment_id'])) in expected_failures:
            return
        print(f"fail SEA{meta['glider_serial']} M{meta['deployment_id']} ")
        return
    start = str(mission['deployment_start'].values[0])[:10]
    devices = deployment['glider_devices']
    for device_name, cal_dict in devices.items():
        if cal_dict['model'] not in df_cal.model.values:
            continue
        df_model = df_cal[df_cal['model'] == cal_dict['model']]
        try:
            serial = str(int(cal_dict['serial']))
        except ValueError:
            serial = cal_dict['serial']
        # fix for incorrect serial number
        if serial == '2110556':
            serial = '210556'
            cal_dict['serial'] = serial
        df_serial = df_model[df_model['serial'] == serial]
        df_serial = df_serial.sort_values('calibration_date')
        if cal_dict['calibration_date'] in df_serial['calibration_date'].values:
            continue
        df_pre_deployment_cals = df_serial[df_serial['calibration_date'] < start]
        new_cal_date = df_pre_deployment_cals['calibration_date'].values[-1]
        old_cal_date = cal_dict['calibration_date']
        time_diff = (datetime.datetime.strptime(new_cal_date, '%Y-%m-%d') - datetime.datetime.strptime(old_cal_date,
                                                                                                       '%Y-%m-%d')).days
        # fix the calibration date
        deployment['glider_devices'][device_name]['calibration_date'] = new_cal_date
        # Don't warn if time difference is small
        if abs(time_diff) < 30:
            continue
        # Don't warn if calibration month-days are just switched american style
        if old_cal_date == new_cal_date[:5] + new_cal_date[8:] + new_cal_date[4:7]:
            continue
        print(
            f"CORRECTION {old_cal_date} >> {new_cal_date}. {yaml_path.name.split('.')[0]} {cal_dict['model']} {serial}. {time_diff} days ")
    df_glider_comment = df_comments[df_comments['Glider'] == f"SEA{meta['glider_serial'].zfill(3)}"]
    df_mission_comment = df_glider_comment[df_glider_comment['Mission'] == f"M{meta['deployment_id']}"]
    if df_mission_comment.empty:
        print(f"no comment found for {yaml_path.name}")
    if not df_mission_comment.empty:
        comment = df_mission_comment['Comments'].values[0]
        try:
            comment = comment.replace('\n', '. ')
        except:
            print(f'failed to strip comment: {yaml_path} {comment}')
        deployment['metadata']['comment'] = comment
    if 'qc' in deployment:
        if 'cdom' in deployment['qc']:
            if 'Previous deployments with this sensor showed a temporal decrease in CDOM' in deployment['qc']['cdom'][
                'comment']:
                deployment['qc'].pop('cdom')
            if 'Previous deployments with this sensor showed a temporal decrease in CDOM' in \
                    deployment['qc']['cdom_raw']['comment']:
                deployment['qc'].pop('cdom_raw')
    if 'qc' in deployment:
        if not deployment['qc']:
            deployment.pop('qc')

    with open(yaml_path, "w") as fout:
        yaml.dump(deployment, fout, sort_keys=False)


def correct_units(yaml_path):
    with open(yaml_path) as fin:
        deployment = yaml.safe_load(fin)

    variables = deployment['netcdf_variables']
    for key, val in variables.items():
        if key in ['keep_variables', 'timebase', 'time', 'ad2cp_time']:
            continue
        source = val['source']
        if 'units' not in val.keys():
            print(f"no units for {key}")
            continue
        unit = val['units']
        if source not in expected_units.keys():
            print(f"no unit for {yaml_path}: {source}")
            continue
        if expected_units[source] != unit:
            print(f"bad unit {source}: {unit}")
            deployment['netcdf_variables'][key]['units'] = expected_units[source]
    with open(yaml_path, "w") as fout:
        yaml.dump(deployment, fout, sort_keys=False)


def zero_pad(yaml_path):
    with open(yaml_path) as fin:
        deployment = yaml.safe_load(fin)
    if 'glider_serial' not in deployment['metadata'].keys():
        return
    glider_num = deployment['metadata']['glider_serial']
    if len(glider_num) > 4:
        platform_serial = glider_num
    else:
        platform_serial = f"SEA{glider_num.zfill(3)}"
    deployment['metadata']['platform_serial'] = platform_serial
    deployment['metadata'].pop('glider_serial')
    with open(yaml_path, "w") as fout:
        yaml.dump(deployment, fout, sort_keys=False)
    yaml_parts = list(yaml_path.parts)
    yaml_parts[-1] = f"{platform_serial}_M{deployment['metadata']['deployment_id']}.yml"
    os.rename(yaml_path, Path("/".join(yaml_parts)))


def add_oxygen_calibrations(yaml_path):
    """
    This function is only meant to be run once, to add oxygen calibration parameters to a subset of missions
    Parameters
    ----------
    yaml_path

    Returns
    -------

    """

    with open(yaml_path) as fin:
        deployment = yaml.safe_load(fin)
    meta = deployment['metadata']
    glidermission = f"{meta['platform_serial']}_M{meta['deployment_id']}"
    if glidermission not in glider_missions_affected.keys():
        return
    coefficients = glider_missions_affected[glidermission]
    devices = deployment['glider_devices']
    if 'oxygen' not in devices.keys():
        return
    if devices['oxygen']['model'].replace(' ', '') != 'AROD-FT':
        return
    if 'calibration_date' in coefficients.keys():
        coefficients.pop('calibration_date')
    devices['oxygen']['calibration_parameters'] = coefficients
    print(f"adding oxygen calibration to {glidermission}")
    with open(yaml_path, "w") as fout:
        yaml.dump(deployment, fout, sort_keys=False)


def add_oxygen_vars(yaml_path):
    """
    This function adds AROD calibrations parameters and oxygen raw count variables to all missions that
    should have them. The list of missions was made by searching for AROD_FT_DO_AN in datafiles
    Parameters
    ----------
    yaml_path

    Returns
    -------

    """
    glider_mission = yaml_path.name.split('.')[0]
    oxygen_ad_missions = ['SEA044_M106',
                          'SEA056_M80',
                          'SEA056_M82',
                          'SEA056_M83',
                          'SEA063_M88',
                          'SEA067_M68',
                          'SEA067_M70',
                          'SEA067_M72',
                          'SEA067_M73',
                          'SEA067_M75',
                          'SEA068_M40',
                          'SEA068_M41',
                          'SEA069_M44',
                          'SEA069_M46',
                          'SEA069_M48',
                          'SEA076_M34',
                          'SEA076_M36',
                          'SEA076_M37',
                          'SEA076_M38',
                          'SEA077_M41',
                          'SEA077_M44',
                          'SEA078_M33',
                          'SEA078_M35',
                          'SEA078_M36',
                          'SEA078_M38',
                          'SEA079_M34',
                          ]

    if glider_mission not in oxygen_ad_missions:
        return

    print(f"adding oxygen vars to {glider_mission}")
    with open(yaml_path) as fin:
        deployment = yaml.safe_load(fin)
    deployment['netcdf_variables']['oxygen_ad_counts'] = {'source': 'AROD_FT_DO_AN',
                                                          'long_name': 'oxygen sensor raw analogue counts',
                                                          'standard_name': 'oxygen_sensor_ad_counts',
                                                          'units': 'counts',
                                                          'coordinates': 'time depth latitude longitude',
                                                          'instrument': 'instrument_phosphorescence',
                                                          'observation_type': 'measured'}

    deployment['netcdf_variables']['oxygen_led_counts'] = {'source': 'AROD_FT_LED',
                                                          'long_name': 'oxygen sensor LED counts',
                                                          'standard_name': 'oxygen_sensor_led_value',
                                                          'units': 'counts',
                                                          'coordinates': 'time depth latitude longitude',
                                                          'instrument': 'instrument_phosphorescence',
                                                          'observation_type': 'measured'}
    devices = deployment['glider_devices']
    serial = str(devices['oxygen']['serial']).zfill(4)
    coefficients = arod_coefficients[serial]
    if 'calibration_date' in coefficients.keys():
        coefficients.pop('calibration_date')
    devices['oxygen']['calibration_parameters'] = coefficients
    if 'qc' in deployment.keys():
        if 'oxygen_concentration' in deployment['qc'].keys():
            print("popping")
            deployment['qc'].pop('oxygen_concentration')
            if not deployment['qc']:
                deployment.pop('qc')

    with open(yaml_path, "w") as fout:
        yaml.dump(deployment, fout, sort_keys=False)
    return


if __name__ == '__main__':
    yaml_files = list(Path("../mission_yaml").glob("*.yml"))
    yaml_files.sort()
    for yml in yaml_files:
        add_oxygen_calibrations(yml)
        add_oxygen_vars(yml)
