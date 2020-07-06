""" Defines the configuration .ini files required by the Raspberry Pi Python
console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2020 Peter Davis

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

# Import required modules
from geopy          import distance as geopy
from packaging      import version
from pathlib        import Path
import configparser
import collections
import requests
import json
import math
import sys
import os

# Define wfpiconsole version number
Version = 'v3.6'

# Define required variables
TEMPEST       = False
INDOORAIR     = False
STATION       = None
OBSERVATION   = None
MAXRETRIES    = 3
NaN           = float('NaN')

# Determine hardware version
try:
    Hardware = os.popen('cat /proc/device-tree/model').read()
    if 'Raspberry Pi 4' in Hardware:
        Hardware = 'Pi4'
    elif 'Raspberry Pi 3' in Hardware:
        Hardware = 'Pi3'
    elif 'Raspberry Pi Model B' in Hardware:
        Hardware = 'PiB'
    else:
        Hardware = 'Other'
except:
    Hardware = 'Other'

def create():

    """ Generates a new user configuration file from the default configuration
        dictionary. Saves the new user configuration file to wfpiconsole.ini
    """

    # Load default configuration dictionary
    default = defaultConfig()

    # CONVERT DEFAULT CONFIGURATION DICTIONARY INTO .ini FILE
    # --------------------------------------------------------------------------
    # Print progress dialogue to screen
    print('')
    print('  ===================================================')
    print('  Starting wfpiconsole configuration wizard          ')
    print('  ===================================================')
    print('')
    print('  Required fields are marked with an asterix (*)     ')
    print('')

    # Open new user configuration file
    Config = configparser.ConfigParser(allow_no_value=True)
    Config.optionxform = str

    # Loop through all sections in default configuration dictionary
    for Section in default:

        # Add section to user configuration file
        Config.add_section(Section)

        # Add remaining sections to user configuration file
        for Key in default[Section]:
            if Key == 'Description':
                print(default[Section][Key])
                print('  ---------------------------------')
            else:
                writeConfigKey(Config,Section,Key,default[Section][Key])
        print('')

    # WRITES USER CONFIGURATION FILE TO wfpiconsole.ini
    # --------------------------------------------------------------------------
    with open('wfpiconsole.ini','w') as configfile:
        Config.write(configfile)

def update():

    """ Updates an existing user configuration file by comparing it against the
        default configuration dictionary. Saves the updated user configuration
        file to wfpiconsole.ini
    """

    # Load default configuration dictionary
    default = defaultConfig()
    defaultVersion = default['System']['Version']['Value']

    # Load current user configuration file
    currentConfig = configparser.ConfigParser(allow_no_value=True)
    currentConfig.optionxform = str
    currentConfig.read('wfpiconsole.ini')
    currentVersion = currentConfig['System']['Version']

    # Tweak current version
    if currentVersion == 'v3.51':
        currentVersion = 'v3.5.1'

    # Create new config parser object to hold updated user configuration file
    newConfig = configparser.ConfigParser(allow_no_value=True)
    newConfig.optionxform = str

    # CONVERT DEFAULT CONFIGURATION DICTIONARY INTO .ini FILE
    # --------------------------------------------------------------------------
    # Check if version numbers are different
    if version.parse(currentVersion) < version.parse(defaultVersion):

        # Print progress dialogue to screen
        print('')
        print('  ===================================================')
        print('  New version detected                               ')
        print('  Starting wfpiconsole configuration wizard          ')
        print('  ===================================================')
        print('')
        print('  Required fields are marked with an asterix (*)     ')
        print('')

        # Loop through all sections in default configuration dictionary. Take
        # existing key values from current configuration file
        for Section in default:
            Changes = False
            newConfig.add_section(Section)
            for Key in default[Section]:
                if Key == 'Description':
                    print(default[Section][Key])
                    print('  ---------------------------------')
                else:
                    if currentConfig.has_option(Section,Key):
                        copyConfigKey(newConfig,currentConfig,Section,Key,default[Section][Key])
                    if not currentConfig.has_option(Section,Key):
                        Changes = True
                        writeConfigKey(newConfig,Section,Key,default[Section][Key])
                    elif Key == 'Version':
                        Changes = True
                        newConfig.set(Section,Key,defaultVersion)
                        print('  Updating version number to: ' + defaultVersion)
            if not Changes:
                print('  No changes required')
            print('')

        # WRITE UPDATED USER .INI FILE TO DISK
        # ----------------------------------------------------------------------
        with open('wfpiconsole.ini','w') as configfile:
            newConfig.write(configfile)

def copyConfigKey(newConfig,currentConfig,Section,Key,keyDetails):

    # Define global variables
    global TEMPEST, INDOORAIR

    # Copy fixed key from default configuration
    if keyDetails['Type'] == 'fixed':
        Value = keyDetails['Value']

    # Copy key value from existing configuration. Ignore AIR/SKY device IDs if
    # switching to TEMPEST
    else:
        if (Key == 'SkyID' or Key == 'SkyHeight') and TEMPEST:
            Value = ''
        elif (Key == 'OutAirID' or Key == 'OutAirHeight') and TEMPEST:
            Value = ''
        else:
            Value = currentConfig[Section][Key]

    # Write key value to new configuration
    newConfig.set(Section,Key,str(Value))


def writeConfigKey(Config,Section,Key,keyDetails):

    """ Gets and writes the key value pair to the specified section of the
        station configuration file

    INPUTS
        Config              Station configuration
        Section             Section of station configuration containing key
                            value pair
        Key                 Name of key value pair
        keyDetails          Details (type/description) of key value pair

    """

    # Define required variables
    keyRequired = True

    # GET VALUE OF userInput KEY TYPE
    # --------------------------------------------------------------------------
    if keyDetails['Type'] in ['userInput']:

        # Define global variables
        global TEMPEST, INDOORAIR

        # Request user input to determine which devices are present
        if Key == 'TempestID':
            if queryUser('Do you own a TEMPEST?*',None):
                TEMPEST = True
            else:
                Value = ''
                keyRequired = False
        elif Key == 'InAirID':
            if queryUser('Do you own an Indoor AIR?*',None):
                INDOORAIR = True
            else:
                Value = ''
                keyRequired = False

        # Skip device ID keys for devices that are not present
        if Key == 'SkyID' and TEMPEST:
            Value = ''
            keyRequired = False
        elif Key == 'OutAirID' and TEMPEST:
            Value = ''
            keyRequired = False

        # userInput key required. Get value from user
        if keyRequired:
            while True:
                if keyDetails['State'] == 'required':
                    String = '  Please enter your ' + keyDetails['Desc'] + '*: '
                else:
                    String = '  Please enter your ' + keyDetails['Desc'] + ': '
                Value = input(String)

                # userInput key value is empty. Check if userInput key is
                # required
                if not Value and keyDetails['State'] == 'required':
                    print('    ' + keyDetails['Desc'] + ' cannot be empty. Please try again')
                    continue
                elif not Value and keyDetails['State'] == 'optional':
                    break

                # Check if userInput key value matches required format
                try:
                    Value = keyDetails['Format'](Value)
                    break
                except ValueError:
                    print('    ' + keyDetails['Desc'] + ' format is not valid. Please try again')

        # Write userInput Key value pair to configuration file
        Config.set(Section,Key,str(Value))

    # GET VALUE OF dependent KEY TYPE
    # --------------------------------------------------------------------------
    elif keyDetails['Type'] in ['dependent']:

        # Get dependent Key value
        if Key in ['BarometerMax']:
            Units = ['mb','hpa','inhg','mmhg']
            Max = ['1050','1050','31.0','788']
            Value = Max[Units.index(Config['Units']['Pressure'])]
        elif Key in ['BarometerMin']:
            Units = ['mb','hpa','inhg','mmhg']
            Min = ['950','950','28.0','713']
            Value = Min[Units.index(Config['Units']['Pressure'])]
        print('  Adding ' + keyDetails['Desc'] + ': ' + Value)

        # Write dependent Key value pair to configuration file
        Config.set(Section,Key,str(Value))

    # GET VALUE OF default OR fixed KEY TYPE
    # --------------------------------------------------------------------------
    elif keyDetails['Type'] in ['default','fixed']:

        # Get default or fixed Key value
        if Key in ['ExtremelyCold','FreezingCold','VeryCold','Cold','Mild','Warm','Hot','VeryHot']:
            if 'c' in Config['Units']['Temp']:
                Value = keyDetails['Value']
            elif 'f' in Config['Units']['Temp']:
                Value = str(int(float(keyDetails['Value'])*9/5 + 32))
        else:
            Value = keyDetails['Value']

        # Write default or fixed Key value pair to configuration file
        print('  Adding ' + keyDetails['Desc'] + ': ' + Value)
        Config.set(Section,Key,str(Value))

    # GET VALUE OF request KEY TYPE
    # --------------------------------------------------------------------------
    elif keyDetails['Type'] in ['request']:

        # Define global variables
        global STATION
        global OBSERVATION

        # Define local variables
        Value = ''

        # Get Station metadata from WeatherFlow API and validate Station ID
        RETRIES = 0
        if keyDetails['Source'] == 'station' and STATION is None:
            while True:
                Template = 'https://swd.weatherflow.com/swd/rest/stations/{}?api_key={}'
                URL = Template.format(Config['Station']['StationID'],Config['Keys']['WeatherFlow'])
                STATION = requests.get(URL).json()
                if 'status' in STATION:
                    if 'NOT FOUND' in STATION['status']['status_message']:
                        inputStr = '    Station not found. Please re-enter your Station ID*: '
                        while True:
                            ID = input(inputStr)
                            if not ID:
                                print('    Station ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                inputStr = '    Station ID not valid. Please re-enter your Station ID*: '
                        Config.set('Station','StationID',str(ID))
                    elif 'SUCCESS' in STATION['status']['status_message']:
                        break
                    else:
                        RETRIES += 1
                else:
                    RETRIES += 1
                if RETRIES >= MAXRETRIES:
                    sys.exit('\n    Error: unable to fetch station meta-data')

        # Get Observation metadata from WeatherFlow API
        RETRIES = 0
        if keyDetails['Source'] == 'observation' and OBSERVATION is None:
            while True:
                Template = 'https://swd.weatherflow.com/swd/rest/observations/station/{}?api_key={}'
                URL = Template.format(Config['Station']['StationID'],Config['Keys']['WeatherFlow'])
                OBSERVATION = requests.get(URL).json()
                if 'status' in STATION:
                    if 'SUCCESS' in STATION['status']['status_message']:
                        break
                    else:
                        RETRIES += 1
                else:
                    RETRIES += 1
                if RETRIES >= MAXRETRIES:
                    sys.exit('\n    Error: unable to fetch observation meta-data')

        # Validate TEMPEST device ID and get height above ground of TEMPEST
        if Section == 'Station':
            if Key == 'TempestHeight' and Config['Station']['TempestID']:
                while True:
                    for Device in STATION['stations'][0]['devices']:
                        if 'device_type' in Device:
                            if str(Device['device_id']) == Config['Station']['TempestID']:
                                if Device['device_type'] == 'ST':
                                    Value = Device['device_meta']['agl']
                    if not Value:
                        inputStr = '    TEMPEST not found. Please re-enter your TEMPEST device ID*: '
                        while True:
                            ID = input(inputStr)
                            if not ID:
                                print('    TEMPEST device ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                inputStr = '    TEMPEST device ID not valid. Please re-enter your TEMPEST device ID*: '
                        Config.set('Station','TempestID',str(ID))
                    else:
                        break

        # Validate AIR device ID and get height above ground of AIR
        if Section == 'Station':
            if Key == 'OutAirHeight' and Config['Station']['OutAirID']:
                while True:
                    for Device in STATION['stations'][0]['devices']:
                        if 'device_type' in Device:
                            if str(Device['device_id']) == Config['Station']['OutAirID']:
                                if Device['device_type'] == 'AR':
                                    Value = Device['device_meta']['agl']
                    if not Value:
                        inputStr = '    Outdoor AIR not found. Please re-enter your Outdoor AIR device ID*: '
                        while True:
                            ID = input(inputStr)
                            if not ID:
                                print('    Outdoor AIR device ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                inputStr = '    Outdoor AIR device ID not valid. Please re-enter your Outdoor AIR device ID*: '
                        Config.set('Station','OutAirID',str(ID))
                    else:
                        break

        # Validate SKY device ID and get height above ground of SKY
        if Section == 'Station':
            if Key == 'SkyHeight' and Config['Station']['SkyID']:
                while True:
                    for Device in STATION['stations'][0]['devices']:
                        if 'device_type' in Device:
                            if str(Device['device_id']) == Config['Station']['SkyID']:
                                if Device['device_type'] == 'SK':
                                    Value = Device['device_meta']['agl']
                    if not Value:
                        inputStr = '    SKY not found. Please re-enter your SKY device ID*: '
                        while True:
                            ID = input(inputStr)
                            if not ID:
                                print('    SKY device ID cannot be empty. Please try again')
                                continue
                            try:
                                ID = int(ID)
                                break
                            except ValueError:
                                inputStr = '    SKY device ID not valid. Please re-enter your SKY device ID*: '
                        Config.set('Station','SkyID',str(ID))
                    else:
                        break

        # Get station latitude/longitude, timezone, or name
        if Section == 'Station':
            if Key in ['Latitude','Longitude','Timezone','Name']:
                Value = STATION['stations'][0][Key.lower()]

        # Get station elevation
        if Section == 'Station':
            if Key == 'Elevation':
                Value = STATION['stations'][0]['station_meta']['elevation']

        # Get station units
        if Section in ['Units']:
            Value = OBSERVATION['station_units']['units_' + Key.lower()]

        # Write request Key value pair to configuration file
        print('  Adding ' + keyDetails['Desc'] + ': ' + str(Value))
        Config.set(Section,Key,str(Value))

def queryUser(Question,Default=None):

    """ Ask a yes/no question via raw_input() and return their answer.

    INPUTS
        Question                Query string presented to user
        Default                 Presumed answer if the user just hits <Enter>.
                                It must be "yes", "no" or None

    OUTPUT
        Valid                   True for "yes" or False for "no"
    """

    # Define valid reponses and prompt based on specified default answer
    valid = {'yes': True, 'y': True, 'ye': True, 'no': False, 'n': False}
    if Default is None:
        prompt = ' [y/n] '
    elif Default == 'yes':
        prompt = ' [Y/n] '
    elif Default == 'no':
        prompt = ' [y/N] '
    else:
        raise ValueError('invalid default answer: "%s"' % Default)

    # Display question to user
    while True:
        sys.stdout.write('  ' + Question + prompt)
        choice = input().lower()
        if Default is not None and choice == '':
            return valid[Default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write('    Please respond with "yes"/"no" or "y"/"n"\n')

def defaultConfig():

    """ Generates the default configuration required by the Raspberry Pi Python
        console for Weather Flow Smart Home Weather Stations.

    OUTPUT:
        Default         Default configuration required by PiConsole

    """

    # DEFINE DEFAULT CONFIGURATION SECTIONS, KEY NAMES, AND KEY DETAILS AS
    # ORDERED DICTS
    # --------------------------------------------------------------------------
    Default =                    collections.OrderedDict()
    Default['Keys'] =            collections.OrderedDict([('Description',    '  API keys'),
                                                          ('CheckWX',        {'Type': 'userInput', 'State': 'required', 'Format': str, 'Desc': 'CheckWX API Key',}),
                                                          ('WeatherFlow',    {'Type': 'fixed',     'Value': '146e4f2c-adec-4244-b711-1aeca8f46a48', 'Desc': 'WeatherFlow API Key'})])
    Default['Station'] =         collections.OrderedDict([('Description',    '  Station and device IDs'),
                                                          ('StationID',      {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'Station ID'}),
                                                          ('TempestID',      {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'TEMPEST device ID'}),
                                                          ('SkyID',          {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'SKY device ID'}),
                                                          ('OutAirID',       {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'outdoor AIR device ID'}),
                                                          ('InAirID',        {'Type': 'userInput', 'State': 'required', 'Format': int, 'Desc': 'indoor AIR device ID'}),
                                                          ('TempestHeight',  {'Type': 'request', 'Source': 'station', 'Desc': 'height of TEMPEST'}),
                                                          ('SkyHeight',      {'Type': 'request', 'Source': 'station', 'Desc': 'height of SKY'}),
                                                          ('OutAirHeight',   {'Type': 'request', 'Source': 'station', 'Desc': 'height of outdoor AIR'}),
                                                          ('Latitude',       {'Type': 'request', 'Source': 'station', 'Desc': 'station latitude'}),
                                                          ('Longitude',      {'Type': 'request', 'Source': 'station', 'Desc': 'station longitude'}),
                                                          ('Elevation',      {'Type': 'request', 'Source': 'station', 'Desc': 'station elevation'}),
                                                          ('Timezone',       {'Type': 'request', 'Source': 'station', 'Desc': 'station timezone'}),
                                                          ('Name',           {'Type': 'request', 'Source': 'station', 'Desc': 'station name'}),
                                                          ('IndoorBME280Corr', {'Type': 'default', 'Value': '2.00',  'Desc': 'Correction factor for optional BME280 sensor'})])
    Default['Units'] =           collections.OrderedDict([('Description',    '  Observation units'),
                                                          ('Temp',           {'Type': 'request', 'Source': 'observation', 'Desc': 'station temperature units'}),
                                                          ('Pressure',       {'Type': 'request', 'Source': 'observation', 'Desc': 'station pressure units'}),
                                                          ('Wind',           {'Type': 'request', 'Source': 'observation', 'Desc': 'station wind units'}),
                                                          ('Direction',      {'Type': 'request', 'Source': 'observation', 'Desc': 'station direction units'}),
                                                          ('Precip',         {'Type': 'request', 'Source': 'observation', 'Desc': 'station precipitation units'}),
                                                          ('Distance',       {'Type': 'request', 'Source': 'observation', 'Desc': 'station distance units'}),
                                                          ('Other',          {'Type': 'request', 'Source': 'observation', 'Desc': 'station other units'})])
    Default['Display'] =         collections.OrderedDict([('Description',    '  Display settings'),
                                                          ('TimeFormat',     {'Type': 'default', 'Value': '24 hr', 'Desc': 'time format'}),
                                                          ('DateFormat',     {'Type': 'default', 'Value': 'Mon, 01 Jan 0000', 'Desc': 'date format'}),
                                                          ('LightningPanel', {'Type': 'default', 'Value': '1',  'Desc': 'lightning panel toggle'}),
                                                          ('IndoorTemp',     {'Type': 'default', 'Value': '1',  'Desc': 'indoor temperature toggle'})])
    Default['FeelsLike'] =       collections.OrderedDict([('Description',    '  "Feels Like" temperature cut-offs'),
                                                          ('ExtremelyCold',  {'Type': 'default', 'Value': '-4', 'Desc': '"Feels extremely cold" cut-off temperature'}),
                                                          ('FreezingCold',   {'Type': 'default', 'Value': '0',  'Desc': '"Feels freezing cold" cut-off temperature'}),
                                                          ('VeryCold',       {'Type': 'default', 'Value': '4',  'Desc': '"Feels very cold" cut-off temperature'}),
                                                          ('Cold',           {'Type': 'default', 'Value': '9',  'Desc': '"Feels cold" cut-off temperature'}),
                                                          ('Mild',           {'Type': 'default', 'Value': '14', 'Desc': '"Feels mild" cut-off temperature'}),
                                                          ('Warm',           {'Type': 'default', 'Value': '18', 'Desc': '"Feels warm" cut-off temperature'}),
                                                          ('Hot',            {'Type': 'default', 'Value': '23', 'Desc': '"Feels hot" cut-off temperature'}),
                                                          ('VeryHot',        {'Type': 'default', 'Value': '28', 'Desc': '"Feels very hot" cut-off temperature'})])
    Default['PrimaryPanels'] =   collections.OrderedDict([('Description',    '  Primary panel layout'),
                                                          ('PanelOne',       {'Type': 'default', 'Value': 'Forecast',      'Desc':'Primary display for Panel One'}),
                                                          ('PanelTwo',       {'Type': 'default', 'Value': 'Temperature',   'Desc':'Primary display for Panel Two'}),
                                                          ('PanelThree',     {'Type': 'default', 'Value': 'WindSpeed',     'Desc':'Primary display for Panel Three'}),
                                                          ('PanelFour',      {'Type': 'default', 'Value': 'SunriseSunset', 'Desc':'Primary display for Panel Four'}),
                                                          ('PanelFive',      {'Type': 'default', 'Value': 'Rainfall',      'Desc':'Primary display for Panel Five'}),
                                                          ('PanelSix',       {'Type': 'default', 'Value': 'Barometer',     'Desc':'Primary display for Panel Six'})])
    Default['SecondaryPanels'] = collections.OrderedDict([('Description',    '  Secondary panel layout'),
                                                          ('PanelOne',       {'Type': 'default', 'Value': 'Sager',         'Desc':'Secondary display for Panel One'}),
                                                          ('PanelTwo',       {'Type': 'default', 'Value': '',              'Desc':'Secondary display for Panel Two'}),
                                                          ('PanelThree',     {'Type': 'default', 'Value': '',              'Desc':'Secondary display for Panel Three'}),
                                                          ('PanelFour',      {'Type': 'default', 'Value': 'MoonPhase',     'Desc':'Secondary display for Panel Four'}),
                                                          ('PanelFive',      {'Type': 'default', 'Value': '',              'Desc':'Secondary display for Panel Five'}),
                                                          ('PanelSix',       {'Type': 'default', 'Value': 'Lightning',     'Desc':'Secondary display for Panel Six'})])
    Default['System'] =          collections.OrderedDict([('Description',    '  System settings'),
                                                          ('BarometerMax',   {'Type': 'dependent', 'Desc': 'maximum barometer pressure'}),
                                                          ('BarometerMin',   {'Type': 'dependent', 'Desc': 'minimum barometer pressure'}),
                                                          ('Timeout',        {'Type': 'default',   'Value': '20',    'Desc': 'Timeout in seconds for API requests'}),
                                                          ('Hardware',       {'Type': 'default',   'Value': Hardware,'Desc': 'Hardware type'}),
                                                          ('Version',        {'Type': 'default',   'Value': Version, 'Desc': 'Version number'})])

    # Return default configuration
    return Default
