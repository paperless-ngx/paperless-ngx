import json

from asgiref.sync import async_to_sync
from channels.exceptions import DenyConnection, AcceptConnection
from channels.generic.websocket import WebsocketConsumer


class StatusConsumer(WebsocketConsumer):

    def connect(self):
        if not self.scope['user'].is_authenticated:
            raise DenyConnection()
        else:
            async_to_sync(self.channel_layer.group_add)(
                'status_updates', self.channel_name)
            raise AcceptConnection()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            'status_updates', self.channel_name)

    def status_update(self, event):
        self.send(json.dumps(event['data']))
