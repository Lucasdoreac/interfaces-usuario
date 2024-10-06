<h1>
    <a href="https://www.udf.edu.br/aluno/">
     <img align="center" width="40px" src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRDXbvV66Z7fLPFjwMmJxAL3RaqdLX165K8WA&s"></a>
    <span>Execução Front-End do projeto LabTech</span>
</h1>

## Objetivo
Orientar novos integrantes do LabTech na execução do projeto Front-End, incluindo manual de instalações necessárias e solução de erros frequêntes.
## Ferramentas
[![GitHub](https://img.shields.io/badge/GitHub-000?style=for-the-badge&logo=github&logoColor=30A3DC)](https://docs.github.com/)
[![VsCode](https://img.shields.io/badge/vscode-000?style=for-the-badge&logo=vscode&logoColor=black)](https://code.visualstudio.com/download)
[![Git](https://img.shields.io/badge/Git-000?style=for-the-badge&logo=git&logoColor=E94D5F)](https://git-scm.com/downloads/win) 
[![Node.js](https://img.shields.io/badge/Node.js-000?style=for-the-badge&logo=node.js&logoColor=green)]([https://git-scm.com/doc](https://nodejs.org/en/download/package-manager)) 
[![Yarn](https://img.shields.io/badge/yarn-000?style=for-the-badge&logo=yarn&logoColor=blue)](https://classic.yarnpkg.com/lang/en/docs/install/#windows-stable) 

## Guia de Instalação de Ferramentas
### GitHub
GitHub é uma plataforma para desenvolvimento colaborativo que permite armazenar, compartilhar e gerenciar projetos de software.
> Acesse [github.com](https://github.com)
> 
> [Crie sua conta](https://github.com/signup?ref_cta=Sign+up&ref_loc=header+logged+out&ref_page=%2F%3Cuser-name%3E%2F%3Crepo-name%3E&source=header-repo&source_repo=coreybutler%2Fnvm-windows) (caso ainda não tenha)

### Git
Git é uma ferramenta de controle de versão que permite gerenciar seu código.
> Acesse o [site oficial do Git](https://git-scm.com/downloads)

    
### VsCode
Visual Studio Code (VS Code) é uma IDE para desenvolvimento em várias linguagens.
> Acesse o [site oficial do VS Code](https://code.visualstudio.com/) e baixe a versão correspondente ao seu sistema operacional.

### Node.js
Node.js é uma plataforma JavaScript que permite executar código JavaScript no lado do servidor.
> Acesse o [site oficial do Node.js](https://nodejs.org/en/download/package-manager/current) e baixe a versão v20.

>[!IMPORTANT] 
> Verifique se o Node.js e o npm (Node Package Manager) estão instalados corretamente, executando os seguintes comandos em terminal:

    node --version
    npm --version

### Yarn
Yarn é um gerenciador de pacotes que facilita o gerenciamento de dependências em projetos.
> Para instalação, execute o seguinte comando no terminal:

    npm install --global yarn
>[!IMPORTANT] 
>Verifique se o yarn foi instalado corretamente, executando o seguinte comando em terminal:

    yarn --version

## Execução do projeto

Após a instalação das ferramentas, vamos prosseguir com a execução do projeto.

Execute o GitBash no seu computador, após a execução digite:

    $ git clone [link_do_repositorio]

>[!IMPORTANT]
>O link do repositório você pode encontrar no GitHub>LabTech>interfaces_usuario>(<>code)>copiar link do repositorio HTTPS.

Se o comando foir executado com sucesso você deve visualizar esse bash:

    Cloning into 'interfaces-usuario'...
    remote: Enumerating objects: 337, done.
    remote: Counting objects: 100% (337/337), done.
    remote: Compressing objects: 100% (222/222), done.
    remote: Total 337 (delta 126), reused 301 (delta 104), pack-reused 0 (from 0)
    Receiving objects: 100% (337/337), 732.20 KiB | 5.27 MiB/s, done.
    Resolving deltas: 100% (126/126), done.

Agora execute no terminal o comando:

    yarn start

Isso abrirá uma janela no browser com o endereço local: [http://localhost:3000](http://localhost:3000) 

###

## Manual de solução de erros
### 1. Execução de scripts foi desabilitada neste sistema
>[!CAUTION]
>Ocorreu um erro; Execução de scripts foi desabilitada neste sistema

Isto é uma política de segurança do Powershell para evitar que scripts maliciosos sejam executados indevidamente no seu sistema. Por isso, todos os scripts que não forem assinados terão sua execução bloqueada. Ou seja, a política de execução está como Restricted (que é o padrão).
>Solução:
>
>Acesse seu Powershell como administrador e execute os seguintes comandos:

    Get-ExecutionPolicy
    RemoteSigned

## Contribua com o READ.ME
Contribua com os erros e soluções encontrados para assim facilitar a jornada dos novos integrantes!


### Membros da comunidade que já contribuiram:
<a href="">
  <img src=""/>
</a>

##
<div align="center">Criado por DW Corp LTDA</a>.</div>
