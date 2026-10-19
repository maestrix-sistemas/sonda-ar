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
