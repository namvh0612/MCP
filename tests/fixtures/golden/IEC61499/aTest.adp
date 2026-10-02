<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE AdapterType SYSTEM "../LibraryElement.dtd">
<AdapterType GUID="5713df17-c756-4713-bab9-31811dc314ef" Name="aTest" Comment="Adapter Interface" Namespace="Main">
  <Identification Standard="61499-1" />
  <VersionInfo Organization="Schneider Electric" Version="0.0" Author=" " Date="10/1/2026" />
  <InterfaceList>
    <EventInputs>
      <Event ID="A739E1BFF2B9B7CE" Name="REQ" Comment="Request from Socket">
        <With Var="ReqValue" />
      </Event>
    </EventInputs>
    <EventOutputs>
      <Event ID="F424BC6D802B49A6" Name="CNF" Comment="Confirmation from Plug">
        <With Var="CnfValue" />
      </Event>
    </EventOutputs>
    <InputVars>
      <VarDeclaration ID="6854D6B5FCEAD707" Name="ReqValue" Type="INT" />
    </InputVars>
    <OutputVars>
      <VarDeclaration ID="FE3EB2BC91B9E5E2" Name="CnfValue" Type="INT" />
    </OutputVars>
  </InterfaceList>
  <Service RightInterface="PLUG" LeftInterface="SOCKET">
    <ServiceSequence Name="request_confirm">
      <ServiceTransaction>
        <InputPrimitive Interface="SOCKET" Event="REQ" Parameters="REQD" />
        <OutputPrimitive Interface="PLUG" Event="REQ" Parameters="REQD" />
      </ServiceTransaction>
      <ServiceTransaction>
        <InputPrimitive Interface="PLUG" Event="CNF" Parameters="CNFD" />
        <OutputPrimitive Interface="SOCKET" Event="CNF" Parameters="CNFD" />
      </ServiceTransaction>
    </ServiceSequence>
    <ServiceSequence Name="indication_response">
      <ServiceTransaction>
        <InputPrimitive Interface="PLUG" Event="IND" Parameters="INDD" />
        <OutputPrimitive Interface="SOCKET" Event="IND" Parameters="INDD" />
      </ServiceTransaction>
      <ServiceTransaction>
        <InputPrimitive Interface="SOCKET" Event="RSP" Parameters="RSPD" />
        <OutputPrimitive Interface="PLUG" Event="RSP" Parameters="RSPD" />
      </ServiceTransaction>
    </ServiceSequence>
  </Service>
</AdapterType>