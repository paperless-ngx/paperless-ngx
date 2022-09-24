from urllib.parse import parse_qs
from urllib.parse import urlparse

import redis
from django_q.brokers.redis_broker import Redis as RedisBroker
from django_q.conf import Conf
from redis import Redis
from redis import Sentinel


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

        url = urlparse(Conf.REDIS)
        scheme_split = url.scheme.split("+")
        if "sentinel" not in scheme_split:
            return RedisBroker.get_connection(list_key)

        query = parse_qs(url.query)
        connection_kwargs = {
            "username": url.username,  # redis node username
            "password": url.password,  # redis node password
            "ssl": ("rediss" in scheme_split),
            "db": url.path[1:],
        }
        if "rediss" in scheme_split:
            connection_kwargs["ssl_cert_reqs"] = query.get(
                "ssl_cert_reqs",
                ["required"],
            )[0]

        sentinel = Sentinel(
            [(url.hostname, url.port)],
            sentinel_kwargs={
                "username": query.get("sentinelusername", [""])[0],
                "password": query.get("sentinelpassword", [""])[0],
                "ssl": ("rediss" in scheme_split),
                "ssl_cert_reqs": query.get("ssl_cert_reqs", ["required"])[0],
            },
            **connection_kwargs,
        )
        return sentinel.master_for(query.get("mastername", ["mymaster"])[0])
