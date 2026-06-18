# RAGFlow Docker 本地源码部署说明

本文档说明如何用当前本地源码构建并启动 RAGFlow Docker 版本，以及如何通过 `docker/.env` 配置默认模型调用地址和 API Key。

适用场景：

- 需要运行当前仓库源码，而不是官方远端镜像。
- 需要让新注册用户和已有用户自动带上默认模型配置。
- 需要使用 OpenAI-compatible 接口作为默认模型供应商。
- 当前定制 UI 中，`Model providers` 页面只保留 `Set default models`，不再显示右侧 `Available models` 和下方 `Added models`。

## 1. 配置链路先看懂

本项目 Docker 启动时的模型配置链路是：

```text
docker/.env
  -> docker-compose.yml 的 env_file: .env
  -> 容器启动时 entrypoint.sh 渲染 service_conf.yaml.template
  -> /ragflow/conf/service_conf.yaml
  -> 后端读取 user_default_llm
  -> 调用 base_url 的 /v1/models
  -> 自动导入模型并设置租户默认模型
```

所以模型 API Key 和 Base URL 应该写在 `docker/.env`，不要直接把密钥写死到 `docker/service_conf.yaml.template` 里。

`docker/service_conf.yaml.template` 中对应配置如下：

```yaml
user_default_llm:
  name: 'Matrix'
  factory: 'OpenAI-API-Compatible'
  api_key: '${USER_DEFAULT_LLM_API_KEY:-}'
  base_url: '${USER_DEFAULT_LLM_BASE_URL:-}'
```

含义：

- `name`: RAGFlow 里显示的模型实例名称，当前为 `Matrix`。
- `factory`: 模型供应商类型，当前固定使用 `OpenAI-API-Compatible`。
- `api_key`: 从 `docker/.env` 的 `USER_DEFAULT_LLM_API_KEY` 读取。
- `base_url`: 从 `docker/.env` 的 `USER_DEFAULT_LLM_BASE_URL` 读取。

## 2. 配置 docker/.env

编辑：

```powershell
cd D:\Projects\Work\ragflow\docker
notepad .env
```

重点配置下面几项：

```dotenv
# 文档解析引擎，当前使用 Elasticsearch
DOC_ENGINE=${DOC_ENGINE:-elasticsearch}

# 当前运行 CPU 版 RAGFlow
DEVICE=${DEVICE:-cpu}

# Compose 会根据 DOC_ENGINE 和 DEVICE 自动启用 elasticsearch,cpu profile
COMPOSE_PROFILES=${DOC_ENGINE},${DEVICE}

# Web 访问端口
SVR_WEB_HTTP_PORT=80
SVR_WEB_HTTPS_PORT=443

# 后端 API 端口
SVR_HTTP_PORT=9380
ADMIN_SVR_HTTP_PORT=9381
SVR_MCP_PORT=9382
GO_ADMIN_PORT=9383
GO_HTTP_PORT=9384

# 默认模型调用配置
USER_DEFAULT_LLM_API_KEY=<填你的模型服务 API Key>
USER_DEFAULT_LLM_BASE_URL=<填你的 OpenAI-compatible Base URL>

# 当前本地源码构建出来的镜像名
RAGFLOW_IMAGE=ragflow:local-source
```

### USER_DEFAULT_LLM_BASE_URL 怎么填

推荐填写到 OpenAI-compatible 的 `/v1` 根路径，例如：

```dotenv
USER_DEFAULT_LLM_BASE_URL=https://example.com/v1
```

后端会用这个地址推导模型列表接口：

```text
https://example.com/v1/models
```

接口要求：

- 支持 OpenAI-compatible 协议。
- 支持 `GET /v1/models`。
- 使用 Bearer Token 鉴权，也就是请求头：

```http
Authorization: Bearer <USER_DEFAULT_LLM_API_KEY>
```

可以先在宿主机用 PowerShell 测一下模型服务是否能访问：

```powershell
$key = "<填你的模型服务 API Key>"
$baseUrl = "https://example.com/v1"
Invoke-RestMethod `
  -Uri "$baseUrl/models" `
  -Headers @{ Authorization = "Bearer $key" }
```

如果这里都访问失败，RAGFlow 容器里也无法自动导入模型。

## 3. 构建本地源码镜像

只有改了源码、前端 UI、后端逻辑、Dockerfile 时才需要重新构建镜像。单纯改 `docker/.env` 的 key 或 url 不需要重新 build。

从仓库根目录执行：

```powershell
cd D:\Projects\Work\ragflow

docker buildx build `
  --load `
  --progress=plain `
  --provenance=false `
  -t ragflow:local-source `
  --build-arg NEED_MIRROR=1 `
  --build-arg RAGFLOW_VERSION=local-source-20260618-default-only `
  .
```

参数说明：

- `-t ragflow:local-source`: 构建出的本地镜像名，必须和 `docker/.env` 的 `RAGFLOW_IMAGE=ragflow:local-source` 一致。
- `--build-arg NEED_MIRROR=1`: 使用国内镜像源构建，网络更稳定。
- `--build-arg RAGFLOW_VERSION=...`: 写入镜像内 `/ragflow/VERSION`，方便确认当前跑的是本地源码镜像。
- `--load`: 把 buildx 构建结果加载到本机 Docker image 列表中，后续 `docker compose` 才能直接使用。
- `--provenance=false`: 不生成 buildx attestation/provenance manifest，避免 Docker Desktop 在 `--load` 导入本地镜像时因为 manifest list unpack 触发 `parent snapshot ... does not exist`。

构建完成后确认镜像存在：

```powershell
docker images ragflow:local-source
```

## 4. 启动 Docker Compose

进入 Docker 目录：

```powershell
cd D:\Projects\Work\ragflow\docker
```

首次启动或完整启动：

```powershell
docker compose -f docker-compose.yml --env-file .env up -d
```

当前 `.env` 中：

```dotenv
DOC_ENGINE=${DOC_ENGINE:-elasticsearch}
DEVICE=${DEVICE:-cpu}
COMPOSE_PROFILES=${DOC_ENGINE},${DEVICE}
```

所以默认会启动：

- `ragflow-cpu`
- `mysql`
- `es01`
- `minio`
- `redis`

访问地址：

```text
http://127.0.0.1/
```

如果宿主机 80 端口已被占用，把 `docker/.env` 中的 `SVR_WEB_HTTP_PORT` 改成其他端口，例如：

```dotenv
SVR_WEB_HTTP_PORT=8080
```

然后重建容器，访问：

```text
http://127.0.0.1:8080/
```

## 5. 修改 .env 后怎么让配置生效

只修改 `docker/.env`，例如修改：

- `USER_DEFAULT_LLM_API_KEY`
- `USER_DEFAULT_LLM_BASE_URL`
- `SVR_WEB_HTTP_PORT`
- `RAGFLOW_IMAGE`

通常不需要重新 build 镜像，但需要重建容器，让 Compose 重新注入环境变量，并让 `entrypoint.sh` 重新生成 `/ragflow/conf/service_conf.yaml`。

执行：

```powershell
cd D:\Projects\Work\ragflow\docker

docker compose -f docker-compose.yml --env-file .env up -d --force-recreate
```

如果只想重建 RAGFlow 主服务，不动 MySQL、Elasticsearch、MinIO、Redis：

```powershell
docker compose -f docker-compose.yml --env-file .env up -d --no-deps --force-recreate ragflow-cpu
```

这次调试默认模型配置时，用的就是这种方式。

## 6. 验证当前跑的是本地源码镜像

查看容器状态：

```powershell
cd D:\Projects\Work\ragflow\docker
docker compose -f docker-compose.yml --env-file .env ps
```

确认 `ragflow-cpu` 使用的是：

```text
IMAGE: ragflow:local-source
```

查看容器内版本号：

```powershell
docker compose -f docker-compose.yml --env-file .env exec -T ragflow-cpu cat /ragflow/VERSION
```

如果输出类似下面内容，说明当前跑的是本地构建镜像：

```text
local-source-20260618-default-only
```

## 7. 验证模型配置是否进入容器

容器启动时会把 `service_conf.yaml.template` 渲染成 `/ragflow/conf/service_conf.yaml`。

可以用下面命令检查，但不要把真实 key 打印出来：

```powershell
docker compose -f docker-compose.yml --env-file .env exec -T ragflow-cpu bash -lc "grep -A4 '^user_default_llm:' /ragflow/conf/service_conf.yaml | sed -E 's/(api_key: ).*/\1<hidden>/'"
```

期望能看到类似：

```yaml
user_default_llm:
  name: 'Matrix'
  factory: 'OpenAI-API-Compatible'
  api_key: <hidden>
  base_url: 'https://example.com/v1'
```

如果 `api_key` 或 `base_url` 是空的，检查：

- `docker/.env` 是否写了 `USER_DEFAULT_LLM_API_KEY` 和 `USER_DEFAULT_LLM_BASE_URL`。
- 是否执行了 `docker compose ... --force-recreate`。
- 是否启动的是当前这个 `docker/docker-compose.yml`。
- `docker-compose.yml` 中 `ragflow-cpu` 是否仍然有 `env_file: .env`。

## 8. 默认模型自动导入逻辑

配置了 `USER_DEFAULT_LLM_API_KEY` 和 `USER_DEFAULT_LLM_BASE_URL` 后，后端会：

1. 读取 `user_default_llm` 配置。
2. 请求模型服务的 `/v1/models`。
3. 创建或更新租户模型供应商 `OpenAI-API-Compatible`。
4. 创建或更新模型实例 `Matrix`。
5. 根据 `/v1/models` 返回的模型名导入模型。
6. 给租户设置默认模型。

模型类型会按模型名做推断：

| 模型名包含 | 推断类型 |
| --- | --- |
| `embed`、`embedding`、`bge` | Embedding |
| `rerank`、`reranker` | Rerank |
| `asr`、`stt`、`transcribe`、`whisper` | ASR |
| `tts`、`text-to-speech` | TTS |
| `vision`、`vl`、`qwen-vl`、`glm-4v`、`gpt-4o` 等 | VLM |
| 其他普通模型名 | LLM |

注意：

- 如果模型服务的 `/v1/models` 不返回 embedding 模型，`Embedding` 默认模型下拉框可能为空。
- 如果模型名不包含可识别关键词，系统可能只把它当成 LLM。
- 已有用户会在服务初始化时尝试补齐默认模型。
- 新注册用户会在注册流程里自动尝试补齐默认模型。
- 如果某个用户已经手动设置过默认模型，系统不会强行覆盖用户自己的选择。

## 9. 当前 UI 定制说明

当前源码里的 `Model providers` 页面已经做了简化：

```text
/user-setting/model
```

页面只保留：

```text
Set default models
```

不再显示：

- 右侧 `Available models`
- 下方 `Added models`
- 手动添加供应商入口

也就是说，模型来源主要依赖 Docker `.env` 中的默认模型配置自动注入。部署时重点保证 `USER_DEFAULT_LLM_API_KEY` 和 `USER_DEFAULT_LLM_BASE_URL` 正确。

## 10. 常用运维命令

查看服务：

```powershell
docker compose -f docker-compose.yml --env-file .env ps
```

查看 RAGFlow 主服务日志：

```powershell
docker compose -f docker-compose.yml --env-file .env logs -f ragflow-cpu
```

重启 RAGFlow 主服务：

```powershell
docker compose -f docker-compose.yml --env-file .env restart ragflow-cpu
```

重建 RAGFlow 主服务容器：

```powershell
docker compose -f docker-compose.yml --env-file .env up -d --no-deps --force-recreate ragflow-cpu
```

停止服务但保留数据卷：

```powershell
docker compose -f docker-compose.yml --env-file .env down
```

不要随便加 `-v`。`down -v` 会删除数据卷，MySQL、Elasticsearch、MinIO 等数据可能会丢失。

## 11. 常见问题

### 11.1 页面还是没有默认模型

按顺序检查：

1. 宿主机能否访问模型服务：

   ```powershell
   $key = "<填你的模型服务 API Key>"
   $baseUrl = "https://example.com/v1"
   Invoke-RestMethod -Uri "$baseUrl/models" -Headers @{ Authorization = "Bearer $key" }
   ```

2. 容器内配置是否生成：

   ```powershell
   docker compose -f docker-compose.yml --env-file .env exec -T ragflow-cpu bash -lc "grep -A4 '^user_default_llm:' /ragflow/conf/service_conf.yaml | sed -E 's/(api_key: ).*/\1<hidden>/'"
   ```

3. 是否重建了容器：

   ```powershell
   docker compose -f docker-compose.yml --env-file .env up -d --no-deps --force-recreate ragflow-cpu
   ```

4. 是否正在跑本地源码镜像：

   ```powershell
   docker compose -f docker-compose.yml --env-file .env exec -T ragflow-cpu cat /ragflow/VERSION
   ```

### 11.2 改了源码但页面没变化

前端代码已经被打进镜像里。改源码后需要：

```powershell
cd D:\Projects\Work\ragflow

docker buildx build `
  --load `
  --progress=plain `
  --provenance=false `
  -t ragflow:local-source `
  --build-arg NEED_MIRROR=1 `
  --build-arg RAGFLOW_VERSION=local-source-<日期或说明> `
  .

cd D:\Projects\Work\ragflow\docker
docker compose -f docker-compose.yml --env-file .env up -d --no-deps --force-recreate ragflow-cpu
```

然后强制刷新浏览器页面。

### 11.3 端口冲突

如果 `http://127.0.0.1/` 打不开，或者 Docker 提示端口占用，优先改 `docker/.env`：

```dotenv
SVR_WEB_HTTP_PORT=8080
SVR_WEB_HTTPS_PORT=8443
SVR_HTTP_PORT=9380
ADMIN_SVR_HTTP_PORT=9381
```

改完后：

```powershell
docker compose -f docker-compose.yml --env-file .env up -d --force-recreate
```

### 11.4 Available models 和 Added models 为什么没了

这是当前本地源码的定制行为，不是 Docker 配置问题。

当前目标是：不让用户从页面右侧供应商列表手动添加模型，也不展示已添加模型列表，只让用户在 `Set default models` 中选择默认模型。

模型的新增和更新由后端根据 `.env` 中的 OpenAI-compatible 配置自动完成。

### 11.5 buildx 最后导入镜像时报 parent snapshot 不存在

如果构建日志已经到：

```text
exporting to image
naming to docker.io/library/ragflow:local-source done
failed to prepare extraction snapshot ... parent snapshot ... does not exist
```

这通常不是 Dockerfile 编译失败，而是 Docker Desktop 本地 image/snapshot 存储在 `--load` 导入镜像时出现了不一致。先只删除这次半加载的目标镜像，不要删除数据卷：

```powershell
docker image rm ragflow:local-source
docker system df
```

然后按本文档的构建命令重新 build，确认命令中带有：

```powershell
--provenance=false `
```

构建完成后验证镜像可运行：

```powershell
docker run --rm --entrypoint cat ragflow:local-source /ragflow/VERSION
```

如果 `docker system df` 本身仍然报 `snapshot ... does not exist`，先重启 Docker Desktop，再重复上面的删除目标镜像和重新构建步骤。不要使用 `docker compose down -v` 处理这个问题，`-v` 会删除 MySQL、Elasticsearch、MinIO 等数据卷。
