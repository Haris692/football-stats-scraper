# Tient `serve.py` et le tunnel Cloudflare en vie, et inscrit le tout au
# démarrage de session.
#
# Pourquoi un superviseur plutôt que deux tâches planifiées : le tunnel doit
# être relancé *après* le serveur, et l'URL d'un tunnel de test change à chaque
# démarrage. Il faut donc quelque chose qui les ordonne et qui note l'adresse
# quelque part — le planificateur seul ne sait pas faire ça.
#
#     powershell -ExecutionPolicy Bypass -File serve_247.ps1            # ici, maintenant
#     powershell -ExecutionPolicy Bypass -File serve_247.ps1 -Register  # à chaque ouverture de session
#     powershell -ExecutionPolicy Bypass -File serve_247.ps1 -Remove
#
# La tâche tourne **dans la session ouverte** (`-LogonType Interactive`), comme
# `schedule_daily.ps1` : le direct pilote un vrai Chrome, il lui faut un bureau.
#
# ⚠️ Le tunnel vise le port PUBLIC, jamais `--port`. Le port local sert aussi la
# console interne, le code, `.git/` et le profil Chrome — donc ses cookies.

param(
    [int]$Port = 8800,
    [int]$PublicPort = 8801,
    [string]$TaskName = "FootballStatsScraper-Serve",
    [switch]$Register,
    [switch]$Remove,
    [int]$CheckSeconds = 30
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$journalServeur = Join-Path $root "serve.log"
$journalTunnel = Join-Path $root "tunnel.log"
$fichierUrl = Join-Path $root "tunnel.url"

function Trouve-Python {
    $p = Join-Path $root ".venv\Scripts\python.exe"
    if (Test-Path $p) { return $p }
    $p = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($p) { return $p }
    throw "python introuvable : ni .venv, ni le PATH"
}

function Trouve-Cloudflared {
    $c = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
    if ($c) { return $c }
    foreach ($p in @("$env:ProgramFiles\cloudflared\cloudflared.exe",
                     "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe")) {
        if (Test-Path $p) { return $p }
    }
    throw "cloudflared introuvable — winget install Cloudflare.cloudflared"
}

# -- inscription au planificateur --------------------------------------------

if ($Remove) {
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "tache supprimee : $TaskName"
    } catch {
        Write-Host "aucune tache nommee $TaskName"
    }
    exit 0
}

if ($Register) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument ("-ExecutionPolicy Bypass -WindowStyle Hidden -NonInteractive " +
                   "-File `"$PSCommandPath`" -Port $Port -PublicPort $PublicPort") `
        -WorkingDirectory $root

    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

    # ExecutionTimeLimit a zero : la tache ne s'arrete jamais d'elle-meme, c'est
    # tout l'objet d'un service. RestartCount rattrape un plantage du
    # superviseur lui-meme, que sa propre boucle ne peut pas voir.
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
        -MultipleInstances IgnoreNew `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
        -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force `
        -Description "Sert le site et /api/live sur le port public, derriere un tunnel Cloudflare." | Out-Null

    Write-Host "tache inscrite : $TaskName, a chaque ouverture de session"
    Write-Host "  dossier : $root"
    Write-Host "  journaux: serve.log, tunnel.log"
    Write-Host "  URL     : tunnel.url"
    Write-Host "  a la main: Start-ScheduledTask -TaskName $TaskName"
    exit 0
}

# -- superviseur --------------------------------------------------------------

$python = Trouve-Python
$cloudflared = Trouve-Cloudflared

function Lance-Serveur {
    Write-Host "$(Get-Date -Format 'HH:mm:ss') serveur : demarrage (local $Port, public $PublicPort)"
    Start-Process -FilePath $python `
        -ArgumentList "serve.py", "--port", $Port, "--public-port", $PublicPort, "--no-open" `
        -WorkingDirectory $root -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $journalServeur `
        -RedirectStandardError "$journalServeur.err"
}

function Lance-Tunnel {
    # Le journal est vide a chaque demarrage : sinon on relirait l'URL du tour
    # precedent, qui ne pointe plus nulle part.
    Set-Content -Path $journalTunnel -Value "" -Encoding utf8
    Write-Host "$(Get-Date -Format 'HH:mm:ss') tunnel  : demarrage vers 127.0.0.1:$PublicPort"
    $p = Start-Process -FilePath $cloudflared `
        -ArgumentList "tunnel", "--url", "http://127.0.0.1:$PublicPort", "--no-autoupdate" `
        -WorkingDirectory $root -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput "$journalTunnel.out" `
        -RedirectStandardError $journalTunnel

    # L'URL n'apparait qu'une fois la connexion enregistree aupres du bord.
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 1
        $texte = Get-Content $journalTunnel, "$journalTunnel.out" -Raw -ErrorAction SilentlyContinue
        $trouve = ([regex]'https://[a-z0-9-]+\.trycloudflare\.com').Matches($texte)
        if ($trouve.Count -gt 0) {
            $url = $trouve[0].Value
            Set-Content -Path $fichierUrl -Value $url -Encoding utf8
            Write-Host "$(Get-Date -Format 'HH:mm:ss') tunnel  : $url"
            return $p
        }
    }
    Write-Host "$(Get-Date -Format 'HH:mm:ss') tunnel  : pas d'URL apres 40 s, voir tunnel.log"
    return $p
}

$serveur = Lance-Serveur
Start-Sleep -Seconds 3
$tunnel = Lance-Tunnel

Write-Host "superviseur en place — verification toutes les $CheckSeconds s."

while ($true) {
    Start-Sleep -Seconds $CheckSeconds
    if ($serveur.HasExited) {
        Write-Host "$(Get-Date -Format 'HH:mm:ss') serveur : tombe (code $($serveur.ExitCode)), relance"
        $serveur = Lance-Serveur
        Start-Sleep -Seconds 3
        # Le tunnel survit au serveur, mais il pointerait vers un port mort le
        # temps que celui-ci reparte : on le relance dans la foulee, quitte a
        # changer d'URL. Mieux vaut une adresse neuve qu'une adresse muette.
        if (-not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue }
        $tunnel = Lance-Tunnel
    }
    elseif ($tunnel.HasExited) {
        Write-Host "$(Get-Date -Format 'HH:mm:ss') tunnel  : tombe (code $($tunnel.ExitCode)), relance"
        $tunnel = Lance-Tunnel
    }
}
