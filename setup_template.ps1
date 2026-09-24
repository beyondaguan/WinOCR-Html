# WinOCR-Html v0.8.0 Self-Contained Installer (template)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$AppName = "WinOCR-Html"
$DefaultInstallDir = "$env:LOCALAPPDATA\WinOCR-Html"

# Embedded payload (runtime zip, base64)
$b64 = @'
__PAYLOAD__
'@

# ---- GUI ----
$form = New-Object System.Windows.Forms.Form
$form.Text = "$AppName v0.8.0 Setup"
$form.Size = New-Object System.Drawing.Size(500, 400)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$welcomeLabel = New-Object System.Windows.Forms.Label
$welcomeLabel.Text = "Welcome to $AppName v0.8.0 Setup"
$welcomeLabel.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$welcomeLabel.AutoSize = $true
$welcomeLabel.Location = New-Object System.Drawing.Point(20, 20)
$form.Controls.Add($welcomeLabel)

$descLabel = New-Object System.Windows.Forms.Label
$descLabel.Text = "This will install $AppName on your computer.`n`nFeatures:`n- OCR (Optical Character Recognition)`n- Multi-engine Translation`n- Browser Extension Support`n- Text-to-Speech`n- Speech Recognition"
$descLabel.Location = New-Object System.Drawing.Point(20, 60)
$descLabel.Size = New-Object System.Drawing.Size(450, 120)
$form.Controls.Add($descLabel)

$dirLabel = New-Object System.Windows.Forms.Label
$dirLabel.Text = "Install Location:"
$dirLabel.Location = New-Object System.Drawing.Point(20, 190)
$dirLabel.AutoSize = $true
$form.Controls.Add($dirLabel)

$dirTextBox = New-Object System.Windows.Forms.TextBox
$dirTextBox.Text = $DefaultInstallDir
$dirTextBox.Location = New-Object System.Drawing.Point(20, 215)
$dirTextBox.Size = New-Object System.Drawing.Size(350, 25)
$form.Controls.Add($dirTextBox)

$browseButton = New-Object System.Windows.Forms.Forms.Button
$browseButton.Text = "Browse..."
$browseButton.Location = New-Object System.Drawing.Point(380, 213)
$browseButton.Size = New-Object System.Drawing.Size(80, 28)
$browseButton.Add_Click({
    $fb = New-Object System.Windows.Forms.FolderBrowserDialog
    $fb.SelectedPath = $dirTextBox.Text
    if ($fb.ShowDialog() -eq "OK") { $dirTextBox.Text = $fb.SelectedPath }
})
$form.Controls.Add($browseButton)

$desktopCheck = New-Object System.Windows.Forms.CheckBox
$desktopCheck.Text = "Create desktop shortcut"
$desktopCheck.Location = New-Object System.Drawing.Point(20, 250)
$desktopCheck.Checked = $true
$desktopCheck.AutoSize = $true
$form.Controls.Add($desktopCheck)

$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(20, 280)
$progressBar.Size = New-Object System.Drawing.Size(440, 25)
$progressBar.Style = "Marquee"
$progressBar.Visible = $false
$form.Controls.Add($progressBar)

$installButton = New-Object System.Windows.Forms.Button
$installButton.Text = "Install"
$installButton.Location = New-Object System.Drawing.Point(280, 320)
$installButton.Size = New-Object System.Drawing.Size(80, 30)
$installButton.Add_Click({
    $installButton.Enabled = $false
    $progressBar.Visible = $true
    try {
        $installDir = $dirTextBox.Text
        if (!(Test-Path $installDir)) { New-Item -ItemType Directory -Path $installDir -Force | Out-Null }

        # 1. Extract embedded payload (instant, no download)
        $form.Text = "Extracting..."
        $tmpZip = "$env:TEMP\winocr_payload.zip"
        [IO.File]::WriteAllBytes($tmpZip, [Convert]::FromBase64String($b64))
        Expand-Archive -Path $tmpZip -DestinationPath $installDir -Force
        Remove-Item $tmpZip -ErrorAction SilentlyContinue

        # 2. Register Native Host (manifest path -> absolute)
        $form.Text = "Registering native host..."
        $manifestTemp = "$env:TEMP\com.winocr_host.json"
        $exePath = "$installDir\extension\native_host\winocr_host.exe" -replace '\\', '/'
        $manifest = @{
            name = "com.winocr_host"
            description = "WinOCR-Html Native Host"
            path = $exePath
            type = "stdio"
            allowed_origins = @("chrome-extension://*/")
        } | ConvertTo-Json
        Set-Content -Path $manifestTemp -Value $manifest -Encoding ASCII
        reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.winocr_host" /ve /d "$manifestTemp" /f | Out-Null
        reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.winocr_host" /ve /d "$manifestTemp" /f | Out-Null

        # 3. Desktop shortcut
        if ($desktopCheck.Checked) {
            $form.Text = "Creating shortcut..."
            $shell = New-Object -ComObject WScript.Shell
            $lnk = $shell.CreateShortcut("$env:USERPROFILE\Desktop\$AppName.lnk")
            $lnk.TargetPath = "$installDir\extension\native_host\winocr_host.exe"
            $lnk.Arguments = "--standalone"
            $lnk.Save()
        }

        [System.Windows.Forms.MessageBox]::Show("$AppName installed successfully!`nLocation: $installDir", "Setup Complete", "OK", "Information")
    } catch {
        [System.Windows.Forms.MessageBox]::Show("Installation failed: $($_.Exception.Message)", "Error", "OK", "Error")
    }
    $form.Close()
})
$form.Controls.Add($installButton)

$cancelButton = New-Object System.Windows.Forms.Button
$cancelButton.Text = "Cancel"
$cancelButton.Location = New-Object System.Drawing.Point(380, 320)
$cancelButton.Size = New-Object System.Drawing.Size(80, 30)
$cancelButton.Add_Click({ $form.Close() })
$form.Controls.Add($cancelButton)

$form.ShowDialog() | Out-Null
