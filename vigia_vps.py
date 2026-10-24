#!/usr/bin/env python3
"""VPS fora? Diz se a culpa é da Hostinger (23/10/2026).

Em 23/10 a VPS sumiu das 16:03 às 17:34 por um apagão no datacenter BR-CAM da
Hostinger, e o único aviso foi o e-mail do Healthchecks dizendo "down", sem
dizer por quê. Este vigia roda FORA da VPS (GitHub Actions, junto da sonda das
rádios) e, quando ela não responde, lê a página de status da Hostinger e manda
no Telegram a causa provável.

Quando avisa (sem repetir a cada 15 min — a duração vem do Healthchecks):
- 🔴 a 1ª vez que a VPS passa de 8 min sem sinal;
- 🔴 lembrete a cada hora enquanto continuar fora;
- 🟢 quando ela volta (com quanto tempo ficou fora).

Segredos (GitHub → Settings → Secrets): HC_API_KEY (Healthchecks, leitura),
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Sem eles, só imprime no log.
"""
import json
import os
import socket
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

VPS = "187.127.45.239"
SAUDE = "https://plataforma.sampaiofm.com.br/v1/health"
STATUS_HOSTINGER = "https://statuspage.hostinger.com/api/v2/incidents/unresolved.json"
STATUS_RECENTES = "https://statuspage.hostinger.com/api/v2/incidents.json"
HC_API = "https://healthchecks.io/api/v3/checks/"
CHECK = "vps-vida"
PRIMEIRO_AVISO_MIN = 8
JANELA_MIN = 15             # o intervalo da sonda: cada marco cai em UMA rodada só
TZ = ZoneInfo("America/Maceio")
# o que, num incidente da Hostinger, indica a NOSSA VPS: o datacenter do Brasil
# em qualquer parte, ou "VPS" no TÍTULO (no corpo, "VPS" aparece até em aviso
# de PHP — falso positivo visto no teste de 23/10)
SINAIS_BR = ("br-cam", "brazil", "brasil", "são paulo", "sao paulo")


def _get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "sonda-ar", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def porta_abre(porta, timeout=8):
    try:
        with socket.create_connection((VPS, porta), timeout=timeout):
            return True
    except OSError:
        return False


def vps_responde():
    """Fora = nem SSH nem HTTPS abrem no IP. Plataforma lenta não é VPS fora."""
    return porta_abre(22) or porta_abre(443) or porta_abre(80)


def check_vps():
    k = os.environ.get("HC_API_KEY")
    if not k:
        return None
    for c in _get(HC_API, {"X-Api-Key": k})["checks"]:
        if c.get("slug") == CHECK:
            flips = _get(f"{HC_API}{c['uuid']}/flips/", {"X-Api-Key": k})
            c["_flips"] = flips.get("flips", flips) if isinstance(flips, dict) else flips
            return c
    return None


def _dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def incidentes_hostinger(recentes=False):
    """Os incidentes da Hostinger que podem ser os nossos (Brasil / VPS)."""
    try:
        dados = _get(STATUS_RECENTES if recentes else STATUS_HOSTINGER)
    except Exception as exc:  # noqa: BLE001
        return None, f"não consegui ler a página de status da Hostinger ({exc})"
    achados = []
    for i in dados.get("incidents", [])[: 15 if recentes else 50]:
        ultimas = i.get("incident_updates") or [{}]
        nome = (i.get("name") or "").lower()
        texto = f"{nome} {ultimas[0].get('body', '')}".lower()
        if any(s in texto for s in SINAIS_BR) or "vps" in nome:
            achados.append(i)
    return achados, None


def _hora(dt):
    return dt.astimezone(TZ).strftime("%H:%M")


def causa_texto(incs, erro):
    if erro:
        return f"Causa: não sei ainda — {erro}."
    if not incs:
        return ("Causa: a Hostinger NÃO tem incidente aberto para o Brasil/VPS. Pode ser a nossa "
                "máquina (travou, sem memória, desligada) — conferir no hPanel.")
    i = incs[0]
    ultima = (i.get("incident_updates") or [{}])[0]
    corpo = " ".join((ultima.get("body") or "").split())[:280]
    return (f"Causa provável: HOSTINGER — “{i.get('name')}” (aberto às {_hora(_dt(i['created_at']))}, "
            f"status {ultima.get('status', i.get('status'))}).\nÚltima nota deles: {corpo}")


def avisar(texto):
    print(texto)
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("(sem Telegram configurado — só no log)")
        return
    corpo = urllib.parse.urlencode({"chat_id": chat, "text": texto,
                                    "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", corpo, timeout=20)
    except Exception as exc:  # noqa: BLE001
        print(f"(não consegui mandar no Telegram: {exc})")


def main():
    agora = datetime.now(timezone.utc)
    no_ar = vps_responde()
    try:
        c = check_vps()
    except Exception as exc:  # noqa: BLE001
        print(f"(Healthchecks indisponível: {exc})")
        c = None
    ultimo = _dt((c or {}).get("last_ping"))
    if not no_ar:
        fora_min = int((agora - ultimo).total_seconds() // 60) if ultimo else None
        if fora_min is None:
            # sem a régua do Healthchecks: avisa uma vez por hora (rodada do :07)
            marco = agora.minute < JANELA_MIN
        else:
            marco = (PRIMEIRO_AVISO_MIN <= fora_min < PRIMEIRO_AVISO_MIN + JANELA_MIN
                     or (fora_min >= 60 and fora_min % 60 < JANELA_MIN))
        print(f"VPS não responde; sem sinal há {fora_min} min; avisar agora: {marco}")
        if not marco:
            return
        incs, erro = incidentes_hostinger()
        desde = f"desde {_hora(ultimo)} ({fora_min} min)" if ultimo else "agora"
        acao = ("SUA: só se passar de 1 h — abrir chamado no hPanel (Suporte) pedindo a previsão. "
                "Não reiniciar: com o problema na Hostinger, reiniciar não resolve."
                if incs else "SUA: abrir o hPanel e ver se a VPS está ligada; se estiver, reiniciar por lá.")
        avisar(f"🔴 VPS · Maestrix (Hostinger) · infra\n"
               f"A VPS não responde {desde}: caem as 3 rádios, a plataforma, os portais e a TV.\n"
               f"{causa_texto(incs, erro)}\nAção: {acao}")
        return
    # no ar: acabou de voltar? (o Healthchecks marcou "up" nesta janela)
    flips = (c or {}).get("_flips") or []
    if not flips:
        print("VPS no ar.")
        return
    fl = sorted(flips, key=lambda f: f["timestamp"])
    ultimo_flip = fl[-1]
    voltou = _dt(ultimo_flip["timestamp"])
    if ultimo_flip.get("up") and (agora - voltou).total_seconds() < JANELA_MIN * 60:
        caiu = next((_dt(f["timestamp"]) for f in reversed(fl[:-1]) if not f.get("up")), None)
        # o Healthchecks marca "down" só depois do prazo + folga sem ping: a queda
        # real começou esse tanto antes
        atraso = int((c or {}).get("timeout") or 0) + int((c or {}).get("grace") or 0)
        dur = (f" depois de ~{int((voltou - caiu).total_seconds() + atraso) // 60} min fora"
               if caiu else "")
        incs, _erro = incidentes_hostinger(recentes=True)
        nome = f" Hostinger: “{incs[0].get('name')}”." if incs else ""
        avisar(f"🟢 VPS · Maestrix (Hostinger) · infra\nVPS fora do ar: resolvido às {_hora(voltou)}{dur}.{nome}\n"
               "Ação: nenhuma — conferir rádios, plataforma e portais (a sonda das rádios confere em até 15 min).")
    else:
        print("VPS no ar.")


if __name__ == "__main__":
    main()
