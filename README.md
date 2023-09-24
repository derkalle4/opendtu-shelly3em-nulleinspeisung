# OpenDTU and Shelly3EM zero feed / Nulleinspeisung
This is an Open Source tool provided "as is" to allow you a solar balkony feed without transmitting power to the grid. Hint: it is impossible to achieve +- 0 feed to the grid. This script will overprovision a little bit to make sure we do not draw power from the grid if the solar panels produce enough power.

## Attention
This tool is provided "as is". There is no guarantee that this is working like expected. However, feel free to create a pull request or an issue in case of any errors.

## Installation

### Prequisites (as root)
Run the following commands as root:
- sudo apt install python3
- sudo apt install python3-pip
- sudo apt install mosquitto

### Prequisites (as user)
Run the following commands as a normal user which later on runs the software:
- pip3 install paho-mqtt
- pip3 install uvicorn
- pip3 install asyncio
- pip3 install fastapi
- pip3 install jinja2

### Configuration of Mosquitto (MQTT Broker)
The configuration of the MQTT browser is easy. After installing the prequisites (see above) you can simply create a new configuration file:
- nano /etc/mosquitto/conf.d/default.conf

```
listener 1883
password_file /etc/mosquitto/passwd
```

Save the file by pressing "CTRL + X" and afterwards acknowledge with "y" and "ENTER".

Create three Accounts (for OpenDTU, Shelly3EM and this tool):

- mosquitto_passwd -c /etc/mosquitto/passwd opendtu
- mosquitto_passwd /etc/mosquitto/passwd shelly3em
- mosquitto_passwd /etc/mosquitto/passwd webinterface

Enable and restart the service to make sure it is running after a reboot:

- systemctl enable mosquitto.service
- systemctl restart mosquitto.service

Enter the above created usernames and passwords to the OpenDTU and Shelly3EM. The account for the tool will be configured in a later step.