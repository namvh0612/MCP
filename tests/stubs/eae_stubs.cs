// Compile-time stubs of the EAE runtime API, with the signatures EAE's own Designer code uses.
// Only for checking that generated C# compiles (tests/test_sa_hmi.py); not a runtime.
using System;
using System.Collections.Generic;
namespace System.Drawing { public enum FontStyle { Regular, Bold } public struct Size { public Size(int w, int h) {} } }
namespace System.Windows.Forms { public enum BorderStyle { None }
  public enum MessageBoxButtons { YesNo } public enum MessageBoxIcon { Question } public enum DialogResult { Yes, No }
  public static class MessageBox { public static DialogResult Show(string t, string c, MessageBoxButtons b, MessageBoxIcon i) { return DialogResult.Yes; } } }
namespace NxtControl.Drawing {
  public class Color { public Color(byte r, byte g, byte b) {} public Color(string n) {} }
  public class Brush { public Brush(Color c) {} public Brush(string n) {} }
  public enum DashStyle { Solid }
  public class Pen { public Pen(Color c, float w, DashStyle s) {} public Pen(string n) {} }
  public class Font { public Font(string f, float s, System.Drawing.FontStyle st) {} public Font(string n) {} }
  public struct RectF { public RectF(float x, float y, float w, float h) {} }
  public struct PointF { public PointF(double x, double y) {} }
  public struct SizeF { public SizeF(double w, double h) {} }
  public class Matrix2D { public Matrix2D(double a, double b, double c, double d, double e, double f) {} }
  public enum ContentAlignment { MiddleLeft, MiddleRight }
  public struct Padding { public Padding(int all) {} }
}
namespace NxtControl.GuiFramework {
  public class ValueChangedEventArgs : EventArgs { public object Value; }
  public enum NumberBase { Decimal }
  public class ShapeList { public void AddRange(System.ComponentModel.IComponent[] items) {} }
  public class Shape : System.ComponentModel.Component {
    public NxtControl.Drawing.RectF Bounds { get; set; } public NxtControl.Drawing.Brush Brush { get; set; }
    public NxtControl.Drawing.Pen Pen { get; set; } public NxtControl.Drawing.Font Font { get; set; }
    public string Name { get; set; } public bool Visible { get; set; } }
  public class Rectangle : Shape {}
  public class Ellipse : Shape {}
  public class Polygon : Shape { public bool Closed { get; set; } public List<NxtControl.Drawing.PointF> Points = new List<NxtControl.Drawing.PointF>(); }
  public class Line : Shape { public NxtControl.Drawing.PointF StartPoint { get; set; } public NxtControl.Drawing.PointF EndPoint { get; set; } }
  public class FreeText : Shape { public NxtControl.Drawing.Color Color { get; set; } public NxtControl.Drawing.PointF Location { get; set; } public string Text { get; set; } }
  public class Label : Shape { public bool AngleIgnore { get; set; } public System.Windows.Forms.BorderStyle BorderStyle { get; set; }
    public bool FontScale { get; set; } public string Text { get; set; } public NxtControl.Drawing.ContentAlignment TextAlignment { get; set; }
    public int TextAutoSizeHorizontalOffset { get; set; } public NxtControl.Drawing.Color TextColor { get; set; }
    public NxtControl.Drawing.Padding TextPadding { get; set; } }
  public class DrawnButton : Shape { public NxtControl.Drawing.Color InnerBorderColor { get; set; } public double Radius { get; set; }
    public string Text { get; set; } public NxtControl.Drawing.Color TextColor { get; set; }
    public NxtControl.Drawing.Color TextColorMouseDown { get; set; } public bool Use3DEffect { get; set; } public event EventHandler Click; }
  public class HMISymbol { public ShapeList Shapes = new ShapeList(); public System.Drawing.Size SymbolSize { get; set; } }
}
namespace System.HMI.Symbols.Base {
  public class Accessor<T> : NxtControl.GuiFramework.Shape {
    public void BeginInit() {} public void EndInit() {}
    public NxtControl.Drawing.Matrix2D DesignMatrix { get; set; } public bool IsOnlyInput { get; set; }
    public string TagName { get; set; } public T Value { get; set; } }
  public class TextBox<T> : Accessor<T> { public bool IgnoreMouseEvents { get; set; } public bool IsPrefixSuffixOutside { get; set; }
    public NxtControl.GuiFramework.NumberBase NumberBase { get; set; } public NxtControl.Drawing.ContentAlignment TextAlignment { get; set; } }
  public class Label : Accessor<string> { public System.Windows.Forms.BorderStyle BorderStyle { get; set; } public bool FontScale { get; set; } }
  public class Execute<T> : Accessor<T> { public NxtControl.Drawing.PointF Location { get; set; } public NxtControl.Drawing.SizeF Size { get; set; }
    public event EventHandler<NxtControl.GuiFramework.ValueChangedEventArgs> ValueChanged; }
}
