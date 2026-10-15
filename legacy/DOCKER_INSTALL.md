# Docker Desktop Installation Guide for Windows

## 🔍 System Requirements

Before installing, check if your system meets these requirements:

### Minimum Requirements:

- **Windows 10/11** (64-bit)
  - Windows 10: Version 21H2 or higher (Home or Pro)
  - Windows 11: Any version
- **RAM**: 4GB minimum (8GB+ recommended)
- **Virtualization**: Must be enabled in BIOS/UEFI
- **WSL 2**: Windows Subsystem for Linux 2

---

## ✅ Step 1: Enable Virtualization (If Not Already Enabled)

### Check if Virtualization is Enabled:

1. Press **Ctrl + Shift + Esc** to open Task Manager
2. Go to **Performance** tab
3. Click **CPU**
4. Look for **Virtualization: Enabled**

### If Disabled, Enable in BIOS:

1. Restart your computer
2. Press **F2**, **F10**, **Del**, or **F12** during boot (varies by manufacturer)
3. Find **Virtualization Technology** or **Intel VT-x** or **AMD-V**
4. Enable it
5. Save and exit

---

## ✅ Step 2: Enable WSL 2

### Open PowerShell as Administrator:

1. Press **Windows Key**
2. Type **PowerShell**
3. Right-click → **Run as Administrator**

### Run these commands:

```powershell
# Enable WSL feature
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# Enable Virtual Machine Platform
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# Restart your computer
Restart-Computer
```

### After Restart, set WSL 2 as default:

```powershell
# Set WSL 2 as default
wsl --set-default-version 2

# Update WSL kernel
wsl --update
```

---

## ✅ Step 3: Download Docker Desktop

1. **Visit Docker's official website:**

   - Go to: https://www.docker.com/products/docker-desktop/

2. **Download Docker Desktop for Windows**
   - Click **Download for Windows**
   - File: `Docker Desktop Installer.exe` (~500MB)

---

## ✅ Step 4: Install Docker Desktop

1. **Run the installer**

   - Double-click `Docker Desktop Installer.exe`
   - If prompted, click **Yes** to allow changes

2. **Configuration during installation:**

   - ✅ Check **"Use WSL 2 instead of Hyper-V"** (recommended)
   - ✅ Check **"Add shortcut to desktop"** (optional)
   - Click **OK**

3. **Wait for installation**

   - Takes 5-10 minutes
   - Do NOT close the installer

4. **Restart when prompted**
   - Click **Close and restart**
   - Your computer will restart

---

## ✅ Step 5: Start Docker Desktop

1. **After restart:**

   - Docker Desktop should start automatically
   - Or find it in Start Menu → **Docker Desktop**

2. **Accept the Service Agreement**

   - Read and accept the terms

3. **Optional: Create Docker account**

   - You can skip this and use Docker without an account
   - Click **Continue without signing in**

4. **Wait for Docker to start**
   - You'll see "Docker Desktop is running" in the system tray
   - Look for the whale icon 🐋 in your taskbar (bottom-right)

---

## ✅ Step 6: Verify Installation

### Open PowerShell and run:

```powershell
# Check Docker version
docker --version

# Should show something like:
# Docker version 24.0.7, build afdd53b

# Check Docker Compose
docker-compose --version

# Run test container
docker run hello-world
```

### Expected output:

```
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

✅ **If you see this, Docker is working!**

---

## 🐛 Common Issues & Solutions

### Issue 1: "WSL 2 installation is incomplete"

**Solution:**

```powershell
# Update WSL
wsl --update

# Install Ubuntu (optional but helpful)
wsl --install -d Ubuntu

# Restart Docker Desktop
```

### Issue 2: "Docker Desktop failed to start"

**Solution:**

```powershell
# Reset Docker to factory defaults
# 1. Right-click Docker icon in system tray
# 2. Click "Troubleshoot"
# 3. Click "Reset to factory defaults"
# 4. Restart Docker Desktop
```

### Issue 3: "Virtualization is not enabled"

**Solution:**

1. Restart computer
2. Enter BIOS (F2, F10, Del, or F12 during boot)
3. Find and enable:
   - Intel: **Intel Virtualization Technology (VT-x)**
   - AMD: **AMD-V** or **SVM Mode**
4. Save and exit BIOS

### Issue 4: "Docker daemon is not running"

**Solution:**

```powershell
# Open Services
# 1. Press Win + R
# 2. Type: services.msc
# 3. Find "Docker Desktop Service"
# 4. Right-click → Start
# 5. Set to "Automatic"
```

### Issue 5: "Port is already allocated"

**Solution:**

```powershell
# Find what's using port 5000
netstat -ano | findstr :5000

# Kill the process (replace PID with actual number)
taskkill /PID <PID> /F
```

### Issue 6: Slow Performance

**Solution:**

1. Open Docker Desktop
2. Click Settings (gear icon)
3. Go to **Resources**
4. Increase:
   - **CPUs**: 2-4
   - **Memory**: 4-8 GB
   - **Swap**: 1-2 GB
5. Click **Apply & Restart**

---

## 🎯 Verify Docker is Ready for Your Project

```powershell
# Navigate to your project
cd C:\Users\benny\OneDrive\Desktop\Projects\Machine-Learning-Engineer-Portfolio\n8n

# Test Docker Compose
docker-compose --version

# Build your containers (this will test everything)
docker-compose build

# If successful, start your services
docker-compose up -d
```

---

## 🔄 Alternative: Docker without Desktop (Advanced)

If Docker Desktop doesn't work, you can use Docker Engine with WSL2:

### In PowerShell (Admin):

```powershell
# Install WSL with Ubuntu
wsl --install -d Ubuntu
```

### In WSL2 Ubuntu terminal:

```bash
# Update packages
sudo apt-get update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt-get install docker-compose-plugin

# Start Docker
sudo service docker start
```

---

## 📋 Post-Installation Configuration

### Configure Docker Desktop:

1. **Open Docker Desktop**
2. Click **Settings** (gear icon)

#### General Settings:

- ✅ Start Docker Desktop when you log in
- ✅ Use WSL 2 based engine

#### Resources Settings:

- **CPUs**: 2-4 (depending on your system)
- **Memory**: 4-8 GB
- **Swap**: 1-2 GB
- **Disk image size**: 60 GB (default is fine)

#### Docker Engine Settings (optional):

```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false
}
```

---

## ✅ Success Checklist

- [ ] Virtualization enabled in BIOS
- [ ] WSL 2 installed and updated
- [ ] Docker Desktop downloaded
- [ ] Docker Desktop installed
- [ ] Computer restarted
- [ ] Docker Desktop started (whale icon in taskbar)
- [ ] `docker --version` works in PowerShell
- [ ] `docker run hello-world` succeeds
- [ ] Project directory accessible
- [ ] `docker-compose build` works

---

## 🆘 Still Having Issues?

### Get Docker Logs:

```powershell
# Get Docker Desktop logs
# 1. Open Docker Desktop
# 2. Click Troubleshoot (bug icon)
# 3. Click "Get support"
# 4. Copy diagnostic ID
```

### Common Error Messages:

| Error                                   | Solution                          |
| --------------------------------------- | --------------------------------- |
| "Hardware assisted virtualization..."   | Enable virtualization in BIOS     |
| "WSL 2 installation incomplete"         | Run `wsl --update`                |
| "Docker Desktop requires Windows 10..." | Update Windows                    |
| "Access denied"                         | Run PowerShell as Administrator   |
| "Port already in use"                   | Change port in docker-compose.yml |

---

## 📞 Next Steps After Installation

Once Docker is working:

```powershell
# Navigate to your project
cd C:\Users\benny\OneDrive\Desktop\Projects\Machine-Learning-Engineer-Portfolio\n8n

# Build your LinkedIn API
docker-compose build

# Start everything (API + ngrok)
docker-compose up -d

# Check if running
docker ps

# View logs
docker-compose logs -f
```

---

## 💡 Quick Commands Reference

```powershell
# Check Docker status
docker info

# List running containers
docker ps

# List all containers
docker ps -a

# Stop all containers
docker-compose down

# Remove all containers and images (clean slate)
docker system prune -a

# Restart Docker Desktop
# Right-click whale icon → Restart
```

---

## 🎉 You're Ready!

Once Docker is installed and verified, return to the main setup guide:

- See **SETUP_GUIDE.md** for deploying your LinkedIn API
- Your next command will be: `docker-compose build`

Good luck! 🚀
