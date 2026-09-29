# Execução Front-End do Projeto LabTech

[![UDF Aluno](https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRDXbvV66Z7fLPFjwMmJxAL3RaqdLX165K8WA&s)](https://www.udf.edu.br/aluno/)

Este documento tem como objetivo orientar os novos integrantes do LabTech na execução do projeto Front-End, detalhando as instalações necessárias e soluções para erros comuns.

---

## Sumário

- [Objetivo](#objetivo)
- [Ferramentas](#ferramentas)
- [Guia de Instalação de Ferramentas](#guia-de-instalação-de-ferramentas)
  - [GitHub](#github)
  - [Git](#git)
  - [Visual Studio Code](#vscode)
  - [Node.js e NVM](#nodejs-e-nvm)
- [Execução do Projeto](#execução-do-projeto)
- [Manual de Solução de Erros](#manual-de-solução-de-erros)
  - [Erro: Execução de scripts desabilitada](#erro-execução-de-scripts-desabilitada)
  - [Problemas com Yarn](#problemas-com-yarn)
- [Referências](#referências)
- [Créditos](#créditos)

---

## Objetivo

Orientar os novos integrantes do LabTech na execução do projeto Front-End, com um manual de instalações necessárias e instruções para solucionar erros frequentes.

---

## Ferramentas

Utilize as ferramentas abaixo para desenvolver o projeto:

[![GitHub](https://img.shields.io/badge/GitHub-000?style=for-the-badge&logo=github&logoColor=30A3DC)](https://docs.github.com/)  
[![VsCode](https://img.shields.io/badge/vscode-000?style=for-the-badge&logo=vscode&logoColor=black)](https://code.visualstudio.com/download)  
[![Git](https://img.shields.io/badge/Git-000?style=for-the-badge&logo=git&logoColor=E94D5F)](https://git-scm.com/downloads/win)  
[![Node.js](https://img.shields.io/badge/Node.js-000?style=for-the-badge&logo=node.js&logoColor=green)](https://nodejs.org/en/download/package-manager)  
[![Yarn](https://img.shields.io/badge/yarn-000?style=for-the-badge&logo=yarn&logoColor=blue)](https://classic.yarnpkg.com/lang/en/docs/install/#windows-stable)  
[![NVM](https://img.shields.io/badge/nvm-000?style=for-the-badge&logo=nvm&logoColor=green)](https://github.com/coreybutler/nvm-windows/releases)

---

## Guia de Instalação de Ferramentas

### GitHub

GitHub é uma plataforma de desenvolvimento colaborativo para armazenamento, compartilhamento e gerenciamento de projetos.

- Acesse: [github.com](https://github.com)
- Crie sua conta: [Cadastre-se no GitHub](https://github.com/signup?ref_cta=Sign+up&ref_loc=header+logged+out&ref_page=%2F%3Cuser-name%3E%2F%3Crepo-name%3E&source=header-repo&source_repo=coreybutler%2Fnvm-windows)

### Git

Git é um sistema de controle de versão que permite gerenciar seu código.

- Baixe: [Site oficial do Git](https://git-scm.com/downloads)

### Visual Studio Code (VsCode)

O VSCode é uma IDE robusta para desenvolvimento em diversas linguagens.

- Baixe: [Site oficial do VS Code](https://code.visualstudio.com/)

### Node.js e NVM (Node Version Manager)

**Node.js:** Plataforma JavaScript para execução de código no servidor.  
**Atenção:** Não é necessário instalar o Node.js diretamente, pois o NVM gerencia as versões instaladas.

**NVM:** Gerenciador de versões do Node.js que facilita o controle das instalações.

- **Windows:** Baixe o instalador [nvm-setup.exe](https://github.com/coreybutler/nvm-windows/releases)
- **Linux:** Siga as instruções em [nvm linux](https://github.com/nvm-sh/nvm)

Após a instalação, verifique com:

```bash
nvm --version
```

> **Importante:** O frontend usa Node.js v26.10.0, definida em `reservas/.nvmrc`.

Para instalar uma versão específica do Node.js:

```bash
nvm install <versão>
```

Para alternar de versão:

```bash
nvm use <versão>
```

---

## Execução do Projeto

Após instalar as ferramentas, siga os passos abaixo:

1. **Clone o repositório:**  
   Abra o GitBash e execute:

   ```bash
   git clone [link_do_repositorio]
   ```

   > **Importante:** O link do repositório pode ser encontrado em GitHub > LabTech > interfaces_usuario > (<>code)> copiar link do repositório HTTPS.

2. **Ative o Yarn 1.22.22 e instale as dependências:**
   No terminal, execute:

   ```bash
   nvm use
   npm install --global yarn@1.22.22
   cd reservas
   yarn install --frozen-lockfile
   ```

   Verifique a instalação do Yarn:

   ```bash
   yarn --version
   ```

3. **Inicie o React Router Framework em modo SPA:**

   ```bash
   yarn dev
   ```

   Abra [http://localhost:3000](http://localhost:3000). A aplicação é uma SPA; não há servidor SSR em runtime.

---

## Manual de Solução de Erros

### Erro: Execução de Scripts Desabilitada

> **Cuidado:**  
> Erro: "Execução de scripts foi desabilitada neste sistema". Esse erro ocorre devido à política de segurança do PowerShell, que por padrão bloqueia a execução de scripts não assinados.

**Solução:**

1. Abra o PowerShell como administrador.
2. Verifique a política atual:

   ```powershell
   Get-ExecutionPolicy
   ```

3. Altere a política para permitir scripts remotos assinados:

   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned
   ```

4. Após alterar, execute novamente o comando `yarn start` no terminal.

### Problemas com Yarn

> **Atenção:**  
> Caso ocorra erro durante a instalação de dependências (possivelmente devido a problemas de conexão com a internet), siga os passos abaixo:

1. Limpe o cache do Yarn:

   ```bash
   yarn cache clean
   ```

2. Reinstale as dependências:

   ```bash
   yarn install
   ```

3. Inicie o projeto:

   ```bash
   yarn start
   ```

Caso o problema persista, verifique sua conexão de internet.

---

## Referências

- [Documentação do PowerShell - Execução de Políticas](https://learn.microsoft.com/pt-pt/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-7.4)

---

## Créditos

<div align="center">
  Criado por DW Corp LTDA
</div>
