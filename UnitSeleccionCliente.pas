unit UnitSeleccionCliente;

interface

uses
  System.SysUtils, System.Types, System.UITypes, System.Classes, System.Variants,
  FMX.Types, FMX.Controls, FMX.Forms, FMX.Graphics, FMX.Dialogs,
  System.Rtti, FMX.Grid.Style, FMX.Grid, FMX.ScrollBox,
  FMX.Edit, FMX.StdCtrls, FMX.Controls.Presentation, DataModule,
  System.Net.HttpClient, System.Net.HttpClientComponent, System.JSON, 
  System.net.URLClient, System.Generics.Collections, FMX.Ani, FMX.Objects, 
  FMX.Effects, FMX.DialogService, System.Threading, FMX.Layouts;

type
  TToastTipo = (Success, Info, Error);
  
  TClienteInfo = record
    IdCliente: string;
    Nombre: string;
    Apellido: string;
    Telefono: string;
    Email: string;
    RFC: string;
  end;

type
  TFormSeleccionCliente = class(TForm)
    // === LAYOUT PRINCIPAL ===
    LayoutPrincipal: TLayout;
    
    // === BÚSQUEDA Y FILTROS ===
    GroupBoxFiltros: TGroupBox;
    LblBuscar: TLabel;
    EditBuscar: TEdit;
    BtnBuscar: TButton;
    BtnLimpiar: TButton;
    LblFiltroTipo: TLabel;
    CheckTodos: TCheckBox;
    CheckEmpresa: TCheckBox;
    CheckConsumidor: TCheckBox;
    
    // === GRID DE CLIENTES ===
    GroupBoxClientes: TGroupBox;
    StringGridClientes: TStringGrid;
    ColNombre: TStringColumn;
    ColApellido: TStringColumn;
    ColTelefono: TStringColumn;
    ColEmail: TStringColumn;
    ColRFC: TStringColumn;
    ColTipo: TStringColumn;
    
    // === PAGINACIÓN ===
    LayoutPaginacion: TLayout;
    BtnAnterior: TButton;
    BtnSiguiente: TButton;
    LblPagina: TLabel;
    LblTotal: TLabel;
    EditTamanoPagina: TEdit;
    LblTamanoPagina: TLabel;
    
    // === BOTONES DE ACCIÓN ===
    LayoutBotones: TLayout;
    BtnSeleccionar: TButton;
    BtnNuevoCliente: TButton;
    BtnCancelar: TButton;
    
    // === INFORMACIÓN DEL CLIENTE SELECCIONADO ===
    GroupBoxSeleccionado: TGroupBox;
    LblClienteSeleccionado: TLabel;
    MemoInfoCliente: TMemo;
    
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
    procedure BtnSeleccionarClick(Sender: TObject);
    procedure BtnNuevoClienteClick(Sender: TObject);
    procedure BtnCancelarClick(Sender: TObject);
    procedure BtnAnteriorClick(Sender: TObject);
    procedure BtnSiguienteClick(Sender: TObject);
    procedure StringGridClientesCellDblClick(const Column: TColumn; const Row: Integer);
    procedure StringGridClientesSelChanged(Sender: TObject);
    procedure EditBuscarKeyDown(Sender: TObject; var Key: Word; var KeyChar: Char; Shift: TShiftState);
    procedure CheckTodosChange(Sender: TObject);
    procedure CheckEmpresaChange(Sender: TObject);
    procedure CheckConsumidorChange(Sender: TObject);
    
  private
    FPaginaActual: Integer;
    FTotalRegistros: Integer;
    FRegistrosPorPagina: Integer;
    FClientes: TJSONArray;
    FClienteSeleccionado: TClienteInfo;
    FHaySeleccion: Boolean;
    
    procedure ConfigurarInterfaz;
    procedure CargarClientes;
    procedure ActualizarGridClientes;
    procedure ActualizarInfoPaginacion;
    procedure ActualizarInfoClienteSeleccionado;
    procedure LimpiarFiltros;
    procedure MostrarToast(const Mensaje: string; Tipo: TToastTipo = TToastTipo.Info);
    function ObtenerUrlConFiltros: string;
    function ObtenerClienteDeGrid(Fila: Integer): TClienteInfo;
    
  public
    property ClienteSeleccionado: TClienteInfo read FClienteSeleccionado;
    property HaySeleccion: Boolean read FHaySeleccion;
    
  end;

var
  FormSeleccionCliente: TFormSeleccionCliente;
  API_BASE_URL: string;

implementation

{$R *.fmx}

procedure TFormSeleccionCliente.FormCreate(Sender: TObject);
begin
  API_BASE_URL := DM.GetApiBaseUrl;
  
  FPaginaActual := 1;
  FRegistrosPorPagina := 20;
  FTotalRegistros := 0;
  FClientes := nil;
  FHaySeleccion := False;
  
  ConfigurarInterfaz;
end;

procedure TFormSeleccionCliente.FormShow(Sender: TObject);
begin
  CargarClientes;
  EditBuscar.SetFocus;
end;

procedure TFormSeleccionCliente.ConfigurarInterfaz;
begin
  // === CONFIGURAR VENTANA ===
  Width := 900;
  Height := 700;
  Position := TFormPosition.ScreenCenter;
  BorderStyle := TFmxFormBorderStyle.Single;
  Caption := 'Seleccionar Cliente';
  
  // === LAYOUT PRINCIPAL ===
  with LayoutPrincipal do
  begin
    Align := TAlignLayout.Client;
    Padding.Left := 15;
    Padding.Right := 15;
    Padding.Top := 15;
    Padding.Bottom := 15;
  end;
  
  // === GRUPO DE FILTROS ===
  with GroupBoxFiltros do
  begin
    Align := TAlignLayout.Top;
    Height := 100;
    Text := 'Búsqueda y Filtros';
    Margins.Bottom := 10;
  end;
  
  with LblBuscar do
  begin
    Position.X := 15;
    Position.Y := 25;
    Text := 'Buscar:';
    Width := 50;
  end;
  
  with EditBuscar do
  begin
    Position.X := 70;
    Position.Y := 22;
    Width := 200;
    TextPrompt := 'Nombre, teléfono, email, RFC...';
  end;
  
  with BtnBuscar do
  begin
    Position.X := 280;
    Position.Y := 22;
    Width := 70;
    Height := 25;
    Text := 'Buscar';
  end;
  
  with BtnLimpiar do
  begin
    Position.X := 360;
    Position.Y := 22;
    Width := 70;
    Height := 25;
    Text := 'Limpiar';
  end;
  
  with LblFiltroTipo do
  begin
    Position.X := 15;
    Position.Y := 55;
    Text := 'Tipo de Cliente:';
    Width := 100;
  end;
  
  with CheckTodos do
  begin
    Position.X := 120;
    Position.Y := 55;
    Width := 60;
    Text := 'Todos';
    IsChecked := True;
  end;
  
  with CheckEmpresa do
  begin
    Position.X := 190;
    Position.Y := 55;
    Width := 80;
    Text := 'Empresa';
  end;
  
  with CheckConsumidor do
  begin
    Position.X := 280;
    Position.Y := 55;
    Width := 100;
    Text := 'Consumidor';
  end;
  
  // === GRUPO DE CLIENTES ===
  with GroupBoxClientes do
  begin
    Align := TAlignLayout.Client;
    Text := 'Lista de Clientes';
    Margins.Bottom := 10;
  end;
  
  // === CONFIGURAR GRID ===
  StringGridClientes.BeginUpdate;
  try
    StringGridClientes.Parent := GroupBoxClientes;
    StringGridClientes.Align := TAlignLayout.Client;
    StringGridClientes.Margins.Top := 25;
    StringGridClientes.Margins.Bottom := 5;
    StringGridClientes.RowCount := 0;
    StringGridClientes.Options := StringGridClientes.Options + [TGridOption.RowSelect];
    
    ColNombre.Header := 'Nombre';
    ColNombre.Width := 150;
    ColApellido.Header := 'Apellido';
    ColApellido.Width := 150;
    ColTelefono.Header := 'Teléfono';
    ColTelefono.Width := 120;
    ColEmail.Header := 'Email';
    ColEmail.Width := 180;
    ColRFC.Header := 'RFC';
    ColRFC.Width := 120;
    ColTipo.Header := 'Tipo';
    ColTipo.Width := 100;
  finally
    StringGridClientes.EndUpdate;
  end;
  
  // === PAGINACIÓN ===
  with LayoutPaginacion do
  begin
    Align := TAlignLayout.Bottom;
    Height := 40;
    Margins.Bottom := 10;
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
    Text := 'Total: 0 clientes';
  end;
  
  // === INFORMACIÓN DEL CLIENTE SELECCIONADO ===
  with GroupBoxSeleccionado do
  begin
    Align := TAlignLayout.Bottom;
    Height := 120;
    Text := 'Cliente Seleccionado';
    Margins.Bottom := 10;
  end;
  
  with LblClienteSeleccionado do
  begin
    Parent := GroupBoxSeleccionado;
    Position.X := 15;
    Position.Y := 25;
    Width := 400;
    Height := 20;
    Text := 'Ningún cliente seleccionado';
    TextSettings.Font.Style := [TFontStyle.fsBold];
  end;
  
  with MemoInfoCliente do
  begin
    Parent := GroupBoxSeleccionado;
    Position.X := 15;
    Position.Y := 50;
    Width := GroupBoxSeleccionado.Width - 30;
    Height := 60;
    ReadOnly := True;
    Text := '';
  end;
  
  // === BOTONES DE ACCIÓN ===
  with LayoutBotones do
  begin
    Align := TAlignLayout.Bottom;
    Height := 50;
  end;
  
  with BtnSeleccionar do
  begin
    Parent := LayoutBotones;
    Align := TAlignLayout.Left;
    Width := 120;
    Text := 'Seleccionar';
    ModalResult := mrOk;
    Enabled := False;
    StyleLookup := 'acceptbuttonstyle';
  end;
  
  with BtnNuevoCliente do
  begin
    Parent := LayoutBotones;
    Align := TAlignLayout.Left;
    Width := 120;
    Text := 'Nuevo Cliente';
    Margins.Left := 10;
  end;
  
  with BtnCancelar do
  begin
    Parent := LayoutBotones;
    Align := TAlignLayout.Right;
    Width := 80;
    Text := 'Cancelar';
    ModalResult := mrCancel;
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

procedure TFormSeleccionCliente.CargarClientes;
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
                  if Assigned(FClientes) then
                    FClientes.Free;
                  FClientes := JsonData.Clone as TJSONArray;
                  
                  ActualizarGridClientes;
                  ActualizarInfoPaginacion;
                  
                  if FClientes.Count > 0 then
                    MostrarToast(Format('Se cargaron %d clientes', [FClientes.Count]), Success)
                  else
                    MostrarToast('No se encontraron clientes con los filtros aplicados', Info);
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
              MostrarToast('Error al cargar clientes: ' + Response.StatusText, Error);
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

function TFormSeleccionCliente.ObtenerUrlConFiltros: string;
var
  Params: TStringList;
  ParamString: string;
  i: Integer;
begin
  Result := API_BASE_URL + '/clientes/';
  
  Params := TStringList.Create;
  try
    // Paginación
    Params.Add('skip=' + IntToStr((FPaginaActual - 1) * FRegistrosPorPagina));
    Params.Add('limit=' + IntToStr(FRegistrosPorPagina));
    
    // Búsqueda general
    if EditBuscar.Text.Trim <> '' then
      Params.Add('nombre=' + TNetEncoding.URL.Encode(EditBuscar.Text.Trim));
    
    // Filtros por tipo (si no están todos seleccionados)
    if not CheckTodos.IsChecked then
    begin
      if CheckEmpresa.IsChecked and not CheckConsumidor.IsChecked then
        Params.Add('tipo_cliente=EMPRESA');
      if CheckConsumidor.IsChecked and not CheckEmpresa.IsChecked then
        Params.Add('tipo_cliente=CONSUMIDOR_FINAL');
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

procedure TFormSeleccionCliente.ActualizarGridClientes;
var
  i: Integer;
  Cliente: TJSONObject;
begin
  if not Assigned(FClientes) then Exit;
  
  StringGridClientes.BeginUpdate;
  try
    StringGridClientes.RowCount := FClientes.Count;
    
    for i := 0 to FClientes.Count - 1 do
    begin
      Cliente := FClientes.Items[i] as TJSONObject;
      
      StringGridClientes.Cells[0, i] := Cliente.GetValue<string>('nombre');
      StringGridClientes.Cells[1, i] := Cliente.GetValue<string>('apellido', '');
      StringGridClientes.Cells[2, i] := Cliente.GetValue<string>('telefono', '');
      StringGridClientes.Cells[3, i] := Cliente.GetValue<string>('email', '');
      StringGridClientes.Cells[4, i] := Cliente.GetValue<string>('rfc', '');
      StringGridClientes.Cells[5, i] := Cliente.GetValue<string>('tipo_cliente', 'CONSUMIDOR_FINAL');
    end;
  finally
    StringGridClientes.EndUpdate;
  end;
end;

procedure TFormSeleccionCliente.ActualizarInfoPaginacion;
var
  TotalPaginas: Integer;
begin
  TotalPaginas := Ceil(FTotalRegistros / FRegistrosPorPagina);
  if TotalPaginas = 0 then TotalPaginas := 1;
  
  LblPagina.Text := Format('Página %d de %d', [FPaginaActual, TotalPaginas]);
  LblTotal.Text := Format('Total: %d clientes', [FTotalRegistros]);
  
  BtnAnterior.Enabled := FPaginaActual > 1;
  BtnSiguiente.Enabled := FPaginaActual < TotalPaginas;
end;

procedure TFormSeleccionCliente.ActualizarInfoClienteSeleccionado;
var
  Info: string;
begin
  if FHaySeleccion then
  begin
    LblClienteSeleccionado.Text := FClienteSeleccionado.Nombre + ' ' + FClienteSeleccionado.Apellido;
    
    Info := '';
    if FClienteSeleccionado.Telefono <> '' then
      Info := Info + 'Teléfono: ' + FClienteSeleccionado.Telefono + #13#10;
    if FClienteSeleccionado.Email <> '' then
      Info := Info + 'Email: ' + FClienteSeleccionado.Email + #13#10;
    if FClienteSeleccionado.RFC <> '' then
      Info := Info + 'RFC: ' + FClienteSeleccionado.RFC;
    
    MemoInfoCliente.Text := Info;
    BtnSeleccionar.Enabled := True;
  end
  else
  begin
    LblClienteSeleccionado.Text := 'Ningún cliente seleccionado';
    MemoInfoCliente.Text := '';
    BtnSeleccionar.Enabled := False;
  end;
end;

function TFormSeleccionCliente.ObtenerClienteDeGrid(Fila: Integer): TClienteInfo;
var
  Cliente: TJSONObject;
begin
  if (Fila >= 0) and (Fila < FClientes.Count) then
  begin
    Cliente := FClientes.Items[Fila] as TJSONObject;
    
    Result.IdCliente := Cliente.GetValue<string>('id_cliente');
    Result.Nombre := Cliente.GetValue<string>('nombre');
    Result.Apellido := Cliente.GetValue<string>('apellido', '');
    Result.Telefono := Cliente.GetValue<string>('telefono', '');
    Result.Email := Cliente.GetValue<string>('email', '');
    Result.RFC := Cliente.GetValue<string>('rfc', '');
  end
  else
  begin
    Result.IdCliente := '';
    Result.Nombre := '';
    Result.Apellido := '';
    Result.Telefono := '';
    Result.Email := '';
    Result.RFC := '';
  end;
end;

procedure TFormSeleccionCliente.StringGridClientesSelChanged(Sender: TObject);
var
  FilaSeleccionada: Integer;
begin
  FilaSeleccionada := StringGridClientes.Selected;
  
  if (FilaSeleccionada >= 0) and (FilaSeleccionada < StringGridClientes.RowCount) then
  begin
    FClienteSeleccionado := ObtenerClienteDeGrid(FilaSeleccionada);
    FHaySeleccion := True;
  end
  else
  begin
    FHaySeleccion := False;
  end;
  
  ActualizarInfoClienteSeleccionado;
end;

procedure TFormSeleccionCliente.StringGridClientesCellDblClick(const Column: TColumn; const Row: Integer);
begin
  if FHaySeleccion then
  begin
    ModalResult := mrOk;
    Close;
  end;
end;

procedure TFormSeleccionCliente.BtnBuscarClick(Sender: TObject);
begin
  FPaginaActual := 1;
  CargarClientes;
end;

procedure TFormSeleccionCliente.EditBuscarKeyDown(Sender: TObject; var Key: Word; var KeyChar: Char; Shift: TShiftState);
begin
  if Key = vkReturn then
  begin
    BtnBuscarClick(nil);
    Key := 0;
  end;
end;

procedure TFormSeleccionCliente.BtnLimpiarClick(Sender: TObject);
begin
  LimpiarFiltros;
end;

procedure TFormSeleccionCliente.LimpiarFiltros;
begin
  EditBuscar.Text := '';
  CheckTodos.IsChecked := True;
  CheckEmpresa.IsChecked := False;
  CheckConsumidor.IsChecked := False;
  FPaginaActual := 1;
  CargarClientes;
end;

procedure TFormSeleccionCliente.CheckTodosChange(Sender: TObject);
begin
  if CheckTodos.IsChecked then
  begin
    CheckEmpresa.IsChecked := False;
    CheckConsumidor.IsChecked := False;
  end;
end;

procedure TFormSeleccionCliente.CheckEmpresaChange(Sender: TObject);
begin
  if CheckEmpresa.IsChecked then
    CheckTodos.IsChecked := False;
end;

procedure TFormSeleccionCliente.CheckConsumidorChange(Sender: TObject);
begin
  if CheckConsumidor.IsChecked then
    CheckTodos.IsChecked := False;
end;

procedure TFormSeleccionCliente.BtnAnteriorClick(Sender: TObject);
begin
  if FPaginaActual > 1 then
  begin
    Dec(FPaginaActual);
    CargarClientes;
  end;
end;

procedure TFormSeleccionCliente.BtnSiguienteClick(Sender: TObject);
var
  TotalPaginas: Integer;
begin
  TotalPaginas := Ceil(FTotalRegistros / FRegistrosPorPagina);
  if FPaginaActual < TotalPaginas then
  begin
    Inc(FPaginaActual);
    CargarClientes;
  end;
end;

procedure TFormSeleccionCliente.BtnSeleccionarClick(Sender: TObject);
begin
  if not FHaySeleccion then
  begin
    MostrarToast('Selecciona un cliente de la lista', Error);
    Exit;
  end;
  
  ModalResult := mrOk;
  Close;
end;

procedure TFormSeleccionCliente.BtnNuevoClienteClick(Sender: TObject);
begin
  // TODO: Abrir formulario de nuevo cliente
  MostrarToast('Formulario de nuevo cliente en desarrollo', Info);
end;

procedure TFormSeleccionCliente.BtnCancelarClick(Sender: TObject);
begin
  ModalResult := mrCancel;
  Close;
end;

procedure TFormSeleccionCliente.MostrarToast(const Mensaje: string; Tipo: TToastTipo);
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