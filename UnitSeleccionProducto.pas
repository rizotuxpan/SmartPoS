unit UnitSeleccionProducto;

interface

uses
  System.SysUtils, System.Types, System.UITypes, System.Classes, System.Variants,
  FMX.Types, FMX.Controls, FMX.Forms, FMX.Graphics, FMX.Dialogs,
  System.Rtti, FMX.Grid.Style, FMX.Grid, FMX.ScrollBox,
  FMX.Edit, FMX.StdCtrls, FMX.Controls.Presentation, DataModule,
  System.Net.HttpClient, System.Net.HttpClientComponent, System.JSON, 
  System.net.URLClient, System.Generics.Collections, FMX.Ani, FMX.Objects, 
  FMX.Effects, FMX.DialogService, System.Threading, FMX.Layouts, FMX.ComboEdit;

type
  TToastTipo = (Success, Info, Error);
  
  TProductoSeleccionado = record
    IdProductoVariante: string;
    IdProducto: string;
    Sku: string;
    CodigoBarras: string;
    Nombre: string;
    Precio: Double;
    Stock: Double;
    Marca: string;
    Categoria: string;
  end;

type
  TFormSeleccionProducto = class(TForm)
    // === LAYOUT PRINCIPAL ===
    LayoutPrincipal: TLayout;
    LayoutSuperior: TLayout;
    LayoutInferior: TLayout;
    
    // === BÚSQUEDA Y FILTROS ===
    GroupBoxFiltros: TGroupBox;
    LblBuscar: TLabel;
    EditBuscar: TEdit;
    BtnBuscar: TButton;
    BtnLimpiar: TButton;
    
    // === FILTROS AVANZADOS ===
    LblMarca: TLabel;
    ComboMarca: TComboBox;
    LblCategoria: TLabel;
    ComboCategoria: TComboBox;
    LblPrecioMin: TLabel;
    EditPrecioMin: TEdit;
    LblPrecioMax: TLabel;
    EditPrecioMax: TEdit;
    CheckSoloConStock: TCheckBox;
    CheckExpandir: TCheckBox;
    
    // === GRID DE PRODUCTOS ===
    GroupBoxProductos: TGroupBox;
    StringGridProductos: TStringGrid;
    ColSku: TStringColumn;
    ColNombre: TStringColumn;
    ColMarca: TStringColumn;
    ColCategoria: TStringColumn;
    ColPrecio: TStringColumn;
    ColStock: TStringColumn;
    ColCodigoBarras: TStringColumn;
    
    // === PAGINACIÓN ===
    LayoutPaginacion: TLayout;
    BtnAnterior: TButton;
    BtnSiguiente: TButton;
    LblPagina: TLabel;
    EditTamanoPagina: TEdit;
    LblTamanoPagina: TLabel;
    LblTotal: TLabel;
    
    // === INFORMACIÓN DEL PRODUCTO SELECCIONADO ===
    GroupBoxSeleccionado: TGroupBox;
    LblProductoSeleccionado: TLabel;
    LblPrecioSeleccionado: TLabel;
    LblStockSeleccionado: TLabel;
    MemoInfoProducto: TMemo;
    
    // === CANTIDAD A AGREGAR ===
    GroupBoxCantidad: TGroupBox;
    LblCantidad: TLabel;
    EditCantidad: TEdit;
    BtnMenos: TButton;
    BtnMas: TButton;
    
    // === BOTONES DE ACCIÓN ===
    LayoutBotones: TLayout;
    BtnAgregarProducto: TButton;
    BtnCancelar: TButton;
    
    // === SISTEMA DE TOAST ===
    RecToast: TRectangle;
    LblToast: TLabel;
    FloatAnimationToast: TFloatAnimation;
    ShadowEffect1: TShadowEffect;
    
    // === EVENTOS ===
    procedure FormCreate(Sender: TObject);
    procedure FormShow(Sender: TObject);
    procedure BtnBuscarClick(Sender: TObject);
    procedure BtnLimpiarClick(Sender: TObject);
    procedure BtnAgregarProductoClick(Sender: TObject);
    procedure BtnCancelarClick(Sender: TObject);
    procedure BtnAnteriorClick(Sender: TObject);
    procedure BtnSiguienteClick(Sender: TObject);
    procedure BtnMenosClick(Sender: TObject);
    procedure BtnMasClick(Sender: TObject);
    procedure StringGridProductosCellDblClick(const Column: TColumn; const Row: Integer);
    procedure StringGridProductosSelChanged(Sender: TObject);
    procedure EditBuscarKeyDown(Sender: TObject; var Key: Word; var KeyChar: Char; Shift: TShiftState);
    procedure EditCantidadKeyDown(Sender: TObject; var Key: Word; var KeyChar: Char; Shift: TShiftState);
    procedure ComboMarcaChange(Sender: TObject);
    procedure ComboCategoriaChange(Sender: TObject);
    
  private
    FPaginaActual: Integer;
    FTotalRegistros: Integer;
    FRegistrosPorPagina: Integer;
    FProductos: TJSONArray;
    FMarcas: TJSONArray;
    FCategorias: TJSONArray;
    FProductoSeleccionado: TProductoSeleccionado;
    FHaySeleccion: Boolean;
    FCantidad: Double;
    
    procedure ConfigurarInterfaz;
    procedure CargarProductos;
    procedure CargarCatalogos;
    procedure ActualizarGridProductos;
    procedure ActualizarInfoPaginacion;
    procedure ActualizarInfoProductoSeleccionado;
    procedure LimpiarFiltros;
    procedure AjustarCantidad(Incremento: Double);
    procedure MostrarToast(const Mensaje: string; Tipo: TToastTipo = TToastTipo.Info);
    function ObtenerUrlConFiltros: string;
    function ObtenerProductoDeGrid(Fila: Integer): TProductoSeleccionado;
    function ValidarCantidad: Boolean;
    
  public
    property ProductoSeleccionado: TProductoSeleccionado read FProductoSeleccionado;
    property Cantidad: Double read FCantidad;
    property HaySeleccion: Boolean read FHaySeleccion;
    
  end;

var
  FormSeleccionProducto: TFormSeleccionProducto;
  API_BASE_URL: string;

implementation

{$R *.fmx}

procedure TFormSeleccionProducto.FormCreate(Sender: TObject);
begin
  API_BASE_URL := DM.GetApiBaseUrl;
  
  FPaginaActual := 1;
  FRegistrosPorPagina := 15;
  FTotalRegistros := 0;
  FProductos := nil;
  FMarcas := nil;
  FCategorias := nil;
  FHaySeleccion := False;
  FCantidad := 1.0;
  
  ConfigurarInterfaz;
end;

procedure TFormSeleccionProducto.FormShow(Sender: TObject);
begin
  CargarCatalogos;
  CargarProductos;
  EditBuscar.SetFocus;
end;

procedure TFormSeleccionProducto.ConfigurarInterfaz;
begin
  // === CONFIGURAR VENTANA ===
  Width := 1000;
  Height := 750;
  Position := TFormPosition.ScreenCenter;
  BorderStyle := TFmxFormBorderStyle.Single;
  Caption := 'Seleccionar Producto';
  
  // === LAYOUT PRINCIPAL ===
  with LayoutPrincipal do
  begin
    Align := TAlignLayout.Client;
    Padding.Left := 15;
    Padding.Right := 15;
    Padding.Top := 15;
    Padding.Bottom := 15;
  end;
  
  // === LAYOUT SUPERIOR (75%) ===
  with LayoutSuperior do
  begin
    Parent := LayoutPrincipal;
    Align := TAlignLayout.Client;
    Padding.Bottom := 5;
  end;
  
  // === LAYOUT INFERIOR (25%) ===
  with LayoutInferior do
  begin
    Parent := LayoutPrincipal;
    Align := TAlignLayout.Bottom;
    Height := 180;
    Padding.Top := 5;
  end;
  
  // === GRUPO DE FILTROS ===
  with GroupBoxFiltros do
  begin
    Parent := LayoutSuperior;
    Align := TAlignLayout.Top;
    Height := 100;
    Text := 'Búsqueda y Filtros';
    Margins.Bottom := 10;
  end;
  
  // Fila 1 de filtros
  with LblBuscar do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 15;
    Position.Y := 25;
    Width := 50;
    Text := 'Buscar:';
  end;
  
  with EditBuscar do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 70;
    Position.Y := 22;
    Width := 200;
    TextPrompt := 'Nombre, SKU, código de barras...';
  end;
  
  with BtnBuscar do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 280;
    Position.Y := 22;
    Width := 70;
    Height := 25;
    Text := 'Buscar';
    StyleLookup := 'acceptbuttonstyle';
  end;
  
  with BtnLimpiar do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 360;
    Position.Y := 22;
    Width := 70;
    Height := 25;
    Text := 'Limpiar';
  end;
  
  with LblMarca do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 460;
    Position.Y := 25;
    Width := 50;
    Text := 'Marca:';
  end;
  
  with ComboMarca do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 515;
    Position.Y := 22;
    Width := 120;
  end;
  
  with LblCategoria do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 655;
    Position.Y := 25;
    Width := 60;
    Text := 'Categoría:';
  end;
  
  with ComboCategoria do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 720;
    Position.Y := 22;
    Width := 120;
  end;
  
  // Fila 2 de filtros
  with LblPrecioMin do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 15;
    Position.Y := 55;
    Width := 70;
    Text := 'Precio min:';
  end;
  
  with EditPrecioMin do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 90;
    Position.Y := 52;
    Width := 80;
    TextPrompt := '0.00';
  end;
  
  with LblPrecioMax do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 185;
    Position.Y := 55;
    Width := 70;
    Text := 'Precio max:';
  end;
  
  with EditPrecioMax do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 260;
    Position.Y := 52;
    Width := 80;
    TextPrompt := '999999.99';
  end;
  
  with CheckSoloConStock do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 360;
    Position.Y := 55;
    Width := 120;
    Text := 'Solo con stock';
    IsChecked := True;
  end;
  
  with CheckExpandir do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 500;
    Position.Y := 55;
    Width := 140;
    Text := 'Expandir relaciones';
    IsChecked := True;
  end;
  
  // === GRUPO DE PRODUCTOS ===
  with GroupBoxProductos do
  begin
    Parent := LayoutSuperior;
    Align := TAlignLayout.Client;
    Text := 'Lista de Productos';
    Margins.Bottom := 10;
  end;
  
  // === CONFIGURAR GRID ===
  StringGridProductos.BeginUpdate;
  try
    StringGridProductos.Parent := GroupBoxProductos;
    StringGridProductos.Align := TAlignLayout.Client;
    StringGridProductos.Margins.Top := 25;
    StringGridProductos.Margins.Bottom := 50;
    StringGridProductos.RowCount := 0;
    StringGridProductos.Options := StringGridProductos.Options + [TGridOption.RowSelect];
    
    ColSku.Header := 'SKU';
    ColSku.Width := 120;
    ColNombre.Header := 'Nombre del Producto';
    ColNombre.Width := 250;
    ColMarca.Header := 'Marca';
    ColMarca.Width := 120;
    ColCategoria.Header := 'Categoría';
    ColCategoria.Width := 120;
    ColPrecio.Header := 'Precio';
    ColPrecio.Width := 100;
    ColStock.Header := 'Stock';
    ColStock.Width := 80;
    ColCodigoBarras.Header := 'Código Barras';
    ColCodigoBarras.Width := 120;
  finally
    StringGridProductos.EndUpdate;
  end;
  
  // === PAGINACIÓN ===
  with LayoutPaginacion do
  begin
    Parent := GroupBoxProductos;
    Align := TAlignLayout.Bottom;
    Height := 40;
    Margins.Bottom := 5;
  end;
  
  with BtnAnterior do
  begin
    Parent := LayoutPaginacion;
    Align := TAlignLayout.Left;
    Width := 80;
    Text := '← Anterior';
    Enabled := False;
  end;
  
  with BtnSiguiente do
  begin
    Parent := LayoutPaginacion;
    Align := TAlignLayout.Right;
    Width := 80;
    Text := 'Siguiente →';
    Enabled := False;
  end;
  
  with LblPagina do
  begin
    Parent := LayoutPaginacion;
    Align := TAlignLayout.Client;
    TextSettings.HorzAlign := TTextAlign.Center;
    TextSettings.VertAlign := TTextAlign.Center;
    Text := 'Página 1 de 1';
  end;
  
  with LblTamanoPagina do
  begin
    Parent := LayoutPaginacion;
    Position.X := 5;
    Position.Y := 10;
    Width := 120;
    Text := 'Registros por página:';
  end;
  
  with EditTamanoPagina do
  begin
    Parent := LayoutPaginacion;
    Position.X := 130;
    Position.Y := 8;
    Width := 50;
    Text := IntToStr(FRegistrosPorPagina);
  end;
  
  with LblTotal do
  begin
    Parent := LayoutPaginacion;
    Position.X := 200;
    Position.Y := 10;
    Width := 200;
    Text := 'Total: 0 productos';
  end;
  
  // === INFORMACIÓN DEL PRODUCTO SELECCIONADO ===
  with GroupBoxSeleccionado do
  begin
    Parent := LayoutInferior;
    Align := TAlignLayout.Left;
    Width := 400;
    Text := 'Producto Seleccionado';
    Margins.Right := 10;
  end;
  
  with LblProductoSeleccionado do
  begin
    Parent := GroupBoxSeleccionado;
    Position.X := 15;
    Position.Y := 25;
    Width := 370;
    Height := 20;
    Text := 'Ningún producto seleccionado';
    TextSettings.Font.Style := [TFontStyle.fsBold];
  end;
  
  with LblPrecioSeleccionado do
  begin
    Parent := GroupBoxSeleccionado;
    Position.X := 15;
    Position.Y := 50;
    Width := 180;
    Height := 20;
    Text := 'Precio: $0.00';
    TextSettings.FontColor := TAlphaColors.Green;
    TextSettings.Font.Style := [TFontStyle.fsBold];
  end;
  
  with LblStockSeleccionado do
  begin
    Parent := GroupBoxSeleccionado;
    Position.X := 200;
    Position.Y := 50;
    Width := 180;
    Height := 20;
    Text := 'Stock: 0';
    TextSettings.FontColor := TAlphaColors.Blue;
  end;
  
  with MemoInfoProducto do
  begin
    Parent := GroupBoxSeleccionado;
    Position.X := 15;
    Position.Y := 75;
    Width := 370;
    Height := 80;
    ReadOnly := True;
    Text := '';
  end;
  
  // === CANTIDAD A AGREGAR ===
  with GroupBoxCantidad do
  begin
    Parent := LayoutInferior;
    Align := TAlignLayout.Left;
    Width := 200;
    Text := 'Cantidad';
    Margins.Right := 10;
  end;
  
  with LblCantidad do
  begin
    Parent := GroupBoxCantidad;
    Position.X := 15;
    Position.Y := 40;
    Width := 60;
    Text := 'Cantidad:';
    TextSettings.VertAlign := TTextAlign.Center;
  end;
  
  with BtnMenos do
  begin
    Parent := GroupBoxCantidad;
    Position.X := 15;
    Position.Y := 70;
    Width := 40;
    Height := 40;
    Text := '-';
    TextSettings.Font.Size := 20;
  end;
  
  with EditCantidad do
  begin
    Parent := GroupBoxCantidad;
    Position.X := 65;
    Position.Y := 70;
    Width := 70;
    Height := 40;
    Text := '1.00';
    TextSettings.HorzAlign := TTextAlign.Center;
    TextSettings.Font.Size := 16;
  end;
  
  with BtnMas do
  begin
    Parent := GroupBoxCantidad;
    Position.X := 145;
    Position.Y := 70;
    Width := 40;
    Height := 40;
    Text := '+';
    TextSettings.Font.Size := 20;
  end;
  
  // === BOTONES DE ACCIÓN ===
  with LayoutBotones do
  begin
    Parent := LayoutInferior;
    Align := TAlignLayout.Client;
    Padding.Top := 25;
  end;
  
  with BtnAgregarProducto do
  begin
    Parent := LayoutBotones;
    Align := TAlignLayout.Top;
    Height := 50;
    Text := 'AGREGAR PRODUCTO';
    Enabled := False;
    StyleLookup := 'acceptbuttonstyle';
    TextSettings.Font.Size := 16;
    Margins.Bottom := 10;
  end;
  
  with BtnCancelar do
  begin
    Parent := LayoutBotones;
    Align := TAlignLayout.Top;
    Height := 40;
    Text := 'Cancelar';
  end;
  
  // === SISTEMA DE TOAST ===
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

procedure TFormSeleccionProducto.CargarCatalogos;
var
  Http: TNetHTTPClient;
  Response: IHTTPResponse;
  JsonResponse: TJSONObject;
  JsonData: TJSONArray;
  i: Integer;
  Item: TJSONObject;
begin
  Http := TNetHTTPClient.Create(nil);
  try
    // Cargar Marcas
    try
      Response := Http.Get(API_BASE_URL + '/marcas/combo', DM.GetHeaders);
      
      if Response.StatusCode = 200 then
      begin
        JsonResponse := TJSONObject.ParseJSONValue(Response.ContentAsString) as TJSONObject;
        try
          if JsonResponse.GetValue<Boolean>('success') then
          begin
            JsonData := JsonResponse.GetValue<TJSONArray>('data');
            
            ComboMarca.Items.Clear;
            ComboMarca.Items.BeginUpdate;
            try
              ComboMarca.Items.Add('Todas las marcas');
              for i := 0 to JsonData.Count - 1 do
              begin
                Item := JsonData.Items[i] as TJSONObject;
                ComboMarca.Items.Add(Item.GetValue<string>('nombre'));
              end;
              
              FMarcas := JsonData.Clone as TJSONArray;
              ComboMarca.ItemIndex := 0;
              
            finally
              ComboMarca.Items.EndUpdate;
            end;
          end;
        finally
          JsonResponse.Free;
        end;
      end;
    except
      on E: Exception do
        MostrarToast('Error al cargar marcas: ' + E.Message, Error);
    end;
    
    // Cargar Categorías
    try
      Response := Http.Get(API_BASE_URL + '/categorias/combo', DM.GetHeaders);
      
      if Response.StatusCode = 200 then
      begin
        JsonResponse := TJSONObject.ParseJSONValue(Response.ContentAsString) as TJSONObject;
        try
          if JsonResponse.GetValue<Boolean>('success') then
          begin
            JsonData := JsonResponse.GetValue<TJSONArray>('data');
            
            ComboCategoria.Items.Clear;
            ComboCategoria.Items.BeginUpdate;
            try
              ComboCategoria.Items.Add('Todas las categorías');
              for i := 0 to JsonData.Count - 1 do
              begin
                Item := JsonData.Items[i] as TJSONObject;
                ComboCategoria.Items.Add(Item.GetValue<string>('nombre'));
              end;
              
              FCategorias := JsonData.Clone as TJSONArray;
              ComboCategoria.ItemIndex := 0;
              
            finally
              ComboCategoria.Items.EndUpdate;
            end;
          end;
        finally
          JsonResponse.Free;
        end;
      end;
    except
      on E: Exception do
        MostrarToast('Error al cargar categorías: ' + E.Message, Error);
    end;
    
  finally
    Http.Free;
  end;
end;

procedure TFormSeleccionProducto.CargarProductos;
var
  Http: TNetHTTPClient;
  Url: string;
begin
  Http := TNetHTTPClient.Create(nil);
  try
    Url := ObtenerUrlConFiltros;
    
    TTask.Run(procedure
    var
      Response: IHTTPResponse;
      JsonResponse: TJSONObject;
      JsonData: TJSONArray;
    begin
      try
        Response := Http.Get(Url, DM.GetHeaders);
        
        if Response.StatusCode = 200 then
        begin
          JsonResponse := TJSONObject.ParseJSONValue(Response.ContentAsString) as TJSONObject;
          try
            if JsonResponse.GetValue<Boolean>('success') then
            begin
              JsonData := JsonResponse.GetValue<TJSONArray>('data');
              FTotalRegistros := JsonResponse.GetValue<Integer>('total_count');
              
              TThread.Synchronize(nil, procedure
              begin
                if Assigned(Self) then
                begin
                  if Assigned(FProductos) then
                    FProductos.Free;
                  FProductos := JsonData.Clone as TJSONArray;
                  
                  ActualizarGridProductos;
                  ActualizarInfoPaginacion;
                  
                  if FProductos.Count > 0 then
                    MostrarToast(Format('Se cargaron %d productos', [FProductos.Count]), Success)
                  else
                    MostrarToast('No se encontraron productos con los filtros aplicados', Info);
                end;
              end);
            end
            else
            begin
              TThread.Synchronize(nil, procedure
              begin
                if Assigned(Self) then
                  MostrarToast('Error en la respuesta del servidor', Error);
              end);
            end;
          finally
            JsonResponse.Free;
          end;
        end
        else
        begin
          TThread.Synchronize(nil, procedure
          begin
            if Assigned(Self) then
              MostrarToast('Error al cargar productos: ' + Response.StatusText, Error);
          end);
        end;
        
      except
        on E: Exception do
        begin
          TThread.Synchronize(nil, procedure
          begin
            if Assigned(Self) then
              MostrarToast('Error de conexión: ' + E.Message, Error);
          end);
        end;
      end;
    end);
    
  finally
    Http.Free;
  end;
end;

function TFormSeleccionProducto.ObtenerUrlConFiltros: string;
var
  Params: TStringList;
  ParamString: string;
  i: Integer;
  PrecioMin, PrecioMax: Double;
begin
  Result := API_BASE_URL + '/variantes/';
  
  Params := TStringList.Create;
  try
    // Paginación
    Params.Add('skip=' + IntToStr((FPaginaActual - 1) * FRegistrosPorPagina));
    Params.Add('limit=' + IntToStr(FRegistrosPorPagina));
    
    // Expandir si está marcado
    if CheckExpandir.IsChecked then
      Params.Add('expandir=true');
    
    // Búsqueda general
    if EditBuscar.Text.Trim <> '' then
    begin
      Params.Add('sku_variante=' + TNetEncoding.URL.Encode(EditBuscar.Text.Trim));
      // También buscar por producto padre
      Params.Add('producto_nombre=' + TNetEncoding.URL.Encode(EditBuscar.Text.Trim));
    end;
    
    // Filtros de precio
    if TryStrToFloat(EditPrecioMin.Text, PrecioMin) and (PrecioMin > 0) then
      Params.Add('precio_min=' + FloatToStr(PrecioMin));
    
    if TryStrToFloat(EditPrecioMax.Text, PrecioMax) and (PrecioMax > 0) then
      Params.Add('precio_max=' + FloatToStr(PrecioMax));
    
    // Filtro por marca
    if (ComboMarca.ItemIndex > 0) and Assigned(FMarcas) and (ComboMarca.ItemIndex <= FMarcas.Count) then
    begin
      var Marca := FMarcas.Items[ComboMarca.ItemIndex - 1] as TJSONObject;
      Params.Add('marca_nombre=' + TNetEncoding.URL.Encode(Marca.GetValue<string>('nombre')));
    end;
    
    // Filtro por categoría
    if (ComboCategoria.ItemIndex > 0) and Assigned(FCategorias) and (ComboCategoria.ItemIndex <= FCategorias.Count) then
    begin
      var Categoria := FCategorias.Items[ComboCategoria.ItemIndex - 1] as TJSONObject;
      Params.Add('categoria_nombre=' + TNetEncoding.URL.Encode(Categoria.GetValue<string>('nombre')));
    end;
    
    // Construir URL final
    if Params.Count > 0 then
    begin
      ParamString := '';
      for i := 0 to Params.Count - 1 do
      begin
        if i > 0 then
          ParamString := ParamString + '&';
        ParamString := ParamString + Params[i];
      end;
      Result := Result + '?' + ParamString;
    end;
    
  finally
    Params.Free;
  end;
end;

procedure TFormSeleccionProducto.ActualizarGridProductos;
var
  i: Integer;
  Variante: TJSONObject;
  Producto: TJSONObject;
  Nombre, Marca, Categoria: string;
begin
  if not Assigned(FProductos) then Exit;
  
  StringGridProductos.BeginUpdate;
  try
    StringGridProductos.RowCount := FProductos.Count;
    
    for i := 0 to FProductos.Count - 1 do
    begin
      Variante := FProductos.Items[i] as TJSONObject;
      
      // Obtener información del producto padre si está expandido
      if Variante.Contains('producto') then
      begin
        Producto := Variante.GetValue<TJSONObject>('producto');
        Nombre := Producto.GetValue<string>('nombre');
        // TODO: Obtener marca y categoría del producto expandido
        Marca := 'N/A';
        Categoria := 'N/A';
      end
      else
      begin
        Nombre := 'Variante ' + Variante.GetValue<string>('sku_variante');
        Marca := 'N/A';
        Categoria := 'N/A';
      end;
      
      StringGridProductos.Cells[0, i] := Variante.GetValue<string>('sku_variante');
      StringGridProductos.Cells[1, i] := Nombre;
      StringGridProductos.Cells[2, i] := Marca;
      StringGridProductos.Cells[3, i] := Categoria;
      StringGridProductos.Cells[4, i] := FormatFloat('$#,##0.00', Variante.GetValue<Double>('precio'));
      StringGridProductos.Cells[5, i] := '0'; // TODO: Obtener stock del inventario
      StringGridProductos.Cells[6, i] := Variante.GetValue<string>('codigo_barras_var', '');
    end;
  finally
    StringGridProductos.EndUpdate;
  end;
end;

procedure TFormSeleccionProducto.ActualizarInfoPaginacion;
var
  TotalPaginas: Integer;
begin
  TotalPaginas := Ceil(FTotalRegistros / FRegistrosPorPagina);
  if TotalPaginas = 0 then TotalPaginas := 1;
  
  LblPagina.Text := Format('Página %d de %d', [FPaginaActual, TotalPaginas]);
  LblTotal.Text := Format('Total: %d productos', [FTotalRegistros]);
  
  BtnAnterior.Enabled := FPaginaActual > 1;
  BtnSiguiente.Enabled := FPaginaActual < TotalPaginas;
end;

procedure TFormSeleccionProducto.ActualizarInfoProductoSeleccionado;
var
  Info: string;
begin
  if FHaySeleccion then
  begin
    LblProductoSeleccionado.Text := FProductoSeleccionado.Nombre;
    LblPrecioSeleccionado.Text := 'Precio: ' + FormatFloat('$#,##0.00', FProductoSeleccionado.Precio);
    LblStockSeleccionado.Text := 'Stock: ' + FormatFloat('#,##0.00', FProductoSeleccionado.Stock);
    
    Info := '';
    if FProductoSeleccionado.Sku <> '' then
      Info := Info + 'SKU: ' + FProductoSeleccionado.Sku + #13#10;
    if FProductoSeleccionado.CodigoBarras <> '' then
      Info := Info + 'Código de Barras: ' + FProductoSeleccionado.CodigoBarras + #13#10;
    if FProductoSeleccionado.Marca <> '' then
      Info := Info + 'Marca: ' + FProductoSeleccionado.Marca + #13#10;
    if FProductoSeleccionado.Categoria <> '' then
      Info := Info + 'Categoría: ' + FProductoSeleccionado.Categoria;
    
    MemoInfoProducto.Text := Info;
    BtnAgregarProducto.Enabled := ValidarCantidad;
  end
  else
  begin
    LblProductoSeleccionado.Text := 'Ningún producto seleccionado';
    LblPrecioSeleccionado.Text := 'Precio: $0.00';
    LblStockSeleccionado.Text := 'Stock: 0';
    MemoInfoProducto.Text := '';
    BtnAgregarProducto.Enabled := False;
  end;
end;

function TFormSeleccionProducto.ObtenerProductoDeGrid(Fila: Integer): TProductoSeleccionado;
var
  Variante: TJSONObject;
  Producto: TJSONObject;
begin
  if (Fila >= 0) and (Fila < FProductos.Count) then
  begin
    Variante := FProductos.Items[Fila] as TJSONObject;
    
    Result.IdProductoVariante := Variante.GetValue<string>('id_producto_variante');
    Result.IdProducto := Variante.GetValue<string>('id_producto');
    Result.Sku := Variante.GetValue<string>('sku_variante');
    Result.CodigoBarras := Variante.GetValue<string>('codigo_barras_var', '');
    Result.Precio := Variante.GetValue<Double>('precio');
    Result.Stock := 0; // TODO: Obtener del inventario
    
    if Variante.Contains('producto') then
    begin
      Producto := Variante.GetValue<TJSONObject>('producto');
      Result.Nombre := Producto.GetValue<string>('nombre');
      // TODO: Obtener marca y categoría expandidas
      Result.Marca := 'N/A';
      Result.Categoria := 'N/A';
    end
    else
    begin
      Result.Nombre := 'Variante ' + Result.Sku;
      Result.Marca := 'N/A';
      Result.Categoria := 'N/A';
    end;
  end
  else
  begin
    // Limpiar registro
    Result.IdProductoVariante := '';
    Result.IdProducto := '';
    Result.Sku := '';
    Result.CodigoBarras := '';
    Result.Nombre := '';
    Result.Precio := 0;
    Result.Stock := 0;
    Result.Marca := '';
    Result.Categoria := '';
  end;
end;

function TFormSeleccionProducto.ValidarCantidad: Boolean;
begin
  Result := FCantidad > 0;
  
  // TODO: Validar que no exceda el stock disponible
  if CheckSoloConStock.IsChecked and FHaySeleccion then
    Result := Result and (FCantidad <= FProductoSeleccionado.Stock);
end;

procedure TFormSeleccionProducto.StringGridProductosSelChanged(Sender: TObject);
var
  FilaSeleccionada: Integer;
begin
  FilaSeleccionada := StringGridProductos.Selected;
  
  if (FilaSeleccionada >= 0) and (FilaSeleccionada < StringGridProductos.RowCount) then
  begin
    FProductoSeleccionado := ObtenerProductoDeGrid(FilaSeleccionada);
    FHaySeleccion := True;
  end
  else
  begin
    FHaySeleccion := False;
  end;
  
  ActualizarInfoProductoSeleccionado;
end;

procedure TFormSeleccionProducto.StringGridProductosCellDblClick(const Column: TColumn; const Row: Integer);
begin
  if FHaySeleccion and ValidarCantidad then
  begin
    BtnAgregarProductoClick(nil);
  end;
end;

procedure TFormSeleccionProducto.AjustarCantidad(Incremento: Double);
begin
  FCantidad := FCantidad + Incremento;
  
  if FCantidad < 0.01 then
    FCantidad := 0.01;
  
  EditCantidad.Text := FormatFloat('#,##0.00', FCantidad);
  ActualizarInfoProductoSeleccionado;
end;

// === EVENTOS DE BOTONES ===

procedure TFormSeleccionProducto.BtnBuscarClick(Sender: TObject);
begin
  FPaginaActual := 1;
  CargarProductos;
end;

procedure TFormSeleccionProducto.EditBuscarKeyDown(Sender: TObject; var Key: Word; var KeyChar: Char; Shift: TShiftState);
begin
  if Key = vkReturn then
  begin
    BtnBuscarClick(nil);
    Key := 0;
  end;
end;

procedure TFormSeleccionProducto.BtnLimpiarClick(Sender: TObject);
begin
  LimpiarFiltros;
end;

procedure TFormSeleccionProducto.LimpiarFiltros;
begin
  EditBuscar.Text := '';
  EditPrecioMin.Text := '';
  EditPrecioMax.Text := '';
  ComboMarca.ItemIndex := 0;
  ComboCategoria.ItemIndex := 0;
  CheckSoloConStock.IsChecked := True;
  CheckExpandir.IsChecked := True;
  FPaginaActual := 1;
  CargarProductos;
end;

procedure TFormSeleccionProducto.ComboMarcaChange(Sender: TObject);
begin
  // Auto-buscar al cambiar filtro
  if ComboMarca.ItemIndex >= 0 then
    BtnBuscarClick(nil);
end;

procedure TFormSeleccionProducto.ComboCategoriaChange(Sender: TObject);
begin
  // Auto-buscar al cambiar filtro
  if ComboCategoria.ItemIndex >= 0 then
    BtnBuscarClick(nil);
end;

procedure TFormSeleccionProducto.BtnAnteriorClick(Sender: TObject);
begin
  if FPaginaActual > 1 then
  begin
    Dec(FPaginaActual);
    CargarProductos;
  end;
end;

procedure TFormSeleccionProducto.BtnSiguienteClick(Sender: TObject);
var
  TotalPaginas: Integer;
begin
  TotalPaginas := Ceil(FTotalRegistros / FRegistrosPorPagina);
  if FPaginaActual < TotalPaginas then
  begin
    Inc(FPaginaActual);
    CargarProductos;
  end;
end;

procedure TFormSeleccionProducto.BtnMenosClick(Sender: TObject);
begin
  AjustarCantidad(-1);
end;

procedure TFormSeleccionProducto.BtnMasClick(Sender: TObject);
begin
  AjustarCantidad(1);
end;

procedure TFormSeleccionProducto.EditCantidadKeyDown(Sender: TObject; var Key: Word; var KeyChar: Char; Shift: TShiftState);
var
  NuevaCantidad: Double;
begin
  if Key = vkReturn then
  begin
    if TryStrToFloat(EditCantidad.Text, NuevaCantidad) and (NuevaCantidad > 0) then
    begin
      FCantidad := NuevaCantidad;
      EditCantidad.Text := FormatFloat('#,##0.00', FCantidad);
      ActualizarInfoProductoSeleccionado;
    end
    else
    begin
      EditCantidad.Text := FormatFloat('#,##0.00', FCantidad);
      MostrarToast('Cantidad no válida', Error);
    end;
    Key := 0;
  end;
end;

procedure TFormSeleccionProducto.BtnAgregarProductoClick(Sender: TObject);
begin
  if not FHaySeleccion then
  begin
    MostrarToast('Selecciona un producto de la lista', Error);
    Exit;
  end;
  
  if not ValidarCantidad then
  begin
    MostrarToast('La cantidad no es válida o excede el stock disponible', Error);
    Exit;
  end;
  
  // Actualizar cantidad final
  if not TryStrToFloat(EditCantidad.Text, FCantidad) or (FCantidad <= 0) then
  begin
    MostrarToast('Ingresa una cantidad válida', Error);
    Exit;
  end;
  
  ModalResult := mrOk;
  Close;
end;

procedure TFormSeleccionProducto.BtnCancelarClick(Sender: TObject);
begin
  ModalResult := mrCancel;
  Close;
end;

procedure TFormSeleccionProducto.MostrarToast(const Mensaje: string; Tipo: TToastTipo);
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

end.