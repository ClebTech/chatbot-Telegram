import os
from dotenv import load_dotenv
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Carrega as variáveis de ambiente
load_dotenv()

# Configurações
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')  # Chave da OpenRouter guardada em um arquivo .env pra segurança
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'  # Endpoint do OpenRouter

# Verifica se as variáveis de ambiente foram carregadas
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("A variável de ambiente TELEGRAM_BOT_TOKEN deve ser definida no arquivo .env.")

# Cardápio da lanchonete
cardapio = {
    "hambúrgueres": [
        {"nome": "Hambúrguer Python", "preco": 15.00},
        {"nome": "Hambúrguer Java", "preco": 18.00},
        {"nome": "Hambúrguer PHP", "preco": 16.00}
    ],
    "pizzas": [
        {"nome": "Pizza de C#", "preco": 35.00},
        {"nome": "Pizza JavaScript", "preco": 40.00},
        {"nome": "Pizza de HTML com CSS", "preco": 38.00}
    ],
    "saladas": [
        {"nome": "Salada de Memória RAM", "preco": 12.00},
        {"nome": "Salada de Pen-Drives", "preco": 10.00},
        {"nome": "Salada de Software", "preco": 8.00}
    ],
    "bebidas": [
        {"nome": "Refrigerante SQL", "preco": 5.00},
        {"nome": "Suco Natural de Linux", "preco": 7.00},
        {"nome": "Água Mineral", "preco": 3.00}
    ]
}

# Função para formatar o cardápio
def formatar_cardapio():
    cardapio_formatado = "🍔 **Cardápio da Lanchonete** 🍕\n\n"
    for categoria, itens in cardapio.items():
        cardapio_formatado += f"**{categoria.capitalize()}:**\n"
        for item in itens:
            cardapio_formatado += f"- {item['nome']}: R$ {item['preco']:.2f}\n"
        cardapio_formatado += "\n"
    return cardapio_formatado

# Função para calcular o valor total do pedido
def calcular_total(pedido, cupom_valido=False):
    taxa_entrega = 3.00  # Taxa de entrega fixa
    subtotal = sum(item['preco'] for item in pedido)  # Soma os preços dos itens
    
    if cupom_valido:
        desconto = subtotal * 0.20  # 20% de desconto
    else:
        desconto = 0.00
    
    total = subtotal - desconto + taxa_entrega
    return subtotal, desconto, taxa_entrega, total

# Função para interagir com a API do OpenRouter
async def get_openrouter_response(conversation_history):
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        "model": "openai/gpt-3.5-turbo",  # Modelo escolhido
        "messages": conversation_history,
        "max_tokens": 150
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_API_URL, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result['choices'][0]['message']['content'].strip()
                else:
                    return f"Erro na API: {response.status} - {await response.text()}"
    except Exception as e:
        return f"Erro ao processar a mensagem: {str(e)}"

# Comando de início
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Olá! Eu sou o Clebinho, atendente virtual da lanchonete "BSI Lanches". Como posso ajudar?')

# Manipulador de mensagens
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.lower()  # Converte a mensagem para minúsculas

    # Verifica se o usuário está perguntando sobre o cardápio
    if "cardápio" in user_message or "o que vocês servem" in user_message or "cardapio" in user_message:
        cardapio_formatado = formatar_cardapio()
        await update.message.reply_text(cardapio_formatado, parse_mode="Markdown")
        return

    # Verifica se o usuário está perguntando sobre o entregador
    if "entregador" in user_message or "quem faz as entregas" in user_message or "quem entrega" in user_message:
        await update.message.reply_text("Nosso entregador se chama Wallan. Ele é super rápido e cuidadoso! 🚴‍♂️")
        return

    # Verifica se o usuário mencionou um cupom de desconto
    if "cupom" in user_message or "desconto" in user_message:
        if "fome20" in user_message:
            context.user_data['cupom_valido'] = True
            await update.message.reply_text("Cupom FOME20 aplicado! Você ganhou 20% de desconto no seu pedido. 🎉")
        else:
            await update.message.reply_text("Cupom inválido. 😕 O cupom válido é 'FOME20'.")
        return

    # Verifica se o usuário está finalizando o pedido
    if "finalizar pedido" in user_message or "fechar pedido" in user_message:
        if 'pedido' not in context.user_data:
            await update.message.reply_text("Você ainda não fez nenhum pedido. 😕")
            return

        pedido = context.user_data['pedido']
        cupom_valido = context.user_data.get('cupom_valido', False)
        subtotal, desconto, taxa_entrega, total = calcular_total(pedido, cupom_valido)

        resposta = (
            "📝 **Resumo do Pedido:**\n\n"
            f"**Itens:**\n"
        )
        for item in pedido:
            resposta += f"- {item['nome']}: R$ {item['preco']:.2f}\n"
        
        resposta += (
            f"\n**Subtotal:** R$ {subtotal:.2f}\n"
            f"**Desconto:** R$ {desconto:.2f}\n"
            f"**Taxa de Entrega:** R$ {taxa_entrega:.2f}\n"
            f"**Total:** R$ {total:.2f}\n\n"
            "Obrigado pelo pedido! 🚴‍♂️"
        )

        await update.message.reply_text(resposta, parse_mode="Markdown")
        return

    # Verifica se o usuário está adicionando itens ao pedido
    for categoria, itens in cardapio.items():
        for item in itens:
            if item['nome'].lower() in user_message:
                if 'pedido' not in context.user_data:
                    context.user_data['pedido'] = []
                context.user_data['pedido'].append(item)
                await update.message.reply_text(f"{item['nome']} adicionado ao pedido! 🛒")
                return

    # Se não for sobre o cardápio, entregador, cupom ou finalização, envia a mensagem para a API do OpenRouter
    if 'conversation_history' not in context.user_data:
        context.user_data['conversation_history'] = [
            {"role": "system", "content": "Você é um atendente virtual de uma lanchonete chamada 'BSI LANCHES', seu nome é Clebinho. Você é descontraído, amigável e entende gírias e expressões informais. Responda de forma natural, como se estivesse conversando com um amigo, mas mantenha o foco em ajudar com o cardápio e pedidos. Depois que o cliente solicitar o cardápio, você informa a ele o card que ele pode digitar 'finalizar' para receber o valor total do pedido, já incluindo possíveis cupons de desconto e taxa de entrega, além do tempo médio de espera."}
        ]

    # Adiciona a mensagem do usuário ao histórico
    context.user_data['conversation_history'].append({"role": "user", "content": user_message})

    # Obtém a resposta da API
    response = await get_openrouter_response(context.user_data['conversation_history'])

    # Adiciona a resposta do assistente ao histórico
    context.user_data['conversation_history'].append({"role": "assistant", "content": response})

    # Envia a resposta para o usuário
    await update.message.reply_text(response)

# Função principal
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Inicia o bot
    application.run_polling()

if __name__ == '__main__':
    main()
