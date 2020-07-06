""" Returns the WeatherFlow forecast variables required by the Raspberry Pi
Python console for WeatherFlow Tempest and Smart Home Weather stations.
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
from datetime   import datetime, date, timedelta, time
from lib        import observationFormat  as observation
from lib        import derivedVariables   as derive
from lib        import requestAPI
from kivy.clock import Clock
import requests
import bisect
import pytz
import time
import calendar

def Download(app):
    metData = app.MetData;
    Config = app.config;

    """ Download the weather forecast data using the WeatherFlow BetterForecast
    API

    INPUTS:
        metData             Dictionary holding weather forecast data
        Config              Station configuration

    OUTPUT:
        metData             Dictionary holding weather forecast data
    """

    # Download latest three-hourly forecast
    Data = requestAPI.forecast.weatherFlow(Config)

    # Verify API response and extract forecast
    if requestAPI.forecast.verifyResponse(Data,'forecast'):
        metData['Dict'] = Data.json()['forecast']
    else:
        Clock.schedule_once(lambda dt: Download(app), 600)
        if not 'Dict' in metData:
            metData['Dict'] = {}
    Extract(app)
    ExtractDaily(app)

    # Return metData dictionary
    return metData


def Extract(app):
    metData = app.MetData
    Config = app.config
    """ Parse the weather forecast from DarkSky

    INPUTS:
        metData             Dictionary holding weather forecast data
        Config              Station configuration

    OUTPUT:
        metData             Dictionary holding weather forecast data
    """

    # Get current time in station time zone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)

    # Extract all forecast data from WeatherFlow JSON file. If  forecast is
    # unavailable, set forecast variables to blank and indicate to user that
    # forecast is unavailable
    Tz = pytz.timezone(Config['Station']['Timezone'])
    try:
        wfDict = metData['Dict']['hourly']
        wfDayDict = metData['Dict']['daily'][0]
        metData['stationOnline'] = metData['Dict']['station']['is_station_online']
        metData['stationUsed'] = metData['Dict']['station']['includes_tempest']
    except KeyError:
        metData['Time']    = Now
        metData['Temp']    = '--'
        metData['WindDir'] = '--'
        metData['WindSpd'] = '--'
        metData['Weather'] = 'ForecastUnavailable'
        metData['Precip']  = '--'
        metData['Valid']   = '--'

        # Attempt to download forecast again in 10 minutes and return
        # metData dictionary
        Clock.schedule_once(lambda dt: Download(app), 600)
        return metData

    # Extract 'valid from' time of all available hourly forecasts, and
    # retrieve forecast for the current hourly period
    Times = list(item['time'] for item in wfDict)
    wfHourDict = wfDict[bisect.bisect(Times,int(time.time()))-1]

    # Extract 'Issued' and 'Valid' times
    Issued = Times[0]
    Valid = Times[bisect.bisect(Times,int(time.time()))]
    Issued = datetime.fromtimestamp(Issued,pytz.utc).astimezone(Tz)
    Valid = datetime.fromtimestamp(Valid,pytz.utc).astimezone(Tz)

    # Extract weather variables from WeatherFlow forecast
    Temp    = [wfHourDict['air_temperature'], 'c']
    TempMax = [wfDayDict['air_temp_high'], 'c']
    TempMin = [wfDayDict['air_temp_low'], 'c']
    WindSpd = [wfHourDict['wind_avg'], 'mps']
    WindDir = [wfHourDict['wind_direction'], 'degrees']
    Precip  = [wfHourDict['precip_probability'], '%']
    Weather =  wfHourDict['icon']

    # Convert forecast units as required
    Temp = observation.Units(Temp,Config['Units']['Temp'])
    TempMax = observation.Units(TempMax,Config['Units']['Temp'])
    TempMin = observation.Units(TempMin,Config['Units']['Temp'])
    WindSpd = observation.Units(WindSpd,Config['Units']['Wind'])

    # Define and format labels
    metData['Time']    = Now
    metData['Issued']  = datetime.strftime(Issued, '%H:%M')
    metData['Valid']   = datetime.strftime(Valid, '%H:%M')
    metData['Temp']    = ['{:.1f}'.format(Temp[0]), Temp[1]]
    metData['TempMax']    = ['{:.1f}'.format(TempMax[0]), TempMax[1]]
    metData['TempMin']    = ['{:.1f}'.format(TempMin[0]), TempMin[1]]
    metData['WindDir'] = derive.CardinalWindDirection(WindDir)[2]
    metData['WindSpd'] = ['{:.0f}'.format(WindSpd[0]), WindSpd[1]]
    metData['Precip']  = '{:.0f}'.format(Precip[0])

    # Define weather icon
    if Weather == 'clear-day':
        metData['Weather'] = '1'
    elif Weather == 'clear-night':
        metData['Weather'] = '0'
    elif Weather == 'rain':
        metData['Weather'] = '12'
    elif Weather == 'snow':
        metData['Weather'] = '27'
    elif Weather == 'sleet':
        metData['Weather'] = '18'
    elif Weather == 'wind':
        metData['Weather'] = 'wind'
    elif Weather == 'fog':
        metData['Weather'] = '6'
    elif Weather == 'cloudy':
        metData['Weather'] = '7'
    elif Weather == 'partly-cloudy-day':
        metData['Weather'] = '3'
    elif Weather == 'partly-cloudy-night':
        metData['Weather'] = '2'
    else:
        metData['Weather'] = 'ForecastUnavailable'

    # Return metData dictionary
    return metData

def ExtractDaily(app):
    metData = app.MetData
    dailyForecast = app.DailyForecast
    Config = app.config
    """
    INPUTS:
        metData             Dictionary holding weather forecast data
        dailyForecast       screen with array of panels
        Config              Station configuration
    """

    # Get current time in station time zone
    Tz = pytz.timezone(Config['Station']['Timezone'])
    Now = datetime.now(pytz.utc).astimezone(Tz)
    weekdays = [ 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun' ]

    for i in range(len(dailyForecast.panels)):
        d = {}
        try:
            wfDayDict = metData['Dict']['daily'][i]

            # Extract weather variables from WeatherFlow forecast
            date    = "%02d/%02d" % (wfDayDict['month_num'], wfDayDict['day_num'])
            tempMax = [wfDayDict['air_temp_high'], 'c']
            tempMin = [wfDayDict['air_temp_low'], 'c']
            precip  = [wfDayDict['precip_probability'], '%']
            weather =  wfDayDict['icon']
            dt = datetime.fromtimestamp(wfDayDict['sunrise'], Tz)
            weekday = calendar.weekday(dt.year, wfDayDict['month_num'], wfDayDict['day_num'])
        except IndexError:
            date    = '0/0'
            tempMax = [ 0, 'c']
            tempMin = [ 0, 'c']
            precip  = [ 0, '%']
            weather = 'XX'
            weekday = 0
        except KeyError:
            date    = '0/0'
            tempMax = [ 0, 'c']
            tempMin = [ 0, 'c']
            precip  = [ 0, '%']
            weather = 'XX'
            weekday = 0

        # Convert forecast units as required
        tempMax = observation.Units(tempMax, Config['Units']['Temp'])
        tempMin = observation.Units(tempMin, Config['Units']['Temp'])

        dailyForecast.panels[i].date = date
        dailyForecast.panels[i].tempMax = ['{:.0f}'.format(tempMax[0]), tempMax[1]]
        dailyForecast.panels[i].tempMin = ['{:.0f}'.format(tempMin[0]), tempMin[1]]
        dailyForecast.panels[i].precip =  ['{:.0f}'.format(precip[0]), ' %']
        dailyForecast.panels[i].weekday = weekdays[weekday]

        # Define weather icon
        if weather == 'clear-day':
            dailyForecast.panels[i].weather = '1'
        elif weather == 'clear-night':
            dailyForecast.panels[i].weather = '0'
        elif weather == 'rain':
            dailyForecast.panels[i].weather = '12'
        elif weather == 'snow':
            dailyForecast.panels[i].weather = '27'
        elif weather == 'sleet':
            dailyForecast.panels[i].weather = '18'
        elif weather == 'wind':
            dailyForecast.panels[i].weather = 'wind'
        elif weather == 'fog':
            dailyForecast.panels[i].weather = '6'
        elif weather == 'cloudy':
            dailyForecast.panels[i].weather = '7'
        elif weather == 'partly-cloudy-day':
            dailyForecast.panels[i].weather = '3'
        elif weather == 'partly-cloudy-night':
            dailyForecast.panels[i].weather = '2'
        else:
            dailyForecast.panels[i].weather = 'ForecastUnavailable'

