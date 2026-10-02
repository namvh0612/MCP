# Function (POU)

An IEC 61131-3 function: inputs → one return value, no internal state, no events. File `IEC61499/POU/<Name>.fct` (`<POUType>`), `IEC61499Type=Function`.

- `<InterfaceList ReturnValueType="INT">` with input variables.
- `<POUBasicFunction>` holds `<TempVars>` and one `<Algorithm>` with ST code.
- Called from ST inside algorithms of Basic FBs or other functions: `x := HexToDecimal(hexString := s);`.
