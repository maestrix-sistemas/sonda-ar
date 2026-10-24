# Sonda das rádios

Escuta as rádios da Rede Alagoas FM **de fora do servidor**, de 15 em 15 min.
Para cada uma confere se o stream responde, se chega áudio e se não é silêncio.
O resultado vai para o Healthchecks.io, que avisa quando algo falha ou quando a
sonda para de rodar.

Público só porque o GitHub Actions é gratuito sem limite em repositório público.
Não há segredo aqui: os endereços de aviso ficam em *Settings › Secrets*.

Atenção: o GitHub desliga agendamentos de repositório público sem nenhuma
atividade por 60 dias. Se isso acontecer, o Healthchecks avisa (os pings somem)
e basta reativar em *Actions*.

## Vigia da VPS (`vigia_vps.py`, 23/10/2026)

Na mesma rodada, confere se a VPS responde (portas 22/443/80). Se não, lê a
página de status da Hostinger e avisa no Telegram a **causa provável**: incidente
aberto no datacenter do Brasil (BR-CAM) ou "nenhum incidente — pode ser a nossa
máquina". Avisa aos 8 min fora, depois de hora em hora, e 🟢 quando volta — a
duração vem do monitor `vps-vida` do Healthchecks, então não repete a cada 15 min.
Segredos: `HC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
