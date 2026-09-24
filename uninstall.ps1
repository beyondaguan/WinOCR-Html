# WinOCR-Html v0.8.0 Uninstaller
# Removes registry entries, install directory, desktop shortcut

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$AppName = "WinOCR-Html"

# Locate install directory from registry (manifest path -> host exe -> root)
$installDir = $null
$regPaths = @(
    "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.winocr_host",
    "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.winocr_host"
)
foreach ($rp in $regPaths) {
    if (Test-Path $rp) {
        $v = Get-ItemProperty $rp -Name "(default)" -ErrorAction SilentlyContinue
        if ($v -and $v.'(default)') {
            $exePath = $v.'(default)' -replace '/', '\'
            # exe: <installDir>\extension\native_host\winocr_host.exe
            $idx = $exePath.IndexOf("\extension\native_host")
            if ($idx -gt 0) { $installDir = $exePath.Substring(0, $idx); break }
        }
    }
}

# Fallback to default location
if (-not $installDir -or -not (Test-Path $installDir)) {
    $installDir = "$env:LOCALAPPDATA\WinOCR-Html"
}

# Result storage
$script:Results = @()

# ---- Main form ----
$form = New-Object System.Windows.Forms.Form
$form.Text = "$AppName Uninstall"
$form.Size = New-Object System.Drawing.Size(480, 300)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$label = New-Object System.Windows.Forms.Label
$label.Text = "This will remove $AppName from your computer.`n`nThe following will be removed:`n- Native Host registration (Chrome/Edge)`n- Program files`n- Desktop shortcut"
$label.Location = New-Object System.Drawing.Point(20, 20)
$label.Size = New-Object System.Drawing.Size(420, 90)
$form.Controls.Add($label)

$pathLabel = New-Object System.Windows.Forms.Label
$pathLabel.Text = "Install location: $installDir"
$pathLabel.Location = New-Object System.Drawing.Point(20, 115)
$pathLabel.Size = New-Object System.Drawing.Size(420, 20)
$form.ForeColor = [System.Drawing.Color]::Gray
$form.Controls.Add($pathLabel)

$progress = New-Object System.Windows.Forms.ProgressBar
$progress.Location = New-Object System.Drawing.Point(20, 145)
$progress.Size = New-Object System.Drawing.Size(420, 20)
$progress.Style = "Marquee"
$progress.Visible = $false
$form.Controls.Add($progress)

$doUninstall = {
    $uninstallButton.Enabled = $false
    $progress.Visible = $true
    $form.Text = "Uninstalling..."

    # 1. Remove registry entries
    foreach ($rp in $script:RegPaths) {
        if (Test-Path $rp) {
            Remove-Item $rp -Recurse -Force -ErrorAction SilentlyContinue
            $script:Results += "Registry: removed $rp"
        }
    }

    # 2. Remove temp manifest
    $tempManifest = "$env:TEMP\com.winocr_host.json"
    if (Test-Path $tempManifest) { Remove-Item $tempManifest -Force -ErrorAction SilentlyContinue }

    # 3. Remove desktop shortcut
    $lnk = "$env:USERPROFILE\Desktop\$AppName.lnk"
    if (Test-Path $lnk) { Remove-Item $lnk -Force -ErrorAction SilentlyContinue; $script:Results += "Desktop shortcut removed" }

    # 4. Remove install directory
    if (Test-Path $script:InstallDir) {
        Remove-Item $script:InstallDir -Recurse -Force -ErrorAction SilentlyContinue
        $script:Results += "Program files removed: $script:InstallDir"
    }

    $progress.Visible = $false
    [System.Windows.Forms.MessageBox]::Show("$AppName has been uninstalled.`n`n$($script:Results -join "`n")", "Uninstall Complete", "OK", "Information")
    $form.Close()
}

$uninstallButton = New-Object System.Windows.Forms.Button
$uninstallButton.Text = "Uninstall"
$uninstallButton.Location = New-Object System.Drawing.Point(260, 205)
$uninstallButton.Size = New-Object System.Drawing.Size(80, 30)
$uninstallButton.Add_Click($doUninstall)
$form.Controls.Add($uninstallButton)

$cancelButton = New-Object System.Windows.Forms.Button
$cancelButton.Text = "Cancel"
$cancelButton.Location = New-Object System.Drawing.Point(355, 205)
$cancelButton.Size = New-Object System.Drawing.Size(80, 30)
$cancelButton.Add_Click({ $form.Close() })
$form.Controls.Add($cancelButton)

# Expose variables to event scope
$script:RegPaths = $regPaths
$script:InstallDir = $installDir

$form.ShowDialog() | Out-Null
