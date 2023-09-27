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
    mqtt_data = {
        'shelly3em': {},
        'opendtu': {},
        'calculated': {
            'old_limit': 0,
            'new_limit': 0,
            'sum_normalized': 0,
            'sum_grid': 0,
            'sum_solar': 0,
            'sum_solar_maximum_power': 0,
            'sum_solar_minimum_power': 0,
            'last_calculated': 0
        }
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
        self.mqtt_data['calculated'] = {
            'old_limit': 0,
            'new_limit': 0,
            'sum_normalized': 0,
            'sum_grid': 0,
            'sum_solar': 0,
            'sum_solar_maximum_power': 0,
            'sum_solar_minimum_power': 0,
            'last_calculated': 0
        }

    def _calculate_solar_power_percentage(self):
        """Calculate the solar power percentage depending on the current power from shelly3em"""
        logging.debug('calculating solar power percentage')
        # check if solar inverters are reachable
        count_reachable_opendtu = 0
        reachable_opendtus = []
        for item in self.config['opendtu']:
            if not item['mqtt_prefix'] in self.mqtt_data['opendtu'] \
                    or not '0/power' in self.mqtt_data['opendtu'][item['mqtt_prefix']] \
                    or not 'status/reachable' in self.mqtt_data['opendtu'][item['mqtt_prefix']] \
                    or int(self.mqtt_data['opendtu'][item['mqtt_prefix']]['status/reachable']) == 0:
                logging.error(
                    'opendtu {} is not reachable'.format(
                        item['mqtt_prefix']
                    ))
            else:
                count_reachable_opendtu += 1
                reachable_opendtus.append(item['mqtt_prefix'])
        # check if there is at least one opendtu reachable
        if count_reachable_opendtu == 0:
            logging.error(
                'no opendtu is reachable, skipping calculation (is it dark outside?)')
            return
        # check if shelly3em are reachable
        count_reachable_shelly3em = 0
        reachable_shelly3em = []
        for item in self.config['shelly3em']:
            if not item['mqtt_prefix'] in self.mqtt_data['shelly3em'] \
                    or 'emeter/0/power' not in self.mqtt_data['shelly3em'][item['mqtt_prefix']] \
                    or 'emeter/1/power' not in self.mqtt_data['shelly3em'][item['mqtt_prefix']] \
                    or 'emeter/2/power' not in self.mqtt_data['shelly3em'][item['mqtt_prefix']]:
                logging.error(
                    'shelly3em {} is not reachable'.format(
                        item['mqtt_prefix']
                    ))
            else:
                count_reachable_shelly3em += 1
                reachable_shelly3em.append(item['mqtt_prefix'])
        # check if there is at least one shelly3em reachable
        if count_reachable_shelly3em == 0:
            logging.error(
                'no shelly3em is reachable, skipping calculation')
            return
        # initialize variables
        sum_grid = 0    # total power consumption of all grids
        sum_solar = 0   # total power production of all solar inverters
        sum_new_limit = 0  # total power production of all solar inverters
        # total normalized power of all sources (grid + solar)
        sum_normalized = 0
        sum_solar_maximum_power = 0  # total maximum power of all solar inverters
        sum_solar_minimum_power = 0  # total minimum power of all solar inverters
        # sum shelly phases if necessary
        for item in self.config['shelly3em']:
            # ignore unreachable shelly3em
            if not item['mqtt_prefix'] in reachable_shelly3em:
                continue
            for phase in item['shelly_phases']:
                logging.debug('adding shelly3em {} phase {} to sum_grid'.format(
                    item['mqtt_prefix'],
                    phase
                ))
                sum_grid += float(
                    self.mqtt_data['shelly3em'][item['mqtt_prefix']]
                    ['emeter/{}/power'.format(phase)]
                )
        logging.debug('total_power_consumption: %i', sum_grid)
        # sum all solar inverters
        for item in self.config['opendtu']:
            # ignore unreachable opendtu
            if not item['mqtt_prefix'] in reachable_opendtus:
                continue
            logging.debug('adding opendtu {} to sum_solar'.format(
                item['mqtt_prefix']
            ))
            sum_solar += float(
                self.mqtt_data['opendtu'][item['mqtt_prefix']]['0/power']
            )
            sum_solar_maximum_power += float(
                (item['max_power'] / 100) *
                self.config['config']['maximum_power_percentage']
            )
            sum_solar_minimum_power += float(
                (item['max_power'] / 100) *
                self.config['config']['minimum_power_percentage']
            )
        # calculate normalized sum for all sources (grid + solar)
        sum_normalized = round(sum_grid + sum_solar, 2)
        # set new limit (and add X watts to prevent drawing power from the grid)
        sum_new_limit = math.ceil(
            sum_grid
            + self.mqtt_data['calculated']['old_limit']
            + self.config['config']['additional_power']
        )
        # check for minimum and maximum power boundaries
        if sum_new_limit > sum_solar_maximum_power:
            sum_new_limit = sum_solar_maximum_power
            logging.debug(
                'new limit is higher than sum_solar_maximum_power, setting sum_new_limit to sum_solar_maximum_power (%i)',
                sum_solar_maximum_power
            )
        elif sum_new_limit < sum_solar_minimum_power:
            sum_new_limit = sum_solar_minimum_power
            logging.debug(
                'new limit is lower than sum_solar_minimum_power, setting sum_new_limit to sum_solar_minimum_power (%i)',
                sum_solar_minimum_power
            )
        else:
            logging.debug(
                'new limit is between sum_solar_maximum_power and sum_solar_minimum_power (%i)',
                sum_new_limit
            )
        # update calculated data
        self.mqtt_data['calculated']['old_limit'] = self.mqtt_data['calculated']['new_limit']
        self.mqtt_data['calculated']['sum_grid'] = sum_grid
        self.mqtt_data['calculated']['sum_solar'] = sum_solar
        self.mqtt_data['calculated']['sum_normalized'] = sum_normalized
        self.mqtt_data['calculated']['sum_solar_maximum_power'] = sum_solar_maximum_power
        self.mqtt_data['calculated']['sum_solar_minimum_power'] = sum_solar_minimum_power
        # publish new limit percentage if it has changed
        if self.mqtt_data['calculated']['old_limit'] != sum_new_limit \
                and self.mqtt_data['calculated']['last_calculated'] < time.time() - self.config['config']['delay_between_updates']:
            # iterate over all opendtu and publish their new limit
            for item in self.config['opendtu']:
                # ignore unreachable opendtu
                if not item['mqtt_prefix'] in reachable_opendtus:
                    continue
                new_limit = math.ceil(
                    sum_new_limit
                    * (float(
                        item['max_power']
                    ) / sum_solar_maximum_power)
                )
                if not 'dry_run' in self.config['config'] or not self.config['config']['dry_run']:
                    logging.info(
                        'publishing new limit for opendtu {}: {} watts'.format(
                            item['mqtt_prefix'],
                            new_limit
                        ))
                    # publish new limit percentage
                    self.mqtt.publish(
                        'solar/{}/cmd/limit_nonpersistent_absolute'.format(
                            item['mqtt_prefix']
                        ),
                        new_limit
                    )
                else:
                    logging.info(
                        'dry run: publishing new limit for opendtu {}: {} watts'.format(
                            item['mqtt_prefix'],
                            new_limit
                        ))
            # update calculated data
            self.mqtt_data['calculated']['new_limit'] = sum_new_limit
            self.mqtt_data['calculated']['last_calculated'] = time.time()

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
                    "page": "overview",
                    "page_title": "Übersicht",
                    "request": request,
                    "config_opendtu": {item['mqtt_prefix']: item for item in self.config['opendtu']},
                    "config_shelly3em": {item['mqtt_prefix']: item for item in self.config['shelly3em']},
                    "mqtt_data": self.mqtt_data
                }
            )

        @app.get("/solar", response_class=HTMLResponse)
        async def _web_solar(request: Request):
            return templates.TemplateResponse(
                "solar.html",
                {
                    "page": "solar",
                    "page_title": "Solaranlage",
                    "request": request,
                    "config_opendtu": {item['mqtt_prefix']: item for item in self.config['opendtu']},
                    "mqtt_data": self.mqtt_data
                }
            )

        @app.get("/grid", response_class=HTMLResponse)
        async def _web_grid(request: Request):
            return templates.TemplateResponse(
                "grid.html",
                {
                    "page": "grid",
                    "page_title": "Hausanschluss",
                    "request": request,
                    "config_shelly3em": {item['mqtt_prefix']: item for item in self.config['shelly3em']},
                    "mqtt_data": self.mqtt_data
                }
            )

        @app.get("/pull", response_class=HTMLResponse)
        async def _web_pull(request: Request):
            return JSONResponse(
                content=jsonable_encoder(self.mqtt_data)
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
            logging.info(
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
        logging.info('subscribing to MQTT topics')
        for item in self.config['shelly3em']:
            self.mqtt.subscribe(
                'shellies/{}/#'.format(item['mqtt_prefix'])
            )
            logging.info(
                'subscribed to Shelly3EM MQTT topic: %s',
                item['mqtt_prefix']
            )
        for item in self.config['opendtu']:
            self.mqtt.subscribe(
                'solar/{}/#'.format(item['mqtt_prefix'])
            )
            logging.info(
                'subscribed to OpenDTU MQTT topic: %s',
                item['mqtt_prefix']
            )

    def _mqtt_callback_shelly3em(self, client, userdata, mqtt_prefix, message):
        """Callback for Shelly 3EM
        :param client: MQTT client instance
        :param userdata: user data
        :param mqtt_prefix: MQTT prefix
        :param message: MQTT message
        """
        # save message to topic
        topic = message.topic.replace(
            'shellies/{}/'.format(mqtt_prefix),
            ''
        )
        data = message.payload.decode("utf-8")
        # check if message is valid json
        try:
            data = json.loads(data)
        except ValueError as e:
            pass
        if mqtt_prefix not in self.mqtt_data['shelly3em']:
            self.mqtt_data['shelly3em'][mqtt_prefix] = {}
        self.mqtt_data['shelly3em'][mqtt_prefix][topic] = data
        self.mqtt_data['shelly3em'][mqtt_prefix]['last_update'] = time.time()

    def _mqtt_callback_opendtu(self, client, userdata, mqtt_prefix, message):
        """Callback for OpenDTU
        :param client: MQTT client instance
        :param userdata: user data
        :param mqtt_prefix: MQTT prefix
        :param message: MQTT message
        """
        # save message to topic
        topic = message.topic.replace(
            'solar/{}/'.format(mqtt_prefix),
            ''
        )
        data = message.payload.decode("utf-8")
        # check if message is valid json
        try:
            data = json.loads(data)
        except ValueError as e:
            pass
        if not mqtt_prefix in self.mqtt_data['opendtu']:
            self.mqtt_data['opendtu'][mqtt_prefix] = {}
        self.mqtt_data['opendtu'][mqtt_prefix][topic] = data
        self.mqtt_data['opendtu'][mqtt_prefix]['last_update'] = time.time()

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
        if msg.topic.startswith('shellies/'):
            for item in self.config['shelly3em']:
                if msg.topic.startswith('shellies/{}/'.format(item['mqtt_prefix'])):
                    self._mqtt_callback_shelly3em(
                        client,
                        userdata,
                        item['mqtt_prefix'],
                        msg
                    )
        # check if message is from opendtu
        if msg.topic.startswith('solar/'):
            for item in self.config['opendtu']:
                if msg.topic.startswith('solar/{}/'.format(item['mqtt_prefix'])):
                    self._mqtt_callback_opendtu(
                        client,
                        userdata,
                        item['mqtt_prefix'],
                        msg
                    )
        # check if message is from shelly3em or opendtu about power and process it
        if msg.topic.endswith('/power'):
            self._calculate_solar_power_percentage()


if __name__ == '__main__':
    app = app()
