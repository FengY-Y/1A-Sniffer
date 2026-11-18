# 实验 1A 虚拟机管理小工具（Windows / VMware Workstation）
#
#   .\vm.ps1 status                  # 看哪些虚拟机在跑
#   .\vm.ps1 start                   # 启动 sniffer（带窗口）
#   .\vm.ps1 start -Gui:$false       # 无窗口启动
#   .\vm.ps1 stop                    # 正常关机
#   .\vm.ps1 stop -Force             # 直接断电（卡死时用）
#   .\vm.ps1 snapshot -Snap 02-deps  # 打快照
#   .\vm.ps1 clone-victim            # 关机状态克隆出 victim
#   .\vm.ps1 ip                      # 取虚拟机 IP（需要 open-vm-tools）
#
# 前提：虚拟机已关机才能 clone；快照建议在关机或稳定状态下打。

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('status', 'start', 'stop', 'reset', 'suspend', 'snapshot', 'clone-victim', 'ip')]
    [string]$Action,

    [string]$Name = 'sniffer',
    [string]$Snap = 'snapshot',
    [bool]$Gui = $true,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$VMRUN = 'D:\soft_computer\VMware Workstation\vmrun.exe'
$ROOT = 'D:\soft_computer\VMs'
$vmx = Join-Path $ROOT "$Name\$Name.vmx"

function Need-Vmx {
    if (-not (Test-Path $vmx)) { throw "找不到虚拟机：$vmx" }
}

switch ($Action) {
    'status' {
        & $VMRUN -T ws list
        Write-Host "`n实验室虚拟机目录：$ROOT"
        Get-ChildItem $ROOT -Directory -ErrorAction SilentlyContinue |
            ForEach-Object { "  {0}  ({1} GB)" -f $_.Name, [math]::Round(((Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB), 2) }
    }
    'start' {
        Need-Vmx
        if ($Gui) { & $VMRUN -T ws start $vmx } else { & $VMRUN -T ws start $vmx nogui }
        Write-Host "已启动 $Name"
    }
    'stop' {
        Need-Vmx
        if ($Force) { & $VMRUN -T ws stop $vmx hard } else { & $VMRUN -T ws stop $vmx soft }
    }
    'reset' {
        Need-Vmx
        & $VMRUN -T ws reset $vmx hard
    }
    'suspend' {
        Need-Vmx
        & $VMRUN -T ws suspend $vmx hard
    }
    'snapshot' {
        Need-Vmx
        & $VMRUN -T ws snapshot $vmx $Snap
        Write-Host "已创建快照：$Snap"
    }
    'clone-victim' {
        Need-Vmx
        $dst = Join-Path $ROOT 'victim\victim.vmx'
        if (Test-Path $dst) { throw "已存在：$dst" }
        & $VMRUN -T ws clone $vmx $dst full
        Write-Host "已克隆到 $dst"
        Write-Host "启动后记得改三样：hostnamectl / machine-id / 静态 IP 10.10.10.20"
    }
    'ip' {
        Need-Vmx
        & $VMRUN -T ws getGuestIPAddress $vmx
    }
}
