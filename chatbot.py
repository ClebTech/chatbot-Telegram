import os #manipulação de arquivos e diretos do linux, acessar variaveis de ambiente
import re #manipulação de strings, busca de padrões e etc (extrair itens de pedidos de mensagens)
import json #para ensinar a IA sobre o cardapio

from dotenv import load_dotenv #importa as variaveis de ambiente (chaves API)

import aiohttp #requisições HTTP assíncronas

#manipulação de dados (usado no arquivo de gírias)
import pandas as pd

#biblioteca para integração com chatbot do Telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


#possiveis estados do pedido até a finalização (para o bot saber onde está)
(
    AGUARDANDO_PEDIDO,
    AGUARDANDO_ENDERECO,
    AGUARDANDO_PAGAMENTO,
    PEDIDO_CONCLUIDO,
    PEDIDO_EM_PREPARO
) = range(5)

# Carregando as variáveis de ambiente do arquivo .env
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Carregando a base de dados com gírias (tenta carregar o arquivo e criar um dicionario a partir dele pro chatbot)
try:
    df_girias = pd.read_csv('girias.csv')
    girias_dict = {
        row['giria'].lower(): {
            'significado': row['significado'],
            'exemplo_uso': row['exemplo_de_uso']
        } for _, row in df_girias.iterrows()
    }
except:
    print("Erro ao carregar as gírias")
    girias_dict = {}

############cardapio de itens
cardapio = {
    "hambúrgueres": [
        {"nome": "Hambúrguer Python", "preco": 15.40},
        {"nome": "Hambúrguer Java", "preco": 18.00},
        {"nome": "Hambúrguer PHP", "preco": 16.30}
    ],
    "pizzas": [
        {"nome": "Pizza de C#", "preco": 35.00},
        {"nome": "Pizza JavaScript", "preco": 40.00},
        {"nome": "Pizza de HTML com CSS", "preco": 38.00}
    ],
    "saladas": [
        {"nome": "Salada de Memória RAM", "preco": 12.30},
        {"nome": "Salada de Pen-Drives", "preco": 10.00},
        {"nome": "Salada de Software", "preco": 8.00}
    ],
    "bebidas": [
        {"nome": "Refrigerante SQL", "preco": 5.50},
        {"nome": "Suco Natural de Linux", "preco": 7.00},
        {"nome": "Água Mineral", "preco": 3.00}
    ],
    "salgados": [
        {"nome": "Pão de Queijo", "preco": 5.00},
        {"nome": "Sanduíche de Presunto", "preco": 7.20},
        {"nome": "Bolo de Milho", "preco": 9.50}
    ]
}

#funções auxiliares
######mostra o cardapio formatado bonitinho
def formatar_cardapio():
    msg = "===== Cardápio da BSI Lanches ===== \n\n"
    for categoria, itens in cardapio.items():
        msg += f"=={categoria.capitalize()}:==\n"
        for item in itens:
            msg += f"- {item['nome']}: R$ {item['preco']:.2f}\n"
        msg += "\n"
    msg += "[!] Certifique-se de escrever o nome do pedido *exatamente* como está no cardápio para que eu reconheça certinho, beleza?\n\nEXEMPLO: 2x pão de queijo, 1x refrigerante SQL"
    return msg

####calcula o valor total do pedido (itens + cupons + entrega)
def calcular_total(pedido, cupom_valido=False):
    taxa_entrega = 3.00
    subtotal = sum(item['preco'] for item in pedido)
    desconto = subtotal * 0.20 if cupom_valido else 0.0
    total = subtotal - desconto + taxa_entrega
    return subtotal, desconto, taxa_entrega, total

#####verifica se a mensagem do usuario tem gírias do dicionario, para adaptar o tom de conversa
def detectar_giria(mensagem):
    mensagem = mensagem.lower()
    for giria in girias_dict.keys():
        if giria in mensagem:
            return True
    return False

####extrai os itens do pedido do usuario, o nome do pedido (e se é valido) a quantidade... usando a lib re
def extrair_itens_do_pedido(mensagem):
    mensagem = mensagem.lower()
    itens_identificados = []
    contagem_itens = {}

    # Padrão para encontrar quantidades e itens (ex: "2x hambúrguer python" ou "3 pizza de c#")
    padrao_quantidade = r"(\d+)\s*(?:x\s*)?([^\d,;.]+?)(?=\d|,|;|\.|$)"
    matches = re.finditer(padrao_quantidade, mensagem)
    
    for match in matches:
        quantidade = int(match.group(1))
        item_pedido = match.group(2).strip()
        
        # Verifica se o item existe no cardápio
        item_encontrado = None
        for categoria, itens in cardapio.items():
            for item in itens:
                if item['nome'].lower() in item_pedido:
                    item_encontrado = item
                    break
            if item_encontrado:
                break
        
        if item_encontrado:
            nome_item = item_encontrado['nome']
            if nome_item in contagem_itens:
                contagem_itens[nome_item] += quantidade
            else:
                contagem_itens[nome_item] = quantidade
            for _ in range(quantidade):
                itens_identificados.append(item_encontrado)
    
    #tbm verifica itens sem quantidade indicada (ent assume q é 1 item)
    for categoria, itens in cardapio.items():
        for item in itens:
            nome_item = item['nome'].lower()
            nome_item_cardapio = item['nome']
            ### se o item for mencionado sem quantidade e não foi capturado pelo padrão anterior
            if (nome_item in mensagem and 
                not any(nome_item in match.group(2).lower() for match in re.finditer(padrao_quantidade, mensagem))):
                if nome_item_cardapio in contagem_itens:
                    contagem_itens[nome_item_cardapio] += 1
                else:
                    contagem_itens[nome_item_cardapio] = 1
                itens_identificados.append(item)
    
    return itens_identificados, contagem_itens
    
####atualiza o modo de fala com base no contexto e na mensagem recebida do useario
def atualizar_modo_de_fala(context, mensagem):
    usa_giria = detectar_giria(mensagem)
    modo_atual = context.user_data.get('modo_fala')
    novo_modo = 'girias' if usa_giria else 'formal'
    if modo_atual != novo_modo:
        context.user_data['modo_fala'] = novo_modo
        prompt = definir_prompt(novo_modo)
        context.user_data['conversation_history'] = [{"role": "system", "content": prompt}]
    return novo_modo

####prompt para a API da openrouter entender como agir
def definir_prompt(modo_fala):
    cardapio_json = json.dumps(cardapio, ensure_ascii=False, indent=2)
    if modo_fala == 'girias':
        prompt = """Você é o Clebinho, atendente da lanchonete BSI. Fale sempre usando gírias.
- Atenda de forma divertida e informal, como um atendente camarada.
- Se perguntarem sobre o cardápio, mostre os itens disponíveis.
- Para pedidos, ajude o usuário a montar o pedido com base no cardápio.
- Sobre entrega: diga que o entregador se chama Wallan e o prazo é de 30 minutos.
- Responda apenas em Português. Se o usuário falar qualquer coisa em outro idioma, diga exatamente essa mensagem, do exato jeito que está: "Sorry, I only speak portuguese!", mesmo que esse idioma seja o inglês.
"""
        for giria, dados in girias_dict.items():
            prompt += f"- {giria}: {dados['significado']} (ex: {dados['exemplo_uso']})\n"
    else:
        prompt = """Você é o Clebinho, atendente da lanchonete BSI. Seja educado, simpático e claro nas respostas.
- Se perguntarem sobre o cardápio, mostre os itens disponíveis.
- Para pedidos, ajude o usuário a montar o pedido com base no cardápio.
- Sobre entrega: diga que o entregador se chama Wallan e o prazo é de 30 minutos.
- Responda apenas em Português. Se o usuário falar qualquer coisa em outro idioma, diga exatamente essa mensagem, do exato jeito que está: "Sorry, I only speak portuguese!", mesmo que esse idioma seja o inglês.
"""

    prompt += "\n\nCardápio disponível:\n" + cardapio_json ###############ensinando a API q itens temos no cardapio
    return prompt

#########obtendo resposta da API da openrouter para as msg
async def get_openrouter_response(history):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openai/gpt-3.5-turbo",
        "messages": history
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_API_URL, headers=headers, json=data) as resp:
            response_json = await resp.json()
            return response_json['choices'][0]['message']['content']

###############comandos do bot
#start para iniciar a conversa
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Olá! Eu sou o Clebinho, o atendente da BSI Lanches. Manda o papo!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.lower()
    modo_fala = atualizar_modo_de_fala(context, user_message)
    estado_atual = context.user_data.get('estado_pedido', AGUARDANDO_PEDIDO)

    #se estiver no estado de pedido em preparo
    if estado_atual == PEDIDO_EM_PREPARO:
        if any(p in user_message for p in ["vai demorar", "quanto tempo", "já vai sair", "está pronto", "pronto", "andamento", "como está", "status", "tá pronto"]):
            respostas_possiveis = [
                "Tá saindo agora mesmo, chefia! O Wallan já tá quase saindo pra entrega!",
                "Não vai demorar não, meu parceiro! Já tá tudo quase pronto!",
                "Seu pedido tá na reta final! Só aguardar mais um pouquinho! ",
                "Já tá tudo prontinho aqui, só esperando o Wallan pegar pra levar!",
                "Relaxa que já tá quase saindo! O cozinheiro tá só dando aquela caprichada final!"
            ]
            import random #######lib para pegar uma resposta aleatoria e mostrar pro usario ansioso kk
            resposta = random.choice(respostas_possiveis)
            await update.message.reply_text(resposta)
            return
        
        if any(p in user_message for p in ["meu pedido", "pedido", "lanche", "comida"]):
            await update.message.reply_text("Seu pedido continua em preparo! Qualquer novidade eu te aviso! ")
            return
        
        #se não for sobre o pedido, ent volta ao estado normal (p/ poder fazer outro pedido)
        context.user_data['estado_pedido'] = AGUARDANDO_PEDIDO

    #se estiver esperando endereço (estado do pedido)
    if estado_atual == AGUARDANDO_ENDERECO:
        context.user_data['endereco'] = update.message.text
        await update.message.reply_text("Ótimo! Agora, qual será a forma de pagamento?\n\nOpções:\n- Dinheiro\n- Cartão de Crédito\n- Cartão de Débito\n- PIX")
        context.user_data['estado_pedido'] = AGUARDANDO_PAGAMENTO
        return
    
    #se estiver esperando forma de pagamento (estado do pedido)
    if estado_atual == AGUARDANDO_PAGAMENTO:
        formas_validas = ['dinheiro', 'cartão de crédito', 'cartão de débito', 'pix', 'credito', 'debito']
        if any(f in user_message for f in formas_validas):
            # Normaliza a forma de pagamento
            if 'dinheiro' in user_message:
                forma_pagamento = 'Dinheiro'
            elif 'débito' in user_message or 'debito' in user_message:
                forma_pagamento = 'Cartão de Débito'
            elif 'crédito' in user_message or 'credito' in user_message:
                forma_pagamento = 'Cartão de Crédito'
            elif 'pix' in user_message:
                forma_pagamento = 'PIX'
            else:
                forma_pagamento = user_message.capitalize()
            
            context.user_data['forma_pagamento'] = forma_pagamento
            await mostrar_resumo_final(update, context)
            context.user_data['estado_pedido'] = PEDIDO_EM_PREPARO
        else:
            await update.message.reply_text("Forma de pagamento inválida. Por favor, escolha entre:\n- Dinheiro\n- Cartão de Crédito\n- Cartão de Débito\n- PIX")
        return

    #comandos normais do bot
    ###chamar o cardapio
    if any(p in user_message for p in ["cardápio", "cardapio", "menu", "comida", "o que tem", "tem o que", "me mostra o cardápio", "quero ver o cardápio",
    "o que vocês têm", "o que vcs têm", "o que cês têm", "opções", "opcoes", "opçoes", "o que vendem", "quero ver as opções",
    "quais os lanches", "mostra o menu", "qual o cardápio", "mostrar cardápio", "mostrar menu", "ver cardápio", "ver menu",
    "tem lanche", "o que tem pra comer", "tem comida", "lanche", "lanchar", "refeição", "refeicoes", "refeições", "tem ai", "têm ai", "vendem", "variações", "variacoes"]):
        await update.message.reply_text(formatar_cardapio(), parse_mode="Markdown")
        return

    if any(p in user_message for p in ["entregador", "quem entrega"]):
        await update.message.reply_text("Nosso entregador se chama Wallan. Ele é super rápido e cuidadoso! 🚴‍♂️")
        return

    if "cupom" in user_message or "desconto" in user_message:
        if "fome20" in user_message:
            context.user_data['cupom_valido'] = True
            await update.message.reply_text("Cupom FOME20 aplicado! Você ganhou 20% de desconto no seu pedido.")
        else:
            await update.message.reply_text("Cupom inválido. O cupom válido é 'FOME20'.")
        return
	
	##para finalizar o pedido
    if any(p in user_message for p in ["finalizar pedido", "fechar pedido", "finalizar", "concluir pedido", "quanto fica?", "quanto deu", 
    "fechar a conta", "concluir", "encerrar pedido", "já escolhi", "quero finalizar", "quero fechar o pedido", 
    "quero concluir", "fechar compra", "terminar pedido", "já fiz meu pedido", "terminar", "finaliza aí",
    "fechou", "pode fechar", "pode concluir", "tá pronto", "está pronto", "finaliza pra mim", "quanto ficou"]):
        if 'pedido' not in context.user_data:
            await update.message.reply_text("Você ainda não fez nenhum pedido.")
            return
        
        #mostra o resumo do pedido e pede o endereço
        pedido = context.user_data['pedido']
        cupom_valido = context.user_data.get('cupom_valido', False)
        subtotal, desconto, taxa_entrega, total = calcular_total(pedido, cupom_valido)
        
        resposta = "**Resumo Parcial do Pedido:**\n\n**Itens:**\n"
        contagem_pedido = {}
        for item in pedido:
            if item['nome'] in contagem_pedido:
                contagem_pedido[item['nome']] += 1
            else:
                contagem_pedido[item['nome']] = 1
        
        for item, quantidade in contagem_pedido.items():
            preco_item = next((i['preco'] for categoria in cardapio.values() for i in categoria if i['nome'] == item), 0)
            resposta += f"- {quantidade}x {item}: R$ {preco_item:.2f} (R$ {preco_item * quantidade:.2f})\n"
        
        resposta += (
            f"\n**Subtotal:** R$ {subtotal:.2f}\n"
            f"**Desconto:** R$ {desconto:.2f}\n"
            f"**Taxa de Entrega:** R$ {taxa_entrega:.2f}\n"
            f"**Total:** R$ {total:.2f}\n\n"
            "Por favor, me informe seu endereço para entrega:"
        )
        
        await update.message.reply_text(resposta, parse_mode="Markdown")
        context.user_data['estado_pedido'] = AGUARDANDO_ENDERECO
        return

    #extração de itens do pedido
    itens_mencionados, contagem_itens = extrair_itens_do_pedido(user_message)
    if itens_mencionados:
        if 'pedido' not in context.user_data:
            context.user_data['pedido'] = []
        context.user_data['pedido'].extend(itens_mencionados)
        
        mensagem_itens = []
        for item, quantidade in contagem_itens.items():
            mensagem_itens.append(f"{quantidade}x {item}")
        
        await update.message.reply_text(
            f"{', '.join(mensagem_itens)} adicionados ao pedido!\n"
            "Digite 'finalizar' para concluir o pedido."
        )
        return

    # cnversa normal com o chatbot
    if 'conversation_history' not in context.user_data:
        prompt = definir_prompt(modo_fala)
        context.user_data['conversation_history'] = [{"role": "system", "content": prompt}]
    
    context.user_data['conversation_history'].append({"role": "user", "content": user_message})
    resposta = await get_openrouter_response(context.user_data['conversation_history'])
    context.user_data['conversation_history'].append({"role": "assistant", "content": resposta})
    await update.message.reply_text(resposta)
#funcao para mostrar o resumo final
async def mostrar_resumo_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pedido = context.user_data['pedido']
    endereco = context.user_data.get('endereco', 'Não informado')
    forma_pagamento = context.user_data.get('forma_pagamento', 'Não informada')
    cupom_valido = context.user_data.get('cupom_valido', False)
    
    subtotal, desconto, taxa_entrega, total = calcular_total(pedido, cupom_valido)
    
    resposta = " *PEDIDO CONFIRMADO!* \n\n"
    resposta += " *Itens do Pedido:*\n"
    
    contagem_pedido = {}
    for item in pedido:
        if item['nome'] in contagem_pedido:
            contagem_pedido[item['nome']] += 1
        else:
            contagem_pedido[item['nome']] = 1
    
    for item, quantidade in contagem_pedido.items():
        preco_item = next((i['preco'] for categoria in cardapio.values() for i in categoria if i['nome'] == item), 0)
        resposta += f"- {quantidade}x {item}: R$ {preco_item:.2f} (R$ {preco_item * quantidade:.2f})\n"
    
    resposta += (
        f"\n💵 *Valores:*\n"
        f"Subtotal: R$ {subtotal:.2f}\n"
        f"Desconto: R$ {desconto:.2f}\n"
        f"Taxa de Entrega: R$ {taxa_entrega:.2f}\n"
        f"*Total: R$ {total:.2f}*\n\n"
        f" *Endereço para entrega:*\n{endereco}\n\n"
        f"*Forma de pagamento:*\n{forma_pagamento}\n\n"
        " *Prazo de entrega:*\n30 minutos\n\n"
        "O entregador Wallan já está a caminho! \n"
        "Obrigado por pedir na BSI Lanches!"
    )
    
    await update.message.reply_text(resposta, parse_mode="Markdown")
    
    # Limpa os dados do pedido para um novo
    context.user_data.pop('pedido', None)
    context.user_data.pop('cupom_valido', None)
    context.user_data.pop('endereco', None)
    context.user_data.pop('forma_pagamento', None)
    context.user_data['estado_pedido'] = AGUARDANDO_PEDIDO

# startando o botzin sabido
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("TUDO CERTO, SÓ METER BALAAAA")
    app.run_polling()

if __name__ == "__main__":
    main()
