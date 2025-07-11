unit UnitPuntoVenta;

interface

uses
  System.SysUtils, System.Types, System.UITypes, System.Classes, System.Variants,
  FMX.Types, FMX.Controls, FMX.Forms, FMX.Graphics, FMX.Dialogs,
  System.Rtti, FMX.Grid.Style, FMX.Grid, FMX.ScrollBox,
  FMX.Edit, FMX.StdCtrls, FMX.Controls.Presentation, DataModule,
  System.Net.HttpClient, System.Net.HttpClientComponent, System.JSON, 
  System.net.URLClient, System.Generics.Collections, FMX.Ani, FMX.Objects, 
  FMX.Effects, FMX.DialogService, System.Threading, FMX.ListBox, FMX.Layouts, 
  FMX.ComboEdit, FMX.Memo.Types, FMX.Memo, System.DateUtils;

type
  TToastTipo = (Success, Info, Error);
  
  TProductoVenta = record
    IdProductoVariante: string;
    Sku: string;
    Nombre: string;
    PrecioUnitario: Double;
    Cantidad: Double;
    DescuentoLinea: Double;
    TotalLinea: Double;
    CodigoBarras: string;
  end;

type
  TFormPuntoVenta = class(TForm)
    // === LAYOUT PRINCIPAL ===
    LayoutPrincipal: TLayout;
    LayoutIzquierdo: TLayout;
    LayoutDerecho: TLayout;
    
    // === INFORMACIÓN DE VENTA ===
    GroupBoxVenta: TGroupBox;
    LblTerminal: TLabel;
    EditTerminal: TEdit;
    LblVendedor: TLabel;
    EditVendedor: TEdit;
    LblFecha: TLabel;
    EditFecha: TEdit;
    LblNumeroFolio: TLabel;
    EditNumeroFolio: TEdit;
    
    // === CLIENTE ===
    GroupBoxCliente: TGroupBox;
    LblCliente: TLabel;
    EditCliente: TEdit;
    BtnSeleccionarCliente: TButton;
    BtnClienteRapido: TButton;
    
    // === BÚSQUEDA DE PRODUCTOS ===
    GroupBoxBusqueda: TGroupBox;
    LblBuscarProducto: TLabel;
    EditBuscarProducto: TEdit;
    BtnBuscarProducto: TButton;
    BtnSeleccionarProducto: TButton;
    
    // === GRID DE PRODUCTOS EN VENTA ===
    GroupBoxProductos: TGroupBox;
    StringGridProductos: TStringGrid;
    ColSku: TStringColumn;
    ColNombre: TStringColumn;
    ColCantidad: TStringColumn;
    ColPrecio: TStringColumn;
    ColDescuento: TStringColumn;
    ColTotal: TStringColumn;
    ColAcciones: TStringColumn;
    
    // === BOTONES DE ACCIÓN DE PRODUCTOS ===
    LayoutAccionesProductos: TLayout;
    BtnEliminarLinea: TButton;
    BtnModificarCantidad: TButton;
    BtnAplicarDescuento: TButton;
    BtnLimpiarVenta: TButton;
    
    // === TOTALES ===
    GroupBoxTotales: TGroupBox;
    LblSubtotal: TLabel;
    EditSubtotal: TEdit;
    LblDescuentoGeneral: TLabel;
    EditDescuentoGeneral: TEdit;
    BtnAplicarDescuentoGeneral: TButton;
    LblImpuestos: TLabel;
    EditImpuestos: TEdit;
    LblTotal: TLabel;
    EditTotal: TEdit;
    
    // === FORMAS DE PAGO ===
    GroupBoxPagos: TGroupBox;
    LblFormaPago: TLabel;
    ComboFormaPago: TComboBox;
    LblMontoPago: TLabel;
    EditMontoPago: TEdit;
    BtnAgregarPago: TButton;
    
    // === GRID DE PAGOS ===
    StringGridPagos: TStringGrid;
    ColFormaPago: TStringColumn;
    ColMonto: TStringColumn;
    ColReferencia: TStringColumn;
    ColEliminarPago: TStringColumn;
    
    // === BOTONES PRINCIPALES ===
    LayoutBotonesPrincipales: TLayout;
    BtnFinalizarVenta: TButton;
    BtnCancelarVenta: TButton;
    BtnNuevaVenta: TButton;
    BtnConsultarVentas: TButton;
    
    // === SISTEMA DE TOAST ===
    RecToast: TRectangle;
    LblToast: TLabel;
    FloatAnimationToast: TFloatAnimation;
    ShadowEffect1: TShadowEffect;
    
    // === EVENTOS ===
    procedure FormCreate(Sender: TObject);
    procedure FormShow(Sender: TObject);
    procedure EditBuscarProductoKeyDown(Sender: TObject; var Key: Word; var KeyChar: Char; Shift: TShiftState);
    procedure BtnBuscarProductoClick(Sender: TObject);
    procedure BtnSeleccionarProductoClick(Sender: TObject);
    procedure BtnSeleccionarClienteClick(Sender: TObject);
    procedure BtnClienteRapidoClick(Sender: TObject);
    procedure BtnEliminarLineaClick(Sender: TObject);
    procedure BtnModificarCantidadClick(Sender: TObject);
    procedure BtnAplicarDescuentoClick(Sender: TObject);
    procedure BtnLimpiarVentaClick(Sender: TObject);
    procedure BtnAplicarDescuentoGeneralClick(Sender: TObject);
    procedure BtnAgregarPagoClick(Sender: TObject);
    procedure BtnFinalizarVentaClick(Sender: TObject);
    procedure BtnCancelarVentaClick(Sender: TObject);
    procedure BtnNuevaVentaClick(Sender: TObject);
    procedure BtnConsultarVentasClick(Sender: TObject);
    procedure StringGridProductosCellDblClick(const Column: TColumn; const Row: Integer);
    procedure StringGridPagosCellDblClick(const Column: TColumn; const Row: Integer);
    procedure EditMontoPagoKeyDown(Sender: TObject; var Key: Word; var KeyChar: Char; Shift: TShiftState);
    
  private
    // === VARIABLES DE ESTADO ===
    FIdClienteSeleccionado: string;
    FIdTerminal: string;
    FIdVendedor: string;
    FNumeroFolio: string;
    FProductosVenta: TArray<TProductoVenta>;
    FFormasPago: TJSONArray;
    FPagosVenta: TJSONArray;
    FSubtotal: Double;
    FDescuentoGeneral: Double;
    FImpuestos: Double;
    FTotal: Double;
    
    // === MÉTODOS PRIVADOS ===
    procedure ConfigurarInterfaz;
    procedure InicializarVenta;
    procedure CargarFormasPago;
    procedure BuscarProductoPorCodigo(const Codigo: string);
    procedure AgregarProductoAVenta(ProductoJson: TJSONObject; Cantidad: Double = 1);
    procedure ActualizarGridProductos;
    procedure ActualizarGridPagos;
    procedure CalcularTotales;
    procedure LimpiarVenta;
    procedure ValidarYFinalizarVenta;
    procedure GuardarVenta;
    procedure MostrarToast(const Mensaje: string; Tipo: TToastTipo = TToastTipo.Info);
    function GenerarNumeroFolio: string;
    function ValidarDatosVenta: Boolean;
    function ObtenerJsonVenta: TJSONObject;
    function ObtenerJsonDetalles: TJSONArray;
    function ObtenerJsonPagos: TJSONArray;
    
  public
    property IdTerminal: string read FIdTerminal write FIdTerminal;
    property IdVendedor: string read FIdVendedor write FIdVendedor;
    
  end;

var
  FormPuntoVenta: TFormPuntoVenta;
  API_BASE_URL: string;

implementation

uses UnitSeleccionCliente, UnitSeleccionProducto, UnitConsultaVentas;

{$R *.fmx}

procedure TFormPuntoVenta.FormCreate(Sender: TObject);
begin
  API_BASE_URL := DM.GetApiBaseUrl;
  
  // Inicializar variables
  FIdClienteSeleccionado := '';
  FIdTerminal := '';
  FIdVendedor := '';
  FNumeroFolio := '';
  SetLength(FProductosVenta, 0);
  FFormasPago := nil;
  FPagosVenta := TJSONArray.Create;
  FSubtotal := 0;
  FDescuentoGeneral := 0;
  FImpuestos := 0;
  FTotal := 0;
  
  ConfigurarInterfaz;
  CargarFormasPago;
end;

procedure TFormPuntoVenta.FormShow(Sender: TObject);
begin
  InicializarVenta;
  EditBuscarProducto.SetFocus;
end;

procedure TFormPuntoVenta.ConfigurarInterfaz;
begin
  // === CONFIGURAR LAYOUT PRINCIPAL ===
  with LayoutPrincipal do
  begin
    Align := TAlignLayout.Client;
    Padding.Left := 10;
    Padding.Right := 10;
    Padding.Top := 10;
    Padding.Bottom := 10;
  end;
  
  // === LAYOUT IZQUIERDO (60%) ===
  with LayoutIzquierdo do
  begin
    Align := TAlignLayout.Left;
    Width := Self.Width * 0.60;
    Padding.Right := 5;
  end;
  
  // === LAYOUT DERECHO (40%) ===
  with LayoutDerecho do
  begin
    Align := TAlignLayout.Client;
    Padding.Left := 5;
  end;
  
  // === CONFIGURAR INFORMACIÓN DE VENTA ===
  with GroupBoxVenta do
  begin
    Parent := LayoutDerecho;
    Align := TAlignLayout.Top;
    Height := 120;
    Text := 'Información de Venta';
    Margins.Bottom := 10;
  end;
  
  EditTerminal.ReadOnly := True;
  EditVendedor.ReadOnly := True;
  EditFecha.ReadOnly := True;
  EditNumeroFolio.ReadOnly := True;
  
  // === CONFIGURAR CLIENTE ===
  with GroupBoxCliente do
  begin
    Parent := LayoutDerecho;
    Align := TAlignLayout.Top;
    Height := 80;
    Text := 'Cliente';
    Margins.Bottom := 10;
  end;
  
  EditCliente.ReadOnly := True;
  EditCliente.TextPrompt := 'Seleccionar cliente...';
  
  with BtnSeleccionarCliente do
  begin
    Text := 'Seleccionar';
    Width := 80;
    Align := TAlignLayout.Right;
  end;
  
  with BtnClienteRapido do
  begin
    Text := 'Rápido';
    Width := 60;
    Align := TAlignLayout.Right;
    Margins.Right := 5;
  end;
  
  // === CONFIGURAR BÚSQUEDA DE PRODUCTOS ===
  with GroupBoxBusqueda do
  begin
    Parent := LayoutIzquierdo;
    Align := TAlignLayout.Top;
    Height := 80;
    Text := 'Buscar Producto';
    Margins.Bottom := 10;
  end;
  
  EditBuscarProducto.TextPrompt := 'Código de barras, SKU o nombre...';
  
  with BtnBuscarProducto do
  begin
    Text := 'Buscar';
    Width := 70;
    Align := TAlignLayout.Right;
  end;
  
  with BtnSeleccionarProducto do
  begin
    Text := 'Catálogo';
    Width := 70;
    Align := TAlignLayout.Right;
    Margins.Right := 5;
  end;
  
  // === CONFIGURAR GRID DE PRODUCTOS ===
  with GroupBoxProductos do
  begin
    Parent := LayoutIzquierdo;
    Align := TAlignLayout.Client;
    Text := 'Productos en Venta';
    Margins.Bottom := 10;
  end;
  
  StringGridProductos.BeginUpdate;
  try
    StringGridProductos.Parent := GroupBoxProductos;
    StringGridProductos.Align := TAlignLayout.Client;
    StringGridProductos.Margins.Top := 25;
    StringGridProductos.Margins.Bottom := 50;
    StringGridProductos.RowCount := 0;
    
    ColSku.Header := 'SKU';
    ColSku.Width := 100;
    ColNombre.Header := 'Producto';
    ColNombre.Width := 200;
    ColCantidad.Header := 'Cant.';
    ColCantidad.Width := 60;
    ColPrecio.Header := 'Precio';
    ColPrecio.Width := 80;
    ColDescuento.Header := 'Desc.';
    ColDescuento.Width := 60;
    ColTotal.Header := 'Total';
    ColTotal.Width := 80;
    ColAcciones.Header := 'Acción';
    ColAcciones.Width := 60;
  finally
    StringGridProductos.EndUpdate;
  end;
  
  // === CONFIGURAR BOTONES DE ACCIÓN ===
  with LayoutAccionesProductos do
  begin
    Parent := GroupBoxProductos;
    Align := TAlignLayout.Bottom;
    Height := 40;
    Padding.Top := 5;
  end;
  
  with BtnEliminarLinea do
  begin
    Parent := LayoutAccionesProductos;
    Text := 'Eliminar';
    Width := 80;
    Align := TAlignLayout.Left;
  end;
  
  with BtnModificarCantidad do
  begin
    Parent := LayoutAccionesProductos;
    Text := 'Cantidad';
    Width := 80;
    Align := TAlignLayout.Left;
    Margins.Left := 5;
  end;
  
  with BtnAplicarDescuento do
  begin
    Parent := LayoutAccionesProductos;
    Text := 'Descuento';
    Width := 80;
    Align := TAlignLayout.Left;
    Margins.Left := 5;
  end;
  
  with BtnLimpiarVenta do
  begin
    Parent := LayoutAccionesProductos;
    Text := 'Limpiar Todo';
    Width := 100;
    Align := TAlignLayout.Right;
  end;
  
  // === CONFIGURAR TOTALES ===
  with GroupBoxTotales do
  begin
    Parent := LayoutDerecho;
    Align := TAlignLayout.Top;
    Height := 140;
    Text := 'Totales';
    Margins.Bottom := 10;
  end;
  
  EditSubtotal.ReadOnly := True;
  EditDescuentoGeneral.TextPrompt := '0.00';
  EditImpuestos.ReadOnly := True;
  EditTotal.ReadOnly := True;
  
  // === CONFIGURAR FORMAS DE PAGO ===
  with GroupBoxPagos do
  begin
    Parent := LayoutDerecho;
    Align := TAlignLayout.Top;
    Height := 200;
    Text := 'Formas de Pago';
    Margins.Bottom := 10;
  end;
  
  EditMontoPago.TextPrompt := '0.00';
  
  with BtnAgregarPago do
  begin
    Text := 'Agregar';
    Width := 80;
    Align := TAlignLayout.Right;
  end;
  
  // === CONFIGURAR GRID DE PAGOS ===
  StringGridPagos.BeginUpdate;
  try
    StringGridPagos.Parent := GroupBoxPagos;
    StringGridPagos.Align := TAlignLayout.Client;
    StringGridPagos.Margins.Top := 80;
    StringGridPagos.Margins.Bottom := 5;
    StringGridPagos.RowCount := 0;
    
    ColFormaPago.Header := 'Forma de Pago';
    ColFormaPago.Width := 120;
    ColMonto.Header := 'Monto';
    ColMonto.Width := 80;
    ColReferencia.Header := 'Referencia';
    ColReferencia.Width := 100;
    ColEliminarPago.Header := 'Eliminar';
    ColEliminarPago.Width := 60;
  finally
    StringGridPagos.EndUpdate;
  end;
  
  // === CONFIGURAR BOTONES PRINCIPALES ===
  with LayoutBotonesPrincipales do
  begin
    Parent := LayoutDerecho;
    Align := TAlignLayout.Bottom;
    Height := 100;
    Padding.Top := 10;
  end;
  
  with BtnFinalizarVenta do
  begin
    Parent := LayoutBotonesPrincipales;
    Text := 'FINALIZAR VENTA';
    Height := 40;
    Align := TAlignLayout.Top;
    Margins.Bottom := 5;
    StyleLookup := 'acceptbuttonstyle';
  end;
  
  with BtnCancelarVenta do
  begin
    Parent := LayoutBotonesPrincipales;
    Text := 'Cancelar';
    Width := 80;
    Height := 35;
    Align := TAlignLayout.Left;
  end;
  
  with BtnNuevaVenta do
  begin
    Parent := LayoutBotonesPrincipales;
    Text := 'Nueva';
    Width := 80;
    Height := 35;
    Align := TAlignLayout.Left;
    Margins.Left := 5;
  end;
  
  with BtnConsultarVentas do
  begin
    Parent := LayoutBotonesPrincipales;
    Text := 'Consultar';
    Width := 80;
    Height := 35;
    Align := TAlignLayout.Right;
  end;
  
  // === CONFIGURAR SISTEMA DE TOAST ===
  with RecToast do
  begin
    Align := TAlignLayout.Bottom;
    Height := 50;
    Margins.Bottom := 10;
    Padding.Left := 20;
    Padding.Right := 20;
    Opacity := 0;
    Visible := False;
    Fill.Color := $FF323232;
    Stroke.Kind := TBrushKind.None;
    XRadius := 12;
    YRadius := 12;
    
    with ShadowEffect1 do
    begin
      Enabled := True;
      ShadowColor := TAlphaColorRec.Black;
      Opacity := 0.4;
      Softness := 0.6;
      Direction := 270;
      Distance := 6;
    end;
  end;
  
  with LblToast do
  begin
    Parent := RecToast;
    StyledSettings := [];
    Align := TAlignLayout.Client;
    TextSettings.Font.Size := 14;
    TextSettings.FontColor := TAlphaColors.White;
    TextSettings.HorzAlign := TTextAlign.Center;
    TextSettings.VertAlign := TTextAlign.Center;
  end;
end;

procedure TFormPuntoVenta.InicializarVenta;
begin
  // Configurar información básica
  EditTerminal.Text := 'Terminal 001'; // TODO: Obtener de configuración
  EditVendedor.Text := 'Vendedor Actual'; // TODO: Obtener del usuario logueado
  EditFecha.Text := FormatDateTime('dd/mm/yyyy hh:nn', Now);
  EditNumeroFolio.Text := GenerarNumeroFolio;
  
  // Limpiar datos
  FIdClienteSeleccionado := '';
  EditCliente.Text := 'CONSUMIDOR FINAL';
  
  LimpiarVenta;
end;

procedure TFormPuntoVenta.CargarFormasPago;
var
  Http: TNetHTTPClient;
  Response: IHTTPResponse;
  JsonResponse: TJSONObject;
  JsonData: TJSONArray;
  i: Integer;
  FormaPago: TJSONObject;
begin
  Http := TNetHTTPClient.Create(nil);
  try
    try
      Response := Http.Get(API_BASE_URL + '/formas_pago/', DM.GetHeaders);
      
      if Response.StatusCode = 200 then
      begin
        JsonResponse := TJSONObject.ParseJSONValue(Response.ContentAsString) as TJSONObject;
        try
          if JsonResponse.GetValue<Boolean>('success') then
          begin
            JsonData := JsonResponse.GetValue<TJSONArray>('data');
            
            ComboFormaPago.Items.Clear;
            ComboFormaPago.Items.BeginUpdate;
            try
              for i := 0 to JsonData.Count - 1 do
              begin
                FormaPago := JsonData.Items[i] as TJSONObject;
                ComboFormaPago.Items.Add(FormaPago.GetValue<string>('nombre'));
              end;
              
              FFormasPago := JsonData.Clone as TJSONArray;
              
              if ComboFormaPago.Items.Count > 0 then
                ComboFormaPago.ItemIndex := 0;
                
            finally
              ComboFormaPago.Items.EndUpdate;
            end;
          end;
        finally
          JsonResponse.Free;
        end;
      end;
    except
      on E: Exception do
        MostrarToast('Error al cargar formas de pago: ' + E.Message, Error);
    end;
  finally
    Http.Free;
  end;
end;

procedure TFormPuntoVenta.EditBuscarProductoKeyDown(Sender: TObject; var Key: Word; var KeyChar: Char; Shift: TShiftState);
begin
  if Key = vkReturn then
  begin
    BuscarProductoPorCodigo(EditBuscarProducto.Text.Trim);
    Key := 0;
  end;
end;

procedure TFormPuntoVenta.BuscarProductoPorCodigo(const Codigo: string);
var
  Http: TNetHTTPClient;
  Response: IHTTPResponse;
  JsonResponse: TJSONObject;
  JsonData: TJSONArray;
  Producto: TJSONObject;
  Url: string;
begin
  if Codigo.Trim = '' then
  begin
    MostrarToast('Ingresa un código para buscar', Info);
    Exit;
  end;
  
  Http := TNetHTTPClient.Create(nil);
  try
    try
      // Buscar por código de barras o SKU
      Url := API_BASE_URL + '/variantes/?expandir=true&sku_variante=' + TNetEncoding.URL.Encode(Codigo);
      Response := Http.Get(Url, DM.GetHeaders);
      
      if Response.StatusCode = 200 then
      begin
        JsonResponse := TJSONObject.ParseJSONValue(Response.ContentAsString) as TJSONObject;
        try
          if JsonResponse.GetValue<Boolean>('success') then
          begin
            JsonData := JsonResponse.GetValue<TJSONArray>('data');
            
            if JsonData.Count > 0 then
            begin
              Producto := JsonData.Items[0] as TJSONObject;
              AgregarProductoAVenta(Producto);
              EditBuscarProducto.Text := '';
              EditBuscarProducto.SetFocus;
            end
            else
            begin
              // Buscar por código de barras si no se encontró por SKU
              Url := API_BASE_URL + '/variantes/?expandir=true&codigo_barras_var=' + TNetEncoding.URL.Encode(Codigo);
              Response := Http.Get(Url, DM.GetHeaders);
              
              if Response.StatusCode = 200 then
              begin
                JsonResponse.Free;
                JsonResponse := TJSONObject.ParseJSONValue(Response.ContentAsString) as TJSONObject;
                
                if JsonResponse.GetValue<Boolean>('success') then
                begin
                  JsonData := JsonResponse.GetValue<TJSONArray>('data');
                  
                  if JsonData.Count > 0 then
                  begin
                    Producto := JsonData.Items[0] as TJSONObject;
                    AgregarProductoAVenta(Producto);
                    EditBuscarProducto.Text := '';
                    EditBuscarProducto.SetFocus;
                  end
                  else
                    MostrarToast('Producto no encontrado: ' + Codigo, Error);
                end;
              end;
            end;
          end;
        finally
          JsonResponse.Free;
        end;
      end;
      
    except
      on E: Exception do
        MostrarToast('Error al buscar producto: ' + E.Message, Error);
    end;
  finally
    Http.Free;
  end;
end;

procedure TFormPuntoVenta.AgregarProductoAVenta(ProductoJson: TJSONObject; Cantidad: Double = 1);
var
  ProductoVenta: TProductoVenta;
  i: Integer;
  Encontrado: Boolean;
begin
  try
    // Verificar si el producto ya está en la venta
    Encontrado := False;
    for i := 0 to High(FProductosVenta) do
    begin
      if FProductosVenta[i].IdProductoVariante = ProductoJson.GetValue<string>('id_producto_variante') then
      begin
        // Aumentar cantidad del producto existente
        FProductosVenta[i].Cantidad := FProductosVenta[i].Cantidad + Cantidad;
        FProductosVenta[i].TotalLinea := FProductosVenta[i].Cantidad * FProductosVenta[i].PrecioUnitario - FProductosVenta[i].DescuentoLinea;
        Encontrado := True;
        Break;
      end;
    end;
    
    if not Encontrado then
    begin
      // Agregar nuevo producto
      ProductoVenta.IdProductoVariante := ProductoJson.GetValue<string>('id_producto_variante');
      ProductoVenta.Sku := ProductoJson.GetValue<string>('sku_variante');
      ProductoVenta.CodigoBarras := ProductoJson.GetValue<string>('codigo_barras_var', '');
      
      // Obtener nombre del producto padre
      if ProductoJson.Contains('producto') then
      begin
        var ProductoPadre := ProductoJson.GetValue<TJSONObject>('producto');
        ProductoVenta.Nombre := ProductoPadre.GetValue<string>('nombre');
      end
      else
        ProductoVenta.Nombre := 'Producto';
        
      ProductoVenta.PrecioUnitario := ProductoJson.GetValue<Double>('precio');
      ProductoVenta.Cantidad := Cantidad;
      ProductoVenta.DescuentoLinea := 0;
      ProductoVenta.TotalLinea := Cantidad * ProductoVenta.PrecioUnitario;
      
      // Agregar al array
      SetLength(FProductosVenta, Length(FProductosVenta) + 1);
      FProductosVenta[High(FProductosVenta)] := ProductoVenta;
    end;
    
    ActualizarGridProductos;
    CalcularTotales;
    MostrarToast('Producto agregado a la venta', Success);
    
  except
    on E: Exception do
      MostrarToast('Error al agregar producto: ' + E.Message, Error);
  end;
end;

procedure TFormPuntoVenta.ActualizarGridProductos;
var
  i: Integer;
begin
  StringGridProductos.BeginUpdate;
  try
    StringGridProductos.RowCount := Length(FProductosVenta);
    
    for i := 0 to High(FProductosVenta) do
    begin
      StringGridProductos.Cells[0, i] := FProductosVenta[i].Sku;
      StringGridProductos.Cells[1, i] := FProductosVenta[i].Nombre;
      StringGridProductos.Cells[2, i] := FormatFloat('#,##0.00', FProductosVenta[i].Cantidad);
      StringGridProductos.Cells[3, i] := FormatFloat('$#,##0.00', FProductosVenta[i].PrecioUnitario);
      StringGridProductos.Cells[4, i] := FormatFloat('$#,##0.00', FProductosVenta[i].DescuentoLinea);
      StringGridProductos.Cells[5, i] := FormatFloat('$#,##0.00', FProductosVenta[i].TotalLinea);
      StringGridProductos.Cells[6, i] := 'Eliminar';
    end;
  finally
    StringGridProductos.EndUpdate;
  end;
end;

procedure TFormPuntoVenta.ActualizarGridPagos;
var
  i: Integer;
  Pago: TJSONObject;
begin
  StringGridPagos.BeginUpdate;
  try
    StringGridPagos.RowCount := FPagosVenta.Count;
    
    for i := 0 to FPagosVenta.Count - 1 do
    begin
      Pago := FPagosVenta.Items[i] as TJSONObject;
      StringGridPagos.Cells[0, i] := Pago.GetValue<string>('forma_pago');
      StringGridPagos.Cells[1, i] := FormatFloat('$#,##0.00', Pago.GetValue<Double>('monto'));
      StringGridPagos.Cells[2, i] := Pago.GetValue<string>('referencia', '');
      StringGridPagos.Cells[3, i] := 'X';
    end;
  finally
    StringGridPagos.EndUpdate;
  end;
end;

procedure TFormPuntoVenta.CalcularTotales;
var
  i: Integer;
  Subtotal, TotalPagos: Double;
  Pago: TJSONObject;
begin
  // Calcular subtotal
  Subtotal := 0;
  for i := 0 to High(FProductosVenta) do
    Subtotal := Subtotal + FProductosVenta[i].TotalLinea;
  
  FSubtotal := Subtotal;
  
  // Aplicar descuento general
  if not TryStrToFloat(EditDescuentoGeneral.Text, FDescuentoGeneral) then
    FDescuentoGeneral := 0;
  
  // Calcular impuestos (16% sobre subtotal menos descuento)
  FImpuestos := (FSubtotal - FDescuentoGeneral) * 0.16;
  
  // Calcular total
  FTotal := FSubtotal - FDescuentoGeneral + FImpuestos;
  
  // Actualizar campos
  EditSubtotal.Text := FormatFloat('$#,##0.00', FSubtotal);
  EditImpuestos.Text := FormatFloat('$#,##0.00', FImpuestos);
  EditTotal.Text := FormatFloat('$#,##0.00', FTotal);
  
  // Calcular total de pagos
  TotalPagos := 0;
  for i := 0 to FPagosVenta.Count - 1 do
  begin
    Pago := FPagosVenta.Items[i] as TJSONObject;
    TotalPagos := TotalPagos + Pago.GetValue<Double>('monto');
  end;
  
  // Actualizar monto sugerido
  EditMontoPago.Text := FormatFloat('#,##0.00', FTotal - TotalPagos);
end;

procedure TFormPuntoVenta.BtnSeleccionarClienteClick(Sender: TObject);
var
  FormSeleccion: TFormSeleccionCliente;
begin
  FormSeleccion := TFormSeleccionCliente.Create(Self);
  try
    if FormSeleccion.ShowModal = mrOk then
    begin
      FIdClienteSeleccionado := FormSeleccion.ClienteSeleccionado.IdCliente;
      EditCliente.Text := FormSeleccion.ClienteSeleccionado.Nombre + ' ' + FormSeleccion.ClienteSeleccionado.Apellido;
    end;
  finally
    FormSeleccion.Free;
  end;
end;

procedure TFormPuntoVenta.BtnClienteRapidoClick(Sender: TObject);
begin
  FIdClienteSeleccionado := '';
  EditCliente.Text := 'CONSUMIDOR FINAL';
  MostrarToast('Cliente establecido como Consumidor Final', Info);
end;

procedure TFormPuntoVenta.BtnAgregarPagoClick(Sender: TObject);
var
  Monto: Double;
  FormaPago: TJSONObject;
  Pago: TJSONObject;
begin
  if ComboFormaPago.ItemIndex < 0 then
  begin
    MostrarToast('Selecciona una forma de pago', Error);
    Exit;
  end;
  
  if not TryStrToFloat(EditMontoPago.Text, Monto) or (Monto <= 0) then
  begin
    MostrarToast('Ingresa un monto válido', Error);
    Exit;
  end;
  
  // Obtener forma de pago seleccionada
  FormaPago := FFormasPago.Items[ComboFormaPago.ItemIndex] as TJSONObject;
  
  // Crear objeto de pago
  Pago := TJSONObject.Create;
  Pago.AddPair('id_forma_pago', FormaPago.GetValue<string>('id_forma_pago'));
  Pago.AddPair('forma_pago', FormaPago.GetValue<string>('nombre'));
  Pago.AddPair('monto', TJSONNumber.Create(Monto));
  Pago.AddPair('referencia', '');
  
  FPagosVenta.AddElement(Pago);
  
  ActualizarGridPagos;
  CalcularTotales;
  
  EditMontoPago.Text := '';
  MostrarToast('Pago agregado', Success);
end;

procedure TFormPuntoVenta.BtnFinalizarVentaClick(Sender: TObject);
begin
  ValidarYFinalizarVenta;
end;

procedure TFormPuntoVenta.ValidarYFinalizarVenta;
var
  TotalPagos: Double;
  i: Integer;
  Pago: TJSONObject;
begin
  // Validar que hay productos
  if Length(FProductosVenta) = 0 then
  begin
    MostrarToast('Agrega productos a la venta', Error);
    Exit;
  end;
  
  // Validar que hay pagos
  if FPagosVenta.Count = 0 then
  begin
    MostrarToast('Agrega al menos una forma de pago', Error);
    Exit;
  end;
  
  // Validar que el total de pagos cubra el total de la venta
  TotalPagos := 0;
  for i := 0 to FPagosVenta.Count - 1 do
  begin
    Pago := FPagosVenta.Items[i] as TJSONObject;
    TotalPagos := TotalPagos + Pago.GetValue<Double>('monto');
  end;
  
  if Abs(TotalPagos - FTotal) > 0.01 then
  begin
    MostrarToast(Format('Total de pagos ($%.2f) no coincide con total de venta ($%.2f)', [TotalPagos, FTotal]), Error);
    Exit;
  end;
  
  // Confirmar venta
  TDialogService.MessageDialog(
    Format('¿Confirmar venta por $%.2f?', [FTotal]),
    TMsgDlgType.mtConfirmation,
    [TMsgDlgBtn.mbYes, TMsgDlgBtn.mbNo],
    TMsgDlgBtn.mbYes,
    0,
    procedure(const AResult: TModalResult)
    begin
      if AResult = mrYes then
        GuardarVenta;
    end
  );
end;

procedure TFormPuntoVenta.GuardarVenta;
begin
  // TODO: Implementar guardado de venta
  MostrarToast('Funcionalidad de guardado en desarrollo', Info);
  
  // Por ahora, limpiar la venta
  BtnNuevaVentaClick(nil);
end;

procedure TFormPuntoVenta.LimpiarVenta;
begin
  SetLength(FProductosVenta, 0);
  FPagosVenta.Free;
  FPagosVenta := TJSONArray.Create;
  FSubtotal := 0;
  FDescuentoGeneral := 0;
  FImpuestos := 0;
  FTotal := 0;
  
  EditDescuentoGeneral.Text := '0.00';
  EditMontoPago.Text := '';
  
  ActualizarGridProductos;
  ActualizarGridPagos;
  CalcularTotales;
end;

procedure TFormPuntoVenta.BtnNuevaVentaClick(Sender: TObject);
begin
  LimpiarVenta;
  InicializarVenta;
  EditBuscarProducto.SetFocus;
  MostrarToast('Nueva venta iniciada', Success);
end;

procedure TFormPuntoVenta.BtnLimpiarVentaClick(Sender: TObject);
begin
  TDialogService.MessageDialog(
    '¿Limpiar todos los productos de la venta?',
    TMsgDlgType.mtConfirmation,
    [TMsgDlgBtn.mbYes, TMsgDlgBtn.mbNo],
    TMsgDlgBtn.mbNo,
    0,
    procedure(const AResult: TModalResult)
    begin
      if AResult = mrYes then
        LimpiarVenta;
    end
  );
end;

function TFormPuntoVenta.GenerarNumeroFolio: string;
begin
  // TODO: Implementar generación de folio desde servidor
  Result := 'F' + FormatDateTime('yyyymmddhhnnss', Now);
end;

procedure TFormPuntoVenta.MostrarToast(const Mensaje: string; Tipo: TToastTipo);
begin
  case Tipo of
    Success: RecToast.Fill.Color := $FF4CAF50;
    Info:    RecToast.Fill.Color := $FF2196F3;
    Error:   RecToast.Fill.Color := $FFF44336;
  end;
  
  LblToast.Text := Mensaje;
  RecToast.Visible := True;
  
  FloatAnimationToast.StartValue := 0;
  FloatAnimationToast.StopValue := 1;
  FloatAnimationToast.PropertyName := 'Opacity';
  FloatAnimationToast.Duration := 0.3;
  FloatAnimationToast.Start;
  
  TTimer.CreateTimer(3000, procedure
  begin
    FloatAnimationToast.StartValue := 1;
    FloatAnimationToast.StopValue := 0;
    FloatAnimationToast.PropertyName := 'Opacity';
    FloatAnimationToast.Duration := 0.3;
    FloatAnimationToast.OnFinish := procedure(Sender: TObject)
    begin
      RecToast.Visible := False;
    end;
    FloatAnimationToast.Start;
  end);
end;

// === EVENTOS PENDIENTES DE IMPLEMENTAR ===
procedure TFormPuntoVenta.BtnBuscarProductoClick(Sender: TObject);
begin
  BuscarProductoPorCodigo(EditBuscarProducto.Text.Trim);
end;

procedure TFormPuntoVenta.BtnSeleccionarProductoClick(Sender: TObject);
begin
  // TODO: Abrir catálogo de productos
  MostrarToast('Catálogo de productos en desarrollo', Info);
end;

procedure TFormPuntoVenta.BtnEliminarLineaClick(Sender: TObject);
begin
  // TODO: Eliminar línea seleccionada
  MostrarToast('Funcionalidad en desarrollo', Info);
end;

procedure TFormPuntoVenta.BtnModificarCantidadClick(Sender: TObject);
begin
  // TODO: Modificar cantidad de línea seleccionada
  MostrarToast('Funcionalidad en desarrollo', Info);
end;

procedure TFormPuntoVenta.BtnAplicarDescuentoClick(Sender: TObject);
begin
  // TODO: Aplicar descuento a línea seleccionada
  MostrarToast('Funcionalidad en desarrollo', Info);
end;

procedure TFormPuntoVenta.BtnAplicarDescuentoGeneralClick(Sender: TObject);
begin
  CalcularTotales;
  MostrarToast('Descuento general aplicado', Success);
end;

procedure TFormPuntoVenta.BtnCancelarVentaClick(Sender: TObject);
begin
  Close;
end;

procedure TFormPuntoVenta.BtnConsultarVentasClick(Sender: TObject);
begin
  // TODO: Abrir consulta de ventas
  MostrarToast('Consulta de ventas en desarrollo', Info);
end;

procedure TFormPuntoVenta.StringGridProductosCellDblClick(const Column: TColumn; const Row: Integer);
begin
  // TODO: Acción al hacer doble clic en producto
  MostrarToast('Funcionalidad en desarrollo', Info);
end;

procedure TFormPuntoVenta.StringGridPagosCellDblClick(const Column: TColumn; const Row: Integer);
begin
  // TODO: Eliminar pago seleccionado
  MostrarToast('Funcionalidad en desarrollo', Info);
end;

procedure TFormPuntoVenta.EditMontoPagoKeyDown(Sender: TObject; var Key: Word; var KeyChar: Char; Shift: TShiftState);
begin
  if Key = vkReturn then
  begin
    BtnAgregarPagoClick(nil);
    Key := 0;
  end;
end;

end.