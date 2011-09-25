#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""M�dulo de conex�o � redes baseadas nas RFCs 1459 / 2812

M�dulo: nucleo
Autor: Vindemiatrix Almuredin
Blog: tocadoelfo.blogspot.com

Descri��o: M�dulo com classes b�sicas para se conectar � redes que
implementam as RFCs 1459 e 2812.
A implementa��o ocorre ao n�vel sint�tico dos protocos sem haver,
no entanto, implementa��o das sintaxes individuais de cada comando.

BNF do Protocolo (RFC 2812)

message    =  [ ":" prefix ESPA�O ] cmd [ params ] crlf
prefix     =  servidor / ( nick [ [ "!" user ] "@" host ] )
cmd        =  1*letra / 3digito
params     =  *14( ESPA�O meio ) [ ESPA�O ":" trailing ]
           =/ 14( ESPA�O meio ) [ ESPA�O [ ":" ] trailing ]
nospcrlfcl =  %x01-09 / %x0B-0C / %x0E-1F / %x21-39 / %x3B-FF
                ; qualquer octeto, exceto NUL, CR, LF, " " and ":"
meio       =  nospcrlfcl *( ":" / nospcrlfcl )
trailing   =  *( ":" / " " / nospcrlfcl )
ESPA�O     =  %x20        ; Caracter de espa�o
crlf       =  %x0D %x0A   ; "carriage return" "linefeed"
"""

import socket, time, string, logging
from threading import Thread

#irclog = logging.getLogger('irc')
#irclog.setLevel(logging.DEBUG)

class ClienteBase(Thread):
    """
    Classe que implementa o modelo sint�tico do protocolo, definido pelas RFCs
    1459 e 2812, para modelo de comunica��o baseado na sintaxe do protocolo IRC.
    A implementa��o ocorre somente � n�vel do marcador "message" da BNF da RFC
    2812, retrocompat�vel com a RFC 1459.
    """
    def __init__(self, fim='\n'):
        """
        Define a inicializa��o da inst�ncia, permitindo tamb�m a defini��o do
        marcador de fim da mensagem.
        """
        Thread.__init__(self)
        self.fim = fim
        self.__cmds = {}
        self.__saida_padrao = None
        self.__erro = None
        #self.log = logging.getLogger('irc.'+self.getName())
        self.conectado = False

    def __bufferiza(self, dados):
        """
        Buferiza a entrada de dados, garantindo que a mensagem chegue sempre da
        mesma forma, evitando problemas como mensagens partidas ou v�rias
        mensagens em um �nico recebimento.
        """
        '''
        self.log.info('>>> def __buferiza(self, dados)')
        self.log.debug('dados: "%s"' % (dados,))
        if len(self.__pbuffer) > 0:
            self.log.debug('__pbuffer: "%s"' % (self.__pbuffer,))
        '''
        self.__pbuffer += dados
        while self.fim in self.__pbuffer:
            x =  self.__pbuffer[:self.__pbuffer.find(self.fim)]
            self.__processa_protocolo(x)
            self.__pbuffer = self.__pbuffer[self.__pbuffer.find(self.fim)+len(self.fim):]

    def __processa_protocolo(self, msg):
        """
        Respons�vel por receber o comando puro e quebrar sob a forma de um
        dicion�rio, cuja sintaxe � a seguinte:
        {'prefix': {'nick':'nickname', 'user':'usermask', 'host':'hostname'},
        'cmd':'command', 'params': ['param', 'param', 'End of Params']}
        """
        '''
        self.log.info('>>> def __processa_protocolo(self, msg)')
        self.log.debug('msg: "%s"' % (msg,))
        '''
        retorno = {}
        mensagem = msg[:]

        #slice do Prefix (:nick!user@host)
        prefix = {}
        if mensagem[0] == ':': 
            prefixmsg = mensagem[1:mensagem.find(' ')]
            mensagem = mensagem[mensagem.find(' ')+1:]
            #slice as op��es de Prefix: servidor / ( nick [ [ "!" user ] "@" host ] )
            if prefixmsg.find('@') > -1:
                usermsg = prefixmsg[:prefixmsg.find('@')]
                prefix['host'] = prefixmsg[prefixmsg.find('@')+1:]
                if usermsg.find('!') > -1:
                    prefix['nick'] = usermsg[:usermsg.find('!')]
                    prefix['user'] = usermsg[usermsg.find('!')+1:]
                else:
                    prefix['nick'] = usermsg
            else:
                prefix['host'] = prefixmsg       
        retorno['prefix'] = prefix

        #slice do Comando
        if mensagem.find(' ') > -1:
            retorno['cmd'] = mensagem[:mensagem.find(' ')]
            mensagem = mensagem[mensagem.find(' ')+1:]
        else:
            retorno['cmd'] = mensagem
            mensagem = ''

        #slice dos parametros
        params = []
        while len(mensagem) > 0:
            if mensagem[0] == ':':
                params.append(mensagem[1:])
                mensagem = ''
            elif mensagem.find(' ') > 0:
                params.append(mensagem[:mensagem.find(' ')])
                mensagem = mensagem[mensagem.find(' ')+1:]
            else:
                params.append(mensagem)
                mensagem = ''
        retorno['params'] = params
        
        retorno['puro'] = msg

        self.__executa_parser(retorno)

    def __executa_parser(self, mensagem):
        """
        Comando respons�vel por buscar um parser para um comando espec�fico.
        Obs.: Quando n�o h� parser dispon�vel para processar o comando, um
        parser de sa�da padr�o pode ser informado para tratar somente os casos
        citados. A fun��o retorna ao encontrar o primeiro parser, sem executar
        o parser de sa�da padr�o.
        """
        '''
        self.log.info('>>> def __executa_parser(self, mensagem)')
        self.log.debug('mensagem[prefix]: "%s"' % mensagem['prefix'])
        self.log.debug('mensagem[cmd]: "%s"' % mensagem['cmd'])
        self.log.debug('mensagem[params]: "%s"' % mensagem['params'])
        '''
        if self.__cmds.has_key(string.upper(mensagem['cmd'])):
            self.__cmds[string.upper(mensagem['cmd'])](mensagem)
        elif self.__saida_padrao <> None:
            self.__saida_padrao(mensagem)
        else:
            pass
        
    def insere_parser(self, comando, interpretador):
        """
        Adiciona um parser para o comando informado.
        Substitui o parser caso seja informado um comando j� existente
        """
        #self.log.info('def insere_parser(self, comando, interpretador)')
        #self.log.debug('comando: "%s"; interpretador: "%s"' % (comando, interpretador.__name__))
        
        self.__cmds[string.upper(comando)] = interpretador

    def remove_parser(self, comando):
        """
        Remove o parser para o comando informado.
        Lan�a uma exce��o caso o parser n�o exista.
        """
        #self.log.info('def remove_parser(self, comando)')
        #self.log.debug('comando: "%s";' % (comando,))
        
        if self__cmds.has_key(comando):
            del self.__cmds[string.upper(comando)]
        else:
            raise

    def insere_saida_padrao(self, comando):
        """
        Adiciona um parser de sa�da padr�o para interpretar comandos que n�o
        foram adicionados usando insere_parser.
        Todo comando n�o processado deve passar por este parser, quando este �
        setado.
        """
        #self.log.info('>>> def insere_saida_padrao(self, comando)')
        #self.log.debug('comando: "%s";' % (comando.__name__,))

        self.__saida_padrao = comando

    def remove_saida_padrao(self):
        """
        Remove o parser de sa�da padr�o.
        Os comandos n�o processados passam a ser ignorados a partir da chamada
        deste m�todo.
        """
        #self.log.info('>>> def remove_saida_padrao(self)')
        
        self.__saida_padrao = None
        
    def insere_controle_erro(self, comando):
        """
        """
        #self.log.debug('>>> def insere_controle_erro(self, comando)')
        #self.log.debug('comando: "%s";' % (comando,))

        self.__erro = comando

    def conecta(self, servidor, porta=6667, timeout=200):
        """
        Obs.: V�lido somente para conex�es como Cliente.
        Inicia a conex�o ao servidor indicado, com a possibilidade de setar uma
        porta alternativa.
        Inicia as vari�veis utilizadas pela inst�ncia durante a vida da conex�o.
        """
        try:
            #self.log.warning('Conectando ao servidor %s na porta %s...' % (servidor, porta))
            
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(timeout)
            self.sock.connect((servidor, porta))
            self.setName('%s:%d' % (servidor, porta))
            self.conectado = True
            self.__pbuffer = ''

            #self.log.warning('Conectado!')
            #self.log.debug('Alterando o nome do log de <%s> para <%s>' % (self.log.name, self.getName()))
            #self.log.name = self.getName()
            
            return True
        except Exception, e:
            self.__tratar_erro(e)
            return False

    def desconecta(self):
        """
        Obs.: Preferencialmente deve ser utilizado ap�s enviar QUIT no caso do
        cliente ou de receber QUIT no caso de servidor.
        Inicia as rotinas de desconex�o do socket e termina o looping de recebi-
        mento de dados.
        Fecha o socket e libera o descritor.
        """
        self.sock.close()
        self.conectado = False

    def aceita_conexao(self, cliente):
        """
        Obs.: V�lido somente para conex�es como Servidor, visto que o socket que
        est� em modo listen fica respons�vel de chamar esta fun��o.
        Sintaxe de cliente: (socket, info do cliente)
        Sintaxe de info do cliente: (endere�o do host, porta)
        """
        self.sock = cliente[0]
        self.setName('%s:%d' % cliente[1])
        self.conectado = True
        self.__pbuffer = ''

    def __tratar_erro(self, e):
        if self.__erro != None:
            #self.log.error('Erro "%s" tratado por "%s".' % (e, self.__erro.__name__))
            self.__erro(e)
        else:
            #self.log.exception('Erro n�o tratado em "%s".' % (e,))
            raise e
    
    def envia(self, mensagem):
        """
        Faz o envio da informa��o em mensagem, imprimindo uma exce��o em caso de
        erro.
        """
        #self.log.info('>>> def envia(self, mensagem)')
        #self.log.info('mensagem: "%s"' % (mensagem,))
        
        try:
            self.sock.send(mensagem + self.fim)
            return True
        except Exception, e:
            self.__tratar_erro(e)
            return False
                
    def run(self):
        """
        Linha de execu��o da thread, respons�vel por manter a conexao aberta e
        recebendo as mensagens da outra ponta.
        """
        while self.conectado:
            try:
                dados = self.sock.recv(1024)
                self.__bufferiza(dados)
            except Exception, e:
                self.__tratar_erro(e)
                break
            #try:
            #    tipo = chardet.detect(dados)['encoding']
            #    if tipo.lower() != 'utf-8':
            #        dados = dados.decode(tipo).encode('utf-8')
            #except Exception, e: pass
            time.sleep(1)

class ServidorBase(Thread):
    """
    Classe que implementa um servidor b�sico, usando como conex�o ponta-a-ponta
    uma inst�ncia de ClienteBase para cada nova conex�o aceita.
    Obs.: Por medidas ergon�micas, mensagens que chegarem ao cliente e que
    necessitarem ser repassados para os outros clientes dever�o repassar a
    mensagem para o servidor para que este providencie o envio para todos os
    clientes conectados e ainda em execu��o.
    """
    def __init__(self, fim='\r\n'):
        raise NotImplementedError('Classe em desenvolvimento')
        #Thread.__init__(self)
        #self.lista_clientes = []
