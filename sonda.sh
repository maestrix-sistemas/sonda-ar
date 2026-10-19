#!/usr/bin/env bash
# Sonda externa das rádios da Rede Alagoas FM (Plano de Blindagem, passo 3.2).
#
# Roda FORA da VPS (GitHub Actions), de 15 em 15 min. Para cada rádio escuta
# 20 s do stream público e confere três coisas:
#   1. o stream responde (ffmpeg conecta e decodifica);
#   2. chega áudio de verdade (pelo menos 15 s decodificados);
#   3. não é silêncio (volume médio acima de -50 dB; silêncio digital ≈ -91 dB).
# O resultado vai para o Healthchecks.io: ping = ok, /fail = problema. Se esta
# sonda parar de rodar (GitHub fora, agendamento desligado), o Healthchecks
# também avisa, porque o ping some.
set -uo pipefail
LIMITE_DB=-50
declare -A URL=(
  [maceio]="https://painel.sampaiofm.com.br/listen/maceio/radio.mp3"
  [delmiro]="https://painel.sampaiofm.com.br/listen/delmiro/radio.mp3"
  [gospel]="https://painel.sampaiofm.com.br/listen/alagoas_fm_gospel/radio.mp3"
)
declare -A PING=([maceio]="${HC_MACEIO:-}" [delmiro]="${HC_DELMIRO:-}" [gospel]="${HC_GOSPEL:-}")

for r in maceio delmiro gospel; do
  log=$(timeout 45 ffmpeg -hide_banner -nostats -rw_timeout 15000000 -t 20 -i "${URL[$r]}" -af volumedetect -f null - 2>&1)
  rc=$?
  media=$(grep -oP 'mean_volume: \K-?[0-9.]+' <<<"$log" | tail -1)
  dur=$(grep -oP 'time=\K[0-9:.]+' <<<"$log" | tail -1)
  seg=$(awk -F: '{ if (NF==3) print $1*3600+$2*60+$3; else print 0 }' <<<"${dur:-0}")
  if [ $rc -ne 0 ] || [ -z "$media" ]; then
    estado=fail; msg="$r: stream não respondeu (ffmpeg $rc)"
  elif awk "BEGIN{exit !($seg < 15)}"; then
    estado=fail; msg="$r: só ${seg}s de áudio em 20s (stream picando)"
  elif awk "BEGIN{exit !($media < $LIMITE_DB)}"; then
    estado=fail; msg="$r: SILÊNCIO no ar (volume médio ${media} dB)"
  else
    estado=ok; msg="$r: ok (${seg}s, volume médio ${media} dB)"
  fi
  echo "$msg"
  if [ -n "${PING[$r]}" ]; then
    alvo="${PING[$r]}"; [ "$estado" = fail ] && alvo="$alvo/fail"
    curl -fsS -m 15 --retry 3 -o /dev/null --data-raw "$msg" "$alvo" || echo "  (não consegui avisar o Healthchecks)"
  fi
done
