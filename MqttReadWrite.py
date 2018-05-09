"""
Recurring Read Property
This application has a static list of points that it would like to read.  It
reads the values of each of them in turn and then quits.

Google Root CA for JWT
https://pki.goog/roots.pem


"""

# MQTT Imports
import json
import datetime
import time
import os
import ssl
import jwt
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import paho.mqtt.subscribe as subscribe
import netifaces

# BACpypes Imports
from collections import deque
from bacpypes.consolelogging import ConfigArgumentParser
from bacpypes.core import run, deferred, enable_sleeping
from bacpypes.iocb import IOCB
from bacpypes.task import RecurringTask
from bacpypes.pdu import Address
from bacpypes.object import get_datatype
from bacpypes.apdu import ReadPropertyRequest, WritePropertyRequest, Error, AbortPDU, ReadPropertyACK, SimpleAckPDU
from bacpypes.primitivedata import Null, Atomic, Integer, Unsigned, Real
from bacpypes.constructeddata import Array, Any
from bacpypes.app import BIPSimpleApplication
from bacpypes.local.device import LocalDeviceObject

# Google IoT Core device variables
project_id = ''
registry_id = ''
iot_device_id = ''

# Unique client ID to address the configuration consumption and publishes
iot_client_id = 'projects/{}/locations/us-central1/registries/{}/devices/{}'.format(project_id, registry_id, iot_device_id)

#
#   BacnetRunner
#

class BacnetRunner(BIPSimpleApplication, RecurringTask):

    def __init__(self, interval, *args):
        BIPSimpleApplication.__init__(self, *args)
        RecurringTask.__init__(self, interval * 1000)

        # Configure IoT telemetry
        self.iot_broker = 'mqtt.googleapis.com'
        self.iot_broker_port = 8883

        # Task Runner Status
        self.is_busy = False

        # Install task to queue
        self.install_task()

        # Bacnet point list
        self.bacnet_points = {}


    def create_auth(self):
        token = {
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
            'aud': project_id
        }
        with open('./rsa_private.pem', 'r') as f:
            private_key = f.read()
        
        auth_password = jwt.encode(token, private_key, algorithm='RS256')

        # Return DICT here. Using func() in config causes issues
        return {'username': "unused", 'password': auth_password}

    def update_config(self):

        # Auth is created on each publish
        auth_config = self.create_auth()
        
        config = subscribe.simple(
                    "/devices/{}/config".format(iot_device_id),
                    qos=1, 
                    hostname="mqtt.googleapis.com", 
                    port=8883, 
                    client_id=iot_client_id, 
                    auth=auth_config,
                    tls={'ca_certs':'./roots.pem', 'tls_version':ssl.PROTOCOL_TLSv1_2}
                    )

        data = json.loads(config.payload) # pylint: disable=E1101
        
        # Create empty DICT
        deviceUUID = {}

        # Expected point list is:
        # {"uuid": ("1.2.3.4", "analogValue", 1, "presentValue")}

        # Parse JSON for Protocol -> Bacnet -> Points
        for v in data['protocol']['bacnet'].values():
            for p in v['points']:
                # Insert into DICT
                deviceUUID[p['uuid']] = (v['address'], p['type'], p['instance'], p['property'])

        # Write DICT to self for reference
        self.bacnet_points = deviceUUID

    def time_converter(self, o):
        # Convert time object to JSON serializable object
        if isinstance(o, datetime.datetime):
            return o.__str__()

    def process_task(self):

        # Update configuration
        self.update_config()

        # Using .values() pulls the list for each unique point
        points = self.bacnet_points.values()

        # check to see if we're idle
        if self.is_busy:
            return

        # now we are busy
        self.is_busy = True

        # turn the point list into a queue
        self.point_queue = deque(points)

        # clean out the list of the response values
        self.response_values = []

        # fire off the next request
        self.next_request()
        

    def next_request(self):
        
        # No .values() use here allows access to the unique point IDs
        points = self.bacnet_points

        # Auth is created on each publish
        auth_config = self.create_auth()

        # check to see if we're done
        if not self.point_queue:
            # dump out the results
            for request, response in zip(points, self.response_values):
                # Payload Format
                # { "measurement":"UUID", "value":89, "ts":1522875810604 }

                # Get current time
                time_now = lambda: int(round(time.time() * 1000))

                # Encode the payload for Google IoT
                payload = str.encode(json.dumps({"measurement": request, "value": response, "ts": time_now()}, ensure_ascii=True))

                print(payload)

                # Publish point values as single message
                # Publish can also be batched as well
                publish.single(
                    "/devices/{}/events".format(iot_device_id), 
                    payload, 
                    qos=1, 
                    hostname="mqtt.googleapis.com", 
                    port=8883, 
                    client_id=iot_client_id, 
                    auth=auth_config,
                    tls={'ca_certs':'./roots.pem', 'tls_version':ssl.PROTOCOL_TLSv1_2}
                    )
                
            # no longer busy
            self.is_busy = False

            return

        # get the next request
        addr, obj_type, obj_inst, prop_id = self.point_queue.popleft()

        # build a request
        request = ReadPropertyRequest(
            objectIdentifier=(obj_type, obj_inst),
            propertyIdentifier=prop_id,
            )
        request.pduDestination = Address(addr)

        # make an IOCB
        iocb = IOCB(request)

        # set a callback for the response
        iocb.add_callback(self.complete_request)

        # give it to the application
        self.request_io(iocb)

    def complete_request(self, iocb):

        if iocb.ioResponse:
            apdu = iocb.ioResponse

            # find the datatype
            datatype = get_datatype(apdu.objectIdentifier[0], apdu.propertyIdentifier)
            if not datatype:
                raise TypeError("unknown datatype")

            # special case for array parts, others are managed by cast_out
            if issubclass(datatype, Array) and (apdu.propertyArrayIndex is not None):
                if apdu.propertyArrayIndex == 0:
                    value = apdu.propertyValue.cast_out(Unsigned)
                else:
                    value = apdu.propertyValue.cast_out(datatype.subtype)
            else:
                value = apdu.propertyValue.cast_out(datatype)

            # save the value
            self.response_values.append(value)

        if iocb.ioError:
            self.response_values.append(iocb.ioError)

        # fire off another request
        deferred(self.next_request)

#
#   __main__
#

def main():
    # make a device object
    gateway_device = LocalDeviceObject(
        objectName='GoogleIoTCollector',
        objectIdentifier=int(599),
        maxApduLengthAccepted=int(1024),
        segmentationSupported='segmentedBoth',
        vendorIdentifier=int(15),
        )

    # Interval to read points
    read_interval = int(60)
    
    # Make Runner

    # Docker specific for running in container
    # Docker uses eth0. Allows us to dynamically pull 
    interface = netifaces.ifaddresses('eth0')[2][0]
    address = interface['addr']
    subnet = interface['netmask']
    cidr_not = sum([bin(int(x)).count("1") for x in subnet.split(".")])
    bacnet_address = str(address) + '/' + str(cidr_not)
    
    print('Address: {}, Subnet: {}, CIDR: {}, Bacnet: {}'.format(address, subnet, cidr_not, bacnet_address))
    
    bacnet_app = BacnetRunner(read_interval, gateway_device, bacnet_address) # pylint: disable=W0612

    run()


if __name__ == "__main__":
    main()