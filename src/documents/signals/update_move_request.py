# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.utils import timezone
# from documents.models import Warehouse, WarehouseMoveRequest
#
#
# @receiver(post_save, sender=Warehouse)
# def update_move_request_on_box_status_change(sender, instance, created, update_fields, **kwargs):
#     if created:
#         return
#     if instance.type == Warehouse.BOXCASE or instance.type == Warehouse.SHELF and update_fields and "boxcase_status" in update_fields:
#         if instance.boxcase_status == Warehouse.TYPE_DELIVERY.STORED:
#             move_request = WarehouseMoveRequest.objects.filter(
#                 container_to_move=instance,
#                 status=WarehouseMoveRequest.Status.IN_TRANSIT,
#             ).first()
#
#             if move_request:
#                 move_request.status = WarehouseMoveRequest.Status.RECEIVED
#                 move_request.container_received = instance.owner,
#                 move_request.accept_date = timezone.now()
#                 move_request.save()
