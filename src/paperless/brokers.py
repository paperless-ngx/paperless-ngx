import redis
from django.conf import settings
from django_q.brokers.redis_broker import Redis as RedisBroker
from django_q.conf import Conf
from paperless.helpers import build_redis_client
from redis import Redis


class RedisSentinelBroker(RedisBroker):
    def enqueue(self, task):
        try:
            return super().enqueue(task)
        except redis.ConnectionError:
            self.connection = self.get_connection()
            return super().enqueue(task)

    def dequeue(self):
        try:
            return super().dequeue()
        except redis.ConnectionError:
            self.connection = self.get_connection()
            return super().dequeue()

    def queue_size(self):
        try:
            return super().queue_size()
        except redis.ConnectionError:
            self.connection = self.get_connection()
            return super().queue_size()

    def delete_queue(self):
        try:
            return super().delete_queue()
        except redis.ConnectionError:
            self.connection = self.get_connection()
            return super().delete_queue()

    def purge_queue(self):
        try:
            return super().purge_queue()
        except redis.ConnectionError:
            self.connection = self.get_connection()
            return super().purge_queue()

    def ping(self) -> bool:
        try:
            return super().ping()
        except redis.ConnectionError:
            self.connection = self.get_connection()
            return super().ping()

    def info(self) -> str:
        try:
            return super().info()
        except redis.ConnectionError:
            self.connection = self.get_connection()
            return super().info()

    def set_stat(self, key: str, value: str, timeout: int):
        try:
            return super().set_stat(key, value, timeout)
        except redis.ConnectionError:
            self.connection = self.get_connection()
            return super().set_stat(key, value, timeout)

    def get_stat(self, key: str):
        try:
            return super().get_stat(key)
        except redis.ConnectionError:
            self.connection = self.get_connection()
            return super().get_stat(key)

    def get_stats(self, pattern: str):
        try:
            return super().get_stats(pattern)
        except redis.ConnectionError:
            self.connection = self.get_connection()
            return super().get_stats(pattern)

    @staticmethod
    def get_connection(list_key: str = Conf.PREFIX) -> Redis:
        if not isinstance(Conf.REDIS, str):
            return RedisBroker.get_connection(list_key)

        return build_redis_client(
            Conf.REDIS,
            settings.Q_CLUSTER.get("sentinel", "master_name=mymaster"),
        )
