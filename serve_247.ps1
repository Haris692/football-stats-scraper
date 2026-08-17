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
$fichierUrl = Join-Path $root "tunnel.url"
$journalSuperviseur = Join-Path $root "superviseur.log"

function Journal([string]$message) {
    # Le superviseur tourne sous une tache planifiee : `Write-Host` ne va nulle
    # part. Le 17/08 il est mort a 06:44 sans laisser une ligne, et il a fallu
    # le reproduire a la main pour voir l'erreur. Desormais il ecrit.
    $ligne = "$(Get-Date -Format 'dd/MM/yyyy HH:mm:ss') $message"
    Write-Host $ligne
    try { Add-Content -Path $journalSuperviseur -Value $ligne -Encoding utf8 } catch { }
}

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
    Write-Host "  journaux: superviseur.log, serve.log, tunnel-<horodatage>.log"
    Write-Host "  URL     : tunnel.url"
    Write-Host "  a la main: Start-ScheduledTask -TaskName $TaskName"
    exit 0
}

# -- superviseur --------------------------------------------------------------

$python = Trouve-Python
$cloudflared = Trouve-Cloudflared

function Port-Occupe([int]$numero) {
    try {
        return [bool](Get-NetTCPConnection -State Listen -LocalPort $numero -ErrorAction SilentlyContinue)
    } catch { return $false }
}

function Lance-Serveur {
    # Un `serve.py` deja en place garde le port ET le port CDP 9333 : en lancer
    # un second ne donnerait pas deux serveurs mais deux collecteurs qui se
    # disputent le meme Chrome. On refuse plutot que de doubler.
    if (Port-Occupe $Port) {
        Journal "serveur : le port $Port ecoute deja — on ne lance pas de second serveur"
        return $null
    }
    Journal "serveur : demarrage (local $Port, public $PublicPort)"
    Start-Process -FilePath $python `
        -ArgumentList "serve.py", "--port", $Port, "--public-port", $PublicPort, "--no-open" `
        -WorkingDirectory $root -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $journalServeur `
        -RedirectStandardError "$journalServeur.err"
}

function Lance-Tunnel {
    # ⚠️ Chaque tunnel ecrit dans SON journal, horodate. Le fichier unique
    # `tunnel.log` a coute deux pannes le 17/08 :
    #
    #   1. On le vidait par `Set-Content` avant de lancer. Quand un cloudflared
    #      le tenait encore ouvert, l'ecriture echouait, et sous
    #      `ErrorActionPreference = "Stop"` cette seule ligne tuait le
    #      superviseur — serveur et tunnel survivaient, plus rien ne veillait.
    #   2. Deux cloudflared partageant le fichier, l'un le tronque pendant que
    #      l'autre y ecrit a son propre offset : on lit alors un journal troue,
    #      et l'URL du tunnel neuf passe inapercue.
    #
    # Un fichier par lancement supprime les deux : personne d'autre n'y ecrit,
    # rien a vider, aucun offset a tenir.
    $journal = Join-Path $root ("tunnel-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

    Journal "tunnel  : demarrage vers 127.0.0.1:$PublicPort ($(Split-Path $journal -Leaf))"
    $p = Start-Process -FilePath $cloudflared `
        -ArgumentList "tunnel", "--url", "http://127.0.0.1:$PublicPort", "--no-autoupdate" `
        -WorkingDirectory $root -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput "$journal.out" `
        -RedirectStandardError $journal

    # L'URL n'apparait qu'une fois la connexion enregistree aupres du bord.
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 1
        $texte = ""
        try {
            # FileShare ReadWrite : `cloudflared` ecrit dedans pendant qu'on lit.
            $flux = [System.IO.File]::Open($journal, 'Open', 'Read', 'ReadWrite')
            try {
                $lecteur = New-Object System.IO.StreamReader($flux)
                $texte = $lecteur.ReadToEnd()
            } finally { $flux.Dispose() }
        } catch { continue }

        $trouve = ([regex]'https://[a-z0-9-]+\.trycloudflare\.com').Matches($texte)
        if ($trouve.Count -gt 0) {
            $url = $trouve[0].Value
            try {
                Set-Content -Path $fichierUrl -Value $url -Encoding utf8
                Journal "tunnel  : $url"
            } catch {
                # L'adresse vaut mieux dans le journal que nulle part : sans
                # elle, un tunnel de test qui tourne est un tunnel introuvable.
                Journal "tunnel  : $url (tunnel.url non ecrit — $($_.Exception.Message))"
            }
            return $p
        }
    }
    Journal "tunnel  : pas d'URL apres 40 s, voir $(Split-Path $journal -Leaf)"
    return $p
}

function Purge-Journaux {
    # Un journal par lancement, sur un poste qui ne s'arrete jamais : sans
    # purge, le dossier se remplit d'un fichier par relance.
    try {
        Get-ChildItem -Path $root -Filter "tunnel-*.log*" -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
            Remove-Item -Force -ErrorAction SilentlyContinue
    } catch { }
}

Purge-Journaux
$serveur = Lance-Serveur
Start-Sleep -Seconds 3
$tunnel = Lance-Tunnel

Journal "superviseur en place — verification toutes les $CheckSeconds s."

# `Tombe` traite le cas d'un serveur qu'on n'a pas lance nous-memes (port deja
# pris, donc `$null`) : on ne peut pas le surveiller, mais tant que le port
# ecoute, il n'y a rien a relancer.
function Tombe($processus, [int]$numero) {
    if ($null -eq $processus) { return -not (Port-Occupe $numero) }
    return $processus.HasExited
}

while ($true) {
    Start-Sleep -Seconds $CheckSeconds

    # ⚠️ Toute la surveillance est sous `try` : une erreur passagere — un
    # journal verrouille, un `Get-NetTCPConnection` qui tousse — ne doit JAMAIS
    # emporter le superviseur. C'est exactement ce qui est arrive le 17/08, et
    # le seul symptome etait un serveur que plus rien ne relancait.
    try {
        if (Tombe $serveur $Port) {
            $code = if ($null -eq $serveur) { "port muet" } else { "code $($serveur.ExitCode)" }
            Journal "serveur : tombe ($code), relance"
            $serveur = Lance-Serveur
            Start-Sleep -Seconds 3
            # Le tunnel survit au serveur, mais il pointerait vers un port mort le
            # temps que celui-ci reparte : on le relance dans la foulee, quitte a
            # changer d'URL. Mieux vaut une adresse neuve qu'une adresse muette.
            if ($null -ne $tunnel -and -not $tunnel.HasExited) {
                Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 2
            }
            $tunnel = Lance-Tunnel
        }
        elseif ($null -eq $tunnel -or $tunnel.HasExited) {
            $code = if ($null -eq $tunnel) { "jamais lance" } else { "code $($tunnel.ExitCode)" }
            Journal "tunnel  : tombe ($code), relance"
            $tunnel = Lance-Tunnel
        }
    } catch {
        Journal "surveillance : erreur ignoree — $($_.Exception.Message)"
    }
}
