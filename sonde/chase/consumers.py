import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import ActiveChaser

class ChaseConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add("chasers", self.channel_name)
        await self.accept()
        
        # Send current list immediately
        await self.broadcast_active_chasers()

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.deactivate_chaser()
            await self.channel_layer.group_discard("chasers", self.channel_name)
            await self.broadcast_active_chasers() 

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('type') == 'location_update':
            await self.update_location(data)
            await self.broadcast_active_chasers()  

    @sync_to_async
    def update_location(self, data):
        ActiveChaser.objects.update_or_create(
            user=self.user,
            defaults={
                'lat': data.get('lat'),
                'lng': data.get('lng'),
                'chase_name': data.get('chase_name', self.user.username),
                'is_active': True
            }
        )

    @sync_to_async
    def deactivate_chaser(self):
        ActiveChaser.objects.filter(user=self.user).update(is_active=False)

    async def broadcast_active_chasers(self):
        chasers = await self.get_active_chasers()
        await self.channel_layer.group_send(
            "chasers",
            {
                "type": "send_chasers_update",
                "chasers": chasers
            }
        )

    async def send_chasers_update(self, event):
        """This method is called for every member in the group"""
        await self.send(text_data=json.dumps({
            'type': 'chasers_update',
            'chasers': event["chasers"]
        }))

    @sync_to_async
    def get_active_chasers(self):
        chasers = ActiveChaser.objects.filter(is_active=True).select_related('user')
        return [{
            'username': c.user.username,
            'name': c.chase_name or c.user.username,
            'lat': c.lat,
            'lng': c.lng,
        } for c in chasers]
