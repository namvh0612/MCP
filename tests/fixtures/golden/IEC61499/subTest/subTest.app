<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE SubAppType SYSTEM "../LibraryElement.dtd">
<SubAppType GUID="2ab32ec2-8f9d-4bb0-98cf-93b20a39cc39" Name="subTest" Format="2.0" Comment="Subapplication " Namespace="Main">
  <Identification Standard="61499-2" />
  <VersionInfo Organization="Schneider Electric" Version="0.0" Author=" " Date="10/1/2026" Remarks="template" />
  <SubAppInterfaceList>
    <SubAppEventInputs>
      <SubAppEvent ID="5D18ED6AA8AB522A" Name="START" />
    </SubAppEventInputs>
    <SubAppEventOutputs>
      <SubAppEvent ID="70B4078AD3C04108" Name="EO" />
    </SubAppEventOutputs>
  </SubAppInterfaceList>
  <SubAppNetwork>
    <FB ID="95F38226A67B5297" Name="FB1" Type="E_DELAY" x="2020" y="1040" Namespace="IEC61499.Standard" />
    <FB ID="2ABDFE936E8CC5E2" Name="FB2" Type="E_PERMIT" x="2580" y="1040" Namespace="IEC61499.Standard" />
    <EventConnections>
      <Connection Source="$95F38226A67B5297.EO" Destination="$2ABDFE936E8CC5E2.EI" />
      <Connection Source="$5D18ED6AA8AB522A" Destination="$95F38226A67B5297.START" />
      <Connection Source="$2ABDFE936E8CC5E2.EO" Destination="$70B4078AD3C04108" />
    </EventConnections>
    <Input ID="5D18ED6AA8AB522A" Name="START" x="1286.073" y="1052" Type="Event" />
    <Output ID="70B4078AD3C04108" Name="EO" x="3265.177" y="1052" Type="Event" />
  </SubAppNetwork>
</SubAppType>