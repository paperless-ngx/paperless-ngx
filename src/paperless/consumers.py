import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer


class StatusConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()
        async_to_sync(self.channel_layer.group_add)(
            'status_updates', self.channel_name)

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            'status_updates', self.channel_name)

    def status_update(self, event):
        self.send(json.dumps(event['data']))
