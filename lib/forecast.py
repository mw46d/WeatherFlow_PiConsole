""" Returns the WeatherFlow forecast variables required by the Raspberry Pi
Python console for WeatherFlow Tempest and Smart Home Weather stations.
Copyright (C) 2018-2021 Peter Davis

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

# Import required library modules
from lib        import observationFormat  as observation
from lib        import derivedVariables   as derive
from lib        import requestAPI

# Import required modules
from datetime   import datetime, date, timedelta, time
from functools  import partial
from kivy.app   import App
from kivy.clock import Clock
import time     as UNIX
import calendar
import bisect
import pytz
import math

def Download(metData,Config,dt):

    """ Download the latest daily and hourly weather forecast data using the
    WeatherFlow BetterForecast API

    INPUTS:
        metData             Dictionary holding weather forecast data
        Config              Station configuration
        dt                  Time in seconds since function last called

    OUTPUT:
        metData             Dictionary holding weather forecast data
    """

    # Get current time in station time zone
    Tz         = pytz.timezone(Config['Station']['Timezone'])
    funcCalled = datetime.now(pytz.utc).astimezone(Tz)
    Midnight   = int(Tz.localize(datetime(funcCalled.year,funcCalled.month,funcCalled.day)).timestamp())
    funcError  = 0

    # Set time format based on user configuration
    if Config['Display']['TimeFormat'] == '12 hr':
        if Config['System']['Hardware'] != 'Other':
            TimeFormat = '%-I %P'
        else:
            TimeFormat = '%I %p'
    else:
        TimeFormat = '%H:%M'

    # Download latest forecast data
    Data = requestAPI.weatherflow.Forecast(Config)

    # Verify API response and extract forecast
    if requestAPI.weatherflow.verifyResponse(Data,'forecast'):
        metData['Dict'] = Data.json()
    else:
        funcError = 1
        if not 'Dict' in metData:
            metData['Dict'] = {}

    # Extract all forecast data from WeatherFlow JSON object
    try:
        # Extract all hourly and daily forecasts
        hourlyForecasts  = (metData['Dict']['forecast']['hourly'])
        dailyForecasts   = (metData['Dict']['forecast']['daily'])

        # Extract 'valid from' time of all available hourly forecasts and
        # retrieve forecast for the current hour
        Hours          = list(forecast['time'] for forecast in hourlyForecasts)
        hoursInd       = bisect.bisect(Hours,int(UNIX.time()))
        hourlyCurrent  = hourlyForecasts[hoursInd]
        hourlyLocalDay = hourlyCurrent['local_day']

        # Extract 'Valid' until time of forecast for current hour
        Valid = Hours[bisect.bisect(Hours,int(UNIX.time()))]
        Valid = datetime.fromtimestamp(Valid,pytz.utc).astimezone(Tz)

        # Extract 'day_start_local' time of all available daily forecasts and
        # retrieve forecast for the current day
        dailyDayNum  = list(forecast['day_num'] for forecast in dailyForecasts)
        dailyCurrent = dailyForecasts[dailyDayNum.index(hourlyLocalDay)]

        # Extract weather variables from current hourly forecast
        Temp         = [hourlyCurrent['air_temperature'],'c']
        WindSpd      = [hourlyCurrent['wind_avg'],'mps']
        WindGust     = [hourlyCurrent['wind_gust'],'mps']
        WindDir      = [hourlyCurrent['wind_direction'],'degrees']
        Icon         =  hourlyCurrent['icon'].replace('cc-','')

        # Extract Precipitation Type, Percent, and Amount from current hourly
        # forecast
        if 'precip_type' in hourlyCurrent:
            PrecipType   =  hourlyCurrent['precip_type']
            if PrecipType not in ['rain','snow']:
                PrecipType = 'rain'
        else:
            PrecipType = 'rain'
        if 'precip_probability' in hourlyCurrent:
            PrecipPercnt = [hourlyCurrent['precip_probability'],'%']
        else:
            PrecipPercnt = [0,'%']
        if 'precip' in hourlyCurrent:
            PrecipAmount = [hourlyCurrent['precip'],'mm']
        else:
            PrecipAmount = [0,'mm']

        # Extract weather variables from current daily forecast
        highTemp  = [dailyCurrent['air_temp_high'],'c']
        lowTemp   = [dailyCurrent['air_temp_low'],'c']
        precipDay = [dailyCurrent['precip_probability'],'%']

        # Extract list of expected conditions and find time when expected conditions
        # will change
        conditionList = list(forecast['conditions'] for forecast in hourlyForecasts[hoursInd:])
        try:
            Ind = next(i for i,C in enumerate(conditionList) if C != hourlyCurrent['conditions'])
        except StopIteration:
            Ind = len(conditionList)-1
        Time = datetime.fromtimestamp(Hours[Ind],pytz.utc).astimezone(Tz)
        if Time.date() == funcCalled.date():
            Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time,TimeFormat) + ' today'
        elif Time.date() == funcCalled.date() + timedelta(days=1):
            Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time,TimeFormat) + ' tomorrow'
        else:
            Conditions = hourlyCurrent['conditions'].capitalize() + ' until ' + datetime.strftime(Time,TimeFormat) + ' on ' + Time.strftime('%A')

        # Calculate derived variables from forecast
        WindDir = derive.CardinalWindDirection(WindDir,WindSpd)

        # Convert forecast units as required
        Temp         = observation.Units(Temp,Config['Units']['Temp'])
        highTemp     = observation.Units(highTemp,Config['Units']['Temp'])
        lowTemp      = observation.Units(lowTemp,Config['Units']['Temp'])
        WindSpd      = observation.Units(WindSpd,Config['Units']['Wind'])
        WindGust     = observation.Units(WindGust,Config['Units']['Wind'])
        WindDir      = observation.Units(WindDir,Config['Units']['Direction'])
        PrecipAmount = observation.Units(PrecipAmount,Config['Units']['Precip'])

        # Define and format labels
        metData['Time']         = funcCalled
        metData['Valid']        = datetime.strftime(Valid,TimeFormat)
        metData['Temp']         = observation.Format(Temp,'forecastTemp')
        metData['highTemp']     = observation.Format(highTemp,'forecastTemp')
        metData['lowTemp']      = observation.Format(lowTemp,'forecastTemp')
        metData['WindSpd']      = observation.Format(WindSpd,'forecastWind')
        metData['WindGust']     = observation.Format(WindGust,'forecastWind')
        metData['WindDir']      = observation.Format(WindDir,'Direction')
        metData['PrecipPercnt'] = observation.Format(PrecipPercnt,'Humidity')
        metData['PrecipDay']    = observation.Format(precipDay,'Humidity')
        metData['PrecipAmount'] = observation.Format(PrecipAmount,'Precip')
        metData['PrecipType']   = PrecipType
        metData['Conditions']   = Conditions
        metData['Icon']         = Icon
        metData['Status']       = ''

        # Check expected conditions icon is recognised
        if Icon in  ['clear-day', 'clear-night', 'rainy', 'possibly-rainy-day',
                     'possibly-rainy-night', 'snow', 'possibly-snow-day',
                     'possibly-snow-night', 'sleet', 'possibly-sleet-day',
                     'possibly-sleet-night', 'thunderstorm', 'possibly-thunderstorm-day'
                     'possibly-thunderstorm-night', 'windy', 'foggy', 'cloudy',
                     'partly-cloudy-day','partly-cloudy-night']:
            metData['Icon'] = Icon
        else:
            metData['Icon'] = '--'

        metData['stationOnline'] = metData['Dict']['station']['is_station_online']
        metData['stationUsed'] = metData['Dict']['station']['includes_tempest']

    # Unable to extract forecast data from JSON object. Set set forecast
    # variables to blank and indicate to user that forecast is unavailable
    except (IndexError, KeyError, ValueError):
        metData['Time']         = funcCalled
        metData['Valid']        = '--'
        metData['Temp']         = '--'
        metData['highTemp']     = '--'
        metData['lowTemp']      = '--'
        metData['WindSpd']      = '--'
        metData['WindGust']     = '--'
        metData['WindDir']      = '--'
        metData['PrecipPercnt'] = '--'
        metData['PrecipDay']    = '--'
        metData['PrecipAmount'] = '--'
        metData['PrecipType']   = '--'
        metData['Conditions']   = ''
        metData['Icon']         = '--'
        metData['Status']       = 'Forecast currently\nunavailable...'
        funcError               = 1

        metData['stationOnline'] = False
        metData['stationUsed'] = False

    # Schedule new forecast to be downloaded at the top of the next hour, or in
    # 5 minutes if error was detected. Note secondsSched refers to number of
    # seconds since the function was last called.
    Now = datetime.now(pytz.utc).astimezone(Tz)
    downloadTime = Tz.localize(datetime.combine(Now.date(),time(Now.hour,0,0))+timedelta(hours=1))
    if not funcError:
        secondsSched = math.ceil((downloadTime-funcCalled).total_seconds())
    else:
        secondsSched = 300 + math.ceil((funcCalled-Now).total_seconds())
    Clock.schedule_once(partial(Download,metData,Config), secondsSched)

    # Return metData dictionary

    ExtractDaily(App.get_running_app())

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
            wfDayDict = metData['Dict']['forecast']['daily'][i]

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
        # Check expected conditions icon is recognised
        if weather in  ['clear-day', 'clear-night', 'rainy', 'possibly-rainy-day',
                        'possibly-rainy-night', 'snow', 'possibly-snow-day',
                        'possibly-snow-night', 'sleet', 'possibly-sleet-day',
                        'possibly-sleet-night', 'thunderstorm', 'possibly-thunderstorm-day'
                        'possibly-thunderstorm-night', 'windy', 'foggy', 'cloudy',
                        'partly-cloudy-day','partly-cloudy-night']:
            dailyForecast.panels[i].weather = weather
        else:
            dailyForecast.panels[i].weather = '--'

