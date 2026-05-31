# Cofre online

O Cofre e um app Flask com SQLite. Para ficar acessivel sempre, o ponto mais importante e manter o arquivo `cofre.db` em armazenamento persistente.

## Opcao recomendada: servidor/VPS pequeno

1. Envie a pasta do projeto para o servidor.
2. Instale dependencias:

```bash
pip install -r requirements.txt
```

3. Defina onde o banco vai ficar:

```bash
export COFRE_DB_PATH=/var/lib/cofre/cofre.db
export COFRE_COOKIE_SECURE=1
```

4. Rode:

```bash
python server.py
```

Depois coloque um proxy HTTPS na frente, como Caddy, Nginx Proxy Manager ou Cloudflare Tunnel.

## Opcao simples: Cloudflare Tunnel no seu PC

Bom quando voce quer manter o banco no seu computador e acessar de fora. O PC precisa ficar ligado.

1. Rode o app:

```powershell
python server.py
```

2. Crie um tunnel apontando para:

```text
http://localhost:5000
```

3. Publique em um dominio, por exemplo:

```text
cofre.seudominio.com
```

## Opcao privada: Tailscale

Bom para acessar apenas dos seus aparelhos. Instale Tailscale no PC e nos dispositivos, rode `python server.py` e acesse pelo IP/nome do aparelho na tailnet. Para abrir publicamente, use Tailscale Funnel.

## Hospedagem tipo Render/Railway

Use o comando de start:

```bash
python server.py
```

Configure:

```text
COFRE_DB_PATH=/data/cofre.db
COFRE_COOKIE_SECURE=1
```

Anexe um disco/volume persistente em `/data`. Sem volume persistente, o SQLite pode ser perdido quando o servico reiniciar ou redeployar.

## Railway passo a passo

1. Suba este projeto para um repositorio GitHub.
2. No Railway, crie um projeto novo a partir do repositorio.
3. O arquivo `railway.json` ja define o start command:

```bash
python server.py
```

4. Adicione um Volume ao servico.
5. Monte o Volume em:

```text
/data
```

6. Configure as variaveis:

```text
COFRE_DB_PATH=/data/cofre.db
COFRE_COOKIE_SECURE=1
```

7. Gere um dominio publico no servico.
8. Acesse o dominio e crie sua senha no primeiro acesso.

Para migrar os dados locais, envie o arquivo `cofre.db` atual para o volume como `/data/cofre.db`.
