"""Tuya Din Power Meter."""
from typing import Dict

from zigpy.profiles import zha
from zigpy.quirks import CustomDevice
import zigpy.types as t
from zigpy.zcl import foundation
from zigpy.zcl.clusters.general import Basic, Groups, Ota, Scenes, Time
from zigpy.zcl.clusters.homeautomation import ElectricalMeasurement
from zigpy.zcl.clusters.smartenergy import Metering

from zhaquirks import LocalDataCluster
from zhaquirks.const import (
    DEVICE_TYPE,
    ENDPOINTS,
    INPUT_CLUSTERS,
    MODELS_INFO,
    OUTPUT_CLUSTERS,
    PROFILE_ID,
)
from zhaquirks.tuya import TuyaLocalCluster
from zhaquirks.tuya.mcu import (
    DPToAttributeMapping,
    EnchantedDevice,
    TuyaMCUCluster,
    TuyaOnOff,
)


class TuyaPowerMeasurement(TuyaLocalCluster, ElectricalMeasurement):
    """Custom class for power, voltage and current measurement."""

    AC_CURRENT_MULTIPLIER = 0x0602
    AC_CURRENT_DIVISOR = 0x0603

    _CONSTANT_ATTRIBUTES = {AC_CURRENT_MULTIPLIER: 1, AC_CURRENT_DIVISOR: 1000}


class TuyaElectricalMeasurement(TuyaLocalCluster, Metering):
    """Custom class for total energy measurement."""

    POWER_WATT = 0x0000

    _CONSTANT_ATTRIBUTES = {
        0x0300: POWER_WATT,  # unit_of_measure
        0x0302: 1000,  # divisor
    }


class DinPowerManufCluster(TuyaMCUCluster):
    """Tuya Manufacturer Cluster with din power datapoints."""

    class TuyaConnectionStatus(t.Struct):
        """Tuya request data."""

        tsn: t.uint8_t
        status: t.LVBytes

    client_commands = TuyaMCUCluster.client_commands.copy()
    client_commands.update(
        {
            0x25: foundation.ZCLCommandDef(
                "mcu_connection_status",
                {"payload": TuyaConnectionStatus},
                True,
                is_manufacturer_specific=True,
            ),
        }
    )

    server_commands = TuyaMCUCluster.server_commands.copy()
    server_commands.update(
        {
            0x25: foundation.ZCLCommandDef(
                "mcu_connection_status_rsp",
                {"payload": TuyaConnectionStatus},
                False,
                is_manufacturer_specific=True,
            ),
        }
    )

    def handle_mcu_connection_status(
        self, payload: TuyaConnectionStatus
    ) -> foundation.Status:
        """Handle gateway connection status requests (0x25)."""

        payload_rsp = DinPowerManufCluster.TuyaConnectionStatus()
        payload_rsp.tsn = payload.tsn
        payload_rsp.status = b"\x01"  # 0x00 not connected to internet | 0x01 connected to internet | 0x02 time out

        self.create_catching_task(
            super().command(0x25, payload_rsp, expect_reply=False)
        )

        return foundation.Status.SUCCESS

    dp_to_attribute: Dict[int, DPToAttributeMapping] = {
        0x01: DPToAttributeMapping(
            TuyaElectricalMeasurement.ep_attribute,
            "current_summ_delivered",
        ),
        0x06: DPToAttributeMapping(
            TuyaPowerMeasurement.ep_attribute,
            ("rms_current", "rms_voltage"),
            converter=lambda x: (x >> 16, (x & 0x0000FFFF) / 10),
        ),
        0x10: DPToAttributeMapping(
            TuyaOnOff.ep_attribute,
            "on_off",
        ),
        0x66: DPToAttributeMapping(
            TuyaElectricalMeasurement.ep_attribute,
            "current_summ_received",
        ),
        0x67: DPToAttributeMapping(
            TuyaPowerMeasurement.ep_attribute,
            "active_power",
        ),
        0x69: DPToAttributeMapping(
            TuyaPowerMeasurement.ep_attribute,
            "ac_frequency",
        ),
        0x6D: DPToAttributeMapping(
            TuyaPowerMeasurement.ep_attribute,
            "total_reactive_power",
        ),
        0x6E: DPToAttributeMapping(
            TuyaPowerMeasurement.ep_attribute,
            "reactive_power",
        ),
        0x6F: DPToAttributeMapping(
            TuyaPowerMeasurement.ep_attribute,
            "power_factor",
        ),
    }

    data_point_handlers = {
        0x01: "_dp_2_attr_update",
        0x06: "_dp_2_attr_update",
        0x10: "_dp_2_attr_update",
        0x66: "_dp_2_attr_update",
        0x67: "_dp_2_attr_update",
        0x69: "_dp_2_attr_update",
        0x6D: "_dp_2_attr_update",
        0x6E: "_dp_2_attr_update",
        0x6F: "_dp_2_attr_update",
    }


class TuyaManufClusterDinPower(DinPowerManufCluster):
    """Manufacturer Specific Cluster of the Tuya Power Meter device."""

    dp_to_attribute: Dict[int, DPToAttributeMapping] = {
        17: DPToAttributeMapping(
            TuyaElectricalMeasurement.ep_attribute,
            "current_summ_delivered",
        ),
        18: DPToAttributeMapping(
            TuyaPowerMeasurement.ep_attribute,
            "rms_current",
        ),
        19: DPToAttributeMapping(
            TuyaPowerMeasurement.ep_attribute,
            "active_power",
            converter=lambda x: x // 10,
        ),
        20: DPToAttributeMapping(
            TuyaPowerMeasurement.ep_attribute,
            "rms_voltage",
            converter=lambda x: x // 10,
        ),
    }

    data_point_handlers = {
        17: "_dp_2_attr_update",
        18: "_dp_2_attr_update",
        19: "_dp_2_attr_update",
        20: "_dp_2_attr_update",
    }


class TuyaPowerMeter(EnchantedDevice):
    """Tuya power meter device."""

    signature = {
        # "node_descriptor": "<NodeDescriptor byte1=1 byte2=64 mac_capability_flags=142 manufacturer_code=4098
        #                       maximum_buffer_size=82 maximum_incoming_transfer_size=82 server_mask=11264
        #                       maximum_outgoing_transfer_size=82 descriptor_capability_field=0>",
        # device_version=1
        # input_clusters=[0x0000, 0x0004, 0x0005, 0xef00]
        # output_clusters=[0x000a, 0x0019]
        MODELS_INFO: [
            ("_TZE204_cjbofhxw", "TS0601"),
        ],
        ENDPOINTS: {
            # <SimpleDescriptor endpoint=1 profile=260 device_type=51
            # device_version=1
            # input_clusters=[0, 4, 5, 61184]
            # output_clusters=[10, 25]>
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.SMART_PLUG,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    TuyaManufClusterDinPower.cluster_id,
                ],
                OUTPUT_CLUSTERS: [Time.cluster_id, Ota.cluster_id],
            }
        },
    }

    replacement = {
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.SMART_PLUG,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    TuyaManufClusterDinPower,
                    TuyaPowerMeasurement,
                    TuyaElectricalMeasurement,
                ],
                OUTPUT_CLUSTERS: [Time.cluster_id, Ota.cluster_id],
            }
        }
    }
