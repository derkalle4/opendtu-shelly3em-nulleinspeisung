import asyncio
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import logging
import math
import paho.mqtt.client as mqtt
import threading
import time
import uvicorn
import yaml


class app:
    yaml_config_file = 'config.yaml'
    config = None
    threads = []
    mqtt = None
    mqtt_shelly3em_data = {}
    mqtt_opendtu_data = {}
    data_calculated = {
        'old_limit_percentage': 0,
        'grid_sum': 0,
        'dtu_maximum_power': 0,
        'dtu_minimum_power': 0,
        'new_limit': 0,
        'new_limit_percentage': 0
    }

    def __init__(self):
        """Initialize the app class
        """
        self.app = FastAPI()
        self._configure_logging()
        self._load_yaml_config()
        self._connect_to_mqtt()
        self._setup_threads()

    def _configure_logging(self):
        logging.basicConfig(
            format='%(asctime)s %(levelname)s: %(message)s',
            level=logging.INFO,
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def _load_yaml_config(self):
        """Load the config file"""
        try:
            logging.info('loading config from %s', self.yaml_config_file)
            with open(self.yaml_config_file, "r") as stream:
                self.config = yaml.safe_load(stream)
        except Exception as exc:
            logging.error('could not load config: %s', exc)
            quit()

    def _reset(self):
        """Reset variables"""
        self.data_calculated = {
            'old_limit_percentage': 0,
            'grid_sum': 0,
            'dtu_maximum_power': 0,
            'dtu_minimum_power': 0,
            'new_limit': 0,
            'new_limit_percentage': 0
        }

    def _calculate_solar_power_percentage(self):
        """Calculate the solar power percentage depending on the current power from shelly3em"""
        logging.debug('calculating solar power percentage')
        # TODO: check if opendtu is sending data, skip otherwise
        if not 'status/reachable' in self.mqtt_opendtu_data or int(self.mqtt_opendtu_data['status/reachable']) == 0:
            logging.error(
                'opendtu is not reachable, skipping calculation (is it dark outside?)')
            self._reset()
            return
        # initialize variables
        grid_sum = 0
        dtu_maximum_power = (self.config['opendtu']['max_power'] / 100) * \
            self.config['config']['maximum_power_percentage']
        dtu_minimum_power = (self.config['opendtu']['max_power'] / 100) * \
            self.config['config']['minimum_power_percentage']
        # sum shelly phases if necessary
        for phase in self.config['shelly3em']['shelly_phases']:
            logging.debug('adding shelly3em phase %i to grid_sum', phase)
            grid_sum += float(
                self.mqtt_shelly3em_data['emeter/{}/power'.format(phase)])
        logging.debug('total_power_consumption: %i', grid_sum)
        # set new limit (and add 5 watts to prevent drawing power from the grid)
        new_limit = grid_sum + 5
        # check for minimum and maximum power boundaries
        if new_limit > dtu_maximum_power:
            new_limit = dtu_maximum_power
            logging.debug(
                'new limit is higher than dtu_maximum_power, setting new_limit to dtu_maximum_power (%i)',
                dtu_maximum_power
            )
        elif new_limit < dtu_minimum_power:
            new_limit = dtu_minimum_power
            logging.debug(
                'new limit is lower than dtu_minimum_power, setting new_limit to dtu_minimum_power (%i)',
                dtu_minimum_power
            )
        else:
            logging.debug(
                'new limit is between dtu_maximum_power and dtu_minimum_power (%i)',
                new_limit
            )
        # calculate new limit percentage
        new_limit_percentage = math.ceil(math.ceil(new_limit) /
                                         (dtu_maximum_power / 100))
        logging.debug('new limit percentage: %i', new_limit_percentage)
        # publish new limit percentage if it has changed
        if self.data_calculated['old_limit_percentage'] != new_limit_percentage:
            logging.info(
                'publishing new limit percentage to MQTT server: %i',
                new_limit_percentage
            )
            self.mqtt.publish(
                '{}/status/limit_relative'.format(
                    self.config['opendtu']['mqtt_prefix']
                ),
                new_limit_percentage
            )
        # update calculated data
        self.data_calculated = {
            'old_limit_percentage': new_limit_percentage,
            'grid_sum': grid_sum,
            'dtu_maximum_power': dtu_maximum_power,
            'dtu_minimum_power': dtu_minimum_power,
            'new_limit': new_limit,
            'new_limit_percentage': new_limit_percentage
        }

    def _setup_threads(self):
        """Setup threads"""
        # setup mqtt thread
        mqtt_thread = threading.Thread(
            target=self._mqtt_worker,
            name='mqtt_thread'
        )
        mqtt_thread.daemon = True
        mqtt_thread.start()
        self.threads.append(mqtt_thread)
        # setup uvicorn thread
        uvicorn_thread = threading.Thread(
            target=asyncio.run,
            args=(self._uvicorn_worker(),),
            name='uvicorn_thread'
        )
        uvicorn_thread.daemon = True
        uvicorn_thread.start()
        self.threads.append(uvicorn_thread)
        try:
            for thread in self.threads:
                thread.join()
        except KeyboardInterrupt:
            logging.info('keyboard interrupt detected (SIGINT), exiting')
            quit()

    async def _uvicorn_worker(self):
        logging.info('starting uvicorn webserver')
        app: FastAPI = self.app
        app.mount(
            "/static",
            StaticFiles(
                directory="webserver/static/"
            ),
            name="static"
        )
        templates = Jinja2Templates(directory="webserver/templates/")
        config = uvicorn.Config(
            app,
            host=self.config['webserver']['host'],
            port=self.config['webserver']['port']
        )
        server = uvicorn.Server(config)

        @app.get("/", response_class=HTMLResponse)
        async def _web_overview(request: Request):
            return templates.TemplateResponse(
                "overview.html",
                {
                    "request": request,
                    "config": self.config,
                    "data": {
                        'shelly3em': self.mqtt_shelly3em_data,
                        'opendtu': self.mqtt_opendtu_data,
                        'calculated': self.data_calculated
                    }
                }
            )

        @app.get("/pull", response_class=HTMLResponse)
        async def _web_pull(request: Request):
            return JSONResponse(
                content=jsonable_encoder({
                    'shelly3em': self.mqtt_shelly3em_data,
                    'opendtu': self.mqtt_opendtu_data,
                    'calculated': self.data_calculated
                })
            )
        # disable logging
        logger = logging.getLogger("uvicorn.error")
        logger.propagate = False
        # serve website
        logging.info(
            'serving website on %s:%i',
            self.config['webserver']['host'],
            self.config['webserver']['port']
        )
        await server.serve()

    def _mqtt_worker(self):
        self.mqtt.loop_forever()

    def _connect_to_mqtt(self):
        """Connect to MQTT server"""
        self.mqtt = mqtt.Client()
        self.mqtt.on_connect = self._on_mqtt_connect
        self.mqtt.on_disconnect = self._on_mqtt_disconnect
        self.mqtt.on_message = self._on_mqtt_message
        self.mqtt.username_pw_set(
            self.config['mqtt']['username'],
            self.config['mqtt']['password']
        )
        try:
            logging.error(
                'trying to connect to MQTT server: %s with port %i and username %s',
                self.config['mqtt']['host'],
                self.config['mqtt']['port'],
                self.config['mqtt']['username'])
            self.mqtt.connect(
                self.config['mqtt']['host'],
                self.config['mqtt']['port'],
                self.config['mqtt']['keepalive']
            )
        except Exception as exc:
            logging.error('could connect to MQTT server: %s', exc)
            quit()

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """When the MQTT client has connected
        :param client: MQTT client instance
        :param userdata: user data
        :param flags: response flags sent by the broker
        :param rc: the connection result
        """
        logging.info('connected to MQTT server')
        # subscribe to topics
        self._mqtt_subscribe_to_topics()

    def _mqtt_subscribe_to_topics(self):
        """Suscribe to MQTT topics"""
        self.mqtt.subscribe(
            'shellies/{}/#'.format(self.config['shelly3em']['mqtt_prefix'])
        )
        self.mqtt.subscribe(
            'solar/{}/#'.format(self.config['opendtu']['mqtt_prefix'])
        )

    def _mqtt_callback_shelly3em(self, client, userdata, message):
        """Callback for Shelly 3EM
        :param client: MQTT client instance
        :param userdata: user data
        :param message: MQTT message
        """
        # save message to topic
        topic = message.topic.replace(
            'shellies/{}/'.format(self.config['shelly3em']['mqtt_prefix']), '')
        data = message.payload.decode("utf-8")
        # check if message is valid json
        try:
            data = json.loads(data)
        except ValueError as e:
            pass
        self.mqtt_shelly3em_data[topic] = data
        self.mqtt_shelly3em_data['last_update'] = time.time()

    def _mqtt_callback_opendtu(self, client, userdata, message):
        """Callback for OpenDTU
        :param client: MQTT client instance
        :param userdata: user data
        :param message: MQTT message
        """
        # save message to topic
        topic = message.topic.replace(
            'solar/{}/'.format(self.config['opendtu']['mqtt_prefix']), '')
        data = message.payload.decode("utf-8")
        # check if message is valid json
        try:
            data = json.loads(data)
        except ValueError as e:
            pass
        self.mqtt_opendtu_data[topic] = data
        self.mqtt_opendtu_data['last_update'] = time.time()

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """When the MQTT client has been disconnected
        :param client: MQTT client instance
        :param userdata: user data
        :param rc: the disconnection result
        """
        logging.error('disconnected from MQTT server with reason %s', rc)
        self.mqtt.reconnect()

    def _on_mqtt_message(self, client, userdata, msg):
        """When the MQTT client has received a message
        :param client: MQTT client instance
        :param userdata: user data
        :param msg: MQTT message
        """
        logging.debug('received message from MQTT server')
        # check if message is from shelly3em
        if msg.topic.startswith('shellies/{}/'.format(self.config['shelly3em']['mqtt_prefix'])):
            self._mqtt_callback_shelly3em(client, userdata, msg)
        # check if message is from opendtu
        if msg.topic.startswith('solar/{}/'.format(self.config['opendtu']['mqtt_prefix'])):
            self._mqtt_callback_opendtu(client, userdata, msg)
        # check if message is from shelly3em or opendtu and process it
        if ('emeter/0/power' in msg.topic and 0 in self.config['shelly3em']['shelly_phases']) \
                or ('/emeter/1/power' in msg.topic and 1 in self.config['shelly3em']['shelly_phases']) \
                or ('/emeter/2/power' in msg.topic and 2 in self.config['shelly3em']['shelly_phases']) \
                or ('/emeter/2/power' in msg.topic and 2 in self.config['shelly3em']['shelly_phases'])
            self._calculate_solar_power_percentage()


if __name__ == '__main__':
    app = app()
