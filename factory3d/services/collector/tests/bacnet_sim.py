"""Тестовий BACnet-пристрій device 140 на bacpypes3 (SPEC §13.0.2): AI:1-3, AO:1, MSV:1, BI:1, LSZ:12, PIV:1/3."""
from __future__ import annotations

import asyncio
import inspect
from typing import Any

from bacpypes3.apdu import UnconfirmedEventNotificationRequest
from bacpypes3.app import Application
from bacpypes3.basetypes import (
    NotificationParameters,
    NotificationParametersChangeOfLifeSafety,
    StatusFlags,
    TimeStamp,
)
from bacpypes3.errors import ExecutionError, UnrecognizedService
from bacpypes3.local.analog import AnalogInputObject, AnalogOutputObject
from bacpypes3.local.binary import BinaryInputObject
from bacpypes3.local.device import DeviceObject
from bacpypes3.local.multistate import MultiStateValueObject
from bacpypes3.local.networkport import NetworkPortObject
from bacpypes3.object import LifeSafetyZoneObject, PositiveIntegerValueObject
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier

from collector.plugins.bacnet_ip import service_name

_READ_ONLY_TYPES = {"analog-input", "binary-input", "life-safety-zone", "positive-integer-value"}


class _Dev(Application):
    sim: BacnetTestDevice

    async def indication(self, apdu: Any) -> None:  # type: ignore[override]
        name = type(apdu).__name__
        if name.endswith("Request"):
            self.sim.services.append(service_name(name.removesuffix("Request")))
        await super().indication(apdu)

    async def do_ReadPropertyMultipleRequest(self, apdu: Any) -> None:
        if self.sim.reject_rpm:
            raise UnrecognizedService("RPM not supported")
        await super().do_ReadPropertyMultipleRequest(apdu)

    async def do_SubscribeCOVRequest(self, apdu: Any) -> None:
        if self.sim.reject_cov:
            raise ExecutionError(errorClass="services", errorCode="service-request-denied")
        await super().do_SubscribeCOVRequest(apdu)

    async def do_WritePropertyRequest(self, apdu: Any) -> None:
        if str(apdu.objectIdentifier[0]) in _READ_ONLY_TYPES:
            raise ExecutionError(errorClass="property", errorCode="write-access-denied")
        await super().do_WritePropertyRequest(apdu)


class BacnetTestDevice:
    host = "127.0.0.1"

    def __init__(self) -> None:
        self.services: list[str] = []
        self.reject_rpm = False
        self.reject_cov = False
        flags = [0, 0, 0, 0]
        objs: list[Any] = [
            AnalogInputObject(objectIdentifier=("analog-input", 1), objectName="supply_c", presentValue=77.4,
                              statusFlags=flags, covIncrement=0.1, units="degrees-celsius"),
            AnalogInputObject(objectIdentifier=("analog-input", 2), objectName="return_c", presentValue=55.0,
                              statusFlags=flags, covIncrement=0.1, units="degrees-celsius"),
            AnalogInputObject(objectIdentifier=("analog-input", 3), objectName="raw_ai3", presentValue=61.1,
                              statusFlags=flags, covIncrement=0.1, units="no-units"),
            AnalogOutputObject(objectIdentifier=("analog-output", 1), objectName="valve", presentValue=0.0,
                               statusFlags=flags, covIncrement=0.1, relinquishDefault=0.0, units="percent"),
            MultiStateValueObject(objectIdentifier=("multi-state-value", 1), objectName="mode", presentValue=2,
                                  statusFlags=flags, numberOfStates=4),
            BinaryInputObject(objectIdentifier=("binary-input", 1), objectName="run", presentValue="active",
                              statusFlags=flags),
            LifeSafetyZoneObject(objectIdentifier=("life-safety-zone", 12), objectName="fa_zone",
                                 presentValue="quiet", statusFlags=flags, trackingValue="quiet", mode="on",
                                 acceptedModes=["on"], silenced="unsilenced", operationExpected="none"),
            PositiveIntegerValueObject(objectIdentifier=("positive-integer-value", 1), objectName="piv1",
                                       presentValue=17, statusFlags=flags),
            PositiveIntegerValueObject(objectIdentifier=("positive-integer-value", 3), objectName="piv3",
                                       presentValue=17, statusFlags=flags),
        ]
        dev = DeviceObject(objectIdentifier=("device", 140), objectName="BACNET-T-140", vendorIdentifier=999)
        port = NetworkPortObject("127.0.0.1:0", objectIdentifier=("network-port", 1), objectName="np",
                                 networkNumber=0, networkNumberQuality="unknown")
        self.app: _Dev = _Dev.from_object_list([dev, port, *objs])  # type: ignore[assignment]
        self.app.sim = self

    async def start(self) -> None:
        for _ in range(50):
            for link in self.app.link_layers.values():
                transport = getattr(link.server, "local_transport", None)
                if transport is not None:
                    self.port = int(transport.get_extra_info("sockname")[1])
                    return
            await asyncio.sleep(0.02)
        raise RuntimeError("bacnet test device did not bind")

    def close(self) -> None:
        self.app.close()

    # --- доступ до об'єктів ---
    def obj(self, ref: str) -> Any:
        """`AI:1` -> об'єкт."""
        from collector.plugins.bacnet_ip import LONG

        short, inst = ref.split(":")
        return self.app.get_object_id(ObjectIdentifier(f"{LONG[short]},{int(inst)}"))

    def set_pv(self, ref: str, value: Any) -> None:
        self.obj(ref).presentValue = value

    def get_pv(self, ref: str) -> Any:
        return self.obj(ref).presentValue

    def set_flags(self, ref: str, **flags: bool) -> None:
        """statusFlags локального об'єкта обчислюються з eventState/reliability/outOfService."""
        o = self.obj(ref)
        o.eventState = "high-limit" if flags.get("in_alarm") else "normal"
        o.reliability = "unreliable-other" if flags.get("fault") else "no-fault-detected"
        o.outOfService = bool(flags.get("out_of_service"))

    def priority(self, ref: str, level: int = 8) -> Any:
        return self.obj(ref).priorityArray[level - 1]

    def count(self, service: str) -> int:
        return self.services.count(service)

    # --- події ---
    async def send_event(self, collector_port: int, *, obj: tuple[str, int] = ("life-safety-zone", 12),
                         event_type: str = "change-of-life-safety", new_state: str = "test-alarm",
                         new_mode: str = "on", message: str = "Тест", from_state: str = "normal",
                         to_state: str = "offnormal", notification_class: int = 1, priority: int = 1,
                         ack_required: bool = False, device: int = 140) -> None:
        kwargs: dict[str, Any] = {
            "destination": Address(f"127.0.0.1:{collector_port}"),
            "processIdentifier": 0,
            "initiatingDeviceIdentifier": ("device", device),
            "eventObjectIdentifier": obj,
            "timeStamp": TimeStamp(sequenceNumber=1),
            "notificationClass": notification_class,
            "priority": priority,
            "eventType": event_type,
            "messageText": message,
            "notifyType": "alarm",
            "ackRequired": ack_required,
            "fromState": from_state,
            "toState": to_state,
        }
        if event_type == "change-of-life-safety":
            kwargs["eventValues"] = NotificationParameters(
                changeOfLifeSafety=NotificationParametersChangeOfLifeSafety(
                    newState=new_state, newMode=new_mode, statusFlags=StatusFlags([0, 0, 0, 0]),
                    operationExpected="none"))
        res = self.app.request(UnconfirmedEventNotificationRequest(**kwargs))
        if inspect.isawaitable(res):
            await res
