# 电脑侧（Windows）链路检查：USB 网卡是否就位、板卡是否可达
# 用法：在仓库根目录执行 powershell -NoProfile -File .\tools\pc-link-check.ps1
# 只读，不修改任何网络配置。

$board = '192.168.128.10'
$pcIp = '192.168.128.100'
$ok = $true

Write-Host "== 1. 带 IPv4 的网卡 ==" -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -ne '127.0.0.1' } |
    Select-Object InterfaceAlias, IPAddress, PrefixLength |
    Format-Table -AutoSize | Out-String | Write-Host

Write-Host "== 2. USB 网卡（RNDIS / USB Ethernet 等）==" -ForegroundColor Cyan
$usb = Get-NetAdapter -ErrorAction SilentlyContinue |
    Where-Object { $_.InterfaceDescription -match 'RNDIS|USB Ethernet|Remote NDIS|CDC' -or $_.Name -match '以太网 \d|Ethernet \d' }
if ($usb) {
    $usb | Select-Object Name, InterfaceDescription, Status, LinkSpeed | Format-Table -AutoSize | Out-String | Write-Host
} else {
    Write-Host "  未发现 USB 网卡：先确认数据线插在 X5 的 USB Device 数据口（不是供电口/USB-A 主机口），并确认是数据线而非纯充电线。" -ForegroundColor Yellow
    $ok = $false
}

Write-Host "== 3. 电脑侧地址应为 $pcIp/24 ==" -ForegroundColor Cyan
$hasIp = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -eq $pcIp } | Select-Object -First 1
if ($hasIp) {
    Write-Host "  已配置：$($hasIp.InterfaceAlias) $pcIp/$($hasIp.PrefixLength)"
} else {
    Write-Host "  未配置：在该 USB 网卡的 IPv4 属性里设 $pcIp，掩码 255.255.255.0，网关/DNS 留空。" -ForegroundColor Yellow
    $ok = $false
}

Write-Host "== 4. 板卡可达性 ==" -ForegroundColor Cyan
$ping = Test-Connection -ComputerName $board -Count 2 -Quiet -ErrorAction SilentlyContinue
Write-Host ("  ping {0}: {1}" -f $board, $(if ($ping) { '通' } else { '不通' }))
$tcp = (Test-NetConnection -ComputerName $board -Port 22 -WarningAction SilentlyContinue).TcpTestSucceeded
Write-Host ("  TCP 22: {0}" -f $(if ($tcp) { '开放' } else { '不可达' }))
if (-not $ping) { $ok = $false }

Write-Host "== 5. 已记录的主机密钥 ==" -ForegroundColor Cyan
$kh = Join-Path $env:USERPROFILE '.ssh\known_hosts'
if (Test-Path $kh) {
    $n = (Select-String -Path $kh -Pattern $board -SimpleMatch -ErrorAction SilentlyContinue).Count
    Write-Host "  known_hosts 中 $board 相关条目：$n"
} else {
    Write-Host "  尚无 known_hosts（还没成功 SSH 过）"
}

Write-Host ""
if ($ok -and $tcp) {
    Write-Host "结论：链路就绪，可直接执行 ssh wheeltec@$board" -ForegroundColor Green
} elseif ($ok) {
    Write-Host "结论：地址与网卡都就位，但板卡无响应：检查板卡是否上电、线是否插在数据口、网线/USB 口是否被系统识别。" -ForegroundColor Yellow
} else {
    Write-Host "结论：电脑侧尚未就绪，按上面第 2、3 条修正后再跑一次本脚本。" -ForegroundColor Yellow
}
