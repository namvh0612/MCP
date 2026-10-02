/*
 * Created by EcoStruxure Automation Expert.
 * User:  
 * Date: 10/2/2026
 * Time: 11:34 AM
 * 
 */
using System;
using System.ComponentModel;
using System.Collections;
using NxtControl.GuiFramework;

namespace HMI.Main.Symbols.catTest
{
	/// <summary>
	/// Summary description for sDefault.
	/// </summary>
	partial class sDefault
	{

		#region Component Designer generated code
		/// <summary>
		/// Required method for Designer support - do not modify
		/// the contents of this method with the code editor.
		/// </summary>
		private void InitializeComponent()
		{
			this.rectangle1 = new NxtControl.GuiFramework.Rectangle();
			this.label1 = new NxtControl.GuiFramework.Label();
			this.OUT1 = new System.HMI.Symbols.Base.BarValueHorizontal<short>();
			// 
			// rectangle1
			// 
			this.rectangle1.Bounds = new NxtControl.Drawing.RectF(((float)(24D)), ((float)(16D)), ((float)(136D)), ((float)(88D)));
			this.rectangle1.Font = new NxtControl.Drawing.Font("HMI Sans Serif", 9F, System.Drawing.FontStyle.Regular);
			this.rectangle1.Name = "rectangle1";
			// 
			// label1
			// 
			this.label1.AngleIgnore = true;
			this.label1.BorderStyle = System.Windows.Forms.BorderStyle.None;
			this.label1.Bounds = new NxtControl.Drawing.RectF(((float)(24D)), ((float)(120D)), ((float)(152D)), ((float)(26D)));
			this.label1.Brush = new NxtControl.Drawing.Brush("LabelBrush");
			this.label1.Font = new NxtControl.Drawing.Font("LabelFont");
			this.label1.FontScale = true;
			this.label1.Name = "label1";
			this.label1.Pen = new NxtControl.Drawing.Pen("LabelPen");
			this.label1.Text = "Label";
			this.label1.TextAlignment = NxtControl.Drawing.ContentAlignment.MiddleLeft;
			this.label1.TextAutoSizeHorizontalOffset = 10;
			this.label1.TextColor = new NxtControl.Drawing.Color("LabelTextColor");
			this.label1.TextPadding = new NxtControl.Drawing.Padding(2);
			// 
			// OUT1
			// 
			this.OUT1.BeginInit();
			this.OUT1.Brush = new NxtControl.Drawing.Brush("TrackerBrush");
			this.OUT1.DesignMatrix = new NxtControl.Drawing.Matrix2D(0.64D, 0D, 0D, 1D, 16D, 144D);
			this.OUT1.Font = new NxtControl.Drawing.Font("TrackerFont");
			this.OUT1.IsOnlyInput = true;
			this.OUT1.Maximum = ((short)(100));
			this.OUT1.MaximumTag = null;
			this.OUT1.Minimum = ((short)(0));
			this.OUT1.MinimumTag = null;
			this.OUT1.MouseMoveValueThreshold = 0D;
			this.OUT1.Name = "OUT1";
			this.OUT1.Pen = new NxtControl.Drawing.Pen("TrackerPen");
			this.OUT1.Radius = 20D;
			this.OUT1.TagName = "OUT1";
			this.OUT1.TickLength = 5;
			this.OUT1.Value = ((short)(0));
			this.OUT1.ValueFont = new NxtControl.Drawing.Font("TrackerValueFont");
			this.OUT1.EndInit();
			// 
			// sDefault
			// 
			this.Shapes.AddRange(new System.ComponentModel.IComponent[] {
			this.rectangle1,
			this.label1,
			this.OUT1});
			this.SymbolSize = new System.Drawing.Size(600, 400);

		}
		private NxtControl.GuiFramework.Rectangle rectangle1;
		private NxtControl.GuiFramework.Label label1;
		private System.HMI.Symbols.Base.BarValueHorizontal<short> OUT1;
		#endregion
	}
}
