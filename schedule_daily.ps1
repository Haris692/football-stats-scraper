# Inscrit `daily.py` au planificateur de tâches Windows, tous les jours à 8 h.
#
# Pourquoi ici et pas dans le cloud : la collecte a besoin du Chrome de cette
# machine et de la clearance Cloudflare gardée dans `.chrome-profile/`. Une
# tâche distante se ferait renvoyer un challenge qu'elle ne peut pas résoudre.
#
#     powershell -ExecutionPolicy Bypass -File schedule_daily.ps1
#     powershell -ExecutionPolicy Bypass -File schedule_daily.ps1 -At 07:30
#     powershell -ExecutionPolicy Bypass -File schedule_daily.ps1 -Remove
#
# La tâche tourne **dans la session ouverte** (`-LogonType Interactive`) : la
# collecte pilote un vrai Chrome, elle a besoin d'un bureau. Elle ne se lance
# donc pas si personne n'est connecté — mais `StartWhenAvailable` la rattrape
# dès l'ouverture de session, ce qui couvre la machine éteinte à 8 h.

param(
    [string]$At = "08:00",
    [string]$TaskName = "FootballStatsScraper-Daily",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($Remove) {
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "tache supprimee : $TaskName"
    } catch {
        Write-Host "aucune tache nommee $TaskName"
    }
    exit 0
}

# Le venv d'abord. Sur un poste neuf, `python` tout court vise le stub du
# Microsoft Store : la tâche partirait à l'heure dite et ne collecterait rien.
# Une panne silencieuse, la pire espèce pour un rafraîchissement quotidien.
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $python) { throw "python introuvable : ni .venv, ni le PATH" }

$action = New-ScheduledTaskAction -Execute $python `
    -Argument "daily.py" -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Daily -At $At

# StartWhenAvailable : rattrape une exécution manquée (machine éteinte à 8 h).
# Pas de DontStopIfGoingOnBatteries par défaut sur portable, donc on l'autorise
# explicitement — sinon la tache ne part jamais sur secteur absent.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description "Collecte Forebet/Sofascore/Flashscore, regenere index.html et publie." | Out-Null

Write-Host "tache inscrite : $TaskName, tous les jours a $At"
Write-Host "  dossier  : $root"
Write-Host "  journal  : $root\daily.log"
Write-Host "  a la main: Start-ScheduledTask -TaskName $TaskName"
