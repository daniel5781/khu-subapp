"""사용자별 디스크 저장소와 낙관적 동시성 제어.

수치 계산은 트랜잭션 밖에서 수행하고, 결과 저장 직전에 revision을 다시
비교한다. 이중 클릭·동시 요청이 같은 편집을 두 번 적용할 수 없다.
"""

from dataclasses import replace
import re
from uuid import uuid4
from diskcache import Cache
from .models import Workspace


class ExpiredWorkspace(ValueError):
    pass


class StaleWorkspace(ValueError):
    pass


class WorkspaceStore:
    def __init__(self, directory, *, ttl=7200):
        self.cache = Cache(str(directory), size_limit=512 * 1024 * 1024)
        self.ttl = ttl

    @staticmethod
    def _key(token):
        if not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{32}", token):
            raise ExpiredWorkspace(
                "작업 세션이 유효하지 않습니다. 페이지를 새로고침하세요."
            )
        return f"workspace:{token}"

    def create(self):
        self.cache.expire()
        token = uuid4().hex
        self.cache.set(self._key(token), Workspace(), expire=self.ttl)
        return {"token": token, "revision": 0}

    def read(self, pointer):
        if not isinstance(pointer, dict):
            raise ExpiredWorkspace("작업 세션이 없습니다. 페이지를 새로고침하세요.")
        key = self._key(pointer.get("token"))
        state = self.cache.get(key)
        if state is None:
            raise ExpiredWorkspace(
                "작업 세션이 만료됐습니다. 페이지를 새로고침하고 원자료를 다시 불러오세요."
            )
        self.cache.touch(key, expire=self.ttl)
        return state

    def latest(self, pointer):
        state = self.read(pointer)
        return {"token": pointer["token"], "revision": state.revision}

    def update(self, pointer, transform):
        state = self.read(pointer)
        expected = pointer.get("revision")
        if expected != state.revision:
            raise StaleWorkspace(
                "다른 요청이 먼저 반영됐습니다. 최신 결과를 확인한 뒤 다시 실행하세요."
            )
        updated = transform(state)
        if not isinstance(updated, Workspace):
            raise TypeError("Workspace 변환 결과가 필요합니다.")
        key = self._key(pointer["token"])
        with self.cache.transact():
            current = self.cache.get(key)
            if current is None:
                raise ExpiredWorkspace(
                    "계산 중 세션이 만료됐습니다. 페이지를 새로고침하세요."
                )
            if current.revision != expected:
                raise StaleWorkspace(
                    "다른 요청이 먼저 반영됐습니다. 최신 결과를 확인한 뒤 다시 실행하세요."
                )
            updated = replace(updated, revision=expected + 1)
            self.cache.set(key, updated, expire=self.ttl)
        return {"token": pointer["token"], "revision": updated.revision}

    def close(self):
        self.cache.close()
