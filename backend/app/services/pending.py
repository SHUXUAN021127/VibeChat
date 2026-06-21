"""
互补匹配的"双向确认"状态管理（内存版）

流程：
1. 检测到两个用户情绪互补 → 创建一个 PendingPair
2. 双方各自看到确认弹窗，10 秒内选择同意/拒绝
3. 两人都同意 → 确认成功，进入聊天室
4. 任一方拒绝或超时 → 确认失败，双方回到等待队列，并记录"拒绝对"避免重复

注意：这是内存状态，单机部署够用。多实例部署需要换成 Redis。
"""
import secrets
import time
from threading import Lock
from typing import Optional

CONFIRM_TIMEOUT = 10  # 确认超时（秒）

class PendingPair:
    def __init__(self, pair_id: str, user_a: int, user_b: int,
                 record_a: int, record_b: int,
                 emotion_a: dict, emotion_b: dict):
        self.pair_id = pair_id
        self.user_a = user_a
        self.user_b = user_b
        self.record_a = record_a   # emotion_record id
        self.record_b = record_b
        self.emotion_a = emotion_a  # 给对方看的情绪信息
        self.emotion_b = emotion_b
        self.created_at = time.time()
        # 各方选择：None=未选, True=同意, False=拒绝
        self.choice = {user_a: None, user_b: None}
        self.room_code: Optional[str] = None  # 双方同意后生成
        self.resolved = False  # 是否已结束（成功或失败）
        self.success = False
        self.match_a_id: Optional[int] = None  # A 原所在等待房间
        self.match_b_id: Optional[int] = None  # B 原所在等待房间

    def is_expired(self) -> bool:
        return time.time() - self.created_at > CONFIRM_TIMEOUT

    def other_user(self, user_id: int) -> int:
        return self.user_b if user_id == self.user_a else self.user_a


class PendingPool:
    def __init__(self):
        self._pairs: dict[str, PendingPair] = {}
        # user_id -> pair_id，方便用户查自己的待确认
        self._user_index: dict[int, str] = {}
        # 拒绝过的配对集合：frozenset({uid1, uid2})
        self._rejected: set[frozenset] = set()
        self._lock = Lock()

    def create_pair(self, user_a, user_b, record_a, record_b, emotion_a, emotion_b) -> PendingPair:
        with self._lock:
            pair_id = secrets.token_urlsafe(8)
            pair = PendingPair(pair_id, user_a, user_b, record_a, record_b, emotion_a, emotion_b)
            self._pairs[pair_id] = pair
            self._user_index[user_a] = pair_id
            self._user_index[user_b] = pair_id
            return pair

    def get_pair(self, pair_id: str) -> Optional[PendingPair]:
        return self._pairs.get(pair_id)

    def get_user_pair(self, user_id: int) -> Optional[PendingPair]:
        pair_id = self._user_index.get(user_id)
        if pair_id:
            return self._pairs.get(pair_id)
        return None

    def is_rejected_before(self, user_a: int, user_b: int) -> bool:
        """这两个人之前是否拒绝过彼此"""
        return frozenset({user_a, user_b}) in self._rejected

    def set_choice(self, pair_id: str, user_id: int, agree: bool) -> Optional[PendingPair]:
        with self._lock:
            pair = self._pairs.get(pair_id)
            if not pair or pair.resolved:
                return pair
            if user_id not in pair.choice:
                return pair
            pair.choice[user_id] = agree
            self._evaluate(pair)
            return pair

    def _evaluate(self, pair: PendingPair):
        """检查配对是否可以结算"""
        if pair.resolved:
            return
        choices = list(pair.choice.values())
        # 有人拒绝 → 立即失败
        if False in choices:
            self._fail(pair)
            return
        # 两人都同意 → 成功
        if all(c is True for c in choices):
            pair.resolved = True
            pair.success = True
            pair.room_code = secrets.token_urlsafe(8)

    def _fail(self, pair: PendingPair):
        pair.resolved = True
        pair.success = False
        # 记录拒绝对，避免重复匹配
        self._rejected.add(frozenset({pair.user_a, pair.user_b}))

    def check_timeout(self, pair: PendingPair):
        """供轮询调用：超时则判为失败"""
        with self._lock:
            if pair.resolved:
                return
            if pair.is_expired():
                self._fail(pair)

    def cleanup(self, pair_id: str):
        """清理已结算的配对索引"""
        with self._lock:
            pair = self._pairs.get(pair_id)
            if pair and pair.resolved:
                self._user_index.pop(pair.user_a, None)
                self._user_index.pop(pair.user_b, None)

pending_pool = PendingPool()


# ===== 在线状态追踪 =====
# 用于解决"幽灵房间"：只和当前在线的用户匹配
import time as _time

class PresenceTracker:
    """记录每个用户最后一次心跳时间。匹配时只考虑近期活跃的用户。"""
    def __init__(self):
        self._last_seen: dict[int, float] = {}

    def heartbeat(self, user_id: int):
        self._last_seen[user_id] = _time.time()

    def is_online(self, user_id: int, window: float = 6.0) -> bool:
        """window 秒内有心跳则视为在线（轮询间隔 2 秒，给 3 倍冗余）"""
        last = self._last_seen.get(user_id)
        if last is None:
            return False
        return (_time.time() - last) <= window

    def leave(self, user_id: int):
        self._last_seen.pop(user_id, None)

presence = PresenceTracker()
