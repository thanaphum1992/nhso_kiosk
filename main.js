const { app, BrowserWindow, Tray, Menu, ipcMain, dialog, nativeImage } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const kill = require('tree-kill');
const getPort = require('get-port');

const isDev = !app.isPackaged;

let mainWindow;
let adminWindow = null;
let tray = null;
let backendProcess = null;
let backendPort = 8000;

function setupIpcHandlers() {
  const baseUrl = `http://127.0.0.1:${backendPort}/api/v1`;

  ipcMain.handle('config:get', async () => {
    const res = await fetch(`${baseUrl}/config/`);
    return res.json();
  });
  
  ipcMain.handle('config:getForceChange', async () => {
    const res = await fetch(`${baseUrl}/config/`);
    const data = await res.json();
    return data.ADMIN_PASSWORD === 'changeme' || data.ADMIN_PASSWORD === '' || data.ADMIN_PASSWORD === 'admin';
  });

  ipcMain.handle('config:update', async (e, data) => {
    const res = await fetch(`${baseUrl}/config/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return res.ok ? { ok: true } : { ok: false, status: res.status };
  });

  ipcMain.handle('config:testDb', async (e, db_url) => {
    const res = await fetch(`${baseUrl}/config/test-db?db_url=${encodeURIComponent(db_url)}`, { method: 'POST' });
    return res.json();
  });

  ipcMain.handle('config:runDbSetup', async () => {
    const res = await fetch(`${baseUrl}/config/run-db-setup`, { method: 'POST' });
    return res.json();
  });

  ipcMain.handle('config:changePassword', async (e, data) => {
    const res = await fetch(`${baseUrl}/config/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
        const error = await res.json();
        return { ok: false, detail: error.detail };
    }
    return { ok: true };
  });

  ipcMain.handle('claim:checkPrivilege', async (e, { pid, token }) => {
    const res = await fetch(`${baseUrl}/claim/check-privilege/${pid}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
  });

  ipcMain.handle('claim:fetchAndSend', async (e, { vn, token }) => {
    const res = await fetch(`${baseUrl}/claim/fetch-and-send/${vn}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
  });

  ipcMain.handle('kiosk:tts', async (e, text) => {
    const res = await fetch(`${baseUrl}/kiosk/tts?text=${encodeURIComponent(text)}`);
    const buffer = await res.arrayBuffer();
    const base64 = Buffer.from(buffer).toString('base64');
    return `data:audio/mp3;base64,${base64}`;
  });

  ipcMain.handle('admin:verifyPassword', async (e, pwd) => {
    const res = await fetch(`${baseUrl}/config/`);
    const data = await res.json();
    return data.ADMIN_PASSWORD === pwd || data.ADMIN_PASSWORD === 'changeme' || data.ADMIN_PASSWORD === '';
  });

  ipcMain.handle('getBackendPort', () => backendPort);

  ipcMain.handle('admin:open', () => {
    if (adminWindow) {
      if (adminWindow.isMinimized()) adminWindow.restore();
      adminWindow.focus();
      return;
    }
    
    adminWindow = new BrowserWindow({
      width: 1200, height: 900,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js')
      }
    });
    
    adminWindow.loadFile(path.join(__dirname, 'renderer', 'admin.html'));
    
    adminWindow.on('closed', () => {
      adminWindow = null;
    });
  });
}


function startBackend() {
  return new Promise((resolve, reject) => {
    let backendExe;
    let args = [backendPort.toString()];
    
    const userDataPath = app.getPath('userData');
    const envPath = path.join(userDataPath, '.env');
    
    if (!fs.existsSync(envPath)) {
      const examplePath = isDev 
        ? path.join(__dirname, '.env.example')
        : path.join(process.resourcesPath, '.env.example');
      
      if (fs.existsSync(examplePath)) {
        fs.copyFileSync(examplePath, envPath);
      } else {
        fs.writeFileSync(envPath, '');
      }
    }
    
    const appDir = isDev ? __dirname : path.dirname(process.execPath);
    const env = {
      ...process.env,
      ENV_FILE_PATH: envPath,
      APP_DIR: appDir
    };

    if (isDev) {
      backendExe = 'python';
      args = ['-m', 'app.main', backendPort.toString()];
    } else {
      backendExe = path.join(process.resourcesPath, 'backend', 'backend.exe');
    }

    console.log(`Starting backend: ${backendExe} ${args.join(' ')}`);

    backendProcess = spawn(backendExe, args, { env, cwd: __dirname });

    backendProcess.stdout.on('data', (data) => {
      if (data.toString().includes('Application startup complete') || data.toString().includes('Uvicorn running on')) {
        resolve();
      }
    });

    backendProcess.stderr.on('data', (data) => {
      if (data.toString().includes('Application startup complete') || data.toString().includes('Uvicorn running on')) {
        resolve();
      }
    });

    setTimeout(resolve, 5000);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    autoHideMenuBar: true,
  });

  setTimeout(() => {
    mainWindow.loadFile(path.join(__dirname, 'renderer', 'kiosk.html'));
  }, 1000);

  mainWindow.on('close', (event) => {
    if (!app.isQuiting) {
      event.preventDefault();
      mainWindow.hide();
    }
    return false;
  });
}

function createTray() {
  const iconPath = isDev
    ? path.join(__dirname, 'renderer', 'icon.png')
    : path.join(process.resourcesPath, 'icon.png');
  const icon = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath)
    : nativeImage.createEmpty();
  tray = new Tray(icon);
  
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Open NHSO Kiosk', click: () => mainWindow.show() },
    { type: 'separator' },
    { 
      label: 'Quit', 
      click: () => {
        app.isQuiting = true;
        app.quit();
      } 
    }
  ]);
  
  tray.setToolTip('NHSO Kiosk System');
  tray.setContextMenu(contextMenu);
  
  tray.on('click', () => {
    mainWindow.show();
  });
}

app.whenReady().then(async () => {
  try {
    backendPort = await getPort({ port: getPort.makeRange(8000, 9000) });
    await startBackend();
  } catch (error) {
    console.error('Failed to start backend:', error);
  }
  
  setupIpcHandlers();
  createWindow();
  createTray();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('will-quit', () => {
  if (backendProcess && backendProcess.pid) {
    kill(backendProcess.pid, 'SIGINT', (err) => {
      if (err) console.error('Error killing backend:', err);
    });
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
  }
});