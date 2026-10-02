<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE SubAppType SYSTEM "../LibraryElement.dtd">
<SubAppType GUID="91d2f282-497a-45f1-9546-44f837cd7868" Name="SubApp1" Comment="Extracted SubApplication Type" Namespace="Main">
  <Identification Standard="61499-2" />
  <VersionInfo Author=" " Date="10/1/2026" />
  <SubAppInterfaceList />
  <SubAppNetwork>
    <FB ID="DE02E0C43473026F" Name="FB1" Type="E_CYCLE" x="560" y="420" Namespace="IEC61499.Standard" />
    <FB ID="1B43F588E5733D9B" Name="FB2" Type="ADD_1990CFD1468AAE4A6" x="1260" y="420" Namespace="Main">
      <Attribute Name="Configuration.GenericFBType.InterfaceParams" Value="Runtime.Standard#CNT:=2;IN${CNT}:LREAL" />
    </FB>
    <EventConnections>
      <Connection Source="$DE02E0C43473026F.EO" Destination="$1B43F588E5733D9B.REQ" />
    </EventConnections>
  </SubAppNetwork>
</SubAppType>