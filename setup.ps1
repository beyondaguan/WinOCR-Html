# WinOCR-Html v0.8.0 Installer
# PowerShell-based installer with GUI

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Configuration
$AppName = "WinOCR-Html"
$AppVersion = "0.8.0"
$AppPublisher = "WinOCR Team"
$DefaultInstallDir = "$env:LOCALAPPDATA\WinOCR-Html"
$GitHubReleaseURL = "https://github.com/beyondaguan/WinOCR-Html/releases/download/v0.8.0/WinOCR-Html-v0.8.0.zip"

# Create main form
$form = New-Object System.Windows.Forms.Form
$form.Text = "$AppName v$AppVersion Setup"
$form.Size = New-Object System.Drawing.Size(500, 400)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

# Welcome label
$welcomeLabel = New-Object System.Windows.Forms.Label
$welcomeLabel.Text = "Welcome to $AppName v$AppVersion Setup"
$welcomeLabel.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$welcomeLabel.AutoSize = $true
$welcomeLabel.Location = New-Object System.Drawing.Point(20, 20)
$form.Controls.Add($welcomeLabel)

# Description label
$descLabel = New-Object System.Windows.Forms.Label
$descLabel.Text = "This will install $AppName on your computer.`n`nFeatures:`n- OCR (Optical Character Recognition)`n- Multi-engine Translation`n- Browser Extension Support`n- Text-to-Speech`n- Speech Recognition"
$descLabel.Location = New-Object System.Drawing.Point(20, 60)
$descLabel.Size = New-Object System.Drawing.Size(450, 120)
$form.Controls.Add($descLabel)

# Install directory
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

$browseButton = New-Object System.Windows.Forms.Button
$browseButton.Text = "Browse..."
$browseButton.Location = New-Object System.Drawing.Point(380, 213)
$browseButton.Size = New-Object System.Drawing.Size(80, 28)
$browseButton.Add_Click({
    $folderBrowser = New-Object System.Windows.Forms.FolderBrowserDialog
    $folderBrowser.SelectedPath = $dirTextBox.Text
    if ($folderBrowser.ShowDialog() -eq "OK") {
        $dirTextBox.Text = $folderBrowser.SelectedPath
    }
})
$form.Controls.Add($browseButton)

# Desktop shortcut checkbox
$desktopCheck = New-Object System.Windows.Forms.CheckBox
$desktopCheck.Text = "Create desktop shortcut"
$desktopCheck.Location = New-Object System.Drawing.Point(20, 250)
$desktopCheck.Checked = $true
$desktopCheck.AutoSize = $true
$form.Controls.Add($desktopCheck)

# Progress bar
$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(20, 280)
$progressBar.Size = New-Object System.Drawing.Size(440, 25)
$progressBar.Style = "Marquee"
$progressBar.Visible = $false
$form.Controls.Add($progressBar)

# Install button
$installButton = New-Object System.Windows.Forms.Button
$installButton.Text = "Install"
$installButton.Location = New-Object System.Drawing.Point(280, 320)
$installButton.Size = New-Object System.Drawing.Size(80, 30)
$installButton.Add_Click({
    $installButton.Enabled = $false
    $progressBar.Visible = $true
    
    try {
        # Download and extract
        $installDir = $dirTextBox.Text
        $tempFile = "$env:TEMP\winocr-setup.zip"
        
        # Update progress
        $form.Text = "Downloading..."
        Invoke-WebRequest -Uri $GitHubReleaseURL -OutFile $tempFile -UseBasicParsing
        
        $form.Text = "Expanding-Archive..."
        if (Test-Path $installDir) { Remove-Item $installDir -Recurse -Force }
        Expand-Archive -Path $tempFile -DestinationPath $installDir -Force
        
        # Register native host
        $form.Text = "Registering native host..."
        $manifestSrc = "$installDir\extension\native_host\com.winocr_host.json"
        $manifestTemp = "$env:TEMP\com.winocr_host.json"
        $manifest = Get-Content $manifestSrc -Raw
        $exePath = "$installDir\extension\native_host\winocr_host.exe" -replace '\\', '/'
        $manifest = $manifest -replace 'winocr_host.exe', $exePath
        Set-Content -Path $manifestTemp -Value $manifest
        
        reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.winocr_host" /ve /d "$manifestTemp" /f | Out-Null
        reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.winocr_host" /ve /d "$manifestTemp" /f | Out-Null
        
        # Create desktop shortcut
        if ($desktopCheck.Checked) {
            $form.Text = "Creating shortcut..."
            $WScriptShell = New-Object -ComObject WScript.Shell
            $shortcut = $WScriptShell.CreateShortcut("$env:USERPROFILE\Desktop\$AppName.lnk")
            $shortcut.TargetPath = "$installDir\extension\native_host\winocr_host.exe"
            $shortcut.Arguments = "--standalone"
            $shortcut.Save()
        }
        
        # Cleanup
        Remove-Item $tempFile -ErrorAction SilentlyContinue
        
        [System.Windows.Forms.MessageBox]::Show("$AppName installed successfully!", "Setup Complete", "OK", "Information")
    } catch {
        [System.Windows.Forms.MessageBox]::Show("Installation failed: $($_.Exception.Message)", "Error", "OK", "Error")
    }
    
    $form.Close()
})
$form.Controls.Add($installButton)

# Cancel button
$cancelButton = New-Object System.Windows.Forms.Button
$cancelButton.Text = "Cancel"
$cancelButton.Location = New-Object System.Drawing.Point(380, 320)
$cancelButton.Size = New-Object System.Drawing.Size(80, 30)
$cancelButton.Add_Click({ $form.Close() })
$form.Controls.Add($cancelButton)

# Show form
$form.ShowDialog() | Out-Null
