/*
 * Created by EcoStruxure Automation Expert.
 * User:  
 * Date: 10/2/2026
 * Time: 12:43 PM
 * 
 */
using System;
using System.ComponentModel;
using System.Collections;
using System.Diagnostics;

using NxtControl.GuiFramework;

namespace HMI.Main.Canvases
{
	/// <summary>
	/// Summary description for Canvas1.
	/// </summary>
	partial class Canvas1
	{
		#region Component Designer generated code
		/// <summary>
		/// Required method for Designer support - do not modify
		/// the contents of this method with the code editor.
		/// </summary>
		private void InitializeComponent()
		{
			this.CAT1 = new HMI.Main.Symbols.catTest.sDefault();
			// 
			// CAT1
			// 
			this.CAT1.BeginInit();
			this.CAT1.DesignMatrix = new NxtControl.Drawing.Matrix2D(1D, 0D, 0D, 1D, 16D, 8D);
			this.CAT1.Name = "CAT1";
			this.CAT1.SecurityToken = ((uint)(4294967295u));
			this.CAT1.TagName = "3811CA558F6E3EFC";
			this.CAT1.EndInit();
			// 
			// Canvas1
			// 
			this.Bounds = new NxtControl.Drawing.RectF(((float)(0D)), ((float)(0D)), ((float)(1280D)), ((float)(730D)));
			this.Brush = new NxtControl.Drawing.Brush("CanvasBrush");
			this.Shapes.AddRange(new System.ComponentModel.IComponent[] {
			this.CAT1});
			this.Size = new System.Drawing.Size(1280, 730);

		}
		private HMI.Main.Symbols.catTest.sDefault CAT1;
		#endregion
	}
}
