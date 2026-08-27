Attribute VB_Name = "SPREAD_SINCE"
Option Explicit

'==================================================================================
' SPREAD_SINCE - spread variation of every bond since a fixed anchor date
'
' Anchor date lives in Company_desc!D1 (currently 14.07.2026). The Formulas sheet
' carries three extra Bloomberg columns driven by that cell:
'     Y  (25) Spread change since <anchor>   = N - BDP(...,"YAS_OAS_SPRD","SETTLE_DT",D1)
'     Z  (26) YTW change since <anchor>      = K - BDP(...,"YAS_BOND_YLD",...,"SETTLE_DT",D1)
'     AA (27) Spread level on <anchor>       =     BDP(...,"YAS_OAS_SPRD","SETTLE_DT",D1)
'
' This module is purely additive - it does not modify any existing procedure.
' Entry point: RM_VERSION_WITH_SINCE
'==================================================================================

Public Const SINCE_SHEET   As String = "Spread - since 14.07.2026"
Public Const SINCE_SRC_COL As Long = 25          ' Formulas/Bonds_list_hard column Y
Public Const LAST_DATA_COL As Long = 27          ' column AA

'----------------------------------------------------------------------------------
' Master routine - same flow as RM_VERSION_SIMPLIFIED plus the "since" table
'----------------------------------------------------------------------------------
Sub RM_VERSION_WITH_SINCE()
    Dim answer As VbMsgBoxResult

    answer = MsgBox("This will refresh Bonds_list_hard from Formulas (columns A:AA) " & _
                    "and rebuild every ranking sheet, including """ & SINCE_SHEET & """." & vbCrLf & vbCrLf & _
                    "Make sure the Bloomberg add-in is connected and the Formulas sheet has finished " & _
                    "calculating before continuing." & vbCrLf & vbCrLf & "Continue?", _
                    vbYesNo + vbExclamation, "Warning")
    If answer = vbNo Then Exit Sub

    Call ActualiserDonneesBonsFull(False)

    With ThisWorkbook.Sheets("Bonds_list_hard")
        .Columns("K").NumberFormat = "0.00"
        .Columns("L").NumberFormat = "0.00"
        .Columns("M").NumberFormat = "0.00"
        .Columns("N").NumberFormat = "0"
        .Columns("W").NumberFormat = "0"
        .Columns("X").NumberFormat = "0"
        .Columns("Y").NumberFormat = "0"
        .Columns("Z").NumberFormat = "0.00"
        .Columns("AA").NumberFormat = "0"
    End With

    Call Grouping                       ' SPREAD module
    Call PROCESSTABLEADVANCED           ' SPREAD module
    Call TOC                            ' SPREAD module
    Call AddSinceNavLink                ' adds the 4th link under "Ranking Sheets"
    Call MacroSPREADWEEK                ' SPREAD module
    Call MacroSPREADMONTH               ' SPREAD module
    Call MacroSPREADSINCE               ' this module

    MsgBox "!Done! The macro has finished running.", vbInformation, "Completed"
End Sub

'----------------------------------------------------------------------------------
' Same as ActualiserDonneesBons but copies A:AA instead of A:X
'----------------------------------------------------------------------------------
Sub ActualiserDonneesBonsFull(Optional ByVal showMessage As Boolean = True)
    Dim wsSource As Worksheet
    Dim wsTarget As Worksheet
    Dim tblRange As Range
    Dim tbl      As ListObject
    Dim lastRow  As Long

    Set wsSource = ThisWorkbook.Sheets("Formulas")
    Set wsTarget = ThisWorkbook.Sheets("Bonds_list_hard")

    On Error Resume Next
    For Each tbl In wsTarget.ListObjects
        tbl.Delete
    Next tbl
    On Error GoTo 0
    wsTarget.Cells.Clear

    lastRow = wsSource.Cells(wsSource.Rows.Count, "A").End(xlUp).Row
    If lastRow < 2 Then
        MsgBox "Aucune donnee trouvee dans la feuille Formulas.", vbExclamation
        Exit Sub
    End If

    Set tblRange = wsTarget.Range("A1").Resize(lastRow, LAST_DATA_COL)
    tblRange.Value = wsSource.Range("A1").Resize(lastRow, LAST_DATA_COL).Value

    Set tbl = wsTarget.ListObjects.Add(xlSrcRange, tblRange, , xlYes)
    With tbl
        .Name = "Tableau_Bonds_Final"
        .TableStyle = "TableStyleMedium2"
    End With

    If showMessage Then MsgBox "Mise a jour terminee avec succes !", vbInformation
End Sub

'----------------------------------------------------------------------------------
' WORST 10 / TOP 10 spread movers since the anchor date, one pair per currency
'----------------------------------------------------------------------------------
Sub MacroSPREADSINCE()
    Dim wsSource      As Worksheet
    Dim wsDest        As Worksheet
    Dim lastRow       As Long
    Dim lastCol       As Long
    Dim i             As Long
    Dim j             As Long
    Dim k             As Long
    Dim dict          As Object
    Dim col           As Collection
    Dim arr           As Variant
    Dim arrWidening   As Variant
    Dim arrTightening As Variant
    Dim wideCount     As Long
    Dim tightCount    As Long
    Dim destRow       As Long
    Dim tableStartRow As Long
    Dim lo            As ListObject
    Dim tableName     As String
    Dim suffix        As Integer
    Dim tblRange      As Range
    Dim colOrder()    As Long
    Dim idx           As Long
    Dim sortPos       As Long
    Dim a             As Long
    Dim b             As Long
    Dim temp          As Variant
    Dim validRows     As Collection
    Dim ki            As Long
    Dim currKey       As String
    Dim anchorTxt     As String

    Dim orderedKeys(1 To 4) As String
    orderedKeys(1) = "USD"
    orderedKeys(2) = "EUR"
    orderedKeys(3) = "GBP"
    orderedKeys(4) = "CHF"

    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    Application.EnableEvents = False

    Set wsSource = ThisWorkbook.Sheets("Bonds_list_hard")

    anchorTxt = "the anchor date"
    On Error Resume Next
    anchorTxt = Format(ThisWorkbook.Sheets("Company_desc").Range("D1").Value, "dd.mm.yyyy")
    On Error GoTo 0

    On Error Resume Next
    Set wsDest = ThisWorkbook.Sheets(SINCE_SHEET)
    On Error GoTo 0
    If wsDest Is Nothing Then
        Set wsDest = ThisWorkbook.Sheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        wsDest.Name = SINCE_SHEET
    End If
    wsDest.Cells.Clear

    lastCol = wsSource.Cells(1, wsSource.Columns.Count).End(xlToLeft).Column
    If lastCol < SINCE_SRC_COL Then
        MsgBox "Bonds_list_hard stops at column " & lastCol & ". Run ActualiserDonneesBonsFull first " & _
               "so columns Y:AA are copied across.", vbExclamation
        GoTo CleanExit
    End If

    ' Same column selection as the 1-week / 1-month tables:
    ' 1-14 (identity + price/yield/spread), 18-20 (currency, classification, rating),
    ' 23-24 (1w / 1m spread change) and 25 onwards (the "since" columns).
    ReDim colOrder(1 To lastCol)
    idx = 1
    For k = 1 To 13:      colOrder(idx) = k: idx = idx + 1: Next k
    colOrder(idx) = 14:   idx = idx + 1
    For k = 18 To 20:     colOrder(idx) = k: idx = idx + 1: Next k
    colOrder(idx) = 23:   idx = idx + 1
    colOrder(idx) = 24:   idx = idx + 1
    For k = 25 To lastCol: colOrder(idx) = k: idx = idx + 1: Next k
    ReDim Preserve colOrder(1 To idx - 1)

    sortPos = 0
    For k = 1 To UBound(colOrder)
        If colOrder(k) = SINCE_SRC_COL Then
            sortPos = k
            Exit For
        End If
    Next k
    If sortPos = 0 Then
        MsgBox "Column " & SINCE_SRC_COL & " is not part of the output layout.", vbExclamation
        GoTo CleanExit
    End If

    Set dict = CreateObject("Scripting.Dictionary")
    lastRow = wsSource.Cells(wsSource.Rows.Count, SINCE_SRC_COL).End(xlUp).Row

    For i = 2 To lastRow
        currKey = SafeTrim(wsSource.Cells(i, "R").Value)
        If currKey <> "" Then
            If Not dict.Exists(currKey) Then Set dict(currKey) = New Collection
            dict(currKey).Add i
        End If
    Next i

    destRow = 1

    For ki = 1 To 4
        currKey = orderedKeys(ki)
        If dict.Exists(currKey) Then
            Set col = dict(currKey)
            ReDim arr(1 To col.Count, 1 To UBound(colOrder))
            For j = 1 To col.Count
                For k = 1 To UBound(colOrder)
                    arr(j, k) = wsSource.Cells(col(j), colOrder(k)).Value
                Next k
            Next j

            Set validRows = New Collection
            For j = 1 To UBound(arr, 1)
                If Not IsError(arr(j, sortPos)) Then
                    If IsNumeric(arr(j, sortPos)) And Not IsEmpty(arr(j, sortPos)) Then
                        If Trim(CStr(arr(j, sortPos))) <> "" Then validRows.Add j
                    End If
                End If
            Next j

            If validRows.Count > 0 Then
                ReDim arrWidening(1 To validRows.Count, 1 To UBound(colOrder))
                ReDim arrTightening(1 To validRows.Count, 1 To UBound(colOrder))
                For j = 1 To validRows.Count
                    For k = 1 To UBound(colOrder)
                        arrWidening(j, k) = arr(validRows(j), k)
                        arrTightening(j, k) = arr(validRows(j), k)
                    Next k
                Next j

                ' Descending: biggest widening since the anchor date
                For a = 1 To UBound(arrWidening, 1) - 1
                    For b = a + 1 To UBound(arrWidening, 1)
                        If arrWidening(a, sortPos) < arrWidening(b, sortPos) Then
                            For k = 1 To UBound(colOrder)
                                temp = arrWidening(a, k): arrWidening(a, k) = arrWidening(b, k): arrWidening(b, k) = temp
                            Next k
                        End If
                    Next b
                Next a

                ' Ascending: biggest tightening since the anchor date
                For a = 1 To UBound(arrTightening, 1) - 1
                    For b = a + 1 To UBound(arrTightening, 1)
                        If arrTightening(a, sortPos) > arrTightening(b, sortPos) Then
                            For k = 1 To UBound(colOrder)
                                temp = arrTightening(a, k): arrTightening(a, k) = arrTightening(b, k): arrTightening(b, k) = temp
                            Next k
                        End If
                    Next b
                Next a

                wideCount = Application.WorksheetFunction.Min(10, UBound(arrWidening, 1))
                tightCount = Application.WorksheetFunction.Min(10, UBound(arrTightening, 1))

                ' ---- WORST 10 (widest spread move since the anchor date)
                tableStartRow = destRow
                wsDest.Cells(destRow, 1).Value = "Currency: " & currKey & " (WORST 10 since " & anchorTxt & ")"
                For k = 2 To UBound(colOrder)
                    wsDest.Cells(destRow, k).Value = wsSource.Cells(1, colOrder(k)).Value
                Next k
                destRow = destRow + 1
                For j = 1 To wideCount
                    For k = 1 To UBound(colOrder)
                        wsDest.Cells(destRow, k).Value = arrWidening(j, k)
                    Next k
                    destRow = destRow + 1
                Next j
                Set tblRange = wsDest.Range(wsDest.Cells(tableStartRow, 1), wsDest.Cells(destRow - 1, UBound(colOrder)))
                tableName = "tbl_SS_" & currKey & "_worst"
                suffix = 1
                Do While TableExists(wsDest, tableName)
                    tableName = "tbl_SS_" & currKey & "_worst_" & suffix
                    suffix = suffix + 1
                Loop
                Set lo = wsDest.ListObjects.Add(xlSrcRange, tblRange, , xlYes)
                lo.Name = tableName
                lo.TableStyle = "TableStyleMedium2"
                lo.ListColumns(sortPos).Range.Font.Bold = True
                destRow = destRow + 1

                ' ---- TOP 10 (biggest tightening since the anchor date)
                tableStartRow = destRow
                wsDest.Cells(destRow, 1).Value = "Currency: " & currKey & " (TOP 10 since " & anchorTxt & ")"
                For k = 2 To UBound(colOrder)
                    wsDest.Cells(destRow, k).Value = wsSource.Cells(1, colOrder(k)).Value
                Next k
                destRow = destRow + 1
                For j = 1 To tightCount
                    For k = 1 To UBound(colOrder)
                        wsDest.Cells(destRow, k).Value = arrTightening(j, k)
                    Next k
                    destRow = destRow + 1
                Next j
                Set tblRange = wsDest.Range(wsDest.Cells(tableStartRow, 1), wsDest.Cells(destRow - 1, UBound(colOrder)))
                tableName = "tbl_SS_" & currKey & "_top"
                suffix = 1
                Do While TableExists(wsDest, tableName)
                    tableName = "tbl_SS_" & currKey & "_top_" & suffix
                    suffix = suffix + 1
                Loop
                Set lo = wsDest.ListObjects.Add(xlSrcRange, tblRange, , xlYes)
                lo.Name = tableName
                lo.TableStyle = "TableStyleMedium2"
                lo.ListColumns(sortPos).Range.Font.Bold = True
                destRow = destRow + 2
            End If
        End If
    Next ki

    ' Output layout: 1-14 -> A:N, 18-20 -> O:Q, 23 -> R, 24 -> S, 25 -> T, 26 -> U, 27 -> V
    wsDest.Columns("K").NumberFormat = "0.00"
    wsDest.Columns("L").NumberFormat = "0.00"
    wsDest.Columns("M").NumberFormat = "0.00"
    wsDest.Columns("N").NumberFormat = "0"
    wsDest.Columns("R").NumberFormat = "0"
    wsDest.Columns("S").NumberFormat = "0"
    wsDest.Columns("T").NumberFormat = "0"
    wsDest.Columns("U").NumberFormat = "0.00"
    wsDest.Columns("V").NumberFormat = "0"
    wsDest.Columns.AutoFit

CleanExit:
    Application.ScreenUpdating = True
    Application.Calculation = xlCalculationAutomatic
    Application.EnableEvents = True
End Sub

'----------------------------------------------------------------------------------
' TOC (SPREAD module) writes three navigation links under a "Ranking Sheets" banner.
' This drops the fourth link next to them without touching that procedure.
'----------------------------------------------------------------------------------
Sub AddSinceNavLink()
    Dim ws      As Worksheet
    Dim found   As Range
    Dim cell    As Range
    Dim navRow  As Long

    On Error Resume Next
    Set ws = ThisWorkbook.Sheets("SpreadRanking")
    On Error GoTo 0
    If ws Is Nothing Then Exit Sub

    Set found = ws.Columns(1).Find(What:="Ranking Sheets", LookIn:=xlValues, LookAt:=xlWhole)
    If found Is Nothing Then Exit Sub

    navRow = found.Row + 1
    Set cell = ws.Cells(navRow, 4)
    cell.ClearContents
    ws.Hyperlinks.Add Anchor:=cell, Address:="", _
        SubAddress:="'" & SINCE_SHEET & "'!A1", TextToDisplay:=SINCE_SHEET
    With cell
        .Font.Name = "Calibri"
        .Font.Size = 12
        .Borders.Weight = xlThin
        .HorizontalAlignment = xlCenter
        .VerticalAlignment = xlCenter
        .Interior.Color = RGB(220, 240, 255)
    End With
    ws.Columns(4).AutoFit
End Sub
