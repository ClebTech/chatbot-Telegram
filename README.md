# BSI Lanches Telegram Bot

## Bem-vindo ao BSI Lanches Bot, um chatbot para Telegram que simula um atendente virtual para pedidos de lanches, bebidas e salgados. O bot aceita pedidos, aplica cupom de desconto, informa o cardápio, solicita endereço e forma de pagamento, além de interagir com o usuário em um tom formal ou usando gírias, dependendo da linguagem detectada.

## Funcionalidades
- Exibe o cardápio com categorias (hambúrgueres, pizzas, saladas, bebidas, salgados).
- Detecta itens e quantidades no pedido através de mensagens.
- Aplica cupom de desconto (código FOME20 para 20% off).
- Solicita endereço para entrega e forma de pagamento.
- Confirma o pedido mostrando resumo e valores (subtotal, desconto, taxa de entrega, total).
- Responde usando linguagem formal ou com gírias, adaptando o tom.
- Informa sobre o entregador e status do pedido.
- Conversa livre com integração à API OpenRouter (modelo GPT-3.5 Turbo).

## Tecnologias usadas
- Python 3.8+
- python-telegram-bot para integração com Telegram
- aiohttp para requisições HTTP assíncronas
- pandas para manipulação da base de gírias
- API OpenRouter para respostas inteligentes do bot (modelo GPT-3.5-turbo)
- Variáveis de ambiente gerenciadas com python-dotenv

### Projeto feito com fins didáticos para a disciplina de Introdução à Inteligência Computacional (IIC), ministrada pelo professor Dr. Felipe Augusto Oliveira Mota no 6º período do curso de Bacharelado em Sistemas de Informação no IFNMG - Campus Januária.
