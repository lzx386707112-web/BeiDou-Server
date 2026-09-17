$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Root = $PSScriptRoot
if (-not $Root) { $Root = Split-Path -Parent $MyInvocation.MyCommand.Path }
Set-Location -LiteralPath $Root

$RuntimeDir = Join-Path $Root 'runtime'
$DefaultJar = Join-Path $Root 'BeiDou.jar'
$TargetJar = Join-Path $Root 'target\BeiDou.jar'
$PidFile = Join-Path $Root 'BeiDou.pid'
$LogFile = Join-Path $Root 'logs\BeiDou.out.log'
$ServerPort = 8686
$DbPort = 3306
$DbUser = 'root'
$DbPassword = 'root'
$DbName = 'beidou'
$DbHost = 'localhost'
$Background = $env:BEIDOU_BACKGROUND -eq '1'
$Jar = $env:BEIDOU_JAR
$Config = $env:BEIDOU_CONFIG
$AppArgs = @()
if (-not [string]::IsNullOrWhiteSpace($env:BEIDOU_APP_ARGS)) {
    $AppArgs = $env:BEIDOU_APP_ARGS.Trim() -split '\s+'
}

$AdoptiumUrl = 'https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse?project=jdk'
$MysqlZipUrls = @(
    'https://mirrors.huaweicloud.com/mysql/Downloads/MySQL-8.0/mysql-8.0.29-winx64.zip',
    'https://mirrors.aliyun.com/mysql/MySQL-8.0/mysql-8.0.28-winx64.zip',
    'https://mirrors.huaweicloud.com/mysql/Downloads/MySQL-8.0/mysql-8.0.28-winx64.zip'
)

function Write-Step {
    param([string]$Index, [string]$Title, [string]$Detail)
    Write-Host ""
    Write-Host "[$Index] $Title" -ForegroundColor Cyan
    Write-Host "    $Detail"
}

function Write-Ok([string]$Message) {
    Write-Host "    $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "    $Message" -ForegroundColor Yellow
}

function Test-PortListening([int]$Port) {
    $out = & netstat -ano | Select-String -Pattern ":$Port\s+.*LISTENING"
    return [bool]$out
}

function Get-ListeningPids([int]$Port) {
    $pids = New-Object System.Collections.Generic.List[int]
    & netstat -ano | Select-String -Pattern ":$Port\s+.*LISTENING" | ForEach-Object {
        $parts = ($_.Line -split '\s+') | Where-Object { $_ }
        $procId = 0
        if ([int]::TryParse($parts[-1], [ref]$procId) -and $procId -gt 0 -and -not $pids.Contains($procId)) {
            $pids.Add($procId)
        }
    }
    return $pids
}

function Stop-PidGracefully {
    param([int]$ProcessId, [string]$Reason)
    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) { return }
    Write-Host "    检测到已有进程 PID $ProcessId（$Reason），正在停止..."
    try { Stop-Process -Id $ProcessId -ErrorAction SilentlyContinue } catch {}
    $waited = 0
    while ($waited -lt 30 -and (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
        Start-Sleep -Seconds 1
        $waited++
    }
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        Write-Warn "进程 $ProcessId 未在 30 秒内退出，改为强制停止。"
        try { Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue } catch {}
        Start-Sleep -Seconds 2
    }
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        throw "无法停止已有进程 PID $ProcessId"
    }
    Write-Ok "已停止进程 PID $ProcessId"
}

function Get-NativeOutput([string]$FilePath, [string[]]$NativeArgs) {
    $quotedArgs = @()
    foreach ($item in $NativeArgs) {
        if ($null -eq $item) { continue }
        $quotedArgs += '"' + ($item -replace '"', '\"') + '"'
    }
    $command = '"' + $FilePath + '"'
    if ($quotedArgs.Count -gt 0) {
        $command = $command + ' ' + ($quotedArgs -join ' ')
    }
    return (& cmd.exe /c "$command 2>&1" | Out-String)
}

function Get-JavaMajor([string]$JavaBin) {
    $text = Get-NativeOutput $JavaBin @('-version')
    if ($text -notmatch 'version\s+"([^"]+)"') { return 0 }
    $ver = $Matches[1]
    if ($ver.StartsWith('1.')) { return [int]($ver.Split('.')[1]) }
    return [int]($ver.Split('.')[0])
}

function Get-BundledJavaHome {
    foreach ($jdkDir in @(
        (Join-Path $Root 'Environment\jre'),
        (Join-Path $Root 'Environment'),
        (Join-Path $Root 'jre')
    )) {
        if (Test-Path (Join-Path $jdkDir 'bin\java.exe')) { return $jdkDir }
    }
    return $null
}

function Find-Jdk21 {
    $homes = New-Object System.Collections.Generic.List[string]
    $bundled = Get-BundledJavaHome
    if ($bundled) { $homes.Add($bundled) }
    foreach ($item in @(
        $env:JAVA_HOME_21,
        $env:JAVA_HOME
    )) {
        if ($item) { $homes.Add($item) }
    }
    Get-ChildItem -Path $Root -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'jdk-21*' -or $_.Name -like 'jdk21*' } |
        ForEach-Object { $homes.Add($_.FullName) }
    $portable = Join-Path $RuntimeDir 'jdk'
    if (Test-Path $portable) { $homes.Add($portable) }
    foreach ($base in @(
        ${env:ProgramFiles},
        ${env:ProgramFiles(x86)},
        "$env:LOCALAPPDATA\Programs"
    )) {
        if (-not $base) { continue }
        foreach ($pattern in @(
            'Eclipse Adoptium\jdk-21*',
            'Microsoft\jdk-21*',
            'Java\jdk-21*',
            'Amazon Corretto\jdk21*',
            'Zulu\zulu-21*',
            'Temurin\jdk-21*'
        )) {
            Get-ChildItem -Path (Join-Path $base $pattern) -Directory -ErrorAction SilentlyContinue |
                ForEach-Object { $homes.Add($_.FullName) }
        }
    }
    $whereJava = Get-Command java -ErrorAction SilentlyContinue
    if ($whereJava) {
        $homes.Add((Split-Path (Split-Path $whereJava.Source)))
    }
    $seen = @{}
    foreach ($jdkDir in $homes) {
        if (-not $jdkDir -or $seen.ContainsKey($jdkDir)) { continue }
        $seen[$jdkDir] = $true
        $javaBin = Join-Path $jdkDir 'bin\java.exe'
        if (-not (Test-Path $javaBin)) { continue }
        $major = Get-JavaMajor $javaBin
        if ($major -ge 21) { return $jdkDir }
    }
    return $null
}

function Invoke-Download([string]$Url, [string]$OutFile) {
    New-Item -ItemType Directory -Force -Path (Split-Path $OutFile) | Out-Null
    Write-Host "    下载地址: $Url"
    Write-Host "    保存到: $OutFile"
    Write-Host "    体积约 210MB，下面会显示百分比，没有数字时也请等着，不要关窗口。"
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & curl.exe -L --fail --retry 3 --retry-delay 2 --progress-bar -o $OutFile $Url
        if ($LASTEXITCODE -ne 0) { throw "下载失败: $Url" }
        if (-not (Test-Path $OutFile) -or ((Get-Item $OutFile).Length -lt 1MB)) {
            throw "下载文件太小或不存在: $OutFile"
        }
        $sizeMb = [math]::Round((Get-Item $OutFile).Length / 1MB, 1)
        Write-Ok "下载完成，大小 ${sizeMb}MB"
        return
    }
    Write-Warn "没有 curl.exe，改用 Invoke-WebRequest（可能没有百分比）。"
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
}

function Invoke-DownloadFirst([string[]]$Urls, [string]$OutFile) {
    $lastError = $null
    $index = 0
    foreach ($url in $Urls) {
        $index++
        Write-Host "    [$index/$($Urls.Count)] 尝试国内镜像..."
        try {
            Invoke-Download $url $OutFile
            return
        } catch {
            $lastError = $_
            Write-Warn "这个镜像失败了: $($_.Exception.Message)"
        }
    }
    throw "所有国内镜像都失败了。最后错误: $lastError"
}

function Expand-Zip([string]$ZipPath, [string]$Destination) {
    Write-Host "    正在解压（约 1-2 分钟，解压时没有百分比）..."
    if (Test-Path $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $Destination -Force
    Write-Ok "解压完成"
}

function Install-Jdk21 {
    Write-Host "    未找到 JDK 21。将下载 Eclipse Temurin 21 到 runtime\jdk（约 180MB，仅首次需要）。"
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    $zip = Join-Path $RuntimeDir 'jdk21.zip'
    $extract = Join-Path $RuntimeDir 'jdk-extract'
    Invoke-Download $AdoptiumUrl $zip
    Expand-Zip $zip $extract
    $found = Get-ChildItem -Path $extract -Recurse -Filter java.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.Directory.Name -eq 'bin' } |
        Select-Object -First 1
    if (-not $found) { throw 'JDK 压缩包里没有找到 bin\java.exe' }
    $extractedHome = $found.Directory.Parent.FullName
    $target = Join-Path $RuntimeDir 'jdk'
    if (Test-Path $target) { Remove-Item -LiteralPath $target -Recurse -Force }
    Move-Item -LiteralPath $extractedHome -Destination $target
    Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
    Write-Ok "JDK 21 已安装到 $target"
    return $target
}

function Try-WingetInstall([string]$PackageId, [string]$DisplayName) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { return $false }
    Write-Host "    尝试用 winget 安装 $DisplayName ..."
    $wingetArgs = @(
        'install','-e','--id',$PackageId,
        '--accept-package-agreements','--accept-source-agreements',
        '--disable-interactivity'
    )
    & winget.exe @wingetArgs
    return $LASTEXITCODE -eq 0
}

function Get-MysqlExe {
    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($rel in @(
        'mysql\bin\mysql.exe',
        'mariadb\bin\mysql.exe',
        'mariadb\bin\mariadb.exe'
    )) {
        $candidates.Add((Join-Path $RuntimeDir $rel))
    }
    foreach ($cmd in @('mysql.exe','mariadb.exe')) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) { $candidates.Add($found.Source) }
    }
    foreach ($base in @(${env:ProgramFiles}, ${env:ProgramFiles(x86)})) {
        if (-not $base) { continue }
        Get-ChildItem -Path $base -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match 'MariaDB|MySQL' } |
            ForEach-Object {
                Get-ChildItem -Path $_.FullName -Recurse -Filter mysql.exe -ErrorAction SilentlyContinue |
                    Select-Object -First 3 |
                    ForEach-Object { $candidates.Add($_.FullName) }
            }
    }
    foreach ($path in $candidates) {
        if ($path -and (Test-Path $path)) { return $path }
    }
    return $null
}

function Build-MysqlArgs {
    param([string]$User, [string]$Password, [string]$Sql)
    $mysqlArgs = @('-h', $DbHost, '-P', "$DbPort", '-u', $User, '--connect-timeout=5', '--default-character-set=utf8mb4')
    if ($null -ne $Password) { $mysqlArgs += "--password=$Password" }
    $mysqlArgs += @('-e', $Sql)
    return $mysqlArgs
}

function Test-MysqlLogin {
    param([string]$MysqlExe, [string]$User, [string]$Password)
    if (-not $MysqlExe) { return $false }
    $mysqlArgs = Build-MysqlArgs $User $Password 'SELECT 1;'
    $null = Get-NativeOutput $MysqlExe $mysqlArgs
    return $LASTEXITCODE -eq 0
}

function Start-CommonDbServices {
    foreach ($name in @('MySQL80','MySQL57','MySQL','MariaDB','MariaDB114','MariaDB113','MariaDB112')) {
        $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
        if (-not $svc) { continue }
        if ($svc.Status -ne 'Running') {
            Write-Host "    发现服务 $name，正在启动..."
            try {
                Start-Service -Name $name -ErrorAction Stop
                Write-Ok "已启动服务 $name"
            } catch {
                Write-Warn "无法启动服务 $name：$($_.Exception.Message)"
            }
        } else {
            Write-Ok "数据库服务 $name 已在运行。"
        }
    }
}

function Wait-Port([int]$Port, [int]$Seconds, [string]$Label) {
    $waited = 0
    while ($waited -lt $Seconds) {
        if (Test-PortListening $Port) { return $true }
        Start-Sleep -Seconds 1
        $waited++
        if (($waited % 2) -eq 0) {
            Write-Host "    等待 $Label 端口 $Port ... 已等 ${waited}s / ${Seconds}s"
        }
    }
    return (Test-PortListening $Port)
}

function Get-MysqldFromDir([string]$Dir) {
    $path = Join-Path $Dir 'bin\mysqld.exe'
    if (Test-Path $path) { return $path }
    return $null
}

function Install-PortableMysql {
    Write-Host "    未检测到可用的 MySQL。将从国内镜像下载 MySQL 8.0 免安装版到 runtime\mysql。"
    Write-Host "    只监听 127.0.0.1:3306，账号密码与配置一致：root / root。不使用 winget，避免卡住。"
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    $zip = Join-Path $RuntimeDir 'mysql.zip'
    $extract = Join-Path $RuntimeDir 'mysql-extract'
    Invoke-DownloadFirst $MysqlZipUrls $zip
    Expand-Zip $zip $extract
    $found = Get-ChildItem -Path $extract -Recurse -Filter mysqld.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $found) { throw 'MySQL 压缩包里没有找到 bin\mysqld.exe' }
    $extractedHome = $found.Directory.Parent.FullName
    $target = Join-Path $RuntimeDir 'mysql'
    if (Test-Path $target) { Remove-Item -LiteralPath $target -Recurse -Force }
    Write-Host "    正在移动到 $target ..."
    Move-Item -LiteralPath $extractedHome -Destination $target
    Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue

    $dataDir = Join-Path $target 'data'
    $ini = Join-Path $target 'my.ini'
    @"
[mysqld]
port=$DbPort
basedir=$($target.Replace('\','/'))
datadir=$($dataDir.Replace('\','/'))
character-set-server=utf8mb4
collation-server=utf8mb4_general_ci
bind-address=127.0.0.1
skip-log-bin
innodb_buffer_pool_size=256M
"@ | Set-Content -LiteralPath $ini -Encoding ASCII

    Write-Host "    正在初始化数据目录（约 10-30 秒，没有百分比属正常）..."
    $mysqld = Get-MysqldFromDir $target
    if (-not $mysqld) { throw "找不到 $target\bin\mysqld.exe" }
    $initOut = Get-NativeOutput $mysqld @("--defaults-file=$ini", '--initialize-insecure')
    if ($LASTEXITCODE -ne 0) {
        Write-Host $initOut
        throw "mysqld --initialize-insecure 失败，退出码 $LASTEXITCODE"
    }
    Write-Ok "MySQL 8.0 免安装版已放到 $target"
    return $target
}

function Start-PortableMysql([string]$MysqlHome) {
    $mysqld = Get-MysqldFromDir $MysqlHome
    if (-not $mysqld) { throw "找不到 $MysqlHome\bin\mysqld.exe" }
    $ini = Join-Path $MysqlHome 'my.ini'
    $pidPath = Join-Path $RuntimeDir 'mysql.pid'
    if (Test-Path $pidPath) {
        $old = Get-Content $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($old -match '^\d+$') { Stop-PidGracefully -ProcessId ([int]$old) -Reason '便携 MySQL PID 文件' }
    }
    Write-Host "    正在启动便携 MySQL..."
    $proc = Start-Process -FilePath $mysqld -ArgumentList @("--defaults-file=$ini") -WorkingDirectory $MysqlHome -WindowStyle Hidden -PassThru
    $proc.Id | Set-Content -LiteralPath $pidPath -Encoding ASCII
    if (-not (Wait-Port -Port $DbPort -Seconds 60 -Label 'MySQL')) {
        throw "便携 MySQL 已启动但端口 $DbPort 仍未监听，请查看是否被占用。"
    }
    Write-Ok "便携 MySQL 已在 127.0.0.1:$DbPort 运行，PID $($proc.Id)"
}

function Read-DbConfigFromYml([string]$Path) {
    if (-not (Test-Path $Path)) { return }
    $text = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if ($text -match '(?m)^\s*url:\s*jdbc:mysql://([^:/]+):(\d+)/([A-Za-z0-9_]+)') {
        $script:DbHost = $Matches[1]
        $script:DbPort = [int]$Matches[2]
        $script:DbName = $Matches[3]
    }
    if ($text -match '(?m)^\s*username:\s*"?([^"\r\n]+)"?') { $script:DbUser = $Matches[1].Trim() }
    if ($text -match '(?m)^\s*password:\s*"?([^"\r\n]+)"?') { $script:DbPassword = $Matches[1].Trim() }
}

function Invoke-Mysql([string]$MysqlExe, [string]$User, [string]$Password, [string]$Sql) {
    $mysqlArgs = Build-MysqlArgs $User $Password $Sql
    $output = Get-NativeOutput $MysqlExe $mysqlArgs
    if ($LASTEXITCODE -ne 0) { throw "执行 SQL 失败:`n$output" }
    return $output
}

try {

# ---- 1. jar ----
Write-Step '1/6' '检查服务端 jar' '优先使用本目录 BeiDou.jar；没有则尝试 target\BeiDou.jar。Windows 分发包不从源码启动。'
if ([string]::IsNullOrWhiteSpace($Jar)) { $Jar = $DefaultJar }
if (-not [System.IO.Path]::IsPathRooted($Jar)) { $Jar = Join-Path $Root $Jar }
if (-not (Test-Path $Jar)) {
    if ($Jar -eq $DefaultJar -and (Test-Path $TargetJar)) {
        Write-Warn "找不到 $DefaultJar ，改用 $TargetJar"
        $Jar = $TargetJar
    } else {
        throw "找不到 jar: $Jar`n请把 BeiDou.jar 和本脚本放在同一目录后再运行。"
    }
}
Write-Ok "将启动: $Jar"

# ---- 2. config ----
Write-Step '2/6' '检查配置文件' '若本目录有 application.yml，会按其中的数据库账号和端口连接；没有则使用 jar 内置配置（默认 root/root，库名 beidou，HTTP 端口 8686）。'
if ([string]::IsNullOrWhiteSpace($Config) -and (Test-Path (Join-Path $Root 'application.yml'))) {
    $Config = Join-Path $Root 'application.yml'
}
if (-not [string]::IsNullOrWhiteSpace($Config)) {
    if (-not [System.IO.Path]::IsPathRooted($Config)) { $Config = Join-Path $Root $Config }
    if (-not (Test-Path $Config)) { throw "找不到配置文件: $Config" }
    Read-DbConfigFromYml $Config
    Write-Ok "使用外部配置: $Config"
} else {
    Write-Ok "未发现外部 application.yml，使用 jar 内置配置。"
}
foreach ($arg in $AppArgs) {
    if ($arg -like '--server.port=*') {
        $ServerPort = [int]($arg.Substring('--server.port='.Length))
    }
}
Write-Host "    数据库: ${DbUser}@${DbHost}:${DbPort} / $DbName"
Write-Host "    HTTP 端口: $ServerPort"

# ---- 3. Java ----
Write-Step '3/6' '检查 JDK 21' '优先使用本目录 Environment\jre（随包发放的 Amazon Corretto 21）。只有没有自带 Java 时才安装。'
$bundledHome = Get-BundledJavaHome
$jdkHome = $null
if ($bundledHome) {
    $jdkHome = $bundledHome
    Write-Ok "使用目录自带 Java: $jdkHome"
} else {
    Write-Host "    本目录没有 Environment\jre，开始在系统中查找 JDK 21。"
    $jdkHome = Find-Jdk21
}
if (-not $jdkHome) {
    $wingetOk = $false
    try { $wingetOk = Try-WingetInstall 'EclipseAdoptium.Temurin.21.JDK' 'Eclipse Temurin JDK 21' } catch { $wingetOk = $false }
    if ($wingetOk) {
        $env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User')
        $jdkHome = Find-Jdk21
    }
}
if (-not $jdkHome) {
    $jdkHome = Install-Jdk21
}
$javaBin = Join-Path $jdkHome 'bin\java.exe'
$javaMajor = Get-JavaMajor $javaBin
if ($javaMajor -lt 21) { throw "找到的 Java 版本过低: $jdkHome （需要 21+）" }
Write-Ok "Java 版本 $javaMajor : $jdkHome"

# ---- 4. Database ----
Write-Step '4/6' '检查 MySQL' "需要本机 ${DbHost}:${DbPort} 上有可登录的 MySQL。没有就从华为云/阿里云镜像下载免安装版，并显示下载进度。"
Start-CommonDbServices
if (-not (Test-PortListening $DbPort)) {
    $portableHome = Join-Path $RuntimeDir 'mysql'
    if (-not (Get-MysqldFromDir $portableHome)) {
        Install-PortableMysql | Out-Null
    } else {
        Write-Ok "已有便携 MySQL 目录: $portableHome"
    }
    if (-not (Test-PortListening $DbPort)) {
        Start-PortableMysql (Join-Path $RuntimeDir 'mysql')
    }
} else {
    Write-Ok "端口 $DbPort 已在监听。"
}

$mysqlExe = Get-MysqlExe
$loginOk = $false
if ($mysqlExe) {
    Write-Host "    使用客户端: $mysqlExe"
    if (Test-MysqlLogin $mysqlExe $DbUser $DbPassword) {
        $loginOk = $true
        Write-Ok "已用 ${DbUser}/${DbPassword} 登录成功。"
    } elseif (Test-MysqlLogin $mysqlExe $DbUser '') {
        Write-Warn "当前 root 密码为空。正在改成配置中的密码，以便服务端连接。"
        Invoke-Mysql $mysqlExe $DbUser '' "ALTER USER 'root'@'localhost' IDENTIFIED BY '$DbPassword'; FLUSH PRIVILEGES;"
        $loginOk = Test-MysqlLogin $mysqlExe $DbUser $DbPassword
        if ($loginOk) { Write-Ok "已将 root 密码设置为与配置一致。" }
    }
} else {
    Write-Warn "没有找到 mysql 命令行客户端，稍后由 Java 在启动时验证账号。若启动报 Access denied，请把密码改成 $DbUser / $DbPassword。"
}

if ($mysqlExe -and -not $loginOk) {
    throw @"
无法用 ${DbUser} / 配置密码 登录 ${DbHost}:${DbPort}。
请任选其一：
  1. 把 MySQL 的 ${DbUser} 密码改成当前配置值
  2. 在本目录放一份 application.yml，改成你现有的 username/password
不要在已经有重要数据的库上盲目改密码。
"@
}

if ($mysqlExe -and $loginOk) {
    Invoke-Mysql $mysqlExe $DbUser $DbPassword "CREATE DATABASE IF NOT EXISTS ``$DbName`` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"
    Write-Ok "数据库 $DbName 已就绪（表结构会在服务端启动时由 Flyway 自动迁移）。"
}

# ---- 5. stop old ----
Write-Step '5/6' '停止旧的服务端进程' "避免端口 $ServerPort 被上次启动占用。不会关闭刚才启动的数据库。"
if (Test-Path $PidFile) {
    $oldPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($oldPid -match '^\d+$') {
        Stop-PidGracefully -ProcessId ([int]$oldPid) -Reason 'PID 文件'
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}
foreach ($procId in (Get-ListeningPids $ServerPort)) {
    Stop-PidGracefully -ProcessId $procId -Reason "端口 $ServerPort"
}
Write-Ok "端口 $ServerPort 空闲。"

# ---- 6. start ----
Write-Step '6/6' '启动服务端' '工作目录必须是 jar 所在目录，这样相对路径 wz、scripts-zh-CN、logs 才会生效。'
$javaArgs = @()
if ($Config) { $javaArgs += "-Dspring.config.location=$Config" }
$javaArgs += @('-jar', $Jar)
$javaArgs += $AppArgs

Write-Host "    命令: `"$javaBin`" $($javaArgs -join ' ')"
Write-Host "    启动后后台管理默认: http://127.0.0.1:$ServerPort"
Write-Host "    客户端登录端口见配置 gms.service.login-port（默认 19696）"
Write-Host ""

if ($Background) {
    New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null
    $errLog = Join-Path (Split-Path $LogFile) 'BeiDou.err.log'
    $proc = Start-Process -FilePath $javaBin -ArgumentList $javaArgs -WorkingDirectory $Root -RedirectStandardOutput $LogFile -RedirectStandardError $errLog -WindowStyle Hidden -PassThru
    $proc.Id | Set-Content -LiteralPath $PidFile -Encoding ASCII
    Write-Ok "服务端已后台启动，PID: $($proc.Id)"
    Write-Host "    标准日志: $LogFile"
    Write-Host "    错误日志: $errLog"
    Write-Host ""
    Write-Host "按回车键关闭窗口（服务端会继续在后台运行）..."
    try { [void](Read-Host) } catch {}
    exit 0
}

Write-Host "    前台启动中，关闭本窗口即停止服务端。" -ForegroundColor Yellow
Write-Host ""
$env:JAVA_HOME = $jdkHome
$env:Path = "$(Join-Path $jdkHome 'bin');$env:Path"
Set-Location -LiteralPath $Root
& $javaBin @javaArgs
exit $LASTEXITCODE

}
catch {
    Write-Host ""
    Write-Host "[失败] $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ScriptStackTrace) {
        Write-Host $_.ScriptStackTrace
    }
    Write-Host ""
    Write-Host "按回车键关闭窗口..."
    try { [void](Read-Host) } catch {}
    exit 1
}
