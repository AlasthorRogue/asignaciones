-- ============================================================
-- SETUP DEVOLUCIONES (RETURNS) MODULE
-- ============================================================
USE [HGT_Assignments];
GO

-- 1. Crear tabla Returns
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Returns')
BEGIN
    CREATE TABLE dbo.Returns (
        ReturnID           INT IDENTITY(1,1) PRIMARY KEY,
        AssignmentID       INT NULL,
        WarehouseID        INT NOT NULL,          -- sin FK: la tabla guarda snapshot, la bodega ya existe
        ReturnDate         DATETIME NOT NULL DEFAULT GETDATE(),
        ReturnedByUserID   INT NULL,
        Notes              NVARCHAR(500) NULL,
        SignedDocumentPath NVARCHAR(500) NULL,
        -- Snapshot capturado al momento de la devolución
        StaffName          NVARCHAR(200) NULL,
        Serial             NVARCHAR(100) NULL,
        DeviceDescription  NVARCHAR(200) NULL
    );
    PRINT 'Tabla Returns creada.';
END
ELSE
    PRINT 'Tabla Returns ya existe.';
GO

-- 2. sp_CreateReturn  (devuelve el ReturnID generado)
IF OBJECT_ID('dbo.sp_CreateReturn', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_CreateReturn;
GO
CREATE PROCEDURE dbo.sp_CreateReturn
    @AssignmentID       INT,
    @WarehouseID        INT,
    @ReturnDate         DATETIME,
    @UserID             INT,
    @Notes              NVARCHAR(500) = NULL,
    @StaffName          NVARCHAR(200) = NULL,
    @Serial             NVARCHAR(100) = NULL,
    @DeviceDescription  NVARCHAR(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO dbo.Returns
        (AssignmentID, WarehouseID, ReturnDate, ReturnedByUserID, Notes, StaffName, Serial, DeviceDescription)
    VALUES
        (@AssignmentID, @WarehouseID, @ReturnDate, @UserID, @Notes, @StaffName, @Serial, @DeviceDescription);
    SELECT SCOPE_IDENTITY() AS ReturnID;
END
GO

-- 3. sp_GetReturns
IF OBJECT_ID('dbo.sp_GetReturns', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_GetReturns;
GO
CREATE PROCEDURE dbo.sp_GetReturns
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        R.ReturnID,
        R.AssignmentID,
        R.ReturnDate,
        R.Notes,
        R.SignedDocumentPath,
        R.StaffName,
        R.Serial,
        R.DeviceDescription,
        W.Name     AS WarehouseName,
        R.WarehouseID,
        U.FullName AS ProcessedBy
    FROM dbo.Returns R
    LEFT JOIN Warehouses W ON R.WarehouseID     = W.WarehouseID
    LEFT JOIN Users      U ON R.ReturnedByUserID = U.UserID
    ORDER BY R.ReturnDate DESC;
END
GO

-- 4. Permisos del módulo Devoluciones
--    Se insertan para los roles que ya tienen acceso a Asignaciones.

IF NOT EXISTS (SELECT 1 FROM Permissions WHERE MenuKey = 'returns')
BEGIN
    INSERT INTO Permissions (RoleID, MenuKey, CanAccess)
    SELECT DISTINCT RoleID, 'returns', 1
    FROM Permissions
    WHERE MenuKey = 'assignments' AND CanAccess = 1;
    PRINT 'Permiso "returns" insertado.';
END

IF NOT EXISTS (SELECT 1 FROM Permissions WHERE MenuKey = 'create_return')
BEGIN
    INSERT INTO Permissions (RoleID, MenuKey, CanAccess)
    SELECT DISTINCT RoleID, 'create_return', 1
    FROM Permissions
    WHERE MenuKey = 'create_assignment' AND CanAccess = 1;
    PRINT 'Permiso "create_return" insertado.';
END

IF NOT EXISTS (SELECT 1 FROM Permissions WHERE MenuKey = 'delete_return')
BEGIN
    INSERT INTO Permissions (RoleID, MenuKey, CanAccess)
    SELECT DISTINCT RoleID, 'delete_return', 1
    FROM Permissions
    WHERE MenuKey = 'delete_assignments' AND CanAccess = 1;
    PRINT 'Permiso "delete_return" insertado.';
END

IF NOT EXISTS (SELECT 1 FROM Permissions WHERE MenuKey = 'upload_return_document')
BEGIN
    INSERT INTO Permissions (RoleID, MenuKey, CanAccess)
    SELECT DISTINCT RoleID, 'upload_return_document', 1
    FROM Permissions
    WHERE MenuKey = 'upload_document' AND CanAccess = 1;
    PRINT 'Permiso "upload_return_document" insertado.';
END

IF NOT EXISTS (SELECT 1 FROM Permissions WHERE MenuKey = 'view_return_document')
BEGIN
    INSERT INTO Permissions (RoleID, MenuKey, CanAccess)
    SELECT DISTINCT RoleID, 'view_return_document', 1
    FROM Permissions
    WHERE MenuKey = 'view_document' AND CanAccess = 1;
    PRINT 'Permiso "view_return_document" insertado.';
END
GO

PRINT 'Módulo Devoluciones configurado correctamente.';
