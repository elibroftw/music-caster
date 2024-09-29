# https://gist.github.com/NyaMisty/6c69c8f5681859b3b9ceb87737fabef7
import ctypes
from ctypes import Structure, POINTER, c_char, c_void_p, c_ulong
from ctypes.wintypes import DWORD, UINT, BYTE, BOOL, ULONG, WCHAR, WORD, USHORT, BOOLEAN
from winerror import NO_ERROR, ERROR_INSUFFICIENT_BUFFER
from comtypes import GUID

ULONGLONG = ctypes.c_ulonglong
ULONG64 = ctypes.c_uint64
UCHAR = ctypes.c_ubyte


###########################################################################
#region GetIfTable2
class NET_LUID(Structure):
    _fields_ = [("Value", ULONGLONG)]

NET_IFINDEX = ULONG
IFTYPE = ULONG
TUNNEL_TYPE = ctypes.c_int
NDIS_MEDIUM = ctypes.c_int
NDIS_PHYSICAL_MEDIUM = ctypes.c_int
NET_IF_ACCESS_TYPE = ctypes.c_int
NET_IF_DIRECTION_TYPE = ctypes.c_int
IF_OPER_STATUS = ctypes.c_int
NET_IF_ADMIN_STATUS = ctypes.c_int
NET_IF_MEDIA_CONNECT_STATE = ctypes.c_int
NET_IF_NETWORK_GUID = GUID
NET_IF_CONNECTION_TYPE = ctypes.c_int

IF_MAX_STRING_SIZE = 256
IF_MAX_PHYS_ADDRESS_LENGTH = 32

class _MIB_IF_ROW2(Structure):
    pass

_MIB_IF_ROW2._fields_ = [
    ("InterfaceLuid", NET_LUID),
    ("InterfaceIndex", NET_IFINDEX),
    ("InterfaceGuid", GUID),
    ("Alias", WCHAR * (IF_MAX_STRING_SIZE + 1)),
    ("Description", WCHAR * (IF_MAX_STRING_SIZE + 1)),
    ("PhysicalAddressLength", ULONG),
    ("PhysicalAddress", UCHAR * IF_MAX_PHYS_ADDRESS_LENGTH),
    ("PermanentPhysicalAddress", UCHAR * IF_MAX_PHYS_ADDRESS_LENGTH),
    ("Mtu", ULONG),
    ("Type", IFTYPE),
    ("TunnelType", TUNNEL_TYPE),
    ("MediaType", NDIS_MEDIUM),
    ("PhysicalMediumType", NDIS_PHYSICAL_MEDIUM),
    ("AccessType", NET_IF_ACCESS_TYPE),
    ("DirectionType", NET_IF_DIRECTION_TYPE),
    ("InterfaceAndOperStatusFlags", BYTE),
    ("OperStatus", IF_OPER_STATUS),
    ("AdminStatus", NET_IF_ADMIN_STATUS),
    ("MediaConnectState", NET_IF_MEDIA_CONNECT_STATE),
    ("NetworkGuid", NET_IF_NETWORK_GUID),
    ("ConnectionType", NET_IF_CONNECTION_TYPE),

    ("TransmitLinkSpeed", ULONG64),
    ("ReceiveLinkSpeed", ULONG64),

    ("InOctets", ULONG64),
    ("InUcastPkts", ULONG64),
    ("InNUcastPkts", ULONG64),
    ("InDiscards", ULONG64),
    ("InErrors", ULONG64),
    ("InUnknownProtos", ULONG64),
    ("InUcastOctets", ULONG64),
    ("InMulticastOctets", ULONG64),
    ("InBroadcastOctets", ULONG64),
    ("OutOctets", ULONG64),
    ("OutUcastPkts", ULONG64),
    ("OutNUcastPkts", ULONG64),
    ("OutDiscards", ULONG64),
    ("OutErrors", ULONG64),
    ("OutUcastOctets", ULONG64),
    ("OutMulticastOctets", ULONG64),
    ("OutBroadcastOctets", ULONG64),
    ("OutQLen", ULONG64),
]
MIB_IF_ROW2 = _MIB_IF_ROW2
PMIB_IF_ROW2 = POINTER(_MIB_IF_ROW2)


class _MIB_IF_TABLE2(Structure):
    pass


_MIB_IF_TABLE2._fields_ = [
    ("NumEntries", ULONG),
    ("Table", MIB_IF_ROW2 * 1)
]
MIB_IF_TABLE2 = _MIB_IF_TABLE2
PMIB_IF_TABLE2 = POINTER(_MIB_IF_TABLE2)


def get_if_table2():
    pIfTable = PMIB_IF_TABLE2()
    if not ctypes.windll.iphlpapi.GetIfTable2(ctypes.byref(pIfTable)) == NO_ERROR:
        logging.error('Failed calling GetAdaptersInfo')

    IfTableMib = pIfTable.contents
    Table = ctypes.cast(ctypes.pointer(IfTableMib.Table), POINTER(MIB_IF_ROW2 * IfTableMib.NumEntries)).contents
    for i in range(IfTableMib.NumEntries):
        tempstruc = MIB_IF_ROW2()
        ctypes.pointer(tempstruc).contents = Table[i]
        yield tempstruc
    ctypes.windll.iphlpapi.FreeMibTable(pIfTable)

#endregion
###############################################################################
#region GetIpInterfaceTable
ScopeLevelCount        = 16
ADDRESS_FAMILY = USHORT
NL_ROUTER_DISCOVERY_BEHAVIOR = ctypes.c_int
NL_LINK_LOCAL_ADDRESS_BEHAVIOR = ctypes.c_int
NL_INTERFACE_OFFLOAD_ROD = BYTE

class MIB_IPINTERFACE_ROW(Structure):
    pass
MIB_IPINTERFACE_ROW._fields_ = [
    ("Family", ADDRESS_FAMILY),
    ("InterfaceLuid", NET_LUID),
    ("InterfaceIndex", NET_IFINDEX),
    ("MaxReassemblySize", ULONG),
    ("InterfaceIdentifier", ULONG64),
    ("MinRouterAdvertisementInterval", ULONG),
    ("MaxRouterAdvertisementInterval", ULONG),
    ("AdvertisingEnabled", BOOLEAN),
    ("ForwardingEnabled", BOOLEAN),
    ("WeakHostSend", BOOLEAN),
    ("WeakHostReceive", BOOLEAN),
    ("UseAutomaticMetric", BOOLEAN),
    ("UseNeighborUnreachabilityDetection", BOOLEAN),
    ("ManagedAddressConfigurationSupported", BOOLEAN),
    ("OtherStatefulConfigurationSupported", BOOLEAN),
    ("AdvertiseDefaultRoute", BOOLEAN),
    ("RouterDiscoveryBehavior", NL_ROUTER_DISCOVERY_BEHAVIOR),
    ("DadTransmits", ULONG),
    ("BaseReachableTime", ULONG),
    ("RetransmitTime", ULONG),
    ("PathMtuDiscoveryTimeout", ULONG),
    ("LinkLocalAddressBehavior", NL_LINK_LOCAL_ADDRESS_BEHAVIOR),
    ("LinkLocalAddressTimeout", ULONG),
    ("ZoneIndices", ULONG * ScopeLevelCount),
    ("SitePrefixLength", ULONG),
    ("Metric", ULONG),
    ("NlMtu", ULONG),
    ("Connected", BOOLEAN),
    ("SupportsWakeUpPatterns", BOOLEAN),
    ("SupportsNeighborDiscovery", BOOLEAN),
    ("SupportsRouterDiscovery", BOOLEAN),
    ("ReachableTime", ULONG),
    ("TransmitOffload", NL_INTERFACE_OFFLOAD_ROD),
    ("ReceiveOffload", NL_INTERFACE_OFFLOAD_ROD),
    ("DisableDefaultRoutes", BOOLEAN)
]

class _MIB_IPINTERFACE_TABLE(Structure):
    pass
_MIB_IPINTERFACE_TABLE._fields_ = [
    ("NumEntries", ULONG),
    ("Table", MIB_IPINTERFACE_ROW * 1),
]
MIB_IPINTERFACE_TABLE = _MIB_IPINTERFACE_TABLE
PMIB_IPINTERFACE_TABLE = POINTER(MIB_IPINTERFACE_TABLE)

def get_ip_interface_table():
    pIfTable = PMIB_IPINTERFACE_TABLE()
    if not ctypes.windll.iphlpapi.GetIpInterfaceTable(socket.AF_INET, ctypes.byref(pIfTable)) == NO_ERROR:
        logging.error('Failed calling GetIpInterfaceTable')

    IfTableMib = pIfTable.contents

    Table = ctypes.cast(ctypes.pointer(IfTableMib.Table), POINTER(MIB_IPINTERFACE_ROW * IfTableMib.NumEntries)).contents
    for i in range(IfTableMib.NumEntries):
        tempstruc = MIB_IPINTERFACE_ROW()
        ctypes.pointer(tempstruc)[0] = Table[i]
        yield tempstruc
    ctypes.windll.iphlpapi.FreeMibTable(pIfTable)
#endregion
###############################################################################
#region GetAdaptersInfo

MAX_ADAPTER_NAME_LENGTH = 256
MAX_ADAPTER_DESCRIPTION_LENGTH = 128
MAX_ADAPTER_LENGTH = 8

MIB_IF_TYPE_ETHERNET = 6
MIB_IF_TYPE_LOOPBACK = 28
IF_TYPE_IEEE80211 = 71


class IP_ADDRESS_STRING(Structure):
    _fields_ = [
        ("String", c_char * 16),
    ]


class IP_MASK_STRING(Structure):
    _fields_ = [
        ("String", c_char * 16),
    ]


class IP_ADDR_STRING(Structure):
    pass


IP_ADDR_STRING._fields_ = [
    ("Next", POINTER(IP_ADDR_STRING)),
    ("IpAddress", IP_ADDRESS_STRING),
    ("IpMask", IP_MASK_STRING),
    ("Context", DWORD),
]


class IP_ADAPTER_INFO(Structure):
    pass


IP_ADAPTER_INFO._fields_ = [
    ("Next", POINTER(IP_ADAPTER_INFO)),
    ("ComboIndex", DWORD),
    ("AdapterName", c_char * (MAX_ADAPTER_NAME_LENGTH + 4)),
    ("Description", c_char * (MAX_ADAPTER_DESCRIPTION_LENGTH + 4)),
    ("AddressLength", UINT),
    ("Address", BYTE * MAX_ADAPTER_LENGTH),
    ("Index", DWORD),
    ("Type", UINT),
    ("DhcpEnabled", UINT),
    ("CurrentIpAddress", c_void_p),  # Not used
    ("IpAddressList", IP_ADDR_STRING),
    ("GatewayList", IP_ADDR_STRING),
    ("DhcpServer", IP_ADDR_STRING),
    ("HaveWins", BOOL),
    ("PrimaryWinsServer", IP_ADDR_STRING),
    ("SecondaryWinsServer", IP_ADDR_STRING),
    ("LeaseObtained", c_ulong),
    ("LeaseExpires", c_ulong),

]
###########################################################################
# The GetAdaptersInfo function retrieves adapter information for the local computer.
#
# On Windows XP and later:  Use the GetAdaptersAddresses function instead of GetAdaptersInfo.
#
# DWORD GetAdaptersInfo(
#   _Out_   PIP_ADAPTER_INFO pAdapterInfo,
#   _Inout_ PULONG           pOutBufLen
# );

def get_adapters_info():
    OutBufLen = DWORD(0)

    ctypes.windll.iphlpapi.GetAdaptersInfo(None, ctypes.byref(OutBufLen))

    AdapterInfo = ctypes.create_string_buffer(OutBufLen.value)
    pAdapterInfo = ctypes.cast(AdapterInfo, POINTER(IP_ADAPTER_INFO))

    if not ctypes.windll.iphlpapi.GetAdaptersInfo(ctypes.byref(AdapterInfo), ctypes.byref(OutBufLen)) == NO_ERROR:
        logging.error('Failed calling GetAdaptersInfo')
        return

    while pAdapterInfo:
        yield pAdapterInfo.contents
        pAdapterInfo = pAdapterInfo.contents.Next

#endregion
###########################################################################
