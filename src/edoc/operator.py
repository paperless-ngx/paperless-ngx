# from apscheduler.schedulers.background import BackgroundScheduler
# from django_apscheduler.jobstores import register_events, DjangoJobStore
# from documents.tasks import revoke_permission


# def start():
#     scheduler = BackgroundScheduler()
#     scheduler.add_jobstore(DjangoJobStore(), 'djangojobstore')
#     register_events(scheduler)

#     # @scheduler.scheduled_job('interval', minutes=1, name='revoke_permission')
#     # def auto_revoke_permission():
#     #     revoke_permission()

#     scheduler.start()
