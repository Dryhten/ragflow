# 本地源码 Docker 构建与部署运行

这份文档用于从当前本地源码构建 RAGFlow Docker 镜像，并使用 `docker/docker-compose.yml` 在本机部署运行。适用于调试本地代码改动、验证 PR 分支、或重新构建一套干净的本地 Docker 环境。

## 前置条件

- Docker Desktop 或 Docker Engine 已启动。
- Docker Compose v2 可用。
- 当前目录位于项目根目录。
- 至少预留 50 GB 磁盘空间；首次构建会下载依赖并生成较大的镜像。

Windows PowerShell 下可先确认：

```powershell
docker --version
docker compose version
git status --short --branch
```

## 1. 构建本地源码镜像

在项目根目录执行：

```powershell
$env:DOCKER_BUILDKIT='1'
docker build --build-arg NEED_MIRROR=1 -t ragflow:local-source .
```

说明：

- `ragflow:local-source` 是本地镜像名，后续 `docker/.env` 的 `RAGFLOW_IMAGE` 需要指向它。
- `NEED_MIRROR=1` 会使用国内镜像源，网络环境稳定时也可以去掉该参数。
- 如果只改了 Python、前端、配置或文档，Docker 构建缓存通常会复用大部分层。

构建后检查镜像：

```powershell
docker images ragflow:local-source
docker run --rm --entrypoint cat ragflow:local-source /ragflow/VERSION
```

## 2. 配置 `docker/.env`

打开 `docker/.env`，至少确认以下配置。

### 2.1 使用本地源码镜像

```env
RAGFLOW_IMAGE=ragflow:local-source
```

如果这里仍是官方镜像，例如 `infiniflow/ragflow:v0.26.1`，`docker compose up` 会运行官方镜像，而不是刚构建的本地代码。

### 2.2 基础运行配置

```env
DOC_ENGINE=${DOC_ENGINE:-elasticsearch}
DEVICE=${DEVICE:-cpu}
COMPOSE_PROFILES=${DOC_ENGINE},${DEVICE}
```

常用取值：

- `DOC_ENGINE=elasticsearch`：本地默认推荐，依赖 `es01` 容器。
- `DEVICE=cpu`：启动 `ragflow-cpu` 服务。
- `DEVICE=gpu`：启动 `ragflow-gpu` 服务，需要主机 Docker GPU 环境可用。

### 2.3 端口配置

默认端口如下：

```env
SVR_WEB_HTTP_PORT=80
SVR_WEB_HTTPS_PORT=443
SVR_HTTP_PORT=9380
ADMIN_SVR_HTTP_PORT=9381
SVR_MCP_PORT=9382
GO_HTTP_PORT=9384
GO_ADMIN_PORT=9383
EXPOSE_MYSQL_PORT=3306
REDIS_PORT=6379
MINIO_PORT=9000
MINIO_CONSOLE_PORT=9001
ES_PORT=1200
```

如果这些端口已经被本机其他服务占用，先改成未占用端口再启动。

## 3. 配置默认模型导入

本项目支持通过 `docker/.env` 配置 OpenAI-compatible endpoint，RAGFlow 启动后会自动读取模型列表，并为租户导入 provider、instance 和模型记录。

在 `docker/.env` 中配置：

```env
USER_DEFAULT_LLM_API_KEY=your_api_key
USER_DEFAULT_LLM_BASE_URL=https://your-openai-compatible-endpoint/v1
```

说明：

- `USER_DEFAULT_LLM_BASE_URL` 必须是模型服务的 OpenAI-compatible base URL。
- 如果 URL 不包含 `/v1`，后端会请求 `<base_url>/v1/models`。
- `USER_DEFAULT_LLM_API_KEY` 会作为 Bearer token 请求模型列表。
- 不要在文档、日志或 PR 描述中暴露真实 API key。

这些变量会在容器启动时被写入 `/ragflow/conf/service_conf.yaml`：

```yaml
user_default_llm:
  name: 'Matrix'
  factory: 'OpenAI-API-Compatible'
  api_key: '${USER_DEFAULT_LLM_API_KEY:-}'
  base_url: '${USER_DEFAULT_LLM_BASE_URL:-}'
```

导入成功后，模型会出现在用户的模型配置页面中。用户仍需要在页面里选择实际的默认 chat、embedding、rerank、VLM、ASR、TTS 等模型。

### 配置优先级注意事项

不要在镜像或工作目录里保留带占位值的 `conf/local.service_conf.yaml`。

RAGFlow 会先读取 `conf/service_conf.yaml`，再用 `conf/local.service_conf.yaml` 覆盖同名配置。如果 `local.service_conf.yaml` 里写着占位值，例如：

```yaml
user_default_llm:
  api_key: '你的key'
  base_url: '你的模型地址'
```

那么即使 `docker/.env` 配置正确，后端实际读取到的仍会是占位值，最终导致新用户没有模型信息。

## 4. 启动本地 Docker 服务

进入 Docker 目录：

```powershell
cd docker
docker compose --env-file .env -f docker-compose.yml up -d
```

启动后查看状态：

```powershell
docker compose --env-file .env -f docker-compose.yml ps
```

期望至少看到：

- `docker-ragflow-cpu-1` 或 `docker-ragflow-gpu-1`
- `docker-mysql-1`
- `docker-redis-1`
- `docker-minio-1`
- `docker-es01-1`，当 `DOC_ENGINE=elasticsearch`

访问：

```text
http://localhost/
```

如果修改了 `SVR_WEB_HTTP_PORT`，使用对应端口访问。

## 5. 验证默认模型配置是否生效

确认容器实际使用的是本地镜像：

```powershell
docker inspect docker-ragflow-cpu-1 --format "ImageName={{.Config.Image}} ImageID={{.Image}}"
```

确认容器内配置：

```powershell
docker exec docker-ragflow-cpu-1 sh -lc "grep -n -A6 -B2 'user_default_llm' /ragflow/conf/service_conf.yaml"
```

确认 Python 配置读取结果：

```powershell
docker exec docker-ragflow-cpu-1 sh -lc "cd /ragflow && . .venv/bin/activate && python - <<'PY'
from common import config_utils
cfg = config_utils.get_base_config('user_default_llm', {}) or {}
print('name=', cfg.get('name'))
print('factory=', cfg.get('factory'))
print('api_key_set=', bool(cfg.get('api_key')))
print('base_url=', cfg.get('base_url'))
PY"
```

确认数据库里已有模型记录：

```powershell
docker exec docker-mysql-1 sh -lc 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -D rag_flow -e "SELECT provider_name, COUNT(1) AS providers FROM tenant_model_provider GROUP BY provider_name; SELECT COUNT(1) AS instances FROM tenant_model_instance; SELECT model_type, COUNT(1) AS models FROM tenant_model GROUP BY model_type;"'
```

页面可访问性检查：

```powershell
curl.exe -s -o NUL -w "HTTP %{http_code}`n" http://localhost/
```

## 6. 本地代码更新后的重建流程

在项目根目录重新构建镜像：

```powershell
$env:DOCKER_BUILDKIT='1'
docker build --build-arg NEED_MIRROR=1 -t ragflow:local-source .
```

只重建 RAGFlow 服务，不动 MySQL、Redis、MinIO、ES 等依赖容器：

```powershell
cd docker
docker compose --env-file .env -f docker-compose.yml up -d --no-deps --force-recreate ragflow-cpu
```

如果 `DEVICE=gpu`，把 `ragflow-cpu` 改为 `ragflow-gpu`。

## 7. 清理本地数据库并重新部署

下面命令会删除本地 Docker volumes，包括 MySQL、ES、MinIO、Redis 数据。只在确认可以丢弃本地数据时执行：

```powershell
cd docker
docker compose --env-file .env -f docker-compose.yml down -v --remove-orphans
docker compose --env-file .env -f docker-compose.yml up -d
```

如果只是重启服务，不要加 `-v`：

```powershell
docker compose --env-file .env -f docker-compose.yml down --remove-orphans
docker compose --env-file .env -f docker-compose.yml up -d
```

## 8. 常见问题

### 运行的不是本地代码

检查：

```powershell
docker compose --env-file .env -f docker-compose.yml ps
docker inspect docker-ragflow-cpu-1 --format "ImageName={{.Config.Image}}"
```

如果输出不是 `ragflow:local-source`，检查 `docker/.env` 的 `RAGFLOW_IMAGE`。

### 新注册用户没有模型信息

按顺序检查：

1. `docker/.env` 是否设置了 `USER_DEFAULT_LLM_API_KEY` 和 `USER_DEFAULT_LLM_BASE_URL`。
2. 容器内 `/ragflow/conf/service_conf.yaml` 是否包含正确的 `user_default_llm`。
3. 容器内是否存在 `/ragflow/conf/local.service_conf.yaml`，如果存在且写了占位值，会覆盖正确配置。
4. 模型服务的 `/v1/models` 是否可访问。
5. RAGFlow 日志里是否出现 `Failed to fetch configured model list`。

### 端口占用

修改 `docker/.env` 中的端口，例如：

```env
SVR_WEB_HTTP_PORT=8080
SVR_HTTP_PORT=19380
ADMIN_SVR_HTTP_PORT=19381
EXPOSE_MYSQL_PORT=13306
```

然后重新执行：

```powershell
docker compose --env-file .env -f docker-compose.yml up -d
```

