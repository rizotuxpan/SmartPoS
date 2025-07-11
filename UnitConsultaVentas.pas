unit UnitConsultaVentas;

interface

uses
  System.SysUtils, System.Types, System.UITypes, System.Classes, System.Variants,
  FMX.Types, FMX.Controls, FMX.Forms, FMX.Graphics, FMX.Dialogs,
  System.Rtti, FMX.Grid.Style, FMX.Grid, FMX.ScrollBox,
  FMX.Edit, FMX.StdCtrls, FMX.Controls.Presentation, DataModule,
  System.Net.HttpClient, System.Net.HttpClientComponent, System.JSON, 
  System.net.URLClient, System.Generics.Collections, FMX.Ani, FMX.Objects, 
  FMX.Effects, FMX.DialogService, System.Threading, FMX.Layouts, 
  FMX.DateTimeCtrls, FMX.ComboEdit, FMX.Memo.Types, FMX.Memo, System.DateUtils;

type
  TToastTipo = (Success, Info, Error);

type
  TFormConsultaVentas = class(TForm)
    // === LAYOUT PRINCIPAL ===
    LayoutPrincipal: TLayout;
    LayoutSuperior: TLayout;
    LayoutInferior: TLayout;
    
    // === FILTROS ===
    GroupBoxFiltros: TGroupBox;
    LblFechaDesde: TLabel;
    DateEditDesde: TDateEdit;
    LblFechaHasta: TLabel;
    DateEditHasta: TDateEdit;
    LblCliente: TLabel;
    EditCliente: TEdit;
    BtnSeleccionarCliente: TButton;
    LblVendedor: TLabel;
    ComboVendedor: TComboBox;
    LblTerminal: TLabel;
    ComboTerminal: TComboBox;
    LblEstado: TLabel;
    ComboEstado: TComboBox;
    LblNumeroFolio: TLabel;
    EditNumeroFolio: TEdit;
    
    // === BOTONES DE FILTRO ===
    LayoutBotonesFiltro: TLayout;
    BtnBuscar: TButton;
    BtnLimpiarFiltros: TButton;
    BtnHoy: TButton;
    BtnUltimos7Dias: TButton;
    BtnEsteMes: TButton;
    BtnExportar: TButton;
    
    // === GRID DE VENTAS ===
    GroupBoxVentas: TGroupBox;
    StringGridVentas: TStringGrid;
    ColFecha: TStringColumn;
    ColFolio: TStringColumn;
    ColCliente: TStringColumn;
    ColVendedor: TStringColumn;
    ColSubtotal: TStringColumn;
    ColDescuento: TStringColumn;
    ColImpuestos: TStringColumn;
    ColTotal: TStringColumn;
    ColEstado: TStringColumn;
    ColAcciones: TStringColumn;
    
    // === PAGINACIÓN ===
    LayoutPaginacion: TLayout;
    BtnAnterior: TButton;
    BtnSiguiente: TButton;
    LblPagina: TLabel;
    EditTamanoPagina: TEdit;
    LblTamanoPagina: TLabel;
    LblTotal: TLabel;
    
    // === RESUMEN DE VENTAS ===
    GroupBoxResumen: TGroupBox;
    LblTotalVentas: TLabel;
    EditTotalVentas: TEdit;
    LblTotalDescuentos: TLabel;
    EditTotalDescuentos: TEdit;
    LblTotalImpuestos: TLabel;
    EditTotalImpuestos: TEdit;
    LblTotalNeto: TLabel;
    EditTotalNeto: TEdit;
    LblCantidadVentas: TLabel;
    EditCantidadVentas: TEdit;
    LblPromedioVenta: TLabel;
    EditPromedioVenta: TEdit;
    
    // === DETALLE DE VENTA SELECCIONADA ===
    GroupBoxDetalle: TGroupBox;
    MemoDetalleVenta: TMemo;
    BtnVerDetalle: TButton;
    BtnReimprimirTicket: TButton;
    BtnAnularVenta: TButton;
    
    // === BOTONES PRINCIPALES ===
    LayoutBotonesPrincipales: TLayout;
    BtnNuevaVenta: TButton;
    BtnCerrar: TButton;
    
    // === SISTEMA DE TOAST ===
    RecToast: TRectangle;
    LblToast: TLabel;
    FloatAnimationToast: TFloatAnimation;
    ShadowEffect1: TShadowEffect;
    
    // === EVENTOS ===
    procedure FormCreate(Sender: TObject);
    procedure FormShow(Sender: TObject);
    procedure BtnBuscarClick(Sender: TObject);
    procedure BtnLimpiarFiltrosClick(Sender: TObject);
    procedure BtnHoyClick(Sender: TObject);
    procedure BtnUltimos7DiasClick(Sender: TObject);
    procedure BtnEsteMesClick(Sender: TObject);
    procedure BtnExportarClick(Sender: TObject);
    procedure BtnSeleccionarClienteClick(Sender: TObject);
    procedure BtnAnteriorClick(Sender: TObject);
    procedure BtnSiguienteClick(Sender: TObject);
    procedure BtnVerDetalleClick(Sender: TObject);
    procedure BtnReimprimirTicketClick(Sender: TObject);
    procedure BtnAnularVentaClick(Sender: TObject);
    procedure BtnNuevaVentaClick(Sender: TObject);
    procedure BtnCerrarClick(Sender: TObject);
    procedure StringGridVentasSelChanged(Sender: TObject);
    procedure StringGridVentasCellDblClick(const Column: TColumn; const Row: Integer);
    procedure DateEditDesdeChange(Sender: TObject);
    procedure DateEditHastaChange(Sender: TObject);
    
  private
    FPaginaActual: Integer;
    FTotalRegistros: Integer;
    FRegistrosPorPagina: Integer;
    FVentas: TJSONArray;
    FIdClienteSeleccionado: string;
    FVentaSeleccionada: TJSONObject;
    
    procedure ConfigurarInterfaz;
    procedure CargarVentas;
    procedure CargarCatalogos;
    procedure ActualizarGridVentas;
    procedure ActualizarInfoPaginacion;
    procedure ActualizarResumenVentas;
    procedure ActualizarDetalleVentaSeleccionada;
    procedure LimpiarFiltros;
    procedure EstablecerFiltrosFechas(Dias: Integer);
    procedure MostrarToast(const Mensaje: string; Tipo: TToastTipo = TToastTipo.Info);
    function ObtenerUrlConFiltros: string;
    function FormatearFecha(const FechaStr: string): string;
    function FormatearMoneda(Valor: Double): string;
    
  public
    
  end;

var
  FormConsultaVentas: TFormConsultaVentas;
  API_BASE_URL: string;

implementation

uses UnitSeleccionCliente, UnitPuntoVenta;

{$R *.fmx}

procedure TFormConsultaVentas.FormCreate(Sender: TObject);
begin
  API_BASE_URL := DM.GetApiBaseUrl;
  
  FPaginaActual := 1;
  FRegistrosPorPagina := 25;
  FTotalRegistros := 0;
  FVentas := nil;
  FIdClienteSeleccionado := '';
  FVentaSeleccionada := nil;
  
  ConfigurarInterfaz;
end;

procedure TFormConsultaVentas.FormShow(Sender: TObject);
begin
  CargarCatalogos;
  EstablecerFiltrosFechas(0); // Hoy
  CargarVentas;
end;

procedure TFormConsultaVentas.ConfigurarInterfaz;
begin
  // === CONFIGURAR VENTANA ===
  Width := 1200;
  Height := 800;
  Position := TFormPosition.ScreenCenter;
  Caption := 'Consulta de Ventas';
  
  // === LAYOUT PRINCIPAL ===
  with LayoutPrincipal do
  begin
    Align := TAlignLayout.Client;
    Padding.Left := 15;
    Padding.Right := 15;
    Padding.Top := 15;
    Padding.Bottom := 15;
  end;
  
  // === LAYOUT SUPERIOR (70%) ===
  with LayoutSuperior do
  begin
    Parent := LayoutPrincipal;
    Align := TAlignLayout.Client;
    Padding.Bottom := 5;
  end;
  
  // === LAYOUT INFERIOR (30%) ===
  with LayoutInferior do
  begin
    Parent := LayoutPrincipal;
    Align := TAlignLayout.Bottom;
    Height := 250;
    Padding.Top := 5;
  end;
  
  // === GRUPO DE FILTROS ===
  with GroupBoxFiltros do
  begin
    Parent := LayoutSuperior;
    Align := TAlignLayout.Top;
    Height := 120;
    Text := 'Filtros de Búsqueda';
    Margins.Bottom := 10;
  end;
  
  // Fila 1 de filtros
  with LblFechaDesde do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 15;
    Position.Y := 25;
    Width := 80;
    Text := 'Fecha desde:';
  end;
  
  with DateEditDesde do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 100;
    Position.Y := 22;
    Width := 120;
    Date := Date;
  end;
  
  with LblFechaHasta do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 240;
    Position.Y := 25;
    Width := 80;
    Text := 'Fecha hasta:';
  end;
  
  with DateEditHasta do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 325;
    Position.Y := 22;
    Width := 120;
    Date := Date;
  end;
  
  with LblCliente do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 465;
    Position.Y := 25;
    Width := 50;
    Text := 'Cliente:';
  end;
  
  with EditCliente do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 520;
    Position.Y := 22;
    Width := 180;
    ReadOnly := True;
    TextPrompt := 'Todos los clientes';
  end;
  
  with BtnSeleccionarCliente do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 710;
    Position.Y := 22;
    Width := 80;
    Height := 25;
    Text := 'Seleccionar';
  end;
  
  // Fila 2 de filtros
  with LblVendedor do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 15;
    Position.Y := 55;
    Width := 60;
    Text := 'Vendedor:';
  end;
  
  with ComboVendedor do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 80;
    Position.Y := 52;
    Width := 140;
  end;
  
  with LblTerminal do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 240;
    Position.Y := 55;
    Width := 60;
    Text := 'Terminal:';
  end;
  
  with ComboTerminal do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 305;
    Position.Y := 52;
    Width := 140;
  end;
  
  with LblEstado do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 465;
    Position.Y := 55;
    Width := 50;
    Text := 'Estado:';
  end;
  
  with ComboEstado do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 520;
    Position.Y := 52;
    Width := 120;
    Items.Add('Todas');
    Items.Add('Completada');
    Items.Add('Pendiente');
    Items.Add('Anulada');
    ItemIndex := 0;
  end;
  
  with LblNumeroFolio do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 660;
    Position.Y := 55;
    Width := 70;
    Text := 'No. Folio:';
  end;
  
  with EditNumeroFolio do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 735;
    Position.Y := 52;
    Width := 120;
    TextPrompt := 'Número de folio';
  end;
  
  // === BOTONES DE FILTRO ===
  with LayoutBotonesFiltro do
  begin
    Parent := GroupBoxFiltros;
    Position.X := 15;
    Position.Y := 85;
    Width := GroupBoxFiltros.Width - 30;
    Height := 30;
  end;
  
  with BtnBuscar do
  begin
    Parent := LayoutBotonesFiltro;
    Align := TAlignLayout.Left;
    Width := 80;
    Text := 'Buscar';
    StyleLookup := 'acceptbuttonstyle';
  end;
  
  with BtnLimpiarFiltros do
  begin
    Parent := LayoutBotonesFiltro;
    Align := TAlignLayout.Left;
    Width := 80;
    Text := 'Limpiar';
    Margins.Left := 5;
  end;
  
  with BtnHoy do
  begin
    Parent := LayoutBotonesFiltro;
    Align := TAlignLayout.Left;
    Width := 60;
    Text := 'Hoy';
    Margins.Left := 20;
  end;
  
  with BtnUltimos7Dias do
  begin
    Parent := LayoutBotonesFiltro;
    Align := TAlignLayout.Left;
    Width := 80;
    Text := 'Últimos 7';
    Margins.Left := 5;
  end;
  
  with BtnEsteMes do
  begin
    Parent := LayoutBotonesFiltro;
    Align := TAlignLayout.Left;
    Width := 80;
    Text := 'Este mes';
    Margins.Left := 5;
  end;
  
  with BtnExportar do
  begin
    Parent := LayoutBotonesFiltro;
    Align := TAlignLayout.Right;
    Width := 80;
    Text := 'Exportar';
  end;
  
  // === GRUPO DE VENTAS ===
  with GroupBoxVentas do
  begin
    Parent := LayoutSuperior;
    Align := TAlignLayout.Client;
    Text := 'Lista de Ventas';
    Margins.Bottom := 10;
  end;
  
  // === CONFIGURAR GRID ===
  StringGridVentas.BeginUpdate;
  try
    StringGridVentas.Parent := GroupBoxVentas;
    StringGridVentas.Align := TAlignLayout.Client;
    StringGridVentas.Margins.Top := 25;
    StringGridVentas.Margins.Bottom := 50;
    StringGridVentas.RowCount := 0;
    StringGridVentas.Options := StringGridVentas.Options + [TGridOption.RowSelect];
    
    ColFecha.Header := 'Fecha';
    ColFecha.Width := 120;
    ColFolio.Header := 'Folio';
    ColFolio.Width := 100;
    ColCliente.Header := 'Cliente';
    ColCliente.Width := 180;
    ColVendedor.Header := 'Vendedor';
    ColVendedor.Width := 120;
    ColSubtotal.Header := 'Subtotal';
    ColSubtotal.Width := 100;
    ColDescuento.Header := 'Descuento';
    ColDescuento.Width := 100;
    ColImpuestos.Header := 'Impuestos';
    ColImpuestos.Width := 100;
    ColTotal.Header := 'Total';
    ColTotal.Width := 100;
    ColEstado.Header := 'Estado';
    ColEstado.Width := 100;
    ColAcciones.Header := 'Acciones';
    ColAcciones.Width := 100;
  finally
    StringGridVentas.EndUpdate;
  end;
  
  // === PAGINACIÓN ===
  with LayoutPaginacion do
  begin
    Parent := GroupBoxVentas;
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
    Text := 'Total: 0 ventas';
  end;
  
  // === RESUMEN DE VENTAS ===
  with GroupBoxResumen do
  begin
    Parent := LayoutInferior;
    Align := TAlignLayout.Left;
    Width := 300;
    Text := 'Resumen de Ventas';
    Margins.Right := 10;
  end;
  
  // Configurar controles de resumen
  with LblTotalVentas do
  begin
    Parent := GroupBoxResumen;
    Position.X := 15;
    Position.Y := 25;
    Width := 120;
    Text := 'Total de Ventas:';
  end;
  
  with EditTotalVentas do
  begin
    Parent := GroupBoxResumen;
    Position.X := 140;
    Position.Y := 22;
    Width := 140;
    ReadOnly := True;
    Text := '$0.00';
  end;
  
  with LblTotalDescuentos do
  begin
    Parent := GroupBoxResumen;
    Position.X := 15;
    Position.Y := 55;
    Width := 120;
    Text := 'Total Descuentos:';
  end;
  
  with EditTotalDescuentos do
  begin
    Parent := GroupBoxResumen;
    Position.X := 140;
    Position.Y := 52;
    Width := 140;
    ReadOnly := True;
    Text := '$0.00';
  end;
  
  with LblTotalImpuestos do
  begin
    Parent := GroupBoxResumen;
    Position.X := 15;
    Position.Y := 85;
    Width := 120;
    Text := 'Total Impuestos:';
  end;
  
  with EditTotalImpuestos do
  begin
    Parent := GroupBoxResumen;
    Position.X := 140;
    Position.Y := 82;
    Width := 140;
    ReadOnly := True;
    Text := '$0.00';
  end;
  
  with LblTotalNeto do
  begin
    Parent := GroupBoxResumen;
    Position.X := 15;
    Position.Y := 115;
    Width := 120;
    Text := 'Total Neto:';
    TextSettings.Font.Style := [TFontStyle.fsBold];
  end;
  
  with EditTotalNeto do
  begin
    Parent := GroupBoxResumen;
    Position.X := 140;
    Position.Y := 112;
    Width := 140;
    ReadOnly := True;
    Text := '$0.00';
    TextSettings.Font.Style := [TFontStyle.fsBold];
  end;
  
  with LblCantidadVentas do
  begin
    Parent := GroupBoxResumen;
    Position.X := 15;
    Position.Y := 145;
    Width := 120;
    Text := 'Cantidad Ventas:';
  end;
  
  with EditCantidadVentas do
  begin
    Parent := GroupBoxResumen;
    Position.X := 140;
    Position.Y := 142;
    Width := 140;
    ReadOnly := True;
    Text := '0';
  end;
  
  with LblPromedioVenta do
  begin
    Parent := GroupBoxResumen;
    Position.X := 15;
    Position.Y := 175;
    Width := 120;
    Text := 'Promedio Venta:';
  end;
  
  with EditPromedioVenta do
  begin
    Parent := GroupBoxResumen;
    Position.X := 140;
    Position.Y := 172;
    Width := 140;
    ReadOnly := True;
    Text := '$0.00';
  end;
  
  // === DETALLE DE VENTA ===
  with GroupBoxDetalle do
  begin
    Parent := LayoutInferior;
    Align := TAlignLayout.Client;
    Text := 'Detalle de Venta Seleccionada';
  end;
  
  with MemoDetalleVenta do
  begin
    Parent := GroupBoxDetalle;
    Align := TAlignLayout.Client;
    Margins.Top := 25;
    Margins.Bottom := 40;
    Margins.Left := 15;
    Margins.Right := 15;
    ReadOnly := True;
    Text := 'Selecciona una venta para ver su detalle';
  end;
  
  with BtnVerDetalle do
  begin
    Parent := GroupBoxDetalle;
    Position.X := 15;
    Position.Y := GroupBoxDetalle.Height - 35;
    Width := 90;
    Height := 25;
    Text := 'Ver Detalle';
    Enabled := False;
  end;
  
  with BtnReimprimirTicket do
  begin
    Parent := GroupBoxDetalle;
    Position.X := 115;
    Position.Y := GroupBoxDetalle.Height - 35;
    Width := 100;
    Height := 25;
    Text := 'Reimprimir';
    Enabled := False;
  end;
  
  with BtnAnularVenta do
  begin
    Parent := GroupBoxDetalle;
    Position.X := 225;
    Position.Y := GroupBoxDetalle.Height - 35;
    Width := 80;
    Height := 25;
    Text := 'Anular';
    Enabled := False;
  end;
  
  // === BOTONES PRINCIPALES ===
  with LayoutBotonesPrincipales do
  begin
    Parent := LayoutInferior;
    Align := TAlignLayout.Bottom;
    Height := 50;
    Padding.Top := 10;
  end;
  
  with BtnNuevaVenta do
  begin
    Parent := LayoutBotonesPrincipales;
    Align := TAlignLayout.Left;
    Width := 120;
    Text := 'Nueva Venta';
    StyleLookup := 'acceptbuttonstyle';
  end;
  
  with BtnCerrar do
  begin
    Parent := LayoutBotonesPrincipales;
    Align := TAlignLayout.Right;
    Width := 80;
    Text := 'Cerrar';
  end;
  
  // === SISTEMA DE TOAST ===
  with RecToast do
  begin
    Align := TAlignLayout.Bottom;
    Height := 50;
    Margins.Bottom := 60;
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

procedure TFormConsultaVentas.CargarCatalogos;
begin
  // TODO: Cargar vendedores y terminales desde la API
  ComboVendedor.Items.Clear;
  ComboVendedor.Items.Add('Todos los vendedores');
  ComboVendedor.Items.Add('Juan Pérez');
  ComboVendedor.Items.Add('María García');
  ComboVendedor.ItemIndex := 0;
  
  ComboTerminal.Items.Clear;
  ComboTerminal.Items.Add('Todas las terminales');
  ComboTerminal.Items.Add('Terminal 001');
  ComboTerminal.Items.Add('Terminal 002');
  ComboTerminal.ItemIndex := 0;
end;

procedure TFormConsultaVentas.EstablecerFiltrosFechas(Dias: Integer);
begin
  case Dias of
    0: // Hoy
    begin
      DateEditDesde.Date := Date;
      DateEditHasta.Date := Date;
    end;
    7: // Últimos 7 días
    begin
      DateEditDesde.Date := Date - 7;
      DateEditHasta.Date := Date;
    end;
    30: // Este mes (aproximado)
    begin
      DateEditDesde.Date := StartOfTheMonth(Date);
      DateEditHasta.Date := Date;
    end;
  end;
end;

procedure TFormConsultaVentas.CargarVentas;
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
                  if Assigned(FVentas) then
                    FVentas.Free;
                  FVentas := JsonData.Clone as TJSONArray;
                  
                  ActualizarGridVentas;
                  ActualizarInfoPaginacion;
                  ActualizarResumenVentas;
                  
                  if FVentas.Count > 0 then
                    MostrarToast(Format('Se cargaron %d ventas', [FVentas.Count]), Success)
                  else
                    MostrarToast('No se encontraron ventas con los filtros aplicados', Info);
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
              MostrarToast('Error al cargar ventas: ' + Response.StatusText, Error);
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

function TFormConsultaVentas.ObtenerUrlConFiltros: string;
var
  Params: TStringList;
  ParamString: string;
  i: Integer;
begin
  Result := API_BASE_URL + '/ventas/';
  
  Params := TStringList.Create;
  try
    // Paginación
    Params.Add('skip=' + IntToStr((FPaginaActual - 1) * FRegistrosPorPagina));
    Params.Add('limit=' + IntToStr(FRegistrosPorPagina));
    
    // Filtros de fecha
    Params.Add('fecha_desde=' + FormatDateTime('yyyy-mm-dd', DateEditDesde.Date));
    Params.Add('fecha_hasta=' + FormatDateTime('yyyy-mm-dd', DateEditHasta.Date));
    
    // Cliente seleccionado
    if FIdClienteSeleccionado <> '' then
      Params.Add('id_cliente=' + FIdClienteSeleccionado);
    
    // Número de folio
    if EditNumeroFolio.Text.Trim <> '' then
      Params.Add('numero_folio=' + TNetEncoding.URL.Encode(EditNumeroFolio.Text.Trim));
    
    // Estado de venta
    if (ComboEstado.ItemIndex > 0) and (ComboEstado.ItemIndex < ComboEstado.Items.Count) then
      Params.Add('estado_venta=' + TNetEncoding.URL.Encode(ComboEstado.Items[ComboEstado.ItemIndex].ToUpper));
    
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

procedure TFormConsultaVentas.ActualizarGridVentas;
var
  i: Integer;
  Venta: TJSONObject;
begin
  if not Assigned(FVentas) then Exit;
  
  StringGridVentas.BeginUpdate;
  try
    StringGridVentas.RowCount := FVentas.Count;
    
    for i := 0 to FVentas.Count - 1 do
    begin
      Venta := FVentas.Items[i] as TJSONObject;
      
      StringGridVentas.Cells[0, i] := FormatearFecha(Venta.GetValue<string>('fecha_venta'));
      StringGridVentas.Cells[1, i] := Venta.GetValue<string>('numero_folio');
      StringGridVentas.Cells[2, i] := 'Cliente'; // TODO: Obtener nombre del cliente
      StringGridVentas.Cells[3, i] := 'Vendedor'; // TODO: Obtener nombre del vendedor
      StringGridVentas.Cells[4, i] := FormatearMoneda(Venta.GetValue<Double>('subtotal'));
      StringGridVentas.Cells[5, i] := FormatearMoneda(Venta.GetValue<Double>('descuento'));
      StringGridVentas.Cells[6, i] := FormatearMoneda(Venta.GetValue<Double>('impuesto'));
      StringGridVentas.Cells[7, i] := FormatearMoneda(Venta.GetValue<Double>('total'));
      StringGridVentas.Cells[8, i] := Venta.GetValue<string>('estado_venta');
      StringGridVentas.Cells[9, i] := 'Ver';
    end;
  finally
    StringGridVentas.EndUpdate;
  end;
end;

procedure TFormConsultaVentas.ActualizarInfoPaginacion;
var
  TotalPaginas: Integer;
begin
  TotalPaginas := Ceil(FTotalRegistros / FRegistrosPorPagina);
  if TotalPaginas = 0 then TotalPaginas := 1;
  
  LblPagina.Text := Format('Página %d de %d', [FPaginaActual, TotalPaginas]);
  LblTotal.Text := Format('Total: %d ventas', [FTotalRegistros]);
  
  BtnAnterior.Enabled := FPaginaActual > 1;
  BtnSiguiente.Enabled := FPaginaActual < TotalPaginas;
end;

procedure TFormConsultaVentas.ActualizarResumenVentas;
var
  i: Integer;
  Venta: TJSONObject;
  TotalVentas, TotalDescuentos, TotalImpuestos, TotalNeto: Double;
  CantidadVentas: Integer;
begin
  if not Assigned(FVentas) then Exit;
  
  TotalVentas := 0;
  TotalDescuentos := 0;
  TotalImpuestos := 0;
  TotalNeto := 0;
  CantidadVentas := FVentas.Count;
  
  for i := 0 to FVentas.Count - 1 do
  begin
    Venta := FVentas.Items[i] as TJSONObject;
    TotalVentas := TotalVentas + Venta.GetValue<Double>('subtotal');
    TotalDescuentos := TotalDescuentos + Venta.GetValue<Double>('descuento');
    TotalImpuestos := TotalImpuestos + Venta.GetValue<Double>('impuesto');
    TotalNeto := TotalNeto + Venta.GetValue<Double>('total');
  end;
  
  EditTotalVentas.Text := FormatearMoneda(TotalVentas);
  EditTotalDescuentos.Text := FormatearMoneda(TotalDescuentos);
  EditTotalImpuestos.Text := FormatearMoneda(TotalImpuestos);
  EditTotalNeto.Text := FormatearMoneda(TotalNeto);
  EditCantidadVentas.Text := IntToStr(CantidadVentas);
  
  if CantidadVentas > 0 then
    EditPromedioVenta.Text := FormatearMoneda(TotalNeto / CantidadVentas)
  else
    EditPromedioVenta.Text := '$0.00';
end;

procedure TFormConsultaVentas.ActualizarDetalleVentaSeleccionada;
var
  Detalle: string;
begin
  if Assigned(FVentaSeleccionada) then
  begin
    Detalle := 'VENTA SELECCIONADA' + #13#10;
    Detalle := Detalle + 'Folio: ' + FVentaSeleccionada.GetValue<string>('numero_folio') + #13#10;
    Detalle := Detalle + 'Fecha: ' + FormatearFecha(FVentaSeleccionada.GetValue<string>('fecha_venta')) + #13#10;
    Detalle := Detalle + 'Subtotal: ' + FormatearMoneda(FVentaSeleccionada.GetValue<Double>('subtotal')) + #13#10;
    Detalle := Detalle + 'Descuento: ' + FormatearMoneda(FVentaSeleccionada.GetValue<Double>('descuento')) + #13#10;
    Detalle := Detalle + 'Impuestos: ' + FormatearMoneda(FVentaSeleccionada.GetValue<Double>('impuesto')) + #13#10;
    Detalle := Detalle + 'Total: ' + FormatearMoneda(FVentaSeleccionada.GetValue<Double>('total')) + #13#10;
    Detalle := Detalle + 'Estado: ' + FVentaSeleccionada.GetValue<string>('estado_venta');
    
    MemoDetalleVenta.Text := Detalle;
    
    BtnVerDetalle.Enabled := True;
    BtnReimprimirTicket.Enabled := True;
    BtnAnularVenta.Enabled := FVentaSeleccionada.GetValue<string>('estado_venta') = 'COMPLETADA';
  end
  else
  begin
    MemoDetalleVenta.Text := 'Selecciona una venta para ver su detalle';
    BtnVerDetalle.Enabled := False;
    BtnReimprimirTicket.Enabled := False;
    BtnAnularVenta.Enabled := False;
  end;
end;

function TFormConsultaVentas.FormatearFecha(const FechaStr: string): string;
begin
  try
    // TODO: Formatear fecha apropiadamente
    Result := FechaStr;
  except
    Result := FechaStr;
  end;
end;

function TFormConsultaVentas.FormatearMoneda(Valor: Double): string;
begin
  Result := FormatFloat('$#,##0.00', Valor);
end;

procedure TFormConsultaVentas.StringGridVentasSelChanged(Sender: TObject);
var
  FilaSeleccionada: Integer;
begin
  FilaSeleccionada := StringGridVentas.Selected;
  
  if (FilaSeleccionada >= 0) and (FilaSeleccionada < FVentas.Count) then
  begin
    FVentaSeleccionada := FVentas.Items[FilaSeleccionada] as TJSONObject;
    ActualizarDetalleVentaSeleccionada;
  end
  else
  begin
    FVentaSeleccionada := nil;
    ActualizarDetalleVentaSeleccionada;
  end;
end;

procedure TFormConsultaVentas.StringGridVentasCellDblClick(const Column: TColumn; const Row: Integer);
begin
  BtnVerDetalleClick(nil);
end;

// === EVENTOS DE BOTONES ===

procedure TFormConsultaVentas.BtnBuscarClick(Sender: TObject);
begin
  FPaginaActual := 1;
  CargarVentas;
end;

procedure TFormConsultaVentas.BtnLimpiarFiltrosClick(Sender: TObject);
begin
  LimpiarFiltros;
end;

procedure TFormConsultaVentas.LimpiarFiltros;
begin
  EditCliente.Text := '';
  FIdClienteSeleccionado := '';
  EditNumeroFolio.Text := '';
  ComboVendedor.ItemIndex := 0;
  ComboTerminal.ItemIndex := 0;
  ComboEstado.ItemIndex := 0;
  EstablecerFiltrosFechas(0); // Hoy
  FPaginaActual := 1;
  CargarVentas;
end;

procedure TFormConsultaVentas.BtnHoyClick(Sender: TObject);
begin
  EstablecerFiltrosFechas(0);
  BtnBuscarClick(nil);
end;

procedure TFormConsultaVentas.BtnUltimos7DiasClick(Sender: TObject);
begin
  EstablecerFiltrosFechas(7);
  BtnBuscarClick(nil);
end;

procedure TFormConsultaVentas.BtnEsteMesClick(Sender: TObject);
begin
  EstablecerFiltrosFechas(30);
  BtnBuscarClick(nil);
end;

procedure TFormConsultaVentas.BtnSeleccionarClienteClick(Sender: TObject);
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

procedure TFormConsultaVentas.BtnAnteriorClick(Sender: TObject);
begin
  if FPaginaActual > 1 then
  begin
    Dec(FPaginaActual);
    CargarVentas;
  end;
end;

procedure TFormConsultaVentas.BtnSiguienteClick(Sender: TObject);
var
  TotalPaginas: Integer;
begin
  TotalPaginas := Ceil(FTotalRegistros / FRegistrosPorPagina);
  if FPaginaActual < TotalPaginas then
  begin
    Inc(FPaginaActual);
    CargarVentas;
  end;
end;

procedure TFormConsultaVentas.BtnVerDetalleClick(Sender: TObject);
begin
  if Assigned(FVentaSeleccionada) then
  begin
    // TODO: Abrir ventana de detalle completo de la venta
    MostrarToast('Detalle completo de venta en desarrollo', Info);
  end;
end;

procedure TFormConsultaVentas.BtnReimprimirTicketClick(Sender: TObject);
begin
  if Assigned(FVentaSeleccionada) then
  begin
    // TODO: Reimprimir ticket
    MostrarToast('Reimpresión de ticket en desarrollo', Info);
  end;
end;

procedure TFormConsultaVentas.BtnAnularVentaClick(Sender: TObject);
begin
  if Assigned(FVentaSeleccionada) then
  begin
    TDialogService.MessageDialog(
      '¿Está seguro de anular esta venta?',
      TMsgDlgType.mtConfirmation,
      [TMsgDlgBtn.mbYes, TMsgDlgBtn.mbNo],
      TMsgDlgBtn.mbNo,
      0,
      procedure(const AResult: TModalResult)
      begin
        if AResult = mrYes then
        begin
          // TODO: Anular venta
          MostrarToast('Anulación de venta en desarrollo', Info);
        end;
      end
    );
  end;
end;

procedure TFormConsultaVentas.BtnNuevaVentaClick(Sender: TObject);
var
  FormPuntoVenta: TFormPuntoVenta;
begin
  FormPuntoVenta := TFormPuntoVenta.Create(Self);
  try
    FormPuntoVenta.ShowModal;
    // Recargar ventas al regresar
    CargarVentas;
  finally
    FormPuntoVenta.Free;
  end;
end;

procedure TFormConsultaVentas.BtnCerrarClick(Sender: TObject);
begin
  Close;
end;

procedure TFormConsultaVentas.BtnExportarClick(Sender: TObject);
begin
  // TODO: Exportar ventas a Excel/PDF
  MostrarToast('Exportación en desarrollo', Info);
end;

procedure TFormConsultaVentas.DateEditDesdeChange(Sender: TObject);
begin
  // Auto-ajustar fecha hasta si es menor que desde
  if DateEditHasta.Date < DateEditDesde.Date then
    DateEditHasta.Date := DateEditDesde.Date;
end;

procedure TFormConsultaVentas.DateEditHastaChange(Sender: TObject);
begin
  // Auto-ajustar fecha desde si es mayor que hasta
  if DateEditDesde.Date > DateEditHasta.Date then
    DateEditDesde.Date := DateEditHasta.Date;
end;

procedure TFormConsultaVentas.MostrarToast(const Mensaje: string; Tipo: TToastTipo);
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