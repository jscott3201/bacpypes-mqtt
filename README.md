# Google IoT Core BACnet

This is intended to facilitate the collection of BACnet functions in a format for use with the Google IoT Core toolkit [Google IoT Core](https://cloud.google.com/iot-core/)

The configuration is consumed from the Google IoT device configuration file in JSON format. This should enable the necessary descriptors to become available to the device for each point. The configuration is updated on every read interval (Defaults to 60s).

## Getting Started

1. Download the Google CA for signing the JWT Token [Google Root PEM](https://pki.goog/roots.pem)

2. Create Device Key-Pairs [Google Key Pair Creation Docs](https://cloud.google.com/iot/docs/how-tos/credentials/keys)

3. Place key files into directory if you wish to use docker or modify code as needed to reference your keys. By default the keys look in the source directory

4. Update Google IoT parameters as needed for the device

```python
# Google IoT Core device variables

project_id = '' # Google Project Name
registry_id = '' # Google IoT Registry Name
iot_device_id = '' # Google IoT Core Device
```

## Create Registry and Devices

[Google IoT Core Registry and Devices](https://cloud.google.com/iot/docs/how-tos/devices)

Documentation to create the necessary registries and devices you will need to control the PubSub message flows and configuration updates for the BACnet Driver.

## Roadmap

1. Add write functionality
2. Move to threading for each device
3. Standardize the configuration consumption for points
4. Allow configuration options for payload formatting

## Packages

```text
bacpypes==0.17.0
google-api-python-client==1.6.5
google-auth-httplib2==0.0.3
google-auth==1.4.1
cryptography==2.1.4
paho-mqtt==1.3.1
pyjwt==1.6.0
netifaces==0.10.6
```

BACpypes BACnet package [BACpypes](https://github.com/JoelBender/bacpypes).

Google Packages for IoT [Google API Docs](https://google-cloud-python.readthedocs.io/en/latest/index.html).

Paho MQTT Python Driver [Paho MQTT Python](https://github.com/eclipse/paho.mqtt.python)