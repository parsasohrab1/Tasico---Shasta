"""رابط پایه برای همه کانکتورها"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TagReading:
    tag_id: str
    value: Any
    quality: str = "good"        # good | bad | uncertain
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class BaseConnector(ABC):
    """رابط انتزاعی همه کانکتورهای صنعتی"""

    def __init__(self, name: str):
        self.name = name
        self.connected: bool = False

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def read_tags(self, tag_ids: List[str]) -> List[TagReading]: ...

    @abstractmethod
    async def write_tag(self, tag_id: str, value: Any) -> bool: ...

    def is_connected(self) -> bool:
        return self.connected

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

  """کانکتور OPC UA با auto-reconnect و batch read"""
import asyncio
import logging
from typing import Any, Dict, List
from asyncua import Client, ua
from connectors.base import BaseConnector, TagReading

log = logging.getLogger(__name__)


class OPCUAConnector(BaseConnector):
    """
    خواندن/نوشتن تگ‌ها از سرور OPC UA.
    نمونه:  opc.tcp://192.168.1.10:4840
    """

    def __init__(self, name: str, endpoint: str,
                 username: str | None = None,
                 password: str | None = None,
                 timeout_s: float = 10.0,
                 security_policy: str = "None"):
        super().__init__(name)
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.timeout_s = timeout_s
        self.security_policy = security_policy
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        async with self._lock:
            if self.connected:
                return
            self._client = Client(self.endpoint, timeout=self.timeout_s)
            if self.username:
                self._client.set_user(self.username)
                self._client.set_password(self.password)
            try:
                await self._client.connect()
                self.connected = True
                log.info(f"[{self.name}] connected to {self.endpoint}")
            except Exception as e:
                self.connected = False
                self._client = None
                raise ConnectionError(f"OPC UA connect failed: {e}") from e

    async def disconnect(self) -> None:
        async with self._lock:
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None
            self.connected = False
            log.info(f"[{self.name}] disconnected")

    async def _ensure_connected(self):
        if not self.connected or not self._client:
            await self.connect()

    async def read_tags(self, tag_ids: List[str]) -> List[TagReading]:
        await self._ensure_connected()
        out: List[TagReading] = []
        try:
            nodes = [self._client.get_node(t) for t in tag_ids]
            values = await self._client.read_values(nodes)
            for tid, val in zip(tag_ids, values):
                out.append(TagReading(tag_id=tid, value=val, quality="good"))
        except Exception as e:
            log.error(f"[{self.name}] read_tags failed: {e}")
            await self.disconnect()
            for t in tag_ids:
                out.append(TagReading(
                    tag_id=t, value=None, quality="bad", error=str(e)
                ))
        return out

    async def write_tag(self, tag_id: str, value: Any) -> bool:
        await self._ensure_connected()
        try:
            node = self._client.get_node(tag_id)
            dv = ua.DataValue(ua.Variant(value))
            await node.write_value(dv)
            return True
        except Exception as e:
            log.error(f"[{self.name}] write_tag failed for {tag_id}: {e}")
            return False

    async def browse(self, node_id: str = "ns=0;i=85") -> list:
        """لیست زیرگره‌ها — برای کشف تگ‌ها"""
        await self._ensure_connected()
        node = self._client.get_node(node_id)
        children = await node.get_children()
        return [{"node_id": c.nodeid.to_string(),
                 "name": (await c.read_browse_name()).Name}
                for c in children]

"""کانکتور Modbus TCP با batch read و auto-reconnect"""
import asyncio
import logging
from typing import Any, Dict, List, Optional
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from connectors.base import BaseConnector, TagReading

log = logging.getLogger(__name__)


class ModbusConnector(BaseConnector):
    """
    خواندن registers از Modbus TCP.
    هر تگ با نقشه: {tag_id: {"unit": 1, "type": "holding", "address": 100, "count": 1, "scale": 0.1}}
    """

    def __init__(self, name: str, host: str, port: int = 502,
                 tag_map: Optional[Dict[str, dict]] = None,
                 timeout_s: float = 5.0):
        super().__init__(name)
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self.tag_map = tag_map or {}
        self._client: Optional[AsyncModbusTcpClient] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        async with self._lock:
            if self.connected:
                return
            self._client = AsyncModbusTcpClient(self.host, port=self.port,
                                                timeout=self.timeout_s)
            ok = await self._client.connect()
            if not ok:
                self._client = None
                raise ConnectionError(
                    f"Modbus connect failed to {self.host}:{self.port}"
                )
            self.connected = True
            log.info(f"[{self.name}] connected to {self.host}:{self.port}")

    async def disconnect(self) -> None:
        async with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
            self.connected = False

    async def _ensure_connected(self):
        if not self.connected or not self._client:
            await self.connect()

    def _apply_scale(self, raw: list, scale: float) -> float:
        """تبدیل registerها به مقدار واقعی"""
        if len(raw) == 1:
            return float(raw[0]) * scale
        # 32-bit: two registers big-endian
        return float((raw[0] << 16) | raw[1]) * scale

    async def read_tags(self, tag_ids: List[str]) -> List[TagReading]:
        await self._ensure_connected()
        out: List[TagReading] = []
        for tid in tag_ids:
            cfg = self.tag_map.get(tid)
            if not cfg:
                out.append(TagReading(tid, None, "bad", error="unknown tag"))
                continue
            try:
                unit = cfg.get("unit", 1)
                addr = cfg["address"]
                count = cfg.get("count", 1)
                kind = cfg.get("type", "holding")
                scale = cfg.get("scale", 1.0)

                if kind == "holding":
                    resp = await self._client.read_holding_registers(
                        addr, count=count, slave=unit
                    )
                elif kind == "input":
                    resp = await self._client.read_input_registers(
                        addr, count=count, slave=unit
                    )
                elif kind == "coil":
                    resp = await self._client.read_coils(
                        addr, count=count, slave=unit
                    )
                elif kind == "discrete":
                    resp = await self._client.read_discrete_inputs(
                        addr, count=count, slave=unit
                    )
                else:
                    raise ValueError(f"unknown type: {kind}")

                if resp.isError():
                    raise ModbusException(str(resp))

                raw = resp.registers if hasattr(resp, "registers") else resp.bits[:count]
                val = self._apply_scale(raw, scale)
                out.append(TagReading(tid, val, "good"))
            except Exception as e:
                log.warning(f"[{self.name}] read {tid} failed: {e}")
                out.append(TagReading(tid, None, "bad", error=str(e)))
        return out

    async def write_tag(self, tag_id: str, value: Any) -> bool:
        await self._ensure_connected()
        cfg = self.tag_map.get(tag_id)
        if not cfg:
            return False
        try:
            unit = cfg.get("unit", 1)
            addr = cfg["address"]
            kind = cfg.get("type", "holding")
            if kind == "holding":
                r = await self._client.write_register(addr, int(value), slave=unit)
            elif kind == "coil":
                r = await self._client.write_coil(addr, bool(value), slave=unit)
            else:
                return False
            return not r.isError()
        except Exception as e:
            log.error(f"[{self.name}] write {tag_id} failed: {e}")
            return False

  """مدیریت همه کانکتورهای فعال + polling loop"""
import asyncio
import logging
from typing import Dict, List
from connectors.base import BaseConnector, TagReading

log = logging.getLogger(__name__)


class ConnectorRegistry:
    """مدیریت چند کانکتور و polling به Kafka/DB"""

    def __init__(self):
        self._connectors: Dict[str, BaseConnector] = {}
        self._tag_to_connector: Dict[str, str] = {}

    def register(self, connector: BaseConnector,
                 tag_ids: List[str] | None = None):
        self._connectors[connector.name] = connector
        for t in tag_ids or []:
            self._tag_to_connector[t] = connector.name

    async def start_all(self):
        for c in self._connectors.values():
            try:
                await c.connect()
            except Exception as e:
                log.error(f"connect {c.name} failed: {e}")

    async def stop_all(self):
        for c in self._connectors.values():
            try:
                await c.disconnect()
            except Exception:
                pass

    async def read_all(self) -> List[TagReading]:
        """خواندن هم‌زمان همه کانکتورها"""
        by_conn: Dict[str, List[str]] = {}
        for tag, name in self._tag_to_connector.items():
            by_conn.setdefault(name, []).append(tag)

        tasks = [
            self._connectors[name].read_tags(tags)
            for name, tags in by_conn.items()
            if name in self._connectors
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        out: List[TagReading] = []
        for r in results:
            if isinstance(r, Exception):
                log.error(f"read_all exception: {r}")
                continue
            out.extend(r)
        return out

    async def poll_forever(self, interval_s: float = 5.0,
                           sink=None):
        """
        حلقه polling نامتناهی.
        sink: async callable که لیست TagReading را می‌گیرد.
        """
        while True:
            readings = await self.read_all()
            if sink:
                try:
                    await sink(readings)
                except Exception as e:
                    log.error(f"sink failed: {e}")
            await asyncio.sleep(interval_s)

  # run_connectors.py — نمونه اجرا
import asyncio
import logging
from connectors.registry import ConnectorRegistry
from connectors.opcua_connector import OPCUAConnector
from connectors.modbus_connector import ModbusConnector

logging.basicConfig(level=logging.INFO)


async def main():
    reg = ConnectorRegistry()

    opc = OPCUAConnector(
        name="f1-opcua",
        endpoint="opc.tcp://192.168.1.10:4840",
        timeout_s=10.0,
    )
    reg.register(opc, tag_ids=[
        "ns=2;s=Boiler.B1.Steam",
        "ns=2;s=Boiler.B1.Gas",
        "ns=2;s=Turbine.T1.Power",
        "ns=2;s=Line.L1.Production",
    ])

    mod = ModbusConnector(
        name="f1-modbus",
        host="192.168.1.20",
        port=502,
        tag_map={
            "METER_ELEC_KWH": {"unit": 1, "type": "holding",
                               "address": 100, "count": 2, "scale": 0.01},
            "METER_WATER_M3": {"unit": 1, "type": "holding",
                               "address": 200, "count": 1, "scale": 0.1},
            "PUMP_1_RUN": {"unit": 1, "type": "coil", "address": 50},
        },
    )
    reg.register(mod, tag_ids=list(mod.tag_map.keys()))

    async def sink(readings):
        for r in readings:
            print(f"{r.tag_id:30s} = {r.value}  [{r.quality}]")

    await reg.start_all()
    try:
        # یک بار خواندن
        await sink(await reg.read_all())
        # یا حلقه بی‌پایان
        # await reg.poll_forever(interval_s=5.0, sink=sink)
    finally:
        await reg.stop_all()


if __name__ == "__main__":
    asyncio.run(main())

