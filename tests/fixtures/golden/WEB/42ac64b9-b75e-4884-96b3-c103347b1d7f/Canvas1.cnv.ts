/*
 * Created by EcoStruxure Automation Expert.
 * User:    
 * Date: 10/2/2026
 * Time: 12:45 PM
 * 
 */
namespace WEB.Main.Canvases {

  export class Canvas1 extends NxtControl.GuiFramework.Canvas {

    /**
     * Type of an object (never change this)
     * @type String
     * @default
     */
    @System.DefaultValue('WEB.Main.Canvases.Canvas1')
    protected type: string;
    
	/// ************ DO NOT DELETE THIS METHOD !!!	******///	
    /**
     * Returns {@link WEB.Main.Canvas1} instance from an object representation
     * @static
     * @param {Object} object Object to create a symbol from
     * @return {WEB.Main.Canvas1} An instance of WEB.Main.Canvas1
     */
    static fromObject(element?: HTMLCanvasElement | string, options?: any): Canvas1 {
      return <Canvas1> new Canvas1(element, options);
    }
    
  } 
}
